import subprocess
import time
from typing import Tuple


def run(cmd: list[str], timeout: int | None = 30) -> str:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False, text=True)
    return result.stdout.strip()


def adb(device: str, *args: str, timeout: int | None = 30) -> str:
    return run(["adb", "-s", device, *args], timeout=timeout)


def adb_no_dev(*args: str, timeout: int | None = 30) -> str:
    return run(["adb", *args], timeout=timeout)


def connect(device: str) -> None:
    # Ensure TCPIP mode and connect
    adb_no_dev("tcpip", "5555")
    out = adb_no_dev("connect", device)
    if "connected to" not in out and "already connected to" not in out:
        raise RuntimeError(f"ADB connect failed: {out}")


def wait_for_device(device: str, timeout_sec: int = 60) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        out = adb_no_dev("devices")
        if device in out and "device" in out.split(device)[-1]:
            return
        time.sleep(1)
    raise TimeoutError("Device not ready")


def start_app(device: str, package: str) -> None:
    # Try launching via monkey for reliability
    adb(device, "shell", "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1")


def force_stop(device: str, package: str) -> None:
    adb(device, "shell", "am", "force-stop", package)


def tap(device: str, x: int, y: int) -> None:
    adb(device, "shell", "input", "tap", str(x), str(y))


def swipe(device: str, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 400) -> None:
    adb(device, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration_ms))


def get_window_size(device: str) -> Tuple[int, int]:
    out = adb(device, "shell", "wm", "size")
    # Example: Physical size: 1080x2400
    for line in out.splitlines():
        if ":" in line and "x" in line:
            _, value = line.split(":", 1)
            value = value.strip()
            if "x" in value:
                w_str, h_str = value.split("x", 1)
                return int(w_str), int(h_str)
    # Fallback via dumpsys display
    out = adb(device, "shell", "dumpsys", "display")
    for line in out.splitlines():
        if "mStableSize=" in line and "x" in line:
            value = line.split("mStableSize=")[-1].split()[0]
            w_str, h_str = value.split("x", 1)
            return int(w_str), int(h_str)
    return 1080, 1920


def ui_dump(device: str) -> str:
    # Use exec-out if available, else fallback via /sdcard
    out = adb(device, "exec-out", "uiautomator", "dump", "--compressed", "/dev/tty")
    if not out.strip().startswith("<?xml"):
        # Fallback
        adb(device, "shell", "uiautomator", "dump", "--compressed", "/sdcard/uidump.xml")
        xml = adb(device, "shell", "cat", "/sdcard/uidump.xml")
        return xml
    return out
