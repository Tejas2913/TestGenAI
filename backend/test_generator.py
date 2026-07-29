import json
import sys
sys.path.insert(0, ".")

from app.domain.test_case import TestCase
from app.domain.test_suite import TestSuite
from app.ai.code_generator import CodeGenerator

tc1 = TestCase(
    name="test_happy",
    description="Test happy",
    category="happy_path",
    inputs={"a": 1, "b": 2},
    expected_output=[1, 2, 3],
    assertions=["assert anything"]
)

tc2 = TestCase(
    name="test_exception",
    description="Test exception",
    category="error_handling",
    inputs={"arr": None},
    expected_output="raises TypeError",
    assertions=["with pytest.raises(TypeError): quicksort(None)"]
)

ts = TestSuite(
    function_name="quicksort_readable",
    test_cases=[tc1, tc2],
    imports=["import pytest", "from typing import Any", "import pytest"],
    setup_code="def setup(): pass"
)

cg = CodeGenerator()
# Simulating the modified logic:
clean_imports = set()
for imp in ts.imports:
    imp = imp.strip()
    if imp and imp != "import pytest":
        clean_imports.add(imp)

clean_imports.add(f"from main import {ts.function_name}")
final_imports = sorted(list(clean_imports))

for tc in ts.test_cases:
    args_str = ", ".join(repr(v) for v in tc.inputs.values())
    call_str = f"{ts.function_name}({args_str})"
    
    if isinstance(tc.expected_output, str) and tc.expected_output.startswith("raises "):
        exc_type = tc.expected_output[7:].strip()
        tc.assertions = [f"with pytest.raises({exc_type}):\n        {call_str}"]
    else:
        tc.assertions = [f"assert {call_str} == {repr(tc.expected_output)}"]

out = cg.generate(ts) # Note: we mutated ts in place, so the original generate is fine except for imports.
# Wait, we need to apply it in code_generator and then run it. Let's print out what it would be.

print("--- REGENERATED ASSERTIONS ---")
for tc in ts.test_cases:
    print(tc.name, tc.assertions)
    
print("--- FINAL IMPORTS ---")
print(final_imports)
