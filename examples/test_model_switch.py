#!/usr/bin/env python3
"""Switch between installed Anima, Illustrious and Pony checkpoints.

The script deliberately requires checkpoint names from the caller.  It does
not guess a local model and it does not download modules.  Without
``--generate`` it only exercises the checkpoint/module switch API, which is
safe to run while preparing a later generation test.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Iterable
from pathlib import Path

# Allow execution as ``python examples/test_model_switch.py`` from any cwd.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules import api

FAMILIES = ("anima", "illustrious", "pony")
ALIASES = {"illustrius": "illustrious"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://localhost:7860")
    parser.add_argument(
        "--family", action="append", choices=FAMILIES,
        help="family to switch (repeatable; default: all configured families)",
    )
    parser.add_argument(
        "--model", action="append", metavar="FAMILY=CHECKPOINT",
        help="installed checkpoint mapping; repeat for each family",
    )
    parser.add_argument("--vae", default="Automatic")
    parser.add_argument("--text-encoder", default="Automatic")
    parser.add_argument("--output-dir", default="./outputs/model-switch")
    parser.add_argument("--generate", action="store_true", help="send one txt2img request after each switch")
    parser.add_argument("--prompt", default="a simple studio still life")
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _model_map(values: Iterable[str] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values or ():
        family, separator, checkpoint = value.partition("=")
        family = ALIASES.get(family.strip().lower(), family.strip().lower())
        checkpoint = checkpoint.strip()
        if not separator or family not in FAMILIES or not checkpoint:
            raise ValueError(f"--model must be FAMILY=CHECKPOINT (family: {', '.join(FAMILIES)})")
        if family in result:
            raise ValueError(f"duplicate model mapping for {family}")
        result[family] = checkpoint
    return result


def _configured_models(args: argparse.Namespace) -> dict[str, str]:
    models = _model_map(args.model)
    for family in FAMILIES:
        env_name = f"CREATE_TXT_{family.upper()}_MODEL"
        if family not in models and os.environ.get(env_name):
            models[family] = os.environ[env_name]
    selected = args.family or [family for family in FAMILIES if family in models]
    if not selected:
        raise ValueError("provide at least one --model FAMILY=CHECKPOINT mapping")
    missing = [family for family in selected if family not in models]
    if missing:
        names = ", ".join(f"--model {family}=CHECKPOINT" for family in missing)
        raise ValueError(f"checkpoint names are required: {names}")
    return {family: models[family] for family in selected}


def run(args: argparse.Namespace) -> int:
    models = _configured_models(args)
    for family, checkpoint in models.items():
        print(f"[{family}] switch -> {checkpoint}")
        if args.dry_run:
            continue
        api.set_sd_model(
            checkpoint,
            base_url=args.api_base,
            sd_vae=args.vae,
            text_encoder=args.text_encoder,
        )
        if args.generate:
            from modules.txt2img import txt2img

            ok = txt2img(
                [{"prompt": args.prompt, "steps": args.steps, "width": 512, "height": 512}],
                base_url=args.api_base,
                output_dir=args.output_dir,
                opt={"model_type": family, "ui_type": "neo", "image_type": "png"},
            )
            if not ok:
                print(f"[{family}] generation failed", file=sys.stderr)
                return 1
    return 0


def main() -> int:
    args = _parser().parse_args()
    try:
        return run(args)
    except Exception as exc:
        print(f"model switch failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
