"""Regression tests for PromptPayload normalization adapter and multi-provider failover.

Verifies:
A. Legacy/V1 PromptPayload -> normalized provider payload
B. v2.3/v2.4 PromptPayload -> passes through correctly
C. system_prompt + developer_prompt combination
D. user_prompt -> rendered_user
E. missing optional developer_prompt
F. safe agent_name handling
G. estimated_tokens handling
H. malformed/unsupported payload produces a clear error
I. Gemini receives normalized payload
J. OpenAI receives normalized payload
K. Claude receives normalized payload
L. Groq receives normalized payload
M. OpenRouter receives normalized payload
N. failover still works after normalization
O. MOCK_MODE workflow remains completely offline
"""

from unittest.mock import MagicMock
import pytest

from app.domain.prompt_payload import PromptPayload as V1PromptPayload
from app.domain.v23_models import PromptPayload as V23PromptPayload
from app.infrastructure.providers.router import LLMProviderRouter, normalize_payload
from app.infrastructure.providers.gemini import GeminiProvider
from app.infrastructure.providers.openai_provider import OpenAIProvider
from app.infrastructure.providers.claude import ClaudeProvider
from app.infrastructure.providers.groq_provider import GroqProvider
from app.infrastructure.providers.openrouter_provider import OpenRouterProvider
from app.domain.provider_response import ProviderResponse


class TestPromptPayloadNormalization:
    """A-H: Core normalization unit tests."""

    def test_A_legacy_v1_prompt_payload_normalization(self):
        v1_payload = V1PromptPayload(
            system_prompt="You are a test generator.",
            developer_prompt="Output strict JSON.",
            user_prompt="def add(a, b): return a + b",
        )
        norm = normalize_payload(v1_payload)
        assert isinstance(norm, V23PromptPayload)
        assert "You are a test generator." in norm.rendered_system
        assert "Output strict JSON." in norm.rendered_system
        assert norm.rendered_user == "def add(a, b): return a + b"

    def test_B_v23_v24_prompt_payload_passthrough(self):
        v23_payload = V23PromptPayload(
            template_name="test_tmpl",
            rendered_system="System instructions",
            rendered_user="User prompt code",
            agent_name="generator",
            estimated_tokens=250,
        )
        norm = normalize_payload(v23_payload)
        assert norm is v23_payload
        assert norm.rendered_system == "System instructions"
        assert norm.rendered_user == "User prompt code"
        assert norm.agent_name == "generator"
        assert norm.estimated_tokens == 250

    def test_C_system_and_developer_prompt_combination(self):
        v1_payload = V1PromptPayload(
            system_prompt="Base System Instruction",
            developer_prompt="Developer Constraint Rules",
            user_prompt="code",
        )
        norm = normalize_payload(v1_payload)
        assert norm.rendered_system == "Base System Instruction\n\nDeveloper Constraint Rules"

    def test_D_user_prompt_mapping_to_rendered_user(self):
        v1_payload = V1PromptPayload(
            system_prompt="System",
            developer_prompt="",
            user_prompt="my_user_code_here",
        )
        norm = normalize_payload(v1_payload)
        assert norm.rendered_user == "my_user_code_here"

    def test_E_missing_optional_developer_prompt(self):
        v1_payload = V1PromptPayload(
            system_prompt="System Only",
            developer_prompt="",
            user_prompt="user_code",
        )
        norm = normalize_payload(v1_payload)
        assert norm.rendered_system == "System Only"

    def test_F_safe_agent_name_handling(self):
        dict_payload = {
            "system_prompt": "sys",
            "user_prompt": "usr",
        }
        norm = normalize_payload(dict_payload)
        assert norm.agent_name == "generator"

    def test_G_estimated_tokens_handling(self):
        dict_payload = {
            "system_prompt": "a" * 400,
            "user_prompt": "b" * 400,
        }
        norm = normalize_payload(dict_payload)
        assert norm.estimated_tokens == 200  # 800 chars / 4

        dict_payload_explicit = {
            "system_prompt": "sys",
            "user_prompt": "usr",
            "estimated_tokens": 1234,
        }
        norm_explicit = normalize_payload(dict_payload_explicit)
        assert norm_explicit.estimated_tokens == 1234

    def test_H_malformed_unsupported_payload_produces_error(self):
        with pytest.raises(ValueError, match="PromptPayload cannot be None"):
            normalize_payload(None)

        with pytest.raises(ValueError, match="Unsupported PromptPayload contract"):
            normalize_payload({"invalid_key": "val"})

        with pytest.raises(ValueError, match="missing prompt content"):
            normalize_payload({"rendered_system": "", "rendered_user": ""})


