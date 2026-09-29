"""The profile, drawn: every panel on github.com/patrick-shrp is built here.

GitHub shows README images without web fonts, so all type is set here and
outlined into paths (PS Kairos and IBM Plex Mono, both SIL OFL). Each panel
comes in a dark and a light cut. The time circuits read the year's real
numbers from the GitHub API, and a daily Action runs this again.

    pip install fonttools && python scripts/build.py   (GITHUB_TOKEN or gh auth for live numbers)
"""

import datetime as dt
import json
import os
import re
import subprocess
import urllib.request
from zoneinfo import ZoneInfo

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
LOGIN = "patrick-shrp"
TZ = ZoneInfo("Europe/Berlin")

FONTS = {
    "serif": TTFont(os.path.join(ROOT, "fonts", "PSKairos-Regular-static.ttf")),
    "italic": TTFont(os.path.join(ROOT, "fonts", "PSKairos-Italic-static.ttf")),
    "mono": TTFont(os.path.join(ROOT, "fonts", "IBMPlexMono-Medium.ttf")),
}

THEMES = {
    "dark": {"bg": "#000000", "ink": "#ECEAE4", "dim": "#8E8C86", "faint": "#55534E", "rule": "#262522", "ghost": "#ECEAE4", "ghost_op": 0.07},
    "light": {"bg": "#ECEAE4", "ink": "#0B0B0B", "dim": "#5C5A55", "faint": "#8E8C86", "rule": "#CFCBC1", "ghost": "#0B0B0B", "ghost_op": 0.07},
}
RED = "#FF4A1C"


# ── type, outlined ────────────────────────────────────────
def advance(style, ch, size):
    f = FONTS[style]
    name = f.getBestCmap().get(ord(ch)) or f.getBestCmap()[ord("?")]
    return f["hmtx"][name][0] * size / f["head"].unitsPerEm


def measure(style, s, size, tracking=0.0):
    return sum(advance(style, ch, size) for ch in s) + tracking * max(0, len(s) - 1)


