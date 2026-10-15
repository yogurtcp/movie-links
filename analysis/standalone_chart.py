#!/usr/bin/env python3
"""Update embedded census data while preserving the standalone chart runtime."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / 'output' / 'imdb-ratings-browser.html'
shell = target.read_text()
import html
import json
import re
pattern = re.compile(r'(\bdata-srcdoc=")([^"]*)(")')
if not pattern.search(shell):
    raise SystemExit('The standalone shell has no data-srcdoc iframe.')
data = json.loads((root / 'output' / 'imdb-rating-distribution.json').read_text())
payload = json.dumps(data, separators=(',', ':')).replace('<', '\\u003c')


def update_iframe(match):
    document = html.unescape(match.group(2))
    data_pattern = re.compile(r'(<script type="application/json" id="census-data">).*?(</script>)', re.S)
    updated, count = data_pattern.subn(lambda part: part.group(1) + payload + part.group(2), document)
    if count != 1:
        raise ValueError('Expected exactly one census data block in the iframe')
    return match.group(1) + html.escape(updated, quote=True) + match.group(3)


shell, count = pattern.subn(update_iframe, shell, count=1)
assert count == 1
target.write_text(shell)
print(target)