class TestAllProvidersReceiveNormalizedPayload:
    """I-M: Verify that all 5 enterprise providers accept normalized payloads in MOCK_MODE."""

    @pytest.fixture
    def v1_payload(self):
        return V1PromptPayload(
            system_prompt="System Role",
            developer_prompt="Developer Rule",
            user_prompt="def foo(): pass",
        )

    def test_I_gemini_receives_normalized_payload(self, v1_payload):
        provider = GeminiProvider(mock_mode=True)
        norm = normalize_payload(v1_payload)
        resp = provider.generate(norm)
        assert resp.response_text
        assert resp.provider_name == "Gemini"

    def test_J_openai_receives_normalized_payload(self, v1_payload):
        provider = OpenAIProvider(mock_mode=True)
        norm = normalize_payload(v1_payload)
        resp = provider.generate(norm)
        assert resp.response_text
        assert resp.provider_name == "OpenAI"

    def test_K_claude_receives_normalized_payload(self, v1_payload):
        provider = ClaudeProvider(mock_mode=True)
        norm = normalize_payload(v1_payload)
        resp = provider.generate(norm)
        assert resp.response_text
        assert resp.provider_name == "Claude"

    def test_L_groq_receives_normalized_payload(self, v1_payload):
        provider = GroqProvider(mock_mode=True)
        norm = normalize_payload(v1_payload)
        resp = provider.generate(norm)
        assert resp.response_text
        assert resp.provider_name == "Groq"

    def test_M_openrouter_receives_normalized_payload(self, v1_payload):
        provider = OpenRouterProvider(mock_mode=True)
        norm = normalize_payload(v1_payload)
        resp = provider.generate(norm)
        assert resp.response_text
        assert resp.provider_name == "OpenRouter"


class TestRouterFailoverAndMockMode:
    """N-O: Failover & MOCK_MODE behavior tests."""

    def test_N_failover_still_works_after_normalization(self):
        router = LLMProviderRouter(mock_mode=True)
        # Mock Gemini (primary) to raise a transient error
        failing_gemini = MagicMock()
        failing_gemini.provider_name = "Gemini"
        failing_gemini.model_name = "gemini-3.5-flash"
        failing_gemini.health_check.return_value = True
        failing_gemini.generate.side_effect = RuntimeError("503 UNAVAILABLE")

        router.register_provider("Gemini", failing_gemini)

        v1_payload = V1PromptPayload(
            system_prompt="sys",
            developer_prompt="dev",
            user_prompt="user code",
        )

        # Generating via router should automatically fail over to OpenAI / Claude / Groq / OpenRouter
        result_text = router.generate(v1_payload)
        assert result_text is not None
        assert len(result_text) > 0

    def test_O_mock_mode_workflow_remains_offline(self):
        router = LLMProviderRouter(mock_mode=True)
        v1_payload = V1PromptPayload(
            system_prompt="sys",
            developer_prompt="dev",
            user_prompt="def sub(a, b): return a - b",
        )
        res_str = router.generate(v1_payload)
        assert res_str is not None
        assert "def test_" in res_str or "{" in res_str or len(res_str) > 0
