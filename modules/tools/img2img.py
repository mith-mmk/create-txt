"""
modules/tools/img2img.py — DSL img2img コマンドの実装
"""

from __future__ import annotations

import glob
import os
from typing import TYPE_CHECKING

import modules.img2img as _img2img
import modules.logger as logger

if TYPE_CHECKING:
    from modules.tools.context import RunnerContext

Logger = logger.getDefaultLogger()


def run(profile_name: str, context: "RunnerContext") -> bool:
    """
    DSL コマンド: img2img <profile_name>
    context.config["profiles"]["img2img"][profile_name] の設定で img2img を実行する。
    """
    profile = context.get_profile("img2img", profile_name)
    if not profile:
        Logger.error(f"[img2img] profile not found: {profile_name}")
        return False

    host = context.effective_host()
    dry_run = context.dry_run

    if profile.get("input"):
        from modules.tools.txt2img import _build_cp2_namespace
        import cp2
        args = _build_cp2_namespace(profile, host, context)
        args.api_type = "img2img"
        raw_options = profile.get("options", {})
        options = raw_options if isinstance(raw_options, dict) else {}
        args.api_set_sd_model = profile.get("model") or options.get(
            "model", options.get("sd_model")
        )
        if dry_run:
            return True
        return bool(cp2.main(args))

    input_dir = profile.get("input_dir") or profile.get("dir", {}).get("input", "")
    if not input_dir:
        Logger.error("[img2img] input_dir が未設定です")
        return False

    output_dir = profile.get("output") or profile.get("dir", {}).get(
        "output", "./outputs"
    )
    work_dir = profile.get("dir", {}).get("work", "")
    mask_dir = profile.get("dir", {}).get("mask", "")
    ended_dir = profile.get("dir", {}).get("ended", "")

    # 画像ファイル収集
    exts = ("*.png", "*.jpg", "*.jpeg", "*.webp")
    imagefiles: list[str] = []
    for ext in exts:
        imagefiles.extend(sorted(glob.glob(os.path.join(input_dir, ext))))

    if not imagefiles:
        Logger.info(f"[img2img] no images in {input_dir}")
        return True

    Logger.info(f"[img2img] {len(imagefiles)} images, output={output_dir}")

    overrides: dict = {}
    for key in ("steps", "denoising_strength", "n_iter", "batch_size", "sampler_name"):
        if key in profile:
            overrides[key] = profile[key]
    # typo 互換
    if "denosing_stringth" in profile and "denoising_strength" not in overrides:
        overrides["denoising_strength"] = profile["denosing_stringth"]

    raw_options = profile.get("options", {})
    opt: dict = dict(raw_options) if isinstance(raw_options, dict) else {}
    if "vae" in opt:
        opt["sd_vae"] = opt["vae"]
    else:
        opt.setdefault("sd_vae", profile.get("vae", "Automatic"))
    opt.setdefault("text_encoder", profile.get("text_encoder", "Automatic"))
    opt.setdefault("sd_model", profile.get("model", opt.get("model", opt.get("sd_model"))))
    opt["work_dir"] = work_dir
    opt["ended_dir"] = ended_dir
    opt["folder_suffix"] = profile.get("folder_suffix", "-images")

    if dry_run:
        Logger.info("[img2img] dry_run: skip img2img()")
        return True

    try:
        results = _img2img.img2img(
            imagefiles=imagefiles,
            overrides=overrides,
            base_url=host,
            output_dir=output_dir,
            opt=opt,
        )
        return bool(results) and all(item.get("success") for item in results)
    except Exception as e:
        Logger.error(f"[img2img] error: {e}")
        return False
