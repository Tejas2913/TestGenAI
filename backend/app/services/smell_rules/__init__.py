"""Test Smell Rules Package for TestGen AI v2.2."""

from app.services.smell_rules.assertion_roulette import AssertionRouletteRule
from app.services.smell_rules.base_rule import TestSmellRule
from app.services.smell_rules.conditional_logic import ConditionalLogicRule
from app.services.smell_rules.duplicate_assertion import DuplicateAssertionRule
from app.services.smell_rules.empty_test import EmptyTestRule
from app.services.smell_rules.magic_numbers import MagicNumbersRule
from app.services.smell_rules.verbose_test import VerboseTestRule

DEFAULT_SMELL_RULES: list[TestSmellRule] = [
    EmptyTestRule(),
    AssertionRouletteRule(),
    DuplicateAssertionRule(),
    MagicNumbersRule(),
    VerboseTestRule(),
    ConditionalLogicRule(),
]

__all__ = [
    "TestSmellRule",
    "AssertionRouletteRule",
    "DuplicateAssertionRule",
    "EmptyTestRule",
    "MagicNumbersRule",
    "VerboseTestRule",
    "ConditionalLogicRule",
    "DEFAULT_SMELL_RULES",
]
