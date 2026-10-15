#!/usr/bin/env python3
"""Embed census aggregates in the editable visualization fragment."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = root / "output"
data = json.loads((output / "imdb-rating-distribution.json").read_text())
template = (output / "imdb-rating-distribution.template.html").read_text()
assert template.count("__IMDB_DISTRIBUTION_DATA__") == 1
embedded = json.dumps(data, separators=(",", ":")).replace("<", "\\u003c")
fragment = template.replace("__IMDB_DISTRIBUTION_DATA__", embedded)
target = output / "imdb-rating-distribution.html"
target.write_text(fragment)
assert target.stat().st_size < 1024 * 1024
print(target)
