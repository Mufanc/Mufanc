"""Daily CodexBar export and SVG panel; only aggregate dates/tokens leave this machine."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from xml.etree import ElementTree as E
import math

N = '{http://www.w3.org/2000/svg}'
TZ = ZoneInfo('Asia/Shanghai')


def short(value):
    for scale, suffix in [(1e9, 'B'), (1e6, 'M'), (1e3, 'K')]:
        if value >= scale:
            return f'{value / scale:.2f}{suffix}'
    return str(value)


def panel(data, dark):
    if data.get('version') != 1:
        raise ValueError('Unsupported usage data')
    end = date.fromisoformat(data['as_of'])
    start = end - timedelta(days=364)
    daily = {date.fromisoformat(day): value for day, value in data['daily'].items()}
    if not daily or any(type(v) is not int or v < 0 or not start <= d <= end for d, v in daily.items()):
        raise ValueError('Invalid usage data')
    week = end - timedelta(days=end.weekday())
    positive = sorted(v for v in daily.values() if v > 0)
    thresholds = [positive[math.ceil(len(positive) * q) - 1] for q in (.25, .5, .75)] if positive else [0] * 3
    ink, muted, accent, missing, zero, colors = (
        ('#e6edf3', '#919ba7', '#69b5ff', '#161b22', '#212a35', ['#164c68', '#147ca0', '#22acd1', '#84e0ef']) if dark else
        ('#202932', '#6b7785', '#0969da', '#ebedf0', '#f0f3f6', ['#c4e9f3', '#79ccdf', '#299abb', '#096e95'])
    )
    root = E.Element(N + 'svg', {'id': 'codex-usage', 'x': '0', 'y': '733', 'width': '900', 'height': '210', 'viewBox': '0 0 900 210', 'role': 'img', 'aria-labelledby': 'usage-title usage-desc'})
    E.SubElement(root, N + 'title', {'id': 'usage-title'}).text = 'Codex token activity'
    E.SubElement(root, N + 'desc', {'id': 'usage-desc'}).text = f'Local daily totalTokens, including cached usage. Snapshot {end}. Missing records are unknown, not zero.'

    def text(x, y, value, size, color, weight='400', mono=False, **attrs):
        attrs.update(x=str(x), y=str(y), fill=color)
        attrs.update({'font-size': str(size), 'font-weight': weight, 'font-family': 'Menlo,Consolas,monospace' if mono else 'Arial,Helvetica,sans-serif'})
        E.SubElement(root, N + 'text', attrs).text = value

    text(28, 26, '$ codex usage --daily', 11, accent, mono=True)
    total = short(sum(daily.values()))
    text(28, 69, total, 28, ink, '700')
    text(28 + len(total) * 16 + 4, 67, 'tokens / 365 days', 12, muted)
    current_week = datetime.now(TZ).date().isocalendar()[:2] == end.isocalendar()[:2]
    text(872, 26, 'THIS WEEK' if current_week else f'WEEK OF {week:%m/%d}', 10, muted, mono=True, **{'text-anchor': 'end'})
    text(872, 69, short(sum(v for d, v in daily.items() if week <= d <= end)), 24, ink, '700', **{'text-anchor': 'end'})
    first = start - timedelta(days=(start.weekday() + 1) % 7)
    for i in range((end - first).days + 1):
        day = first + timedelta(days=i)
        if day < start:
            continue
        col, row = divmod(i, 7)
        value = daily.get(day)
        fill = missing if value is None else zero if value == 0 else colors[sum(value > t for t in thresholds)]
        cell = E.SubElement(root, N + 'rect', {'x': str(28 + col * 16), 'y': str(88 + row * 16), 'width': '12', 'height': '12', 'rx': '2', 'fill': fill})
        E.SubElement(cell, N + 'title').text = f'{day}: ' + ('no record' if value is None else f'{value:,} tokens')
    return root
