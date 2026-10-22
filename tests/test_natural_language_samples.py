"""Validate complete English output from the randomized phrase examples."""

import random
from pathlib import Path

import pytest
import yaml

from modules.prompt_v2 import create_text_v2

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
CASES = [
    ("natural-language-maid", None),
    ("natural-language-maid", "red_dress"),
    ("natural-language-maid", "alternate_action"),
    ("natural-language-spatial", None),
    ("natural-language-spatial", "abc_left_to_right"),
]


@pytest.fixture(autouse=True)
def preserve_random_state():
    state = random.getstate()
    yield
    random.setstate(state)


@pytest.mark.parametrize("name", ["natural-language-maid", "natural-language-spatial"])
def test_every_variable_has_distinct_choices_without_column_delimiters(name):
    document = yaml.safe_load((EXAMPLES / f"{name}.yaml").read_text(encoding="utf-8"))
    collections = [document["variables"]]
    collections.extend(profile["variables"] for profile in document["profiles"].values())
    for variables in collections:
        for key, candidates in variables.items():
            assert len(candidates) >= 2, key
            assert len(set(candidates)) == len(candidates), key
            # Raw semicolons silently start another column in the prompt reader.
            assert all(";" not in candidate for candidate in candidates), key


@pytest.mark.parametrize("name,profile", CASES)
@pytest.mark.parametrize("seed", [0, 1, 7, 31])
def test_randomized_sentences_remain_complete(name, profile, seed):
    random.seed(seed)
    options = {"input": str(EXAMPLES / f"{name}.yaml"), "json": True, "max_number": -1}
    if profile:
        options["profile"] = profile
    text = create_text_v2(options)["output_text"][0]["prompt"]
    assert "${" not in text
    assert len(text.split()) > 300
    assert all(paragraph.rstrip().endswith(".") for paragraph in text.split("\n\n"))
    if name.endswith("spatial"):
        # A name is selected once, including every repeated ownership reference.
        for first, second in [("Aria", "Elena"), ("Bram", "Cedric"), ("Celia", "Livia")]:
            assert (first in text) != (second in text)
        assert "right hand" in text and "left hand grips" in text
        assert ("blue cloak" in text) != ("green cloak" in text)
    elif profile == "red_dress":
        assert "black maid dress" not in text


@pytest.mark.parametrize("name", ["natural-language-maid", "natural-language-spatial"])
def test_text_example_is_the_first_choice_expansion(name, tmp_path):
    document = yaml.safe_load((EXAMPLES / f"{name}.yaml").read_text(encoding="utf-8"))
    document["variables"] = {key: [values[0]] for key, values in document["variables"].items()}
    path = tmp_path / "first.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    text = create_text_v2({"input": str(path), "json": True, "max_number": -1})["output_text"][0]["prompt"]
    assert text == (EXAMPLES / f"{name}.txt").read_text(encoding="utf-8").rstrip("\n")
