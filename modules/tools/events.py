"""
events.py — サーバー死活監視・スケジュール・ファイル監視・モデルアンロード
"""

from __future__ import annotations

import fnmatch
import os
import time
from datetime import datetime, timedelta
from typing import Callable

import httpx

import modules.logger as logger

Logger = logger.getDefaultLogger()

# ---------------------------------------------------------------------------
# 内部ユーティリティ
# ---------------------------------------------------------------------------

_DEFAULT_TIMEOUT = 3.0  # 接続タイムアウト（秒）
_PING_INTERVAL = 5.0  # リトライ間隔（秒）


def _normalize(url: str) -> str:
    return url.rstrip("/")


def _post(
    url: str, payload: dict | None = None, timeout: float = _DEFAULT_TIMEOUT
) -> bool:
    """POST を送り成功したら True。"""
    try:
        with httpx.Client(timeout=timeout) as c:
            r = c.post(url, json=payload or {})
        return r.status_code < 400
    except Exception:
        return False


def _get(url: str, timeout: float = _DEFAULT_TIMEOUT) -> httpx.Response | None:
    """GET を送り Response を返す。失敗したら None。"""
    try:
        with httpx.Client(timeout=timeout) as c:
            return c.get(url)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Ping / 死活確認
# ---------------------------------------------------------------------------


def ping(host: str) -> bool:
    """HTTP GET でサーバーが応答するか確認する。"""
    r = _get(_normalize(host) + "/")
    return r is not None and r.status_code < 500


def wait_ping(
    host: str,
    interval: float = _PING_INTERVAL,
    timeout: float = 0,  # 0 = 永久待機
    quiet: bool = False,
) -> bool:
    """ping が成功するまで待機する。timeout 秒で諦めたら False。"""
    deadline = time.time() + timeout if timeout > 0 else None
    while True:
        if ping(host):
            return True
        if deadline and time.time() >= deadline:
            return False
        if not quiet:
            Logger.info(f"[events] waiting for {host} ...")
        time.sleep(interval)


# ---------------------------------------------------------------------------
# スケジュール
# ---------------------------------------------------------------------------


def _parse_time(t: str) -> datetime:
    """'HH:MM' を今日の datetime に変換する。"""
    h, m = map(int, t.split(":"))
    now = datetime.now()
    return now.replace(hour=h, minute=m, second=0, microsecond=0)


def check_schedule(time_range: str) -> bool:
    """
    'HH:MM-HH:MM' 形式の時刻範囲内なら True を返す。
    終了時刻 < 開始時刻 の場合は日またぎ（例: '22:00-06:00'）を考慮する。
    """
    try:
        start_s, end_s = time_range.strip().split("-")
        start = _parse_time(start_s)
        end = _parse_time(end_s)
        now = datetime.now()
        if start <= end:
            return start <= now <= end
        # 日またぎ
        return now >= start or now <= end
    except Exception as e:
        Logger.warning(f"[events] check_schedule parse error: {e}")
        return True  # 解析失敗は通過させる


def wait_until(time_str: str) -> None:
    """
    指定時刻 ('HH:MM') まで分単位でスリープする。
    既に過ぎている場合は翌日の同時刻まで待つ。
    """
    target = _parse_time(time_str)
    now = datetime.now()
    if target <= now:
        target += timedelta(days=1)
    diff = (target - now).total_seconds()
    Logger.info(f"[events] waiting until {time_str} ({diff:.0f}s)")
    time.sleep(diff)


# ---------------------------------------------------------------------------
# サーバー種別の自動検出
# ---------------------------------------------------------------------------


