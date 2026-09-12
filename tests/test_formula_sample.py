import json
from pathlib import Path
import subprocess
import sys

import pytest

import cp2
from modules.prompt_v2 import create_text_v2


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples" / "formula.yaml"
EXPECTED = json.loads((ROOT / "examples" / "formula.expected.json").read_text(encoding="utf-8"))


def test_sample_expansion_is_offline_and_repeatable(monkeypatch, tmp_path):
    def no_network(*args, **kwargs):
        pytest.fail("Formula sample must not contact a generation server")

    monkeypatch.setattr("modules.webui.get_json", no_network)
    monkeypatch.setattr(cp2, "dispatch_webui", no_network)
    monkeypatch.setattr(cp2, "dispatch_comfy", no_network)
    for _ in range(2):
        result = create_text_v2({"input": str(SAMPLE), "max_number": -1})
        commands = [{k: v for k, v in item.items() if k != "verbose"}
                    for item in result["output_text"]]
        assert commands == EXPECTED
    output = tmp_path / "offline.json"
    args = cp2.build_parser().parse_args([str(SAMPLE), "--output", str(output)])
    assert cp2.main(args)
    assert json.loads(output.read_text(encoding="utf-8")) == EXPECTED


def test_sample_cli_saves_expected_json(tmp_path):
    output = tmp_path / "formula.json"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "cp2.py"), str(SAMPLE), "--output", str(output)],
        cwd=tmp_path, capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert json.loads(output.read_text(encoding="utf-8")) == EXPECTED
