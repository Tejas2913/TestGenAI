"""Extracts and converts raw LLM output into strongly typed domain models."""

import json
import re

import structlog  # pyrefly: ignore [missing-import]

from app.domain.test_case import TestCase
from app.domain.test_suite import TestSuite
from app.exceptions import ValidationException

logger = structlog.get_logger()

# Matches a stray `]` or `],` that sits ALONE on its own line
# (nothing before it except whitespace, nothing after except optional `,`
# and whitespace), followed on the next line by `"test_cases"` or
# `"setup_code"` as a top-level key.
#
# This is intentionally narrow — it only fires on the exact hallucination
# pattern where the model emits an extraneous closing bracket on its own
# line between two top-level scalar properties. It will NOT match `]`
# that appears at the end of a normal array line like `["import pytest"],`.
_STRAY_BRACKET_BEFORE_KEY = re.compile(
    r"(?m)^[ \t]*\][ \t]*,?[ \t]*\n([ \t]*)(?=\"(?:test_cases|setup_code)\")"
)


class ResponseParser:
    """Parses raw LLM response text into a validated TestSuite.

    Handles markdown code fences, surrounding explanations,
    and whitespace normalization before JSON extraction.
    """

    def parse(self, raw_response: str) -> TestSuite:
        """Extract JSON from the LLM response and convert to a TestSuite."""
        json_string = self._extract_json_string(raw_response)
        data = self._parse_json(json_string)
        return self._convert_to_test_suite(data)

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def _extract_json_string(self, raw: str) -> str:
        """Strip markdown fences and surrounding text to isolate JSON."""
        fenced = re.search(
            r"```(?:json)?\s*\n?(.*?)\n?\s*```",
            raw,
            re.DOTALL,
        )
        if fenced:
            return fenced.group(1).strip()

        brace_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if brace_match:
            return brace_match.group(0).strip()

        return raw.strip()

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_json(self, json_string: str) -> dict:
        """Parse the extracted JSON string into a dictionary.

        Attempt 1: direct json.loads().
        Attempt 2 (only on failure): remove ONE stray closing bracket
            immediately before ,\"test_cases\" or ,\"setup_code\".
        Falls back to ValidationException if both attempts fail.
        """
        # --- Attempt 1: parse as-is ---
        try:
            data = json.loads(json_string)
            if not isinstance(data, dict):
                raise ValidationException(
                    detail="LLM response JSON must be an object, not an array or primitive"
                )
            return data
        except json.JSONDecodeError:
            pass

        # --- Attempt 2: minimal targeted repair ---
        repaired, repaired_desc = self._repair_stray_bracket(json_string)

        if repaired_desc:
            logger.warning(
                "response_parser_json_repaired",
                repair=repaired_desc,
            )

        try:
            data = json.loads(repaired)
        except json.JSONDecodeError as exc:
            raise ValidationException(
                detail=(
                    f"Failed to parse JSON at line {exc.lineno}, "
                    f"column {exc.colno}: {exc.msg}"
                )
            ) from exc

        if not isinstance(data, dict):
            raise ValidationException(
                detail="LLM response JSON must be an object, not an array or primitive"
            )

        return data

    # ------------------------------------------------------------------
    # Minimal repair
    # ------------------------------------------------------------------

    @staticmethod
    def _repair_stray_bracket(json_string: str) -> tuple[str, str]:
        """Remove at most ONE stray `]` immediately before `,"test_cases"`
        or `,"setup_code"`.

        Returns (repaired_string, description_of_repair).
        If no stray bracket is found the original string is returned unchanged
        and description is an empty string.
        """
        match = _STRAY_BRACKET_BEFORE_KEY.search(json_string)
        if match is None:
            return json_string, ""

        # The matched text is the stray `],` line plus the newline.
        # group(1) captures the indentation on the following key line.
        # We replace the entire match with just `,\n<indent>` so the
        # preceding property gets its comma and the next key stays indented.
        indent = match.group(1)
        repaired = json_string[: match.start()] + ",\n" + indent + json_string[match.end() :]
        desc = (
            f"removed stray bracket at position {match.start()}: "
            f"{match.group()!r}"
        )
        return repaired, desc

    # ------------------------------------------------------------------
    # Conversion
    # ------------------------------------------------------------------

    def _convert_to_test_suite(self, data: dict) -> TestSuite:
        """Convert a parsed dictionary into a strongly typed TestSuite."""
        try:
            test_cases = [
                TestCase(**tc) for tc in data.get("test_cases", [])
            ]
            return TestSuite(
                function_name=data.get("function_name", "unknown"),
                test_cases=test_cases,
                imports=data.get("imports", []),
                setup_code=data.get("setup_code"),
            )
        except Exception as exc:
            raise ValidationException(
                detail=f"Failed to convert JSON to TestSuite: {exc}"
            ) from exc