def detect_server(
    host: str,
    comfyui_host: str = "",
    comfyui_port: int = 8188,
) -> str:
    """
    接続先のサーバー種別を検出して返す。
    戻り値: "a1111" | "forge" | "neo" | "comfyui" | "unknown"
    """
    h = _normalize(host)

    # Identify the requested host before probing a different ComfyUI port.
    r = _get(h + "/sdapi/v1/options")
    if r is not None and r.status_code == 200:
        settings = r.json()
        if "forge_additional_modules" in settings:
            kind = "neo" if any(key in settings for key in (
                "forge_checkpoint_anima", "forge_checkpoint_klein", "anima_do_reference")) else "forge"
        else:
            kind = "a1111"
        Logger.info(f"[events] detected {kind} at {h}")
        return kind
    r = _get(h + "/system_stats")
    if r is not None and r.status_code == 200:
        return "comfyui"

    # --- ComfyUI ---
    comfy_base = (
        _normalize(comfyui_host) if comfyui_host else f"http://localhost:{comfyui_port}"
    )
    r = _get(comfy_base + "/system_stats")
    if r is not None and r.status_code == 200:
        Logger.info(f"[events] detected comfyui at {comfy_base}")
        return "comfyui"

    # --- SD WebUI 系（A1111 / Forge）---
    r = _get(h + "/sdapi/v1/memory")
    if r is not None and r.status_code == 200:
        # Forge は /forge-api/v1/version を持つ
        r2 = _get(h + "/forge-api/v1/version")
        if r2 is not None and r2.status_code == 200:
            Logger.info(f"[events] detected forge at {h}")
            return "forge"
        Logger.info(f"[events] detected a1111 at {h}")
        return "a1111"

    Logger.warning(f"[events] server not detected at {host}")
    return "unknown"


# ---------------------------------------------------------------------------
# モデルアンロード
# ---------------------------------------------------------------------------


def unload_model(host: str, server_type: str = "") -> bool:
    """
    モデルを VRAM からアンロードする。
    - comfyui : POST /api/free  {"unload_models": true, "free_memory": true}
    - forge / a1111 / 未確定 : POST /sdapi/v1/unload-checkpoint
    """
    h = _normalize(host)
    stype = (server_type or "").lower()

    if stype == "comfyui":
        url = h + "/api/free"
        payload = {"unload_models": True, "free_memory": True}
        ok = _post(url, payload)
        Logger.info(f"[events] unload_model (comfyui) -> {ok}")
        return ok
    else:
        # forge / a1111 — ボディなし POST
        url = h + "/sdapi/v1/unload-checkpoint"
        ok = _post(url, {})
        Logger.info(f"[events] unload_model (sdapi) -> {ok}")
        return ok


# ---------------------------------------------------------------------------
# ファイルシステム監視
# ---------------------------------------------------------------------------


def watch_files(
    path: str,
    pattern: str = "*",
    callback: Callable[[str], None] | None = None,
    interval: float = 2.0,
    timeout: float = 0,
) -> list[str]:
    """
    path 内に pattern に一致するファイルが到着するまで polling で待機し、
    到着したファイルパスのリストを返す。
    callback が指定されていればファイルごとに呼ぶ（ブロッキング）。
    timeout=0 は永久待機。watchdog がインストールされていれば inotify を使う。
    """
    try:
        return _watch_files_watchdog(path, pattern, callback, interval, timeout)
    except ImportError:
        return _watch_files_polling(path, pattern, callback, interval, timeout)


def _watch_files_polling(
    path: str,
    pattern: str,
    callback: Callable[[str], None] | None,
    interval: float,
    timeout: float,
) -> list[str]:
    seen: set[str] = (
        set(f for f in os.listdir(path) if fnmatch.fnmatch(f, pattern))
        if os.path.isdir(path)
        else set()
    )
    deadline = time.time() + timeout if timeout > 0 else None
    found: list[str] = []

    while True:
        if os.path.isdir(path):
            current = set(f for f in os.listdir(path) if fnmatch.fnmatch(f, pattern))
            new_files = current - seen
            for f in sorted(new_files):
                full = os.path.join(path, f)
                found.append(full)
                Logger.info(f"[events] watch_files: new file {full}")
                if callback:
                    callback(full)
            seen = current
        if found:
            return found
        if deadline and time.time() >= deadline:
            return found
        time.sleep(interval)


def _watch_files_watchdog(
    path: str,
    pattern: str,
    callback: Callable[[str], None] | None,
    interval: float,
    timeout: float,
) -> list[str]:
    """watchdog ライブラリ使用版（ImportError をそのまま伝播させる）。"""
    from watchdog.events import FileSystemEventHandler  # type: ignore
    from watchdog.observers import Observer  # type: ignore

    found: list[str] = []

    class _Handler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            f = os.path.basename(event.src_path)
            if fnmatch.fnmatch(f, pattern):
                found.append(event.src_path)
                Logger.info(f"[events] watch_files (watchdog): {event.src_path}")
                if callback:
                    callback(event.src_path)

    obs = Observer()
    obs.schedule(_Handler(), path, recursive=False)
    obs.start()
    deadline = time.time() + timeout if timeout > 0 else None
    try:
        while not found:
            if deadline and time.time() >= deadline:
                break
            time.sleep(interval)
    finally:
        obs.stop()
        obs.join()
    return found
