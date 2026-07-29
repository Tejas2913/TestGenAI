"""Assembles prompt payloads from versioned templates.

Templates are stored under app/prompts/<version>/ (e.g. prompts/v1/).
The active version is controlled by settings.PROMPT_VERSION.

V2 prompts must be added as prompts/v2/ — never overwrite prompts/v1/.
"""

from pathlib import Path

from app.core.config import settings
from app.domain.code_metadata import CodeMetadata
from app.domain.prompt_payload import PromptPayload

_PROMPTS_BASE_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptBuilder:
    """Loads versioned prompt templates from disk and injects runtime variables.

    Reads system.txt, developer.txt, and user.txt from the versioned
    prompts directory (e.g. prompts/v1/), fills in function metadata,
    and returns a fully assembled PromptPayload.

    Version is resolved via settings.PROMPT_VERSION at construction time,
    allowing per-request overrides to be injected via the constructor.
    """

    def __init__(
        self,
        prompt_version: str | None = None,
        prompts_base_dir: Path | None = None,
    ) -> None:
        self._version = prompt_version or settings.PROMPT_VERSION
        base = prompts_base_dir or _PROMPTS_BASE_DIR
        self._prompts_dir = base / self._version

        # Validate that the versioned directory exists at construction time
        # so errors surface early rather than at generation time.
        if not self._prompts_dir.is_dir():
            raise ValueError(
                f"Prompt directory not found: {self._prompts_dir}. "
                f"Expected layout: prompts/{self._version}/{{system,developer,user}}.txt"
            )

    def build(
        self,
        metadata: CodeMetadata,
        specification: str | None = None,
    ) -> PromptPayload:
        """Assemble system, developer, and user prompts from versioned templates."""
        system_prompt = self._load_template("system.txt")

        specification_section = ""
        if specification:
            specification_section = f"Specification:\n{specification}"

        developer_prompt = self._load_template("developer.txt").format(
            function_name=metadata.function_name,
            parameters=self._format_parameters(metadata),
            return_type=metadata.return_type or "Not specified",
            docstring=metadata.docstring or "Not provided",
            class_name=metadata.class_name or "None (standalone function)",
            decorators=", ".join(metadata.decorators) if metadata.decorators else "None",
            source_code=metadata.source_code,
            specification_section=specification_section,
        )

        # user.txt is kept as a no-op so the three-part PromptPayload
        # structure stays intact. All prompt content now lives in developer.txt.
        user_prompt = ""

        return PromptPayload(
            system_prompt=system_prompt,
            developer_prompt=developer_prompt,
            user_prompt=user_prompt,
        )

    def build_repair_prompt(
        self,
        source_code: str,
        generated_tests: str,
        traceback: str,
        failure_category: str,
        rule_id: str,
        failure_reason: str,
    ) -> PromptPayload:
        """Assemble surgical repair prompt payload from versioned repair.txt template."""
        template = self._load_template("repair.txt")
        developer_prompt = template.format(
            source_code=source_code,
            generated_tests=generated_tests,
            traceback=traceback,
            failure_category=failure_category,
            rule_id=rule_id,
            failure_reason=failure_reason,
        )
        return PromptPayload(
            system_prompt="You are an expert Python automated test repair engine.",
            developer_prompt=developer_prompt,
            user_prompt="",
        )

    def _load_template(self, filename: str) -> str:
        """Read a prompt template file from the versioned directory."""
        template_path = self._prompts_dir / filename
        return template_path.read_text(encoding="utf-8")

    def _format_parameters(self, metadata: CodeMetadata) -> str:
        """Format parameter list as a human-readable string."""
        if not metadata.parameters:
            return "None"

        parts = []
        for param in metadata.parameters:
            entry = param.name
            if param.type_hint:
                entry += f": {param.type_hint}"
            if param.default_value:
                entry += f" = {param.default_value}"
            parts.append(entry)

        return ", ".join(parts)
