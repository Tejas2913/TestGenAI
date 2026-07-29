"""Demonstrates the full AI pipeline using a mock LLM response."""

import json

from app.ai.input_analyser import InputAnalyser
from app.ai.prompt_builder import PromptBuilder
from app.ai.response_parser import ResponseParser
from app.ai.validators import (
    BusinessRuleValidator,
    JSONSchemaValidator,
    SemanticValidator,
)
from app.ai.code_generator import CodeGenerator


SAMPLE_SOURCE = '''
def calculate_discount(price: float, discount_percent: float = 0.0) -> float:
    """Apply a percentage discount to a price.

    Args:
        price: The original price.
        discount_percent: Discount percentage (0-100).

    Returns:
        The discounted price.

    Raises:
        ValueError: If price is negative or discount is out of range.
    """
    if price < 0:
        raise ValueError("Price cannot be negative")
    if not 0 <= discount_percent <= 100:
        raise ValueError("Discount must be between 0 and 100")
    return price * (1 - discount_percent / 100)
'''

MOCK_LLM_RESPONSE = '''```json
{
  "function_name": "calculate_discount",
  "test_cases": [
    {
      "name": "test_calculate_discount_basic",
      "description": "Apply a 10% discount to a price of 100",
      "category": "happy_path",
      "inputs": {"price": 100.0, "discount_percent": 10.0},
      "expected_output": 90.0,
      "assertions": ["assert calculate_discount(100.0, 10.0) == 90.0"]
    },
    {
      "name": "test_calculate_discount_no_discount",
      "description": "Apply zero discount returns original price",
      "category": "happy_path",
      "inputs": {"price": 50.0, "discount_percent": 0.0},
      "expected_output": 50.0,
      "assertions": ["assert calculate_discount(50.0, 0.0) == 50.0"]
    },
    {
      "name": "test_calculate_discount_full_discount",
      "description": "Apply 100% discount returns zero",
      "category": "boundary",
      "inputs": {"price": 200.0, "discount_percent": 100.0},
      "expected_output": 0.0,
      "assertions": ["assert calculate_discount(200.0, 100.0) == 0.0"]
    },
    {
      "name": "test_calculate_discount_zero_price",
      "description": "Zero price with any discount returns zero",
      "category": "edge_case",
      "inputs": {"price": 0.0, "discount_percent": 50.0},
      "expected_output": 0.0,
      "assertions": ["assert calculate_discount(0.0, 50.0) == 0.0"]
    },
    {
      "name": "test_calculate_discount_negative_price",
      "description": "Negative price raises ValueError",
      "category": "error_handling",
      "inputs": {"price": -10.0, "discount_percent": 10.0},
      "expected_output": "raises ValueError",
      "assertions": [
        "import pytest",
        "with pytest.raises(ValueError, match='Price cannot be negative'):",
        "    calculate_discount(-10.0, 10.0)"
      ]
    },
    {
      "name": "test_calculate_discount_over_100_percent",
      "description": "Discount over 100% raises ValueError",
      "category": "error_handling",
      "inputs": {"price": 100.0, "discount_percent": 150.0},
      "expected_output": "raises ValueError",
      "assertions": [
        "import pytest",
        "with pytest.raises(ValueError, match='Discount must be between 0 and 100'):",
        "    calculate_discount(100.0, 150.0)"
      ]
    }
  ],
  "imports": ["from mymodule import calculate_discount"],
  "setup_code": null
}
```'''


def main():
    print("=" * 70)
    print("TestGen AI -- Full Pipeline Demo (Mock LLM)")
    print("=" * 70)

    # Step 1: InputAnalyser
    print("\n[1] InputAnalyser -- CodeMetadata")
    print("-" * 40)
    analyser = InputAnalyser()
    metadata = analyser.analyse(SAMPLE_SOURCE)
    print(metadata.model_dump_json(indent=2))

    # Step 2: PromptBuilder
    print("\n[2] PromptBuilder -- PromptPayload")
    print("-" * 40)
    builder = PromptBuilder()
    payload = builder.build(metadata, specification="Should reject negative prices")
    print(f"System prompt:    {len(payload.system_prompt)} chars")
    print(f"Developer prompt: {len(payload.developer_prompt)} chars")
    print(f"User prompt:      {len(payload.user_prompt)} chars")
    print(f"User prompt preview:\n{payload.user_prompt[:200]}...")

    # Step 3: Mock LLM Response (skip actual LLM call)
    print("\n[3] Mock LLM Response")
    print("-" * 40)
    print(f"Raw response: {len(MOCK_LLM_RESPONSE)} chars (fenced JSON)")

    # Step 4: ResponseParser
    print("\n[4] ResponseParser -- TestSuite")
    print("-" * 40)
    parser = ResponseParser()
    test_suite = parser.parse(MOCK_LLM_RESPONSE)
    print(f"Function: {test_suite.function_name}")
    print(f"Test cases: {len(test_suite.test_cases)}")
    for tc in test_suite.test_cases:
        print(f"  - {tc.name} [{tc.category}]")

    # Step 5: Validators
    print("\n[5] Validators")
    print("-" * 40)
    all_warnings = []
    for name, validator_cls in [
        ("JSONSchema", JSONSchemaValidator),
        ("Semantic", SemanticValidator),
        ("BusinessRule", BusinessRuleValidator),
    ]:
        warnings = validator_cls().validate(test_suite)
        print(f"  {name}: {len(warnings)} warnings")
        all_warnings.extend(warnings)

    if all_warnings:
        for w in all_warnings:
            print(f"    [!] {w}")
    else:
        print("  All validations passed!")

    # Step 6: CodeGenerator
    print("\n[6] CodeGenerator -- pytest source")
    print("-" * 40)
    generator = CodeGenerator()
    code = generator.generate(test_suite)
    print(code)

    print("=" * 70)
    print("Pipeline complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
