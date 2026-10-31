#!/usr/bin/env python3
import re
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "index.html"
content = path.read_text(encoding="utf-8")
pattern = r"(النسخة التقريبية\s+)(\d+)\.(\d+)\.(\d+)"
match = re.search(pattern, content)
if not match:
    raise SystemExit("Site version not found in index.html")
major, minor, patch = map(int, match.groups()[1:])
version = f"{major}.{minor}.{patch + 1}"
updated = re.sub(pattern, lambda m: m.group(1) + version, content, count=1)
path.write_text(updated, encoding="utf-8")
print("Site version:", version)
