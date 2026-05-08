#!/usr/bin/env python3
"""Lightweight repository validation for the static project page."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    "README.md",
    "index.html",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "docs/ARCHITECTURE.md",
    "docs/ROADMAP.md",
    "docs/GRANT_SCOPE.md",
]
SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"[0-9]{8,10}:[A-Za-z0-9_-]{35}"),  # Telegram bot token shape
    re.compile(r"(?i)(api[_-]?key|secret|password|private[_-]?key|bot[_-]?token)\s*=\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"),
]


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, dict[str, str]]] = []
        self.elements: list[tuple[str, dict[str, str]]] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key: value or "" for key, value in attrs}
        self.elements.append((tag, attr))
        if "id" in attr:
            self.ids.add(attr["id"])
        if tag == "a":
            self.links.append((tag, attr))


def fail(message: str) -> None:
    raise SystemExit(f"validation failed: {message}")


def validate_required_files() -> None:
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if not path.is_file():
            fail(f"missing required file: {relative}")


def validate_no_secrets() -> None:
    for path in ROOT.rglob("*"):
        if ".git" in path.parts or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                fail(f"potential secret pattern in {path.relative_to(ROOT)}")


def validate_html() -> None:
    html_path = ROOT / "index.html"
    html = html_path.read_text(encoding="utf-8")
    if "<!doctype html>" not in html.lower():
        fail("index.html is missing doctype")
    if "<script" in html.lower():
        fail("index.html should remain script-free until interactive code is needed")

    parser = LinkParser()
    parser.feed(html)

    for tag, attrs in parser.elements:
        for key in attrs:
            if key.lower().startswith("on"):
                fail(f"inline event handler is not allowed on <{tag}>: {key}")

    for _, attrs in parser.links:
        href = attrs.get("href", "")
        if href.lower().startswith("javascript:"):
            fail(f"unsafe javascript URL: {href}")
        if href.startswith("#") and href[1:] not in parser.ids:
            fail(f"broken anchor link: {href}")
        if attrs.get("target") == "_blank":
            rel = set(attrs.get("rel", "").split())
            if not {"noopener", "noreferrer"}.issubset(rel):
                fail(f"external link missing rel noopener noreferrer: {href}")


def main() -> None:
    validate_required_files()
    validate_no_secrets()
    validate_html()
    print("validation passed")


if __name__ == "__main__":
    main()
