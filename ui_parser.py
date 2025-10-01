from __future__ import annotations
import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


@dataclass
class UINode:
    text: str
    resource_id: str
    content_desc: str
    bounds: str
    clickable: bool = False
    enabled: bool = True
    class_name: str = ""
    visible_to_user: bool = True

    def center(self) -> Tuple[int, int]:
        # bounds format: [x1,y1][x2,y2]
        m = re.findall(r"\[(\d+),(\d+)\]", self.bounds)
        if len(m) == 2:
            (x1, y1), (x2, y2) = [(int(a), int(b)) for a, b in m]
            return (x1 + x2) // 2, (y1 + y2) // 2
        return 0, 0


def _sanitize_xml(xml_text: str) -> str:
    # В дампе может быть служебный текст до/после XML. Обрежем строго по <hierarchy>...</hierarchy>
    start = xml_text.find("<hierarchy")
    end = xml_text.rfind("</hierarchy>")
    if start != -1 and end != -1:
        return xml_text[start : end + len("</hierarchy>")]
    # Если нет <hierarchy>, попробуем с начала декларации XML
    start2 = xml_text.find("<?xml")
    if start2 != -1:
        # Обрезаем всё после последнего ">" если нет закрывающего тега (лучше чем ничего)
        last_angle = xml_text.rfind(">")
        if last_angle != -1 and last_angle > start2:
            return xml_text[start2 : last_angle + 1]
        return xml_text[start2:]
    return xml_text


def parse_nodes(xml_text: str) -> List[UINode]:
    xml_text = _sanitize_xml(xml_text)
    try:
        tree = ET.fromstring(xml_text)
    except ET.ParseError:
        cleaned = _sanitize_xml(xml_text.replace("\x00", "").strip())
        tree = ET.fromstring(cleaned)
    nodes: List[UINode] = []
    for el in tree.iter():
        if el.tag.endswith("node"):
            nodes.append(
                UINode(
                    text=el.attrib.get("text", ""),
                    resource_id=el.attrib.get("resource-id", ""),
                    content_desc=el.attrib.get("content-desc", ""),
                    bounds=el.attrib.get("bounds", "[0,0][0,0]"),
                    clickable=(el.attrib.get("clickable", "false").lower() == "true"),
                    enabled=(el.attrib.get("enabled", "true").lower() == "true"),
                    class_name=el.attrib.get("class", ""),
                    visible_to_user=(el.attrib.get("visible-to-user", "true").lower() == "true"),
                )
            )
    return nodes


def find_by_text_or_desc(nodes: Iterable[UINode], needle: str) -> List[UINode]:
    needle_low = needle.lower()
    return [n for n in nodes if needle_low in n.text.lower() or needle_low in n.content_desc.lower()]


def find_by_resource_id(nodes: Iterable[UINode], resource_id: str) -> List[UINode]:
    return [n for n in nodes if n.resource_id == resource_id]


def dump_hash(xml_text: str) -> str:
    return hashlib.sha1(xml_text.encode("utf-8")).hexdigest()
