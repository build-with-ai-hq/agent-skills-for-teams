#!/usr/bin/env python3
"""Lint Agent Skills (SKILL.md, agentskills.io format) for a team repository.

Usage:
    python3 scripts/lint_skills.py [PATH ...]

Scans each PATH (default: current directory) for SKILL.md files and reports:
  ERROR  spec violations (name format, name/folder mismatch, missing or
         oversized description, broken relative file links)
  ERROR  the same skill name present with different content (copy-paste drift)
  WARN   weak descriptions, oversized bodies, missing version metadata,
         risky patterns in bundled scripts

Exit code: 1 if any ERROR, else 0. Standard library only (uses PyYAML if
installed, otherwise a minimal frontmatter parser).
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from collections import defaultdict

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
TRIGGER_HINT_RE = re.compile(r"\b(use (this|when|for|whenever)|when (the )?user|trigger|asks?|mentions?)\b", re.I)
RISKY_SCRIPT_PATTERNS = [
    (re.compile(r"(curl|wget)[^\n|]*\|\s*(sh|bash|zsh|python3?)\b"), "pipes a download into a shell"),
    (re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?\s+(/|~|\$HOME|\*)"), "recursive delete on a broad path"),
    (re.compile(r"\bsudo\b"), "uses sudo"),
    (re.compile(r"chmod\s+(-R\s+)?777"), "chmod 777"),
    (re.compile(r"\beval\s*[\(\"'$]"), "eval of dynamic input"),
    (re.compile(r"base64\s+(-d|--decode)[^\n]*\|\s*(sh|bash|python3?)"), "decodes and executes a payload"),
    (re.compile(r"(\.ssh/|\.aws/credentials|\.netrc|id_rsa|\.npmrc)"), "touches credential files"),
    (re.compile(r"(printenv|\benv\b\s*\||os\.environ\b[^\n]*(post|request|send))", re.I), "may export environment variables"),
    (re.compile(r"(git\s+push\s+--force|git\s+reset\s+--hard)"), "destructive git operation"),
]
SCRIPT_EXTS = {".sh", ".bash", ".zsh", ".py", ".js", ".mjs", ".cjs", ".ts", ".rb", ".ps1"}


def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    raw = text[3:end].strip("\n")
    body = text[end + 4 :].lstrip("\n")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(raw) or {}
        return (data if isinstance(data, dict) else {}), body
    except ImportError:
        pass
    except Exception:
        return {"__invalid__": True}, body
    return minimal_yaml(raw), body


def minimal_yaml(raw: str) -> dict:
    """Parse top-level keys, one level of nesting, and >/| block scalars."""
    data: dict = {}
    lines = raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        i += 1
        if val in (">", ">-", "|", "|-", ""):
            block = []
            while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                block.append(lines[i])
                i += 1
            nested = {}
            for b in block:
                nm = re.match(r"^\s+([A-Za-z0-9_.-]+):\s*(.*)$", b)
                if nm and val == "":
                    nested[nm.group(1)] = nm.group(2).strip().strip("\"'")
            if val == "" and nested:
                data[key] = nested
            else:
                joiner = "\n" if val.startswith("|") else " "
                data[key] = joiner.join(b.strip() for b in block if b.strip())
        else:
            data[key] = val.strip("\"'")
    return data


def iter_skill_files(paths):
    for root in paths:
        if os.path.isfile(root) and os.path.basename(root) == "SKILL.md":
            yield os.path.abspath(root)
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            if "SKILL.md" in filenames:
                yield os.path.abspath(os.path.join(dirpath, "SKILL.md"))


def lint_skill(path: str, report):
    skill_dir = os.path.dirname(path)
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    fm, body = parse_frontmatter(text)
    if fm is None:
        report("ERROR", path, "missing YAML frontmatter (file must start with ---)")
        return None
    if fm.get("__invalid__"):
        report("ERROR", path, "frontmatter is not valid YAML")
        return None

    name = str(fm.get("name", "") or "")
    desc = str(fm.get("description", "") or "").strip()
    folder = os.path.basename(skill_dir)

    if not name:
        report("ERROR", path, "missing required field: name")
    else:
        if len(name) > 64 or not NAME_RE.match(name):
            report("ERROR", path, f"name '{name}' must be 1-64 chars, lowercase a-z 0-9 and single hyphens")
        if name != folder:
            report("ERROR", path, f"name '{name}' does not match folder '{folder}'")

    if not desc:
        report("ERROR", path, "missing required field: description")
    else:
        if len(desc) > 1024:
            report("ERROR", path, f"description is {len(desc)} chars (max 1024)")
        if len(desc) < 120:
            report("WARN", path, f"description is only {len(desc)} chars; it likely under-triggers")
        if not TRIGGER_HINT_RE.search(desc):
            report("WARN", path, "description says what but not when; add 'Use when ...' trigger situations")

    meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
    if "version" not in meta:
        report("WARN", path, "no metadata.version; consumers cannot tell which revision they run")

    body_lines = body.count("\n") + 1
    approx_tokens = len(body) // 4
    if body_lines > 500 or approx_tokens > 5000:
        report("WARN", path, f"body is {body_lines} lines / ~{approx_tokens} tokens; move detail into references/")

    prose = re.sub(r"```.*?```", "", body, flags=re.S)  # ignore links inside code fences
    prose = re.sub(r"`[^`\n]*`", "", prose)  # and inside inline code
    for target in sorted(set(LINK_RE.findall(prose))):
        if re.match(r"^(https?:|mailto:|#)", target):
            continue
        rel = target.split("#", 1)[0]
        if rel and not os.path.exists(os.path.normpath(os.path.join(skill_dir, rel))):
            report("ERROR", path, f"broken relative link: {target}")

    for dirpath, dirnames, filenames in os.walk(skill_dir):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            if os.path.splitext(fn)[1] not in SCRIPT_EXTS or os.path.abspath(full) == os.path.abspath(__file__):
                continue
            try:
                with open(full, encoding="utf-8", errors="replace") as sf:
                    src = sf.read()
            except OSError:
                continue
            for rx, why in RISKY_SCRIPT_PATTERNS:
                if rx.search(src):
                    report("WARN", full, f"review required: {why}")

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return name or folder, digest


def main(argv):
    paths = argv[1:] or ["."]
    counts = defaultdict(int)

    def show(p):
        rel = os.path.relpath(p)
        return p if rel.startswith("..") else rel

    def report(level, where, msg):
        counts[level] += 1
        print(f"{level:5} {show(where)}: {msg}")

    seen = defaultdict(list)
    files = sorted(set(iter_skill_files(paths)))
    for f in files:
        res = lint_skill(f, report)
        if res:
            seen[res[0]].append((res[1], f))

    for name, entries in sorted(seen.items()):
        hashes = {h for h, _ in entries}
        if len(entries) > 1 and len(hashes) > 1:
            locs = ", ".join(f"{show(p)} [{h}]" for h, p in entries)
            report("ERROR", entries[0][1], f"skill '{name}' exists in {len(entries)} places with different content: {locs}")
        elif len(entries) > 1:
            report("WARN", entries[0][1], f"skill '{name}' is copied in {len(entries)} places (identical today, will drift)")

    print(f"\n{len(files)} skill(s) scanned: {counts['ERROR']} error(s), {counts['WARN']} warning(s)")
    return 1 if counts["ERROR"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
