"""Validate generated SVGs before publishing: python3 scripts/check-profile.py dist."""
import base64
import sys
from pathlib import Path
from xml.etree import ElementTree as E

root = Path(sys.argv[1] if len(sys.argv) > 1 else 'dist')
ns = '{http://www.w3.org/2000/svg}'
for theme in ('light', 'dark'):
    svg = E.parse(root / f'profile-{theme}.svg').getroot()
    images = svg.findall(ns + 'image')
    assert len(images) == 1, 'Expected only the static toolchain as an image'
    for image in images:
        href = image.get('href')
        assert href.startswith('data:image/svg+xml;base64,'), 'External image dependency'
        E.fromstring(base64.b64decode(href.split(',', 1)[1]))
    snake_root = svg.find(f"{ns}svg[@id='contribution-snake']")
    assert snake_root is not None, 'Snake must be inline, not an image resource'
    snake = E.tostring(snake_root)
    assert b'@keyframes' in snake and b'infinite' in snake, 'Snake animation lost'
    clip = svg.find(f"{ns}defs/{ns}clipPath[@id='language-bar']/{ns}rect")
    assert clip is not None and float(clip.get('rx')) > 0, 'Language bar lost rounded ends'
    segments = [e for e in svg.findall(ns + 'rect') if e.get('clip-path') == 'url(#language-bar)']
    assert len(segments) == 8
    assert abs(sum(float(e.get('width')) for e in segments) - 337) < 1, 'Invalid language shares'
    print(f'{theme}: self-contained, animation intact, rounded language bar verified')
