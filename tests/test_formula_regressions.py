from unittest.mock import patch

import pytest

from modules.formula import FormulaCompute
from modules.prompt_v2 import text_formula_v2


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("formula, expected", [
    ("10 - 2 * 3 - 1", 3),
    ("24 / 2 / 3", 4),
    ("20 - 2 * 3 - 4 * 2", 6),
    ("10 - pow(2, 2) * 2 - 1", 1),
    ("(10 - 2) * (3 - 1)", 16),
    ("2 >= 1", 1), ("2 >= 2", 1), ("1 >= 2", 0),
    ("2 <= 3", 1), ("2 <= 2", 1), ("3 <= 2", 0),
    ('if(2 >= 1 && 2 <= 3, "yes", "no")', "yes"),
    ("max(-1, -2)", -1), ("min(-1, -2)", -2),
    ("pow(2, -2)", 0.25), ("max(-1, +2)", 2),
    ("max(-1, min(-2, -3))", -1),
    ('"a" * 3', "aaa"), ('"a" * 0', ""),
    ('"a" * 2 + "b"', "aab"), ('len("a" * 3)', 3),
    ('split("a,b", ",")', ["a", "b"]),
    ('split("a,,b", ",")', ["a", "", "b"]),
    ('len(split("a,b", ","))', 2),
])
def test_expression_regressions(version, formula, expected):
    compute = FormulaCompute(formula, version=version)
    assert compute.compute(), compute.getError()
    assert compute.result == expected


@pytest.mark.parametrize("formula, expected", [
    ("x - 2", 3), ("2 - x", -3), ("x * 2 + 3", 13),
    ("10 - x * 2 - 1", -1), ("max(x, y) - x", 3),
    ("x[2] - x", 2), ("x[y - 6] * 2 - x", 9),
    ('x["size"] - x', 7),
    ('label + "!"', "hello!"),
    ("max(x, min(y, 6))", 6),
])
def test_variable_operands_and_indexing(formula, expected):
    compute = FormulaCompute(formula, {"x": [5, 7], "y": 8, "label": "hello"},
                             attributes={"x": {"size": 12}}, version=2)
    assert compute.compute(), compute.getError()
    assert compute.result == expected


@pytest.mark.parametrize("helper", ["calculate", "calculate_debug"])
@pytest.mark.parametrize("version", [1, 2])
def test_static_helpers_evaluate_random_once(helper, version):
    with patch("modules.formula.function.random.randint", side_effect=[111, 222]) as draw:
        result = getattr(FormulaCompute, helper)("random_int()", version=version)
    assert result == ((111, None) if helper == "calculate_debug" else 111)
    draw.assert_called_once()


def test_debug_helper_preserves_attributes():
    assert FormulaCompute.calculate_debug('x["size"]', {"x": [5]},
                                          {"x": {"size": 12}}, version=2) == (12, None)


@pytest.mark.parametrize("helper", ["calculate", "calculate_debug"])
def test_static_helpers_report_failure(helper):
    result = getattr(FormulaCompute, helper)("1 / 0", version=2)
    if helper == "calculate_debug":
        assert result[0] is None
        assert "division by zero" in str(result[1])
    else:
        assert result is None


def test_prompt_expansion_regressions():
    result = text_formula_v2(
        '${=10 - 2 * 3 - 1}|${=x - 2}|${=max(-1,-2)}|'
        '${=2 >= 1}|${=2 <= 3}|${="a" * 3}|${=split("a,b", ",")}',
        {"variables": {"x": [5]}, "attributes": {}},
    )
    assert result == "3|3|-1|1|1|aaa|['a', 'b']"
