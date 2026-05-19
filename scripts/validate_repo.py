#!/usr/bin/env python3
"""Lightweight repository validation for the static project page.

This script enforces a few cheap, deterministic invariants so that the
GitHub Pages site cannot accidentally regress on:

- presence of the documents required by the project
- absence of obvious credential patterns
- safe HTML (no executable scripts, no inline event handlers, no broken anchors,
  external links carry rel=noopener noreferrer, images carry alt text)
- presence of the SEO/meta basics (lang, viewport, description, charset)

It is intentionally dependency-free so it can run in CI without setup.
"""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    "README.md",
    "index.html",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "docs/ARCHITECTURE.md",
    "docs/ROADMAP.md",
    "docs/GRANT_SCOPE.md",
    "docs/ARC_MVP.md",
    "pyproject.toml",
    "src/domainfi_toolkit/__init__.py",
    "src/domainfi_toolkit/cli.py",
    "src/domainfi_toolkit/agent.py",
    "src/domainfi_toolkit/scoring.py",
    "src/domainfi_toolkit/arc.py",
    "src/domainfi_toolkit/data/sample_inventory.json",
    "examples/watchlists/brandable-ai.json",
    "examples/arc-x402-paid-agent/README.md",
    "examples/arc-x402-paid-agent/server.py",
    "examples/arc-x402-paid-agent/client.py",
    "examples/arc-x402-paid-agent/arc-mvp.config.json",
    "prompts/wire-arc-testnet-status.md",
    "scripts/smoke_arc_paid_agent.py",
    "src/domainfi_toolkit/arc_mcp.py",
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
# Files we never want to scan for secrets — they only describe patterns,
# not real credentials.
SECRET_SCAN_SKIP = {
    Path("scripts/validate_repo.py"),
}
# Directories we should not scan (third-party caches, build artifacts).
SECRET_SCAN_SKIP_DIR_PARTS = {".git", "__pycache__", ".venv", "venv", "node_modules", "dist", "build", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
# script type values that are inert (no JavaScript execution).
INERT_SCRIPT_TYPES = {
    "application/ld+json",
    "application/json",
    "text/plain",
}


class HtmlInspector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str]]] = []
        self.ids: set[str] = set()
        self.html_lang: str | None = None
        self.has_charset = False
        self.has_viewport = False
        self.has_description = False
        self.script_type_stack: list[str] = []
        self.script_text_segments: list[str] = []
        self._in_inert_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): (value or "") for key, value in attrs}
        self.elements.append((tag, attr))
        if "id" in attr:
            self.ids.add(attr["id"])
        if tag == "html":
            self.html_lang = attr.get("lang")
        if tag == "meta":
            if attr.get("charset"):
                self.has_charset = True
            name = attr.get("name", "").lower()
            if name == "viewport":
                self.has_viewport = True
            if name == "description" and attr.get("content"):
                self.has_description = True
        if tag == "script":
            script_type = attr.get("type", "").lower()
            self.script_type_stack.append(script_type)
            self._in_inert_script = script_type in INERT_SCRIPT_TYPES

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.script_type_stack:
            self.script_type_stack.pop()
            self._in_inert_script = bool(
                self.script_type_stack
                and self.script_type_stack[-1] in INERT_SCRIPT_TYPES
            )

    def handle_data(self, data: str) -> None:
        if self.script_type_stack and not self._in_inert_script and data.strip():
            self.script_text_segments.append(data)


def fail(message: str) -> None:
    raise SystemExit(f"validation failed: {message}")


def validate_required_files() -> None:
    for relative in REQUIRED_FILES:
        path = ROOT / relative
        if not path.is_file():
            fail(f"missing required file: {relative}")


def validate_no_secrets() -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SECRET_SCAN_SKIP_DIR_PARTS for part in path.parts):
            continue
        relative = path.relative_to(ROOT)
        if relative in SECRET_SCAN_SKIP:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                fail(f"potential secret pattern in {relative}")


def validate_html() -> None:
    html_path = ROOT / "index.html"
    html = html_path.read_text(encoding="utf-8")
    if "<!doctype html>" not in html.lower():
        fail("index.html is missing doctype")

    inspector = HtmlInspector()
    inspector.feed(html)

    if inspector.script_text_segments:
        fail(
            "index.html should not contain executable scripts; "
            "only inert types (e.g. application/ld+json) are allowed"
        )

    for tag, attrs in inspector.elements:
        if tag == "script":
            script_type = attrs.get("type", "").lower()
            if script_type and script_type not in INERT_SCRIPT_TYPES:
                fail(f"executable script type is not allowed: {script_type}")
            if attrs.get("src"):
                fail("external scripts are not allowed in index.html")
        for key in attrs:
            if key.lower().startswith("on"):
                fail(f"inline event handler is not allowed on <{tag}>: {key}")
        if tag == "img":
            if "alt" not in attrs:
                fail(f"<img> missing alt attribute (src={attrs.get('src','?')})")
        if tag == "a":
            href = attrs.get("href", "")
            normalized_href = href.strip().lower()
            if normalized_href.startswith("javascript:"):
                fail(f"unsafe javascript URL: {href}")
            if href.startswith("#") and len(href) > 1 and href[1:] not in inspector.ids:
                fail(f"broken anchor link: {href}")
            if attrs.get("target", "").strip().lower() == "_blank":
                rel = {value.lower() for value in attrs.get("rel", "").split()}
                if not {"noopener", "noreferrer"}.issubset(rel):
                    fail(f"external link missing rel noopener noreferrer: {href}")

    if not inspector.html_lang:
        fail("index.html <html> tag must declare a lang attribute")
    if not inspector.has_charset:
        fail("index.html is missing <meta charset>")
    if not inspector.has_viewport:
        fail("index.html is missing <meta name=\"viewport\">")
    if not inspector.has_description:
        fail("index.html is missing a non-empty <meta name=\"description\">")


def main() -> None:
    validate_required_files()
    validate_no_secrets()
    validate_html()
    print("validation passed", file=sys.stdout)


if __name__ == "__main__":
    main()