def text(style, s, x, y, size, tracking=0.0):
    """Path data for `s` with its baseline at y (SVG space). Tracking in px."""
    f = FONTS[style]
    cmap, gs = f.getBestCmap(), f.getGlyphSet()
    k = size / f["head"].unitsPerEm
    pen = SVGPathPen(gs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
    cx = x
    for ch in s:
        name = cmap.get(ord(ch)) or cmap[ord("?")]
        gs[name].draw(TransformPen(pen, (k, 0, 0, -k, cx, y)))
        cx += gs[name].width * k + tracking
    return pen.getCommands()


def wrap(style, s, size, width):
    lines, cur = [], ""
    for word in s.split():
        trial = (cur + " " + word).strip()
        if measure(style, trial, size) > width and cur:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + ([cur] if cur else [])


def path(d, fill, extra=""):
    return f'<path fill="{fill}" {extra} d="{d}"/>' if d else ""


# ── the mark ──────────────────────────────────────────────
_mark = open(os.path.join(ROOT, "scripts", "mark.svg")).read()
MARK_W, MARK_H = map(float, re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', _mark).groups())
MARK_INK, MARK_RED = [d for _, d in re.findall(r'<path fill="([^"]+)" d="([^"]+)"', _mark)]


def mark(x, y, h, t):
    k = h / MARK_H
    return (f'<g transform="translate({x} {y}) scale({k:.5f})">'
            f'<path fill="{t["ink"]}" d="{MARK_INK}"/><path class="today" fill="{RED}" d="{MARK_RED}"/></g>')


# ── seven segments, as on the site's time panel ───────────
def _poly(pts):
    return " ".join(f"{a},{b}" for a, b in pts)


SEG = {
    "a": [(2.3, 1), (9.7, 1), (10.6, 2), (9.7, 3), (2.3, 3), (1.4, 2)],
    "g": [(2.3, 10), (9.7, 10), (10.6, 11), (9.7, 12), (2.3, 12), (1.4, 11)],
    "d": [(2.3, 19), (9.7, 19), (10.6, 20), (9.7, 21), (2.3, 21), (1.4, 20)],
}
for key, cx, y0, y1 in (("f", 1.4, 2, 11), ("b", 10.6, 2, 11), ("e", 1.4, 11, 20), ("c", 10.6, 11, 20)):
    SEG[key] = [(cx, y0 + 0.9), (cx + 1, y0 + 1.8), (cx + 1, y1 - 1.8), (cx, y1 - 0.9), (cx - 1, y1 - 1.8), (cx - 1, y0 + 1.8)]
LIT = {"0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc", "5": "afgcd", "6": "afgedc",
       "7": "abc", "8": "abcdefg", "9": "abcdfg", "-": "g", " ": ""}


def segs(value, x, y, h, fill, t, gap=0.28, dark_colon=False):
    """A row of segment digits, h tall, skewed like the site's panel; unlit segments stay faintly there."""
    k = h / 22
    out, cx = [], x
    for ch in value:
        if ch == ":":
            cf = f'{t["ghost"]}" fill-opacity="{t["ghost_op"]}' if dark_colon else fill
            out.append(f'<rect x="{cx + 1.2 * k:.1f}" y="{y + 6 * k:.1f}" width="{2 * k:.1f}" height="{2 * k:.1f}" fill="{cf}"/>'
                       f'<rect x="{cx + 0.5 * k:.1f}" y="{y + 14 * k:.1f}" width="{2 * k:.1f}" height="{2 * k:.1f}" fill="{cf}"/>')
            cx += 4.5 * k
            continue
        lit = LIT.get(ch, "")
        g = []
        for s_, pts in SEG.items():
            on = s_ in lit
            g.append(f'<polygon points="{_poly(pts)}" fill="{fill if on else t["ghost"]}"'
                     f'{"" if on else f" fill-opacity=\"{t["ghost_op"]}\""}/>')
        out.append(f'<g transform="translate({cx:.1f} {y:.1f}) scale({k:.3f}) skewX(-7)">{"".join(g)}</g>')
        cx += 12 * k * (1 + gap)
    return "".join(out), cx - x


def svg(w, h, body, t, title, css=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{title}">'
            f"<title>{title}</title>"
            f"<style>{css}@media (prefers-reduced-motion: reduce){{*{{animation:none!important}}}}</style>"
            f'<rect width="{w}" height="{h}" fill="{t["bg"]}"/>{body}</svg>\n')


def write(name, theme, content):
    with open(os.path.join(OUT, f"{name}-{theme}.svg"), "w") as fh:
        fh.write(content)


# ── the year's numbers ────────────────────────────────────
def token():
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return None


def year_numbers(now):
    q = """query($login:String!,$from:DateTime!){user(login:$login){contributionsCollection(from:$from){
      contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}"""
    body = json.dumps({"query": q, "variables": {"login": LOGIN, "from": f"{now.year}-01-01T00:00:00Z"}}).encode()
    tok = token()
    if not tok:
        return None
    req = urllib.request.Request("https://api.github.com/graphql", body, {"Authorization": f"bearer {tok}", "User-Agent": LOGIN})
    cal = json.load(urllib.request.urlopen(req, timeout=30))["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"] if d["contributionCount"] > 0]
    return {"total": cal["totalContributions"], "active": len(days), "last": days[-1]["date"] if days else None}


# ── panels ────────────────────────────────────────────────
W = 1280
MONTHS = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()


def hero(t, now):
    H = 600
    b = []
    b.append(mark(64, 56, 40, t))
    b.append(path(text("mono", "PATRICK SCHRÖPPEL · FOUNDER · AUGSBURG", 150, 84, 15, 2.4), t["dim"]))
    right = "AUVY · OPENPULSE · IMTAKT · LIMBOVA"
    b.append(path(text("mono", right, W - 64 - measure("mono", right, 15, 2.4), 84, 15, 2.4), t["dim"]))
    # the line, set large; the full stop is today
    b.append(f'<g class="l1">{path(text("serif", "Work is slower", 60, 290, 150, -3), t["ink"])}</g>')
    l2 = "than it has to be"
    b.append(f'<g class="l2">{path(text("italic", l2, 150, 430, 150, -3), t["ink"])}</g>')
    stop_x = 150 + measure("italic", l2, 150, -3) + 8
    b.append(f'<rect class="today" x="{stop_x:.0f}" y="410" width="20" height="20" fill="{RED}"/>')
    b.append(path(text("serif", "I find where the time goes, and build what wins it back.", 64, 506, 30), t["dim"]))
    # the year as a line: months ticked, today in red
    y0, x0, x1 = 548, 64, W - 64
    frac = (now.timetuple().tm_yday - 1) / (366 if now.year % 4 == 0 else 365)
    tx = x0 + (x1 - x0) * frac
    b.append(f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="1.5" fill="{t["faint"]}"/>')
    b.append(f'<rect class="lived" x="{x0}" y="{y0 - 0.5}" width="{tx - x0:.1f}" height="2.5" fill="{t["ink"]}"/>')
    for m in range(12):
        mx = x0 + (x1 - x0) * m / 12
        b.append(f'<rect x="{mx:.1f}" y="{y0 - 6}" width="1.5" height="13" fill="{t["faint"]}"/>')
        b.append(path(text("mono", MONTHS[m], mx + 6, y0 + 26, 11, 1.5), t["ink"] if mx <= tx else t["faint"]))
    b.append(f'<rect class="today" x="{tx - 6:.1f}" y="{y0 - 5}" width="12" height="12" fill="{RED}"/>')
    css = (".l1,.l2{animation:rise 1.1s cubic-bezier(.2,.7,.1,1) both}.l2{animation-delay:.12s}"
           "@keyframes rise{from{opacity:0;transform:translateY(26px)}}"
           ".today{animation:blink 2.4s steps(1) infinite}@keyframes blink{50%{opacity:.25}}"
           ".lived{transform-box:fill-box;animation:run 1.8s cubic-bezier(.2,.7,.1,1) .3s both}@keyframes run{from{transform:scaleX(0)}}")
    return svg(W, H, "".join(b), t, "Patrick Schröppel. Work is slower than it has to be. I find where the time goes, and build what wins it back.", css)


def circuits(t, now, nums):
    H = 500
    b = []
    b.append(path(text("mono", "TIME CIRCUITS · " + str(now.year), 64, 62, 13, 2.6), t["dim"]))
    upd = f"UPDATED DAILY · {now.strftime('%d %b %H:%M').upper()} CET"
    b.append(path(text("mono", upd, W - 64 - measure("mono", upd, 13, 2.6), 62, 13, 2.6), t["faint"]))
    last = dt.date.fromisoformat(nums["last"]) if nums and nums["last"] else None
    rows = [
        ("DESTINATION TIME", dt.datetime(now.year, 12, 31, 23, 59), t["ink"], "everything ships this year"),
        ("PRESENT TIME", now, RED, None),
        ("LAST TIME DEPARTED", dt.datetime.combine(last, dt.time()) if last else None, t["ink"], "the last commit"),
    ]
    y = 96
    for label, when, fill, _ in rows:
        b.append(f'<rect x="64" y="{y}" width="{W - 128}" height="88" fill="none" stroke="{t["rule"]}"/>')
        # the month in plain letters, the rest in segments
        mon = MONTHS[when.month - 1] if when else "---"
        b.append(path(text("mono", mon, 92, y + 62, 44, 2), fill if when else t["faint"]))
        x = 230
        for part, w in ((f"{when.day:02d}" if when else "  ", 2), (f"{when.year}" if when else "    ", 4),
                        ((f"{when.hour:02d}:{when.minute:02d}" if label != "LAST TIME DEPARTED" else "  :  ") if when else "  :  ", 5)):
            g, gw = segs(part, x, y + 18, 52, fill, t, dark_colon=part.strip() == ":")
            b.append(g)
            x += gw + 44
        b.append(path(text("mono", label, W - 92 - measure("mono", label, 13, 2.6), y + 50, 13, 2.6), t["dim"]))
        y += 104
    # readouts
    y = 462
    reads = []
    if nums:
        reads = [(f"{nums['total']:,}", "contributions this year"), (str(nums["active"]), "days at work"), ("4", "ventures")]
    x = 64
    for val, lab in reads:
        b.append(path(text("serif", val, x, y, 40, -0.5), t["ink"]))
        vx = x + measure("serif", val, 40, -0.5) + 14
        b.append(path(text("mono", lab.upper(), vx, y - 4, 12, 2.2), t["dim"]))
        x = vx + measure("mono", lab.upper(), 12, 2.2) + 56
    return svg(W, H, "".join(b), t, f"Time circuits. Present time {now:%d %B %Y}." + (f" {nums['total']} contributions this year over {nums['active']} days; last on {nums['last']}." if nums else ""))


def heading(t, idx, a, b_):
    H = 150
    b = [path(text("mono", idx, 64, 50, 13, 2.6), t["dim"]),
         f'<rect x="64" y="22" width="{W - 128}" height="1" fill="{t["rule"]}"/>',
         path(text("serif", a, 60, 122, 64, -1), t["ink"])]
    bx = 60 + measure("serif", a, 64, -1) + 16
    b.append(path(text("italic", b_, bx, 122, 64, -1), t["ink"]))
    return svg(W, H, "".join(b), t, f"{a} {b_}")


VENTURES = [
    ("AUVY", "in build · opening to the first teams", False, "auvy.ai",
     "Reads a project's emails, meetings and files, spots what changed, and prepares the next step. Nothing goes out until a person approves it."),
    ("OpenPulse", "live · claim your address today", True, "openpulse.org",
     "One address for people and their AI assistants: messages, calls and payments, sealed end to end. OpenPulse carries it but cannot read it."),
    ("ImTakt", "live · every stop in Germany", True, "imtakt.dev",
     "Germany's public train data, made usable: connections side by side, live departures at every stop, and which lines keep running late."),
    ("Limbova", "in build · site live, first clinic to come", False, "limbova.de",
     "A workspace for psychotherapists, with an app that carries patients through the week between sessions."),
]


def venture(t, i, v):
    name, status, live, url, summary = v
    Wc, H = 632, 340
    b = [f'<rect x="0.5" y="0.5" width="{Wc - 1}" height="{H - 1}" fill="none" stroke="{t["rule"]}"/>']
    b.append(path(text("mono", f"0{i + 1}", 36, 52, 13, 2.4), t["faint"]))
    sx = 36 + measure("mono", f"0{i + 1}", 13, 2.4) + 22
    if live:
        b.append(f'<rect class="today" x="{sx}" y="42" width="9" height="9" fill="{RED}"/>')
        sx += 22
    b.append(path(text("mono", status.upper(), sx, 52, 12, 2.2), t["dim"]))
    b.append(path(text("serif", name, 32, 142, 76, -1.5), t["ink"]))
    y = 196
    lines = wrap("serif", summary, 24, Wc - 68)
    if len(lines) > 1 and len(lines[-1].split()) == 1:  # no word left alone on the last line
        *head, prev = lines[:-1]
        words = prev.split()
        lines = head + [" ".join(words[:-1]), words[-1] + " " + lines[-1]]
    for line in lines:
        b.append(path(text("serif", line, 36, y, 24), t["dim"]))
        y += 31
    b.append(path(text("mono", url + " ↗", 36, H - 32, 13, 2.2), t["ink"]))
    css = ".today{animation:blink 2.4s steps(1) infinite}@keyframes blink{50%{opacity:.25}}"
    return svg(Wc, H, "".join(b), t, f"{name}, {status}. {summary}", css)


def button(t, label, primary):
    size, tr = 14, 2.4
    w = int(measure("mono", label, size, tr) + 64)
    H = 56
    fg, bg = (t["bg"], t["ink"]) if primary else (t["ink"], t["bg"])
    b = f'<rect x="0.5" y="0.5" width="{w - 1}" height="{H - 1}" fill="{bg}" stroke="{t["ink"] if not primary else bg}"/>'
    b += path(text("mono", label, 32, 33, size, tr), fg)
    return svg(w, H, b, {**t, "bg": bg}, label)


def main():
    os.makedirs(OUT, exist_ok=True)
    now = dt.datetime.now(TZ)
    cache = os.path.join(OUT, "numbers.json")
    try:
        nums = year_numbers(now)
    except Exception as e:
        print("numbers unavailable:", e)
        nums = None
    if nums:
        with open(cache, "w") as fh:
            json.dump(nums, fh)
    elif os.path.exists(cache):  # a bad day at the API keeps the last good numbers
        nums = json.load(open(cache))
    for name, t in THEMES.items():
        write("hero", name, hero(t, now))
        write("circuits", name, circuits(t, now, nums))
        write("h-ventures", name, heading(t, "02 · THE VENTURES", "Four places", "where time gets lost."))
        write("h-research", name, heading(t, "03 · RESEARCH", "What I found,", "including what fell short."))
        for i, v in enumerate(VENTURES):
            write(f"v-{v[0].lower()}", name, venture(t, i, v))
        write("b-site", name, button(t, "PATRICKSCHROEPPEL.COM ↗", True))
        write("b-linkedin", name, button(t, "LINKEDIN ↗", False))
        write("b-mail", name, button(t, "WRITE TO ME ↗", False))
    print("built", now.isoformat(timespec="minutes"), nums)


if __name__ == "__main__":
    main()
