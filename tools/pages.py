"""Shared helpers for reading and rewriting the chart pages.

The pages are self-contained static HTML with their data in an inline JS array,
and they stay that way: these helpers patch the array rows and the few constants
in place rather than generating the pages from a template.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEAMS = {
    "mclaren": {
        "label": "McLaren",
        "winners": "mclaren-race-winners.html",
        "roster": "mclaren-complete-roster.html",
        "first_win_year": 1968,
    },
    "ferrari": {
        "label": "Ferrari",
        "winners": "ferrari-race-winners.html",
        "roster": "ferrari-complete-roster.html",
        "first_win_year": 1951,
    },
}

INDEX = "index.html"
PAGES = [INDEX] + [t[k] for t in TEAMS.values() for k in ("winners", "roster")]

WATERMARK = re.compile(r"(<!-- race-data through: )(\d{4}-\d{2}-\d{2})( -->)")


def path(name):
    return os.path.join(ROOT, name)


def read(name):
    with open(path(name), encoding="utf-8") as fh:
        return fh.read()


def write(name, text):
    with open(path(name), "w", encoding="utf-8") as fh:
        fh.write(text)


def ledger():
    with open(path("data/races.json"), encoding="utf-8") as fh:
        races = json.load(fh)["races"]
    return sorted(races, key=lambda r: r["date"])


def watermark(html):
    m = WATERMARK.search(html)
    if not m:
        raise ValueError("page has no '<!-- race-data through: ... -->' watermark")
    return m.group(2)


def set_watermark(html, date):
    return WATERMARK.sub(lambda m: m.group(1) + date + m.group(3), html, count=1)


def const(html, name):
    m = re.search(r"\bconst %s = (\d+);" % name, html)
    if not m:
        raise ValueError("constant %s not found" % name)
    return int(m.group(1))


def set_const(html, name, value):
    return re.sub(r"\b(const %s = )\d+;" % name,
                  lambda m: "%s%d;" % (m.group(1), value), html, count=1)


def _block(html):
    m = re.search(r"(const data = \[)(.*?)(\n  \];)", html, re.S)
    if not m:
        raise ValueError("no 'const data = [...]' block")
    return m


def rows(html):
    """Parse the data array into [name, [raw field strings...]] pairs."""
    out = []
    for line in _block(html).group(2).splitlines():
        m = re.match(r'\s*\["([^"]+)",\s*(.+?)\],?\s*$', line)
        if m:
            out.append((m.group(1), [f.strip() for f in m.group(2).split(",")]))
    return out


def edit_row(html, driver, field, delta):
    """Add `delta` to the numeric `field` (0-based) of one driver's row."""
    pattern = re.compile(r'(\n\s*\["%s",\s*)(.+?)(\],)' % re.escape(driver))
    m = pattern.search(html)
    if not m:
        raise KeyError(driver)
    fields = [f.strip() for f in m.group(2).split(",")]
    fields[field] = str(int(fields[field]) + delta)
    return pattern.sub(lambda x: x.group(1) + ", ".join(fields) + x.group(3), html, count=1)


def has_row(html, driver):
    return any(name == driver for name, _ in rows(html))


def add_winner_row(html, driver, wins=1):
    """Insert a new driver onto a winners board. The page sorts, so position
    within the array only decides tie order; newcomers go last among equals."""
    block = _block(html)
    lines = block.group(2).rstrip().splitlines()
    lines.append('    ["%s", %d],' % (driver, wins))
    return html[:block.start(2)] + "\n" + "\n".join(lines) + html[block.end(2):]


def marker(html, tag, text):
    """Replace the contents of a <!--tag-->...<!--/--> span."""
    pattern = re.compile(r"(<!--%s-->)(.*?)(<!--/-->)" % re.escape(tag), re.S)
    if not pattern.search(html):
        raise ValueError("marker %r not found" % tag)
    return pattern.sub(lambda m: m.group(1) + text + m.group(3), html, count=1)


def marker_text(html, tag):
    m = re.search(r"<!--%s-->(.*?)<!--/-->" % re.escape(tag), html, re.S)
    return m.group(1) if m else None


ONES = ("zero one two three four five six seven eight nine ten eleven twelve "
        "thirteen fourteen fifteen sixteen seventeen eighteen nineteen").split()
TENS = ("_ _ twenty thirty forty fifty sixty seventy eighty ninety").split()


def spell(n):
    """Spell a year gap the way the index blurbs do: 58 -> 'fifty-eight'."""
    if n < 20:
        return ONES[n]
    tens, ones = divmod(n, 10)
    if tens < 10:
        return TENS[tens] + ("-" + ONES[ones] if ones else "")
    hundreds, rest = divmod(n, 100)
    return ONES[hundreds] + " hundred" + (" " + spell(rest) if rest else "")


def surname(name):
    """'Pedro de la Rosa' -> 'de la Rosa'. Mirrors the helper in the pages."""
    parts = re.sub(r" (Jr\.|Sr\.)$", "", name).split()
    for i, part in enumerate(parts):
        if i and part.lower() in ("de", "van", "von", "di", "la", "del"):
            return " ".join(parts[i:])
    return parts[-1]
