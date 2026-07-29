"""Comprehensive unit tests for AST-based TestSmellDetector service (Phase 2).

Verifies:
  - Clean test suites return 0 smells.
  - Assertion Roulette detection for unlabeled multiple assertions.
  - Duplicate assertion detection for identical assert expressions.
  - Empty test detection for pass / docstring-only functions.
  - Magic number detection in assertions (ignoring 0, 1, -1).
  - Verbose test detection for functions exceeding configurable line thresholds.
  - Conditional logic detection (If, For, While, Match).
  - Resilience against malformed Python syntax (returns empty report without crashing).
  - Pytest fixtures, pytest.raises, and parametrized test support.
"""

import pytest
from app.domain.test_smell import TestSmellCategory
from app.services.test_smell_detector import TestSmellDetector


class TestSmellDetectorSuite:
    """Test suite for TestSmellDetector static AST analysis service."""

    @pytest.fixture
    def detector(self) -> TestSmellDetector:
        """Provide a default TestSmellDetector instance."""
        return TestSmellDetector(max_lines=10)

    def test_clean_test_suite_has_zero_smells(self, detector: TestSmellDetector) -> None:
        """Verify clean test functions return zero smells."""
        code = """
def test_add():
    a = 2
    b = 3
    result = add(a, b)
    assert result == a + b, "Expected sum to equal a + b"
"""
        summary = detector.detect(code)
        assert summary.total_smells == 0
        assert summary.high_severity_count == 0
        assert summary.medium_severity_count == 0
        assert summary.low_severity_count == 0
        assert len(summary.diagnostics) == 0

    def test_empty_string_returns_zero_smells(self, detector: TestSmellDetector) -> None:
        """Verify empty input returns zero smells."""
        summary = detector.detect("")
        assert summary.total_smells == 0

        summary_whitespace = detector.detect("   \n\t  ")
        assert summary_whitespace.total_smells == 0

    def test_malformed_syntax_does_not_crash(self, detector: TestSmellDetector) -> None:
        """Verify syntax errors log warning and return zero smells gracefully."""
        bad_code = "def test_broken(: assert 1 =="
        summary = detector.detect(bad_code)
        assert summary.total_smells == 0
        assert summary.diagnostics == []

    def test_empty_test_detection(self, detector: TestSmellDetector) -> None:
        """Verify empty test functions with pass or docstrings are detected."""
        code = """
def test_empty_pass():
    pass

def test_empty_docstring():
    \"\"\"This is a test docstring.\"\"\"
    pass
"""
        summary = detector.detect(code)
        assert summary.total_smells == 2
        assert summary.high_severity_count == 2
        types = [d.smell_type for d in summary.diagnostics]
        assert types == [TestSmellCategory.EMPTY_TEST, TestSmellCategory.EMPTY_TEST]

    def test_assertion_roulette_detection(self, detector: TestSmellDetector) -> None:
        """Verify multiple assertions without custom messages trigger Assertion Roulette."""
        code = """
def test_multiple_asserts():
    x = 0
    y = 1
    assert x == 0
    assert y == 1
"""
        summary = detector.detect(code)
        assert summary.total_smells == 1
        assert summary.low_severity_count == 1
        diag = summary.diagnostics[0]
        assert diag.smell_type == TestSmellCategory.ASSERTION_ROULETTE
        assert "without custom messages" in diag.message

    def test_assertion_roulette_ignored_when_messages_provided(
        self, detector: TestSmellDetector
    ) -> None:
        """Verify assertions with custom messages do not trigger Assertion Roulette."""
        code = """
def test_multiple_asserts_with_messages():
    x = 0
    y = 1
    assert x == 0, "x should be 0"
    assert y == 1, "y should be 1"
"""
        summary = detector.detect(code)
        assert summary.total_smells == 0

    def test_duplicate_assertion_detection(self, detector: TestSmellDetector) -> None:
        """Verify duplicate assertion expressions trigger Duplicate Assertions smell."""
        code = """
def test_duplicate():
    res = calc()
    assert res == 0, "First check"
    assert res == 0, "Second check"
"""
        summary = detector.detect(code)
        assert summary.total_smells == 1
        assert summary.medium_severity_count == 1
        diag = summary.diagnostics[0]
        assert diag.smell_type == TestSmellCategory.DUPLICATE_ASSERTION

    def test_magic_number_detection(self, detector: TestSmellDetector) -> None:
        """Verify unnamed numeric literals in assertions trigger Magic Number smell."""
        code = """
def test_magic():
    val = get_val()
    assert val == 999, "Magic check"
"""
        summary = detector.detect(code)
        assert summary.total_smells == 1
        assert summary.low_severity_count == 1
        diag = summary.diagnostics[0]
        assert diag.smell_type == TestSmellCategory.MAGIC_NUMBER
        assert "999" in diag.message

    def test_allowed_numeric_constants_ignored(self, detector: TestSmellDetector) -> None:
        """Verify 0, 1, -1, True, False, None in assertions do not trigger Magic Number smell."""
        code = """
def test_allowed_constants():
    assert is_active() is True, "Active check"
    assert count() == 0, "Zero check"
    assert delta() == 1, "One check"
    assert offset() == -1, "Minus one check"
"""
        summary = detector.detect(code)
        assert summary.total_smells == 0

    def test_verbose_test_detection(self) -> None:
        """Verify test functions exceeding max_lines threshold trigger Verbose Test smell."""
        detector = TestSmellDetector(max_lines=5)
        code = """
def test_very_long_function():
    a = 0
    b = 0
    c = 0
    d = 0
    e = 0
    f = 0
    assert a == 0, "Check verbose"
"""
        summary = detector.detect(code)
        assert summary.total_smells == 1
        assert summary.medium_severity_count == 1
        diag = summary.diagnostics[0]
        assert diag.smell_type == TestSmellCategory.VERBOSE_TEST

    def test_conditional_logic_detection(self, detector: TestSmellDetector) -> None:
        """Verify control flow statements inside test functions trigger Conditional Logic smell."""
        code = """
def test_conditional():
    items = [1, 2, 3]
    for item in items:
        if item > 1:
            assert item > 0
"""
        summary = detector.detect(code)
        assert summary.total_smells == 2
        assert summary.medium_severity_count == 2
        types = [d.smell_type for d in summary.diagnostics]
        assert types == [
            TestSmellCategory.CONDITIONAL_LOGIC,
            TestSmellCategory.CONDITIONAL_LOGIC,
        ]

    def test_pytest_raises_and_fixtures_support(
        self, detector: TestSmellDetector
    ) -> None:
        """Verify pytest.raises context manager and fixtures analyze properly."""
        code = """
import pytest

@pytest.fixture
def sample_data():
    return {"key": "value"}

def test_divide_by_zero(sample_data):
    assert sample_data["key"] == "value", "Fixture check"
    with pytest.raises(ZeroDivisionError):
        1 / 0
"""
        summary = detector.detect(code)
        assert summary.total_smells == 0

    def test_multiple_smells_combined(self) -> None:
        """Verify multiple different smells are detected across test suite."""
        detector = TestSmellDetector(max_lines=5)
        code = """
def test_multi_smells():
    pass

def test_bad_test():
    x = 1000
    if x > 100:
        assert x == 1000
        assert x == 1000
        y = 1
        z = 2
        w = 3
"""
        summary = detector.detect(code)
        assert summary.total_smells > 0
        assert summary.high_severity_count >= 1
        assert summary.medium_severity_count >= 1

    def test_analyze_test_smells_alias(self, detector: TestSmellDetector) -> None:
        """Verify analyze_test_smells alias functions identically to detect."""
        code = "def test_empty(): pass"
        summary1 = detector.detect(code)
        summary2 = detector.analyze_test_smells(code)
        assert summary1.total_smells == summary2.total_smells
        assert summary1.high_severity_count == summary2.high_severity_count

    @pytest.mark.parametrize(
        "code_snippet,expected_smell",
        [
            ("def test_e(): pass", TestSmellCategory.EMPTY_TEST),
            ("def test_a():\n  assert 1 == 1\n  assert 2 == 2", TestSmellCategory.ASSERTION_ROULETTE),
            ("def test_m():\n  assert get_code() == 404", TestSmellCategory.MAGIC_NUMBER),
            ("def test_c():\n  while True:\n    break", TestSmellCategory.CONDITIONAL_LOGIC),
        ],
    )
    def test_parametrized_smell_categories(
        self, detector: TestSmellDetector, code_snippet: str, expected_smell: TestSmellCategory
    ) -> None:
        """Parametrized test checking individual smell category triggers."""
        summary = detector.detect(code_snippet)
        assert summary.total_smells >= 1
        detected_types = {d.smell_type for d in summary.diagnostics}
        assert expected_smell in detected_types
