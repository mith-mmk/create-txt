"""
model_selector.py — モデルのランダム選択
CSV ファイル・リスト・API 応答から使用モデルを選ぶ。
"""

from __future__ import annotations

import csv
import os
import random
from typing import Any

import modules.logger as logger

Logger = logger.getDefaultLogger()


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------


def random_model(
    source: str | list,
    context=None,
    abort_matrix: dict | None = None,
    genre: str | None = None,
) -> str | None:
    """
    source に応じてモデルを1つランダム選択して返す。

    source:
      - list  → 直接リストからランダム選択
      - str   → CSV ファイルパスとして読み込む
               CSV 1列目: モデルファイル名（コメント行 # は無視）
    abort_matrix:
      {"PONY": ["py","pysfw"], ...} 形式。genre を受け取り
      モデルの suffix に対応するジャンルが abort リストにある場合は除外。
    genre: 現在のジャンル（abort_matrix フィルタに使用）
    """
    if isinstance(source, list):
        candidates = [str(s) for s in source if s]
    elif isinstance(source, str):
        candidates = _load_csv(source)
    else:
        Logger.warning(f"[model_selector] unknown source type: {type(source)}")
        return None

    if not candidates:
        Logger.warning("[model_selector] no candidates")
        return None

    if abort_matrix and genre:
        candidates = _apply_abort_matrix(candidates, abort_matrix, genre)

    if not candidates:
        Logger.warning(f"[model_selector] all candidates filtered out (genre={genre})")
        return None

    chosen = random.choice(candidates)
    Logger.info(f"[model_selector] selected model: {chosen}")
    return chosen


# ---------------------------------------------------------------------------
# 内部実装
# ---------------------------------------------------------------------------


def _load_csv(filepath: str) -> list[str]:
    """CSV ファイルを読み込んで 1 列目のモデル名リストを返す。"""
    if not os.path.isfile(filepath):
        Logger.warning(f"[model_selector] CSV not found: {filepath}")
        return []
    models: list[str] = []
    try:
        with open(filepath, encoding="utf-8", newline="") as f:
            for row in csv.reader(f):
                if not row:
                    continue
                name = row[0].strip()
                if not name or name.startswith("#"):
                    continue
                models.append(name)
    except Exception as e:
        Logger.error(f"[model_selector] CSV read error: {e}")
    return models


def _apply_abort_matrix(
    candidates: list[str],
    abort_matrix: dict[str, list[str]],
    genre: str,
) -> list[str]:
    """
    abort_matrix に基づいてモデルをフィルタリングする。
    abort_matrix の値リストに genre が含まれるキーを suffix として持つ
    モデルは除外する。
    """
    blocked_suffixes: set[str] = set()
    for key, genres in abort_matrix.items():
        if genre in genres:
            blocked_suffixes.add(key.lower())

    if not blocked_suffixes:
        return candidates

    filtered = []
    for m in candidates:
        name_lower = m.lower().replace(".safetensors", "").replace(".ckpt", "")
        blocked = any(name_lower.endswith(s) for s in blocked_suffixes)
        if not blocked:
            filtered.append(m)
    return filtered
