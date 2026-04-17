"""
jsonl_converter.py — JSONL/TXT/CSV 相互変換ユーティリティ

DSL コマンド: jsonl convert <subcommand> <src> <dest> [options]
  subcommands:
    txt2jsonl   src.txt   dest.jsonl
    jsonl2txt   src.jsonl dest.txt
    jsonl2csv   src.jsonl dest.csv
    reorder     src.jsonl dest.jsonl  [key=W,V,C,...]
"""

from __future__ import annotations

import csv
import json
import os
import sys
from typing import Any

import modules.logger as logger

Logger = logger.getDefaultLogger()

# ---------------------------------------------------------------------------
# テキスト → JSONL
# ---------------------------------------------------------------------------


def txt_to_jsonl(src: str, dest: str) -> int:
    """
    `0.1;val1;val2` 形式のテキストを JSONL に変換する。
    先頭が '#' の行はコメントとして無視する。
    戻り値: 変換行数
    """
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    count = 0
    with open(src, encoding="utf-8") as fin, open(dest, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split(";")
            # 先頭が数値ならウェイト
            try:
                w = float(parts[0])
                values = [p.strip() for p in parts[1:] if p.strip()]
            except ValueError:
                w = None
                values = [p.strip() for p in parts if p.strip()]

            record: dict[str, Any] = {}
            if w is not None:
                record["W"] = w
            if values:
                record["V"] = values
            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    Logger.info(f"[jsonl_converter] txt2jsonl: {count} lines → {dest}")
    return count


# ---------------------------------------------------------------------------
# JSONL → テキスト
# ---------------------------------------------------------------------------


def jsonl_to_txt(src: str, dest: str) -> int:
    """JSONL を `W;V[0];V[1];...` 形式のテキストに変換する。"""
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    count = 0
    with open(src, encoding="utf-8") as fin, open(dest, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            parts: list[str] = []
            if "W" in record:
                parts.append(str(record["W"]))
            values = record.get("V", [])
            if isinstance(values, str):
                values = [values]
            parts.extend(str(v) for v in values)
            fout.write(";".join(parts) + "\n")
            count += 1
    Logger.info(f"[jsonl_converter] jsonl2txt: {count} lines → {dest}")
    return count


# ---------------------------------------------------------------------------
# JSONL → CSV
# ---------------------------------------------------------------------------


def jsonl_to_csv(src: str, dest: str) -> int:
    """JSONL を CSV に変換する（全フィールドをヘッダー行付きで出力）。"""
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    records: list[dict] = []
    with open(src, encoding="utf-8") as fin:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not records:
        Logger.warning(f"[jsonl_converter] jsonl2csv: no records in {src}")
        return 0

    # 全レコードのキーを収集（登場順を維持）
    keys: list[str] = []
    seen: set[str] = set()
    for r in records:
        for k in r:
            if k not in seen:
                keys.append(k)
                seen.add(k)

    with open(dest, "w", encoding="utf-8", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            # V が list の場合は文字列化
            row = {
                k: (
                    json.dumps(v, ensure_ascii=False)
                    if isinstance(v, (list, dict))
                    else v
                )
                for k, v in r.items()
            }
            writer.writerow(row)
    Logger.info(f"[jsonl_converter] jsonl2csv: {len(records)} lines → {dest}")
    return len(records)


# ---------------------------------------------------------------------------
# JSONL → JSONL（フィールド順変換）
# ---------------------------------------------------------------------------


def jsonl_reorder(
    src: str,
    dest: str,
    field_order: list[str] | None = None,
    rename: dict[str, str] | None = None,
) -> int:
    """
    JSONL のフィールド順を並び替え・リネームして出力する。
    field_order: ['W', 'C', 'V', ...]  — この順で並び替え（未指定キーは末尾に追加）
    rename: {'old_key': 'new_key', ...}
    """
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    count = 0
    with open(src, encoding="utf-8") as fin, open(dest, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            # リネーム
            if rename:
                record = {rename.get(k, k): v for k, v in record.items()}

            # 並び替え
            if field_order:
                ordered: dict = {}
                for k in field_order:
                    if k in record:
                        ordered[k] = record[k]
                # 残りのキーを末尾に
                for k, v in record.items():
                    if k not in ordered:
                        ordered[k] = v
                record = ordered

            fout.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    Logger.info(f"[jsonl_converter] reorder: {count} lines → {dest}")
    return count


# ---------------------------------------------------------------------------
# DSL エントリーポイント
# ---------------------------------------------------------------------------


def run_convert(args: list[str]) -> int:
    """
    DSL: jsonl convert <subcommand> <src> <dest> [options]
    options:
      order=W,C,V,...   (reorder のフィールド順)
      rename=old:new,...  (リネームマッピング)
    戻り値: 変換行数（エラー時 -1）
    """
    if len(args) < 3:
        Logger.error("[jsonl_converter] usage: jsonl convert <subcommand> <src> <dest>")
        return -1

    subcmd, src, dest = args[0], args[1], args[2]
    opts = _parse_opts(args[3:])

    if not os.path.isfile(src):
        Logger.error(f"[jsonl_converter] source not found: {src}")
        return -1

    subcmd = subcmd.lower()
    if subcmd in ("txt2jsonl", "txt"):
        return txt_to_jsonl(src, dest)
    elif subcmd in ("jsonl2txt", "txt2"):
        return jsonl_to_txt(src, dest)
    elif subcmd in ("jsonl2csv", "csv"):
        return jsonl_to_csv(src, dest)
    elif subcmd in ("reorder", "jsonl"):
        order = [k.strip() for k in opts.get("order", "").split(",") if k.strip()]
        rename_raw = opts.get("rename", "")
        rename: dict[str, str] = {}
        for pair in rename_raw.split(","):
            if ":" in pair:
                old, new = pair.split(":", 1)
                rename[old.strip()] = new.strip()
        return jsonl_reorder(
            src, dest, field_order=order or None, rename=rename or None
        )
    else:
        Logger.error(f"[jsonl_converter] unknown subcommand: {subcmd}")
        return -1


def _parse_opts(args: list[str]) -> dict[str, str]:
    """key=value 形式のオプションリストを辞書に変換する。"""
    opts: dict[str, str] = {}
    for a in args:
        if "=" in a:
            k, v = a.split("=", 1)
            opts[k.strip()] = v.strip()
    return opts


# ---------------------------------------------------------------------------
# スタンドアロン実行
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # python -m modules.tools.jsonl_converter convert txt2jsonl src.txt dest.jsonl
    argv = sys.argv[1:]
    if argv and argv[0] == "convert":
        result = run_convert(argv[1:])
        sys.exit(0 if result >= 0 else 1)
    else:
        print(
            "Usage: python -m modules.tools.jsonl_converter convert <subcommand> <src> <dest> [options]"
        )
        sys.exit(1)
