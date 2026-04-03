import os
import argparse
import time
from typing import Set, Tuple

from adb_utils import connect, wait_for_device, start_app, force_stop, tap, swipe, get_window_size, ui_dump, adb, back
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
    # На разных экранах/версиях может быть "Extend", "Extend 1h", и т.п.
    return t == "extend" or d == "extend" or t.startswith("extend") or d.startswith("extend")


def _contains_any(value: str, needles: list[str]) -> bool:
    value = (value or "").strip().lower()
    return any(n in value for n in needles)


def _find_action_node(nodes: list[UINode], labels: list[str]) -> UINode | None:
    for n in nodes:
        text = (n.text or "").strip().lower()
        desc = (n.content_desc or "").strip().lower()
        if text in labels or desc in labels:
            return n
    return None


def recover_if_system_dialog(device: str) -> bool:
    """
    Обрабатывает системные окна типа "System UI keeps stopping".
    Возвращает True, если было вмешательство и выполнен recovery.
    """
    xml = ui_dump(device)
    nodes = parse_nodes(xml)
    crash_needles = [
        "keeps stopping",
        "isn't responding",
        "is not responding",
        "not responding",
        "app isn't responding",
        "не отвечает",
        "перестало работать",
    ]
    has_crash_dialog = any(
        _contains_any(n.text, crash_needles)
        or _contains_any(n.content_desc, crash_needles)
        for n in nodes
    )
    if not has_crash_dialog:
        return False

    print("[WARN] System crash dialog detected. Trying to recover.")
    close_labels = ["close app", "force close", "ок", "ok", "закрыть приложение", "закрыть"]
    wait_labels = ["wait", "подождать", "wait for app", "подождать ответ"]

    node = _find_action_node(nodes, close_labels) or _find_action_node(nodes, wait_labels)
    if node is not None:
        x, y = node.center()
        if x > 0 and y > 0:
            print(f"[INFO] Tap dialog action at ({x},{y})")
            tap(device, x, y)
            time.sleep(1.0)
    else:
        # Если кнопку не нашли в дампе, пробуем просто Back как fallback.
        back(device)
        time.sleep(1.0)

    # Перезапускаем Smule и возвращаемся в рабочий экран.
    safe_force_stop(device)
    time.sleep(0.8)
    start_app(device, PACKAGE)
    time.sleep(2.0)
    navigate_to_profile(device)
    return True


def recover_if_smule_overlay(device: str) -> bool:
    """
    Обрабатывает внутренние экраны Smule, которые перекрывают список:
    например "What to sing next?" / "Let's sing" / "Later".
    """
    xml = ui_dump(device)
    nodes = parse_nodes(xml)
    overlay_needles = [
        "what to sing next",
        "let's sing",
        "lets sing",
        "pick a song from our tuned playlist",
        "later",
        "спеть позже",
    ]
    has_overlay = any(
        _contains_any(n.text, overlay_needles) or _contains_any(n.content_desc, overlay_needles)
        for n in nodes
    )
    if not has_overlay:
        return False

    print("[WARN] Smule overlay detected. Closing it.")
    dismiss_labels = ["later", "not now", "skip", "close", "спеть позже", "позже", "закрыть"]
    node = _find_action_node(nodes, dismiss_labels)
    if node is not None:
        x, y = node.center()
        if x > 0 and y > 0:
            tap(device, x, y)
            time.sleep(0.8)
            return True

    # Если в дампе нет явной кнопки, пробуем Back.
    back(device)
    time.sleep(0.8)
    return True


def _looks_like_back_button(node: UINode) -> bool:
    d = (node.content_desc or "").strip().lower()
    t = (node.text or "").strip().lower()
    # Частые варианты у тулбара Android/Compose
    return any(k in d for k in ["navigate up", "up", "back"]) or t in ["back", "назад"]


def _is_profile_screen(nodes: list[UINode]) -> bool:
    # Ищем любые признаки вкладки Profile (текст/desc/resource-id).
    # Это защита от ложных срабатываний на Back в "нормальном" списке.
    if find_by_text_or_desc(nodes, "Profile"):
        return True
    return any("profile" in (n.resource_id or "").lower() or "profile" in (n.content_desc or "").lower() for n in nodes)


def ensure_not_stuck_in_details(device: str, max_back: int = 3) -> None:
    """
    Если вместо списка песен открылся другой экран, часто появляется back/up кнопка.
    В таком случае делаем несколько Back и возвращаемся в Profile.
    """
    for _ in range(max_back):
        if recover_if_system_dialog(device):
            return
        if recover_if_smule_overlay(device):
            return
        xml = ui_dump(device)
        nodes = parse_nodes(xml)
        # Если видим кнопки Extend — скорее всего мы на правильном списке.
        extends = [n for n in nodes if n.resource_id == EXTEND_RESOURCE_ID and _is_extend_text(n)]
        if extends:
            return
        # Если мы уже в профиле (пусть Extend сейчас не в видимой области),
        # НЕ жмём Back, иначе можно уехать на "главную".
        if _is_profile_screen(nodes):
            return
        back_buttons = [n for n in nodes if _looks_like_back_button(n)]
        if not back_buttons:
            return
        print("[WARN] Looks like details screen. Returning to Profile.")
        # Более безопасно: вместо одиночного Back возвращаемся через вкладку Profile.
        navigate_to_profile(device)
        time.sleep(0.8)
    # Финальная попытка перепрыгнуть на Profile (на случай если back не помог).
    try:
        navigate_to_profile(device)
    except Exception:
        pass


