import modules.prompt_v2 as prompt_v2


def test_repeated_choice_formula_evaluates_each_occurrence(monkeypatch):
    choices = iter(
        [
            (["first"], None),
            (["second"], None),
        ]
    )

    def fake_choice_v2(_array, choice=None):
        return next(choices)

    monkeypatch.setattr(prompt_v2, "choice_v2", fake_choice_v2)

    result = prompt_v2.text_formula_v2(
        '${=choice("x")}|${=choice("x")}',
        {
            "variables": {},
            "attributes": {},
            "chained_var": {
                "x": [{"choice_start": 0.0, "choice_end": 1.0, "variables": ["unused"]}]
            },
            "chained_attr": {},
        },
    )

    assert result == "first|second"
