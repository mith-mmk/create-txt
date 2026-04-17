"""
modules/tools/dsl.py — YAML ベース疑似プログラムの DSL インタープリタ

スクリプト言語仕様: temp/script.py 参照
式評価には modules.formula.FormulaCompute を流用する。
"""

from __future__ import annotations

import importlib
import os
import re
import subprocess
import time
from typing import Any

import yaml

import modules.logger as logger
import modules.share as share
from modules.formula import FormulaCompute
from modules.tools.context import RunnerContext

Logger = logger.getDefaultLogger()

# ---------------------------------------------------------------------------
# 例外
# ---------------------------------------------------------------------------


class BreakException(Exception):
    """BREAK コマンドで LOOP/FOREACH を抜けるために使う。"""


class ExitException(Exception):
    """EXIT コマンドでスクリプトを終了するために使う。"""


# ---------------------------------------------------------------------------
# DSL インタープリタ
# ---------------------------------------------------------------------------


class DSLInterpreter:
    """
    YAML script: キーに記述されたテキストスクリプトを実行する。

    スクリプト書式:
      コマンドは1行1コマンド（大文字・小文字どちらでも可）。
      ブロック構造:
        LOOP N / ENDLOOP
        FOREACH var IN arr / END
        WHILE expr / END
        IF expr / ELSE / ENDIF
      代入:
        SET var = expr
      配列:
        ARRAY var = [val1, val2, ...]
      設定ロード:
        VALLOAD filename.yaml|.csv
    """

    def __init__(self, context: RunnerContext):
        self.context = context

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    def run(self, script: str | list) -> None:
        """スクリプト文字列またはコマンドリストを実行する。"""
        if isinstance(script, list):
            lines = []
            for item in script:
                if isinstance(item, str):
                    lines.append(item)
                elif isinstance(item, dict):
                    # YAML の複合構造は無視
                    pass
            script = "\n".join(lines)
        lines = self._preprocess(script)
        self._exec_block(lines, 0, len(lines))

    # ------------------------------------------------------------------
    # 前処理
    # ------------------------------------------------------------------

    def _preprocess(self, text: str) -> list[str]:
        """スクリプトテキストを行リストに変換し、空行・コメントを除去する。"""
        lines = []
        for raw in text.splitlines():
            stripped = raw.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lines.append(stripped)
        return lines

    # ------------------------------------------------------------------
    # ブロック実行
    # ------------------------------------------------------------------

    def _exec_block(self, lines: list[str], start: int, end: int) -> None:
        """lines[start:end] を順次実行する。"""
        i = start
        while i < end:
            line = lines[i]
            upper = line.upper()

            # ---------- LOOP ----------
            if re.match(r"^LOOP\s*(-?\d+)$", upper):
                count = int(re.match(r"^LOOP\s*(-?\d+)$", upper).group(1))
                close = self._find_block_end(lines, i, "LOOP", "ENDLOOP")
                self._exec_loop(lines, i + 1, close, count)
                i = close + 1
                continue

            # ---------- FOREACH ----------
            m = re.match(r"^FOREACH\s+(\S+)\s+IN\s+(.+)$", line, re.IGNORECASE)
            if m:
                var_name = m.group(1)
                arr_expr = m.group(2).strip()
                close = self._find_block_end(lines, i, "FOREACH", "END")
                self._exec_foreach(lines, i + 1, close, var_name, arr_expr)
                i = close + 1
                continue

            # ---------- WHILE ----------
            m = re.match(r"^WHILE\s+(.+)$", line, re.IGNORECASE)
            if m:
                cond_expr = m.group(1).strip()
                close = self._find_block_end(lines, i, "WHILE", "END")
                self._exec_while(lines, i + 1, close, cond_expr)
                i = close + 1
                continue

            # ---------- IF ----------
            m = re.match(r"^IF\s+(.+)$", line, re.IGNORECASE)
            if m:
                close = self._find_if_end(lines, i)
                i = self._exec_if(lines, i, close) + 1
                continue

            # ---------- 単純コマンド ----------
            self._exec_command(line)
            i += 1

    # ------------------------------------------------------------------
    # 制御構造
    # ------------------------------------------------------------------

    def _exec_loop(self, lines: list[str], start: int, end: int, count: int) -> None:
        """LOOP N / ENDLOOP — count=-1 で無限ループ。"""
        iteration = 0
        while count < 0 or iteration < count:
            try:
                self._exec_block(lines, start, end)
            except BreakException:
                break
            iteration += 1

    def _exec_foreach(
        self,
        lines: list[str],
        start: int,
        end: int,
        var_name: str,
        arr_expr: str,
    ) -> None:
        """FOREACH var IN arr / END"""
        items = self._eval_array_expr(arr_expr)
        for item in items:
            self.context.set_var(var_name, item)
            try:
                self._exec_block(lines, start, end)
            except BreakException:
                break

    def _exec_while(
        self, lines: list[str], start: int, end: int, cond_expr: str
    ) -> None:
        """WHILE expr / END"""
        while self._eval_bool(cond_expr):
            try:
                self._exec_block(lines, start, end)
            except BreakException:
                break

    def _exec_if(self, lines: list[str], if_line: int, endif_line: int) -> int:
        """IF ... [ELSE IF ...] [ELSE] ENDIF ブロックを評価して対応するブランチを実行する。"""
        # ブランチを収集: (condition_line_idx, body_start, body_end)
        branches: list[tuple[int | None, int, int]] = []
        else_start: int | None = None

        i = if_line
        while i <= endif_line:
            u = lines[i].upper()
            if i == if_line:
                body_start = i + 1
                branches.append((i, -1, -1))  # placeholder
                i += 1
                continue
            if re.match(r"^ELSE\s+IF\s+", u):
                # 直前ブランチの body_end を確定
                prev_cond, prev_start, _ = branches[-1]
                branches[-1] = (prev_cond, prev_start, i)
                branches.append((i, i + 1, -1))
                i += 1
                continue
            if u == "ELSE":
                prev_cond, prev_start, _ = branches[-1]
                branches[-1] = (prev_cond, prev_start, i)
                else_start = i + 1
                i += 1
                continue
            i += 1

        # 最後のブランチの body_end を確定
        if branches:
            prev_cond, prev_start, prev_end = branches[-1]
            if prev_end < 0:
                close = else_start - 1 if else_start else endif_line
                branches[-1] = (prev_cond, prev_start, close)

        # 評価
        executed = False
        for cond_line, body_start, body_end in branches:
            if cond_line is None:
                continue
            raw_line = lines[cond_line]
            m = re.match(r"^(?:ELSE\s+)?IF\s+(.+)$", raw_line, re.IGNORECASE)
            if not m:
                continue
            if self._eval_bool(m.group(1).strip()):
                self._exec_block(lines, body_start, body_end)
                executed = True
                break

        if not executed and else_start is not None:
            self._exec_block(lines, else_start, endif_line)

        return endif_line

    # ------------------------------------------------------------------
    # ブロック境界検索
    # ------------------------------------------------------------------

    def _find_block_end(
        self, lines: list[str], start: int, open_kw: str, close_kw: str
    ) -> int:
        """ネストを考慮して close_kw の位置を返す。"""
        depth = 1
        i = start + 1
        while i < len(lines):
            u = lines[i].upper()
            if u.startswith(open_kw):
                depth += 1
            elif u == close_kw:
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        raise SyntaxError(f"'{close_kw}' not found for '{open_kw}' at line {start}")

    def _find_if_end(self, lines: list[str], start: int) -> int:
        """ENDIF の位置を返す（ネスト考慮）。"""
        depth = 1
        i = start + 1
        while i < len(lines):
            u = lines[i].upper()
            if u.startswith("IF ") or u == "IF":
                depth += 1
            elif u == "ENDIF":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        raise SyntaxError(f"ENDIF not found for IF at line {start}")

    # ------------------------------------------------------------------
    # 単純コマンドのディスパッチ
    # ------------------------------------------------------------------

    def _exec_command(self, line: str) -> None:
        """1行コマンドをパースしてディスパッチする。"""
        ctx = self.context
        parts = _split_args(line)
        if not parts:
            return
        cmd = parts[0].upper()
        args = parts[1:]

        # ---------- 制御 ----------
        if cmd == "BREAK":
            raise BreakException()

        if cmd == "EXIT":
            raise ExitException()

        # ---------- 変数代入 SET var = expr ----------
        if cmd == "SET":
            self._cmd_set(args)
            return

        # ---------- ARRAY var = [...] ----------
        if cmd == "ARRAY":
            self._cmd_array(args)
            return

        # ---------- VALLOAD ----------
        if cmd == "VALLOAD":
            self._cmd_valload(args)
            return

        # ---------- VALSAVE ----------
        if cmd == "VALSAVE":
            self._cmd_valsave(args)
            return

        # ---------- HOST ----------
        if cmd == "HOST":
            ctx.host = args[0] if args else ctx.host
            Logger.info(f"[dsl] HOST = {ctx.host}")
            return

        # ---------- OPT / OPTION ----------
        if cmd in ("OPT", "OPTION"):
            self._cmd_option(args)
            return

        # ---------- LOG ----------
        if cmd == "LOG":
            Logger.info("[script] " + " ".join(args))
            return

        # ---------- SLEEP / WAIT ----------
        if cmd == "SLEEP":
            sec = float(self._eval_expr(args[0])) if args else 1
            Logger.info(f"[dsl] sleep {sec}s")
            time.sleep(sec)
            return

        if cmd == "WAIT":
            from modules.tools.events import wait_until

            wait_until(args[0] if args else "00:00")
            return

        # ---------- PING ----------
        if cmd == "PING":
            from modules.tools.events import wait_ping

            host = args[0] if args else ctx.host
            ok = wait_ping(host)
            ctx.exitcode = ok
            return

        # ---------- CHECK ----------
        if cmd == "CHECK":
            from modules.tools.events import check_schedule

            time_range = args[0] if args else "00:00-23:59"
            in_schedule = check_schedule(time_range)
            if not in_schedule:
                wait_sec = 60
                Logger.info(
                    f"[dsl] CHECK: out of schedule ({time_range}), sleep {wait_sec}s"
                )
                time.sleep(wait_sec)
            ctx.exitcode = in_schedule
            return

        # ---------- CHECKSERVER ----------
        if cmd == "CHECKSERVER":
            from modules.tools.events import detect_server

            comfyui_host = args[0] if args else ctx.comfyui_host
            server_type = detect_server(ctx.host, comfyui_host=comfyui_host)
            ctx.server_type = server_type
            ctx.exitcode = server_type
            ctx.set_var("EXITCODE", server_type)
            return

        # ---------- UNLOAD ----------
        if cmd == "UNLOAD":
            from modules.tools.events import unload_model

            host = args[0] if args else ctx.host
            ok = unload_model(host, ctx.server_type)
            ctx.exitcode = ok
            return

        # ---------- SETMODEL ----------
        if cmd == "SETMODEL":
            import modules.api as api

            model = args[0] if args else ""
            vae = args[1] if len(args) > 1 else "Automatic"
            if not ctx.dry_run and model:
                api.set_sd_model(model, base_url=ctx.host, sd_vae=vae)
            ctx.exitcode = model
            return

        # ---------- GETMODEL ----------
        if cmd == "GETMODEL":
            import modules.api as api

            r = api.get_response(ctx.host + "/sdapi/v1/options")
            if r and hasattr(r, "text"):
                import json as _json

                try:
                    data = _json.loads(r.text)
                    ctx.exitcode = data.get("sd_model_checkpoint", "")
                except Exception:
                    ctx.exitcode = ""
            return

        # ---------- LOAD ----------
        if cmd == "LOAD":
            self._cmd_load(args)
            return

        # ---------- SAVE ----------
        if cmd == "SAVE":
            self._cmd_save(args)
            return

        # ---------- CALL ----------
        if cmd == "CALL":
            raw = " ".join(args)
            Logger.info(f"[dsl] CALL: {raw}")
            if not ctx.dry_run:
                result = subprocess.run(raw, shell=True)
                ctx.exitcode = result.returncode
            return

        # ---------- WATCH ----------
        if cmd == "WATCH":
            from modules.tools.events import watch_files

            path = args[0] if args else "."
            pattern = args[1] if len(args) > 1 else "*"
            timeout = float(args[2]) if len(args) > 2 else 0
            files = watch_files(path, pattern=pattern, timeout=timeout)
            ctx.exitcode = files
            return

        # ---------- JSONL ----------
        if cmd == "JSONL":
            from modules.tools.jsonl_converter import run_convert

            result = run_convert(args)
            ctx.exitcode = result
            return

        # ---------- txt2img ----------
        if cmd == "TXT2IMG":
            from modules.tools.txt2img import run

            profile = args[0] if args else "default"
            ok = run(profile, ctx)
            ctx.exitcode = ok
            return

        # ---------- img2img ----------
        if cmd == "IMG2IMG":
            from modules.tools.img2img import run

            profile = args[0] if args else "default"
            ok = run(profile, ctx)
            ctx.exitcode = ok
            return

        # ---------- img2txt2img ----------
        if cmd == "IMG2TXT2IMG":
            from modules.tools.img2txt2img import run

            profile = args[0] if args else "default"
            ok = run(profile, ctx)
            ctx.exitcode = ok
            return

        # ---------- workflow ----------
        if cmd == "WORKFLOW":
            from modules.tools.comfyui import run_workflow

            wf = args[0] if args else ""
            ok = run_workflow(wf, ctx, extra_args=args[1:])
            ctx.exitcode = ok
            return

        # ---------- custom ----------
        if cmd == "CUSTOM":
            self._cmd_custom(args)
            return

        Logger.warning(f"[dsl] unknown command: {line}")

    # ------------------------------------------------------------------
    # 個別コマンド実装
    # ------------------------------------------------------------------

    def _cmd_set(self, args: list[str]) -> None:
        """SET var = expr"""
        joined = " ".join(args)
        m = re.match(r"^(\w+)\s*=\s*(.+)$", joined, re.DOTALL)
        if not m:
            Logger.warning(f"[dsl] SET parse error: {joined}")
            return
        var_name = m.group(1)
        expr = m.group(2).strip()
        # EXITCODE を参照
        if expr.upper() == "EXITCODE":
            value = self.context.exitcode
        else:
            value = self._eval_expr(expr)
        self.context.set_var(var_name, value)

    def _cmd_array(self, args: list[str]) -> None:
        """ARRAY var = [val1, val2, ...]"""
        joined = " ".join(args)
        m = re.match(r"^(\w+)\s*=\s*\[(.+)\]$", joined, re.DOTALL)
        if not m:
            Logger.warning(f"[dsl] ARRAY parse error: {joined}")
            return
        var_name = m.group(1)
        raw_list = m.group(2)
        items = [v.strip().strip("'\"") for v in raw_list.split(",") if v.strip()]
        self.context.set_var(var_name, items)

    def _cmd_valload(self, args: list[str]) -> None:
        """VALLOAD filename.yaml|.csv — 変数を外部ファイルから一括ロードする。"""
        if not args:
            return
        filepath = args[0]
        if not os.path.isfile(filepath):
            Logger.warning(f"[dsl] VALLOAD: file not found: {filepath}")
            return
        ext = os.path.splitext(filepath)[1].lower()
        if ext in (".yaml", ".yml"):
            with open(filepath, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            for k, v in data.items():
                self.context.set_var(k, v)
        elif ext == ".csv":
            import csv

            with open(filepath, encoding="utf-8", newline="") as f:
                for row in csv.reader(f):
                    if len(row) >= 2:
                        self.context.set_var(row[0].strip(), row[1].strip())
        Logger.info(f"[dsl] VALLOAD: {filepath}")

    def _cmd_valsave(self, args: list[str]) -> None:
        """VALSAVE filename.yaml — 変数を外部ファイルに保存する。"""
        if not args:
            return
        filepath = args[0]
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        ext = os.path.splitext(filepath)[1].lower()
        if ext in (".yaml", ".yml"):
            with open(filepath, "w", encoding="utf-8") as f:
                yaml.dump(dict(self.context.variables), f, allow_unicode=True)
        elif ext == ".csv":
            import csv

            with open(filepath, "w", encoding="utf-8", newline="") as f:
                w = csv.writer(f)
                for k, v in self.context.variables.items():
                    w.writerow([k, v])
        Logger.info(f"[dsl] VALSAVE: {filepath}")

    def _cmd_option(self, args: list[str]) -> None:
        """OPT key = value"""
        joined = " ".join(args)
        m = re.match(r"^(\w+)\s*=\s*(.+)$", joined)
        if not m:
            Logger.warning(f"[dsl] OPT parse error: {joined}")
            return
        self.context.set_option(m.group(1), self._eval_expr(m.group(2).strip()))

    def _cmd_load(self, args: list[str]) -> None:
        """LOAD filename — 設定 YAML を再ロードして context.config に反映する。"""
        if not args:
            return
        filepath = args[0]
        if not os.path.isfile(filepath):
            Logger.warning(f"[dsl] LOAD: file not found: {filepath}")
            return
        with open(filepath, encoding="utf-8") as f:
            new_cfg = yaml.safe_load(f) or {}
        self.context.config.update(new_cfg)
        share.set("config", new_cfg)
        if "host" in new_cfg:
            self.context.host = new_cfg["host"]
        Logger.info(f"[dsl] LOAD: {filepath}")

    def _cmd_save(self, args: list[str]) -> None:
        """SAVE filename — 現在の config を YAML に保存する。"""
        if not args:
            return
        filepath = args[0]
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.dump(self.context.config, f, allow_unicode=True)
        Logger.info(f"[dsl] SAVE: {filepath}")

    def _cmd_custom(self, args: list[str]) -> None:
        """custom <plugin_name> [args...]"""
        if not args:
            return
        plugin_name = args[0]
        plugin_args = args[1:]
        try:
            mod = importlib.import_module(f"plugins.{plugin_name}")
            result = mod.run_plugin(plugin_args, self.context.config)
            self.context.exitcode = result
        except ImportError:
            Logger.error(f"[dsl] custom plugin not found: {plugin_name}")
        except Exception as e:
            Logger.error(f"[dsl] custom plugin error ({plugin_name}): {e}")

    # ------------------------------------------------------------------
    # 式評価
    # ------------------------------------------------------------------

    def _eval_expr(self, expr: str) -> Any:
        """
        式を評価して値を返す。
        FormulaCompute を使って +,-,*,/,==,!=,<,>,&&,|| などを処理する。
        文字列リテラル（引用符で囲まれた値）はそのまま返す。
        """
        expr = expr.strip()

        # 引用符で囲まれた文字列リテラル
        if (expr.startswith('"') and expr.endswith('"')) or (
            expr.startswith("'") and expr.endswith("'")
        ):
            return expr[1:-1]

        # ${var} 展開後の式
        expr_expanded = self._expand_vars(expr)

        # True / False / None リテラル
        if expr_expanded.lower() == "true":
            return True
        if expr_expanded.lower() == "false":
            return False
        if expr_expanded.lower() in ("none", "null"):
            return None

        # 数値リテラル
        try:
            return int(expr_expanded)
        except ValueError:
            pass
        try:
            return float(expr_expanded)
        except ValueError:
            pass

        # FormulaCompute で評価
        variables = {k: v for k, v in self.context.variables.items()}
        try:
            fc = FormulaCompute(
                formula=expr_expanded,
                variables=variables,
            )
            result = fc.getCompute()
            if result is not None:
                return result
        except Exception:
            pass

        # 変数名として直接参照
        val = self.context.get_var(expr)
        if val is not None:
            return val

        # そのまま文字列として返す
        return expr_expanded

    def _eval_bool(self, expr: str) -> bool:
        """条件式を評価してbool を返す。"""
        val = self._eval_expr(expr)
        if isinstance(val, bool):
            return val
        if isinstance(val, (int, float)):
            return val != 0
        if isinstance(val, str):
            return val.lower() not in ("false", "0", "", "none", "null")
        return bool(val)

    def _eval_array_expr(self, expr: str) -> list:
        """配列式（変数参照またはリテラル）を評価してリストを返す。"""
        val = self._eval_expr(expr)
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [v.strip() for v in val.split(",") if v.strip()]
        return [val]

    def _expand_vars(self, text: str) -> str:
        """${var} を context.variables で置換する。"""

        def replacer(m: re.Match) -> str:
            key = m.group(1).strip()
            v = self.context.get_var(key)
            return str(v) if v is not None else m.group(0)

        return re.sub(r"\$\{([^}]+)\}", replacer, text)


# ---------------------------------------------------------------------------
# 引数分割ユーティリティ
# ---------------------------------------------------------------------------


def _split_args(line: str) -> list[str]:
    """
    コマンド行をスペース区切りで分割する。
    引用符（' または "）で囲まれた部分はひとつのトークンとして扱う。
    """
    tokens: list[str] = []
    current = []
    in_quote = None
    for ch in line:
        if in_quote:
            if ch == in_quote:
                in_quote = None
                tokens.append("".join(current))
                current = []
            else:
                current.append(ch)
        elif ch in ('"', "'"):
            in_quote = ch
        elif ch == " " or ch == "\t":
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        tokens.append("".join(current))
    return tokens
