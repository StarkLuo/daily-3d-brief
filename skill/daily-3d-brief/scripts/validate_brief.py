#!/usr/bin/env python3
"""Validate a generated daily-3d-brief HTML file before state is updated."""

from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path


class BriefParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.page_count = 0
        self.images: list[str] = []
        self.items: list[dict[str, str]] = []
        self.has_title = False
        self.lang = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "html":
            self.lang = values.get("lang", "")
        if tag == "title":
            self.has_title = True
        if "page" in values.get("class", "").split():
            self.page_count += 1
        if tag == "img":
            self.images.append(values.get("src", ""))
        if values.get("data-item-key"):
            self.items.append({
                "key": values["data-item-key"].strip(),
                "title": values.get("data-item-title", "").strip(),
                "type": values.get("data-item-type", "").strip(),
                "url": values.get("data-item-url", "").strip(),
            })


def validate(report: Path, state_path: Path | None) -> list[str]:
    errors: list[str] = []
    if not report.is_file():
        return [f"Report does not exist: {report}"]
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.html", report.name):
        errors.append("Report filename must be YYYY-MM-DD.html")

    text = report.read_text(encoding="utf-8")
    parser = BriefParser()
    parser.feed(text)

    if parser.lang != "zh-CN":
        errors.append('Root html element must use lang="zh-CN"')
    if not parser.has_title:
        errors.append("Missing title element")
    if parser.page_count not in {2, 3}:
        errors.append(f"Expected 2 or 3 page sections, found {parser.page_count}")
    if "@media print" not in text or "@page" not in text:
        errors.append("Missing print CSS")
    if "{{" in text or "}}" in text or ("[" + "TO" + "DO") in text:
        errors.append("Unresolved template marker found")

    for src in parser.images:
        if not src:
            errors.append("Image with empty src")
            continue
        if src.startswith(("http://", "https://", "//", "data:")):
            errors.append(f"Image must be a local relative file: {src}")
            continue
        image_path = (report.parent / src).resolve()
        try:
            image_path.relative_to(report.parent.resolve())
        except ValueError:
            errors.append(f"Image escapes report directory: {src}")
            continue
        if not image_path.is_file():
            errors.append(f"Missing image: {src}")

    keys: set[str] = set()
    allowed_types = {"academic", "industry", "event"}
    for item in parser.items:
        if item["key"] in keys:
            errors.append(f"Duplicate data-item-key: {item['key']}")
        keys.add(item["key"])
        if not item["title"]:
            errors.append(f"Missing data-item-title for {item['key']}")
        if item["type"] not in allowed_types:
            errors.append(f"Invalid data-item-type for {item['key']}: {item['type']!r}")
        if not item["url"].startswith("https://"):
            errors.append(f"data-item-url must be HTTPS for {item['key']}")

    if state_path:
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"Cannot read state file: {exc}")
        else:
            if state.get("version") != 1 or not isinstance(state.get("items"), dict):
                errors.append("Invalid or unsupported state file")
            else:
                duplicates = sorted(keys.intersection(state["items"]))
                if duplicates:
                    errors.append("Report contains previously seen items: " + ", ".join(duplicates))

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--state", type=Path)
    args = parser.parse_args()
    errors = validate(args.report, args.state)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
