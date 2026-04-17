"""
modules/tools/img2txt2img.py — DSL img2txt2img コマンドの実装
"""

from __future__ import annotations

import glob
import os
from typing import TYPE_CHECKING

import modules.img2txt2img as _i2t2i
import modules.logger as logger
from modules.tools.model_selector import random_model

if TYPE_CHECKING:
    from modules.tools.context import RunnerContext

Logger = logger.getDefaultLogger()


def run(profile_name: str, context: "RunnerContext") -> bool:
    """
    DSL コマンド: img2txt2img <profile_name>
    context.config["profiles"]["img2txt2img"][profile_name] の設定で実行する。
    """
    profile = context.get_profile("img2txt2img", profile_name)
    if not profile:
        Logger.error(f"[img2txt2img] profile not found: {profile_name}")
        return False

    host = context.effective_host()
    dry_run = context.dry_run

    input_dir = profile.get("input_dir") or profile.get("dir", {}).get("input", "")
    if not input_dir:
        Logger.error("[img2txt2img] input_dir が未設定です")
        return False

    output_dir = profile.get("output") or profile.get("dir", {}).get(
        "output", "./outputs"
    )

    # 画像ファイル収集
    exts = ("*.png", "*.jpg", "*.jpeg", "*.webp")
    imagefiles: list[str] = []
    for ext in exts:
        imagefiles.extend(sorted(glob.glob(os.path.join(input_dir, ext))))

    if not imagefiles:
        Logger.info(f"[img2txt2img] no images in {input_dir}")
        return True

    # モデル辞書 {modelname: vae}
    models: dict[str, str] = {}
    model_source = profile.get("models") or profile.get("modelfile")
    if model_source:
        if isinstance(model_source, list):
            models = {m: "Automatic" for m in model_source}
        elif isinstance(model_source, str) and os.path.isfile(model_source):
            import csv as _csv

            with open(model_source, encoding="utf-8", newline="") as f:
                for row in _csv.reader(f):
                    if not row or row[0].startswith("#"):
                        continue
                    mname = row[0].strip()
                    vae = row[1].strip() if len(row) > 1 else "Automatic"
                    models[mname] = vae

    opt = dict(profile.get("options", {}))
    opt["dry_run"] = dry_run

    Logger.info(f"[img2txt2img] {len(imagefiles)} images, output={output_dir}")

    if dry_run:
        Logger.info("[img2txt2img] dry_run: skip img2txt2img()")
        return True

    try:
        _i2t2i.img2txt2img(
            imagefiles=imagefiles,
            base_url=host,
            overrides=profile.get("overrides", {}),
            seed_diff=profile.get("seed_diff", 0),
            models=models,
            output_dir=output_dir,
            opt=opt,
        )
        return True
    except Exception as e:
        Logger.error(f"[img2txt2img] error: {e}")
        return False
