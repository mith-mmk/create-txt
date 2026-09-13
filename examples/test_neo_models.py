#!/usr/bin/env python3
"""Run a real Forge Neo model-switch smoke test from a YAML case list.

The checkpoint and module names are intentionally read from the YAML instead
of guessed.  Use without ``--generate`` to switch and verify the active model
only; add ``--generate`` to send one small txt2img request per case.
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import api, webui  # noqa: E402


def load_config(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict) or not isinstance(value.get("tests"), list):
        raise ValueError("test YAML must contain a tests list")
    return value


def _args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "config", nargs="?", type=Path,
        default=ROOT / "examples" / "neo-real-models.yaml",
    )
    parser.add_argument("--api-base", default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--case", action="append", dest="cases", default=None)
    parser.add_argument("--generate", action="store_true", help="send one t2i request for each case")
    parser.add_argument("--dry-run", action="store_true", help="validate YAML without contacting Neo")
    parser.add_argument("--continue-on-error", action="store_true")
    return parser


def _as_options(case: dict[str, Any]) -> dict[str, Any]:
    raw = case.get("options", {})
    if not isinstance(raw, dict):
        raise ValueError(f"{case.get('name', '<unnamed>')}: options must be a mapping")
    options = copy.deepcopy(raw)
    options.setdefault("ui_type", case.get("ui_type", "neo"))
    options.setdefault("model_type", case.get("model_type"))
    return options


def _selected_module(options: dict[str, Any], key: str) -> Any:
    if key in options:
        return options[key]
    # Keep the old sd_vae spelling accepted by the runtime and test files.
    if key == "vae" and "sd_vae" in options:
        return options["sd_vae"]
    return "Automatic"


def _case_names(cases: list[dict[str, Any]], selected: list[str] | None) -> list[dict[str, Any]]:
    if not selected:
        return cases
    wanted = set(selected)
    result = [case for case in cases if str(case.get("name")) in wanted]
    missing = wanted - {str(case.get("name")) for case in result}
    if missing:
        raise ValueError(f"unknown case(s): {', '.join(sorted(missing))}")
    return result


def run(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    cases = _case_names(config["tests"], args.cases)
    base_url = args.api_base or config.get("api_base", "http://localhost:7860")
    output_dir = args.output_dir or Path(config.get("output_dir", "./outputs/neo-real-models"))

    for case in cases:
        name = str(case.get("name", "<unnamed>"))
        model = case.get("model")
        model_type = case.get("model_type")
        if not isinstance(model, str) or not model:
            raise ValueError(f"{name}: model is required")
        if not isinstance(model_type, str) or not model_type:
            raise ValueError(f"{name}: model_type is required")
        options = _as_options(case)
        vae = _selected_module(options, "vae")
        text_encoder = options.get("text_encoder", "Automatic")
        mode = str(case.get("mode", "txt2img"))
        if mode not in {"txt2img", "img2img"}:
            raise ValueError(f"{name}: mode must be txt2img or img2img")
        print(f"[{name}] model={model} type={model_type} vae={vae} text_encoder={text_encoder}")
        if args.dry_run:
            continue

        try:
            api.set_sd_model(
                model,
                base_url=base_url,
                sd_vae=vae,
                text_encoder=text_encoder,
            )
            server = webui.inspect_server(base_url)
            active = server.get("options", {}).get("sd_model_checkpoint")
            if webui.lookup_model(server.get("models", []), model, required=False) is None:
                raise ValueError(f"{name}: switched model is not in the API model list")
            print(f"[{name}] active checkpoint={active}")

            command = case.get("command", {})
            if not isinstance(command, dict):
                raise ValueError(f"{name}: command must be a mapping")
            payload_options = dict(options)
            payload_options.update({"base_url": base_url, "ui_type": "neo", "model_type": model_type})
            prepared = webui.prepare_payloads(
                [copy.deepcopy(command)], payload_options, mode,
                {"ui_type": "neo", "model_type": model_type, "server": server},
            )
            if args.generate:
                from modules.txt2img import txt2img

                ok = txt2img(
                    prepared,
                    base_url=base_url,
                    output_dir=str(output_dir),
                    opt={**payload_options, "image_type": "png"},
                )
                if not ok:
                    raise RuntimeError("generation returned no saved image")
                print(f"[{name}] generation saved under {output_dir}")
        except Exception as exc:
            print(f"[{name}] FAILED: {exc}", file=sys.stderr)
            if not args.continue_on_error:
                return 1
    return 0


def main() -> int:
    try:
        return run(_args().parse_args())
    except Exception as exc:
        print(f"Neo model test failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