def click_extends_on_screen(device: str, max_clicks: int = 12, post_click_delay_sec: float = 0.35) -> int:
    """
    Кликаем Extend по одному и после каждого клика обновляем UI-дамп,
    чтобы не нажимать по устаревшим координатам.
    """
    clicked = 0
    seen_bounds: set[str] = set()
    while clicked < max_clicks:
        if recover_if_system_dialog(device):
            continue
        if recover_if_smule_overlay(device):
            continue
        ensure_not_stuck_in_details(device)
        xml = ui_dump(device)
        nodes = parse_nodes(xml)
        extends = [
            n
            for n in nodes
            if n.resource_id == EXTEND_RESOURCE_ID
            and _is_extend_text(n)
            and n.enabled
            and n.visible_to_user
        ]
        # Уберём те, по которым уже пытались нажать на этом экране
        extends = [n for n in extends if n.bounds not in seen_bounds]
        if not extends:
            break
        # Жмём снизу вверх: меньше шанс что список "поедет" и мы промахнёмся
        extends.sort(key=lambda n: n.center()[1], reverse=True)
        node = extends[0]
        x, y = node.center()
        if x <= 0 or y <= 0:
            seen_bounds.add(node.bounds)
            continue
        print(f"[INFO] Click Extend at ({x},{y})")
        tap(device, x, y)
        clicked += 1
        seen_bounds.add(node.bounds)
        time.sleep(post_click_delay_sec)
    return clicked


def infinite_scroll_and_click_extends(
    device: str,
    max_idle_iters: int = 5,
    max_swipes: int = 250,
    swipe_duration_ms: int = 300,
    post_swipe_delay_sec: float = 0.25,
    post_click_delay_sec: float = 0.35,
    start_y_frac: float = 0.90,
    end_y_frac: float = 0.15,
) -> None:
    w, h = get_window_size(device)
    # Уменьшаем дистанцию свайпа, чтобы не "пролистывать" целую карточку одним движением.
    start_y = int(h * start_y_frac)
    end_y = int(h * end_y_frac)

    last_hashes: list[str] = []
    idle = 0
    swipes = 0

    while True:
        if recover_if_system_dialog(device):
            continue
        if recover_if_smule_overlay(device):
            continue
        clicked = click_extends_on_screen(device, post_click_delay_sec=post_click_delay_sec)
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
        if swipes >= max_swipes:
            print("[WARN] Reached max swipes. Finishing to avoid endless loop.")
            break
        print(f"[INFO] Swipe from ({int(w*0.5)},{start_y}) to ({int(w*0.5)},{end_y})")
        swipe(device, int(w * 0.5), start_y, int(w * 0.5), end_y, duration_ms=swipe_duration_ms)
        swipes += 1
        time.sleep(post_swipe_delay_sec)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smule extender via ADB")
    parser.add_argument("--device", "-d", default=os.getenv("ADB_DEVICE", "192.168.2.105:5555"), help="ADB device address, e.g. 192.168.2.105:5555")
    parser.add_argument("--swipe-duration-ms", type=int, default=220, help="Duration of swipe in ms (smaller = faster)")
    parser.add_argument("--post-swipe-delay-sec", type=float, default=0.14, help="Delay after swipe in seconds")
    parser.add_argument("--post-click-delay-sec", type=float, default=0.26, help="Delay after tapping Extend in seconds")
    # Чем меньше расстояние (start_y_frac - end_y_frac), тем "мельче" шаг и меньше шанс перепрыгнуть карточки.
    parser.add_argument("--start-y-frac", type=float, default=0.86, help="Swipe start Y as fraction of height (smaller = shorter swipe)")
    parser.add_argument("--end-y-frac", type=float, default=0.33, help="Swipe end Y as fraction of height (bigger = shorter swipe)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    device = args.device
    print(f"[INFO] Using device: {device}")
    try:
        connect(device)
        wait_for_device(device, timeout_sec=30)
        start_app(device, PACKAGE)
        recover_if_system_dialog(device)
        recover_if_smule_overlay(device)
        navigate_to_profile(device)
        infinite_scroll_and_click_extends(
            device,
            swipe_duration_ms=args.swipe_duration_ms,
            post_swipe_delay_sec=args.post_swipe_delay_sec,
            post_click_delay_sec=args.post_click_delay_sec,
            start_y_frac=args.start_y_frac,
            end_y_frac=args.end_y_frac,
        )
    except KeyboardInterrupt:
        print("[INFO] Interrupted by user")
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        print("[INFO] Force-stopping app")
        safe_force_stop(device)


if __name__ == "__main__":
    main()
