import os
import argparse
from typing import Set, Tuple

from adb_utils import connect, wait_for_device, start_app, force_stop, tap, swipe, get_window_size, ui_dump, adb
from ui_parser import parse_nodes, find_by_text_or_desc, find_by_resource_id, dump_hash, UINode

PACKAGE = "com.smule.singandroid"
EXTEND_RESOURCE_ID = "com.smule.singandroid:id/btn_cta_active"


def safe_force_stop(device: str):
    try:
        force_stop(device, PACKAGE)
    except Exception as e:
        print(f"[WARN] Force-stop failed: {e}")


def navigate_to_profile(device: str, max_attempts: int = 8) -> None:
    attempts = 0
    while attempts < max_attempts:
        xml = ui_dump(device)
        nodes = parse_nodes(xml)
        candidates = find_by_text_or_desc(nodes, "Profile")
        if not candidates:
            candidates = [n for n in nodes if "profile" in n.resource_id.lower()]
        if candidates:
            x, y = candidates[0].center()
            if x > 0 and y > 0:
                print(f"[INFO] Tapping Profile at ({x},{y})")
                tap(device, x, y)
                return
        w, h = get_window_size(device)
        print(f"[INFO] Profile not found. Tapping bottom nav fallback")
        tap(device, int(w * 0.9), int(h * 0.94))
        attempts += 1
    raise RuntimeError("Не удалось перейти на вкладку Profile")


def _is_extend_text(node: UINode) -> bool:
    t = (node.text or "").strip().lower()
    d = (node.content_desc or "").strip().lower()
    return t == "extend" or d == "extend"


def click_all_extends_on_screen(device: str) -> int:
    xml = ui_dump(device)
    nodes = parse_nodes(xml)
    extends = [n for n in nodes if n.resource_id == EXTEND_RESOURCE_ID and _is_extend_text(n)]
    if not extends:
        return 0
    clicked = 0
    for node in extends:
        x, y = node.center()
        if x <= 0 or y <= 0:
            continue
        print(f"[INFO] Click Extend at ({x},{y})")
        tap(device, x, y)
        clicked += 1
    return clicked


def infinite_scroll_and_click_extends(device: str, max_idle_iters: int = 3) -> None:
    w, h = get_window_size(device)
    start_y = int(h * 0.90)
    end_y = int(h * 0.15)

    last_hashes: list[str] = []
    idle = 0

    while True:
        clicked = click_all_extends_on_screen(device)
        xml = ui_dump(device)
        hsh = dump_hash(xml)
        if last_hashes and hsh == last_hashes[-1] and clicked == 0:
            idle += 1
        else:
            idle = 0
        last_hashes.append(hsh)
        if len(last_hashes) > 5:
            last_hashes.pop(0)
        if idle >= max_idle_iters:
            print("[INFO] Reached stable UI state. Finishing.")
            break
        print(f"[INFO] Swipe from ({int(w*0.5)},{start_y}) to ({int(w*0.5)},{end_y})")
        swipe(device, int(w * 0.5), start_y, int(w * 0.5), end_y, duration_ms=500)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smule extender via ADB")
    parser.add_argument("--device", "-d", default=os.getenv("ADB_DEVICE", "192.168.2.105:5555"), help="ADB device address, e.g. 192.168.2.105:5555")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    device = args.device
    print(f"[INFO] Using device: {device}")
    try:
        connect(device)
        wait_for_device(device, timeout_sec=30)
        start_app(device, PACKAGE)
        navigate_to_profile(device)
        infinite_scroll_and_click_extends(device)
    except KeyboardInterrupt:
        print("[INFO] Interrupted by user")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        print("[INFO] Force-stopping app")
        safe_force_stop(device)


if __name__ == "__main__":
    main()
