"""Read-only Codex app-server client. Never reads/copies authentication tokens."""
import json
import math
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path


class UsageError(Exception):
    pass


def launch_codex(executable, flags):
    """Keep the packaged Qt/Python DLL search path out of the external Codex process."""
    environment = os.environ.copy()
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        bundle = Path(bundled).resolve()
        environment["PATH"] = os.pathsep.join(p for p in environment.get("PATH", "").split(os.pathsep)
            if p and not Path(p).resolve().is_relative_to(bundle))
        for key in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH"):
            environment.pop(key, None)
    restore = None
    if bundled and sys.platform == "win32":
        import ctypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
        kernel.SetDllDirectoryW.restype = ctypes.c_int
        kernel.GetDllDirectoryW.argtypes = [ctypes.c_uint, ctypes.c_wchar_p]
        kernel.GetDllDirectoryW.restype = ctypes.c_uint
        buf = ctypes.create_unicode_buffer(32768)
        kernel.GetDllDirectoryW(len(buf), buf)
        restore = (kernel, buf.value)
        if not kernel.SetDllDirectoryW(None):
            raise OSError("Unable to prepare external process DLL search path")
    try:
        return subprocess.Popen([executable, "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace", creationflags=flags, env=environment)
    finally:
        if restore:
            restore[0].SetDllDirectoryW(restore[1] or None)


@dataclass(frozen=True)
class WindowUsage:
    used: float | None
    duration: int | None
    resets_at: int | None

    @property
    def remaining(self):
        return None if self.used is None else max(0.0, min(100.0, 100.0 - self.used))


@dataclass(frozen=True)
class BucketUsage:
    id: str
    name: str
    windows: tuple[WindowUsage, ...]

    def window(self, minutes: int):
        return next((w for w in self.windows if w.duration == minutes), None)


@dataclass(frozen=True)
class UsageSnapshot:
    fetched_at: float
    buckets: tuple[BucketUsage, ...]

    def to_dict(self):
        return asdict(self)


def finite_number(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def parse_limits(result: dict, now: float | None = None) -> UsageSnapshot:
    if not isinstance(result, dict):
        raise UsageError("额度服务返回了无法识别的数据")
    mapping = result.get("rateLimitsByLimitId")
    if not isinstance(mapping, dict) or not mapping:
        legacy = result.get("rateLimits")
        mapping = {str(legacy.get("limitId") or "codex"): legacy} if isinstance(legacy, dict) else {}
    buckets = []
    for key, value in mapping.items():
        if not isinstance(value, dict):
            continue
        windows = []
        for slot in ("primary", "secondary"):
            raw = value.get(slot)
            if not isinstance(raw, dict):
                continue
            used = finite_number(raw.get("usedPercent"))
            duration = finite_number(raw.get("windowDurationMins"))
            reset = finite_number(raw.get("resetsAt"))
            windows.append(WindowUsage(
                None if used is None else max(0.0, min(100.0, used)),
                int(duration) if duration is not None and duration > 0 else None,
                int(reset) if reset is not None and reset > 0 else None,
            ))
        name = value.get("limitName")
        buckets.append(BucketUsage(str(key), str(name or key), tuple(windows)))
    if not buckets:
        raise UsageError("当前登录方式或账户未提供额度窗口")
    return UsageSnapshot(time.time() if now is None else now, tuple(buckets))


def snapshot_from_cache(data: dict) -> UsageSnapshot:
    timestamp = finite_number(data.get("fetched_at"))
    if timestamp is None or timestamp > time.time() + 60:
        raise ValueError("Invalid cache time")
    mapping = {}
    for b in data["buckets"]:
        value = {"limitName": b["name"]}
        for slot, w in zip(("primary", "secondary"), b["windows"]):
            value[slot] = {"usedPercent": w["used"], "windowDurationMins": w["duration"], "resetsAt": w["resets_at"]}
        mapping[b["id"]] = value
    return parse_limits({"rateLimitsByLimitId": mapping}, timestamp)


def find_codex(configured="") -> str:
    if configured:
        p = Path(configured)
        if p.is_file() and p.suffix.lower() == ".exe":
            return str(p)
        raise UsageError("配置的 Codex 程序不存在，请检查设置")
    candidate = shutil.which("codex.exe") or shutil.which("codex")
    if candidate and Path(candidate).suffix.lower() == ".exe":
        return candidate
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
    candidates = list(root.glob("*/codex.exe")) if root.is_dir() else []
    if candidates:
        return str(max(candidates, key=lambda p: p.stat().st_mtime))
    raise UsageError("未找到 Codex，请先安装并登录 Codex 桌面应用")


def read_usage(configured="", timeout=25, cancel: threading.Event | None = None) -> UsageSnapshot:
    executable = find_codex(configured)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    proc = launch_codex(executable, flags)
    messages = queue.Queue()

    def consume():
        try:
            for line in proc.stdout:
                try:
                    item = json.loads(line)
                    if isinstance(item, dict):
                        messages.put(item)
                except ValueError:
                    continue
        finally:
            messages.put(None)

    reader = threading.Thread(target=consume, daemon=True, name="CodexQuotaPipe")
    reader.start()
    deadline = time.monotonic() + timeout

    def send(message):
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def receive(request_id):
        while time.monotonic() < deadline:
            if cancel is not None and cancel.is_set():
                raise UsageError("查询已取消")
            try:
                response = messages.get(timeout=min(0.2, max(0.01, deadline - time.monotonic())))
            except queue.Empty:
                continue
            if response is None:
                raise UsageError("Codex 额度服务已退出，请检查登录状态")
            if response.get("id") == request_id:
                if "error" in response:
                    # Upstream errors may contain account details; keep the UI and log generic.
                    raise UsageError("额度读取失败，请确认 Codex 已登录且网络正常")
                return response.get("result")
            if "method" in response and "id" in response:
                send({"id": response["id"], "error": {"code": -32601, "message": "Unsupported client method"}})
        raise UsageError("额度查询超时；稍后会自动重试")

    try:
        send({"method": "initialize", "id": 1, "params": {
            "clientInfo": {"name": "desktop_pet", "title": "DesktopPet", "version": "0.1.0"}}})
        receive(1)
        send({"method": "initialized", "params": {}})
        send({"method": "account/rateLimits/read", "id": 2})
        return parse_limits(receive(2))
    except (OSError, BrokenPipeError) as exc:
        raise UsageError("无法连接本机 Codex 额度服务") from exc
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
        reader.join(timeout=2)
        proc.stdin.close()
        proc.stdout.close()
