#!/usr/bin/env python3
"""Manage the durable deduplication state for daily-3d-brief."""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


SUPPORTED_VERSION = 1
ALLOWED_TYPES = {"academic", "industry", "event"}


def empty_state() -> dict:
    return {"version": SUPPORTED_VERSION, "updated_at": None, "items": {}, "runs": []}


def load_state(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"State file does not exist: {path}")
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if state.get("version") != SUPPORTED_VERSION:
        raise ValueError(f"Unsupported state version: {state.get('version')!r}")
    if not isinstance(state.get("items"), dict) or not isinstance(state.get("runs"), list):
        raise ValueError("State must contain an items object and a runs array")
    return state


def atomic_write(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(data)
        temp_name = handle.name
    os.replace(temp_name, path)


class ItemParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        key = values.get("data-item-key")
        if not key:
            return
        item = {
            "key": key.strip(),
            "title": values.get("data-item-title", "").strip(),
            "type": values.get("data-item-type", "").strip(),
            "url": values.get("data-item-url", "").strip(),
        }
        self.items.append(item)


def parse_report(path: Path) -> list[dict[str, str]]:
    parser = ItemParser()
    parser.feed(path.read_text(encoding="utf-8"))
    seen: set[str] = set()
    for item in parser.items:
        if not item["title"]:
            raise ValueError(f"Missing data-item-title for {item['key']!r}")
        if item["type"] not in ALLOWED_TYPES:
            raise ValueError(f"Invalid data-item-type for {item['key']!r}: {item['type']!r}")
        if not item["url"]:
            raise ValueError(f"Missing data-item-url for {item['key']!r}")
        if item["key"] in seen:
            raise ValueError(f"Duplicate data-item-key in report: {item['key']}")
        seen.add(item["key"])
    return parser.items


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), parts.query, ""))


def parse_markdown_history(path: Path) -> list[dict[str, str]]:
    link_pattern = re.compile(r"\[([^\]]+)\]\((https://[^)]+)\)")
    arxiv_pattern = re.compile(r"^https://arxiv\.org/abs/(\d{4}\.\d{4,5})(?:v\d+)?$")
    items: list[dict[str, str]] = []
    in_industry = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            in_industry = "产业" in line or "产品" in line or "应用动态" in line
        for title, raw_url in link_pattern.findall(line):
            url = normalize_url(raw_url)
            arxiv_match = arxiv_pattern.match(url)
            if arxiv_match:
                items.append({
                    "key": f"arxiv:{arxiv_match.group(1)}",
                    "title": title.strip(" *`"),
                    "type": "academic",
                    "url": url,
                })
            elif in_industry:
                items.append({
                    "key": f"industry:{url}",
                    "title": title.strip(" *`"),
                    "type": "industry",
                    "url": url,
                })
    unique: dict[str, dict[str, str]] = {}
    for item in items:
        unique.setdefault(item["key"], item)
    return list(unique.values())


def command_init(path: Path) -> None:
    if path.exists():
        load_state(path)
        print(f"State already exists and is valid: {path}")
        return
    atomic_write(path, empty_state())
    print(f"Initialized state: {path}")


def command_has(path: Path, key: str) -> int:
    state = load_state(path)
    present = key in state["items"]
    print("yes" if present else "no")
    return 0 if present else 1


def command_list(path: Path) -> None:
    state = load_state(path)
    for key, item in sorted(state["items"].items()):
        print(f"{key}\t{item.get('first_seen', '')}\t{item.get('title', '')}")


def command_sync(path: Path, report: Path, date: str) -> None:
    datetime.strptime(date, "%Y-%m-%d")
    state = load_state(path)
    items = parse_report(report)
    for item in items:
        existing = state["items"].get(item["key"])
        if existing and existing.get("title") != item["title"]:
            raise ValueError(
                f"Key {item['key']!r} already belongs to {existing.get('title')!r}, "
                f"not {item['title']!r}"
            )
        if existing:
            existing["last_seen"] = date
            existing["url"] = item["url"]
        else:
            state["items"][item["key"]] = {
                "title": item["title"],
                "type": item["type"],
                "first_seen": date,
                "last_seen": date,
                "url": item["url"],
            }

    run = {"date": date, "output": report.name, "item_keys": [item["key"] for item in items]}
    state["runs"] = [entry for entry in state["runs"] if entry.get("date") != date]
    state["runs"].append(run)
    state["runs"].sort(key=lambda entry: entry.get("date", ""))
    state["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    atomic_write(path, state)
    print(f"Synced {len(items)} items from {report} into {path}")


def command_import_history(path: Path, project: Path) -> None:
    state = load_state(path)
    reports = sorted(project.glob("20??-??-??.md")) + sorted(project.glob("20??-??-??.html"))
    imported = 0
    for report in reports:
        date = report.name[:10]
        datetime.strptime(date, "%Y-%m-%d")
        items = parse_report(report) if report.suffix == ".html" else parse_markdown_history(report)
        run_keys: list[str] = []
        for item in items:
            run_keys.append(item["key"])
            existing = state["items"].get(item["key"])
            if existing:
                existing["last_seen"] = max(existing.get("last_seen", date), date)
                existing["url"] = item["url"]
                continue
            state["items"][item["key"]] = {
                "title": item["title"],
                "type": item["type"],
                "first_seen": date,
                "last_seen": date,
                "url": item["url"],
            }
            imported += 1
        state["runs"] = [entry for entry in state["runs"] if entry.get("date") != date]
        state["runs"].append({"date": date, "output": report.name, "item_keys": run_keys})
    state["runs"].sort(key=lambda entry: entry.get("date", ""))
    state["updated_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    atomic_write(path, state)
    print(f"Imported {imported} unique items from {len(reports)} historical reports")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("state", type=Path)

    has_parser = subparsers.add_parser("has")
    has_parser.add_argument("state", type=Path)
    has_parser.add_argument("key")

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("state", type=Path)

    sync_parser = subparsers.add_parser("sync-report")
    sync_parser.add_argument("state", type=Path)
    sync_parser.add_argument("report", type=Path)
    sync_parser.add_argument("--date", required=True)

    import_parser = subparsers.add_parser("import-history")
    import_parser.add_argument("state", type=Path)
    import_parser.add_argument("project", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "init":
        command_init(args.state)
        return 0
    if args.command == "has":
        return command_has(args.state, args.key)
    if args.command == "list":
        command_list(args.state)
        return 0
    if args.command == "sync-report":
        command_sync(args.state, args.report, args.date)
        return 0
    if args.command == "import-history":
        command_import_history(args.state, args.project)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
