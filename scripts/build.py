"""Builds every SVG on the profile, and the essays block of README.md.

    python scripts/build.py              # fetches https://arkanji.com/index.xml
    RSS_FILE=index.xml python scripts/build.py

Deterministic: the same feed gives the same files, so the daily workflow only
commits when an essay actually changed.
"""
import datetime as dt
import email.utils
import html
import json
import os
import random
import re
import urllib.request

from svgtext import face

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ASSETS = os.path.join(ROOT, "assets")
ICONS = json.load(open(os.path.join(os.path.dirname(__file__), "icons.json")))
RSS_URL = "https://arkanji.com/index.xml"

# The cave palette, from arkanji.com's dark theme (oklch tokens → sRGB).
PAPER, SUNK = "#0d0c0a", "#151411"
INK, SOFT, FAINT = "#d4d3ce", "#aba9a4", "#8f8c85"
GOLD, QUIET, PALE = "#e2b849", "#ad8e44", "#f3dc98"
RULE = "rgba(240,238,230,.12)"

DISP_B = lambda: face("ThmanyahSerifDisplay-Bold")
DISP_M = lambda: face("ThmanyahSerifDisplay-Medium")
DISP_R = lambda: face("ThmanyahSerifDisplay-Regular")
SANS_L = lambda: face("ThmanyahSans-Light")
SANS_R = lambda: face("ThmanyahSans-Regular")
SANS_M = lambda: face("ThmanyahSans-Medium")
MONO = lambda: face("IBMPlexMono-400-latin")

AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو",
             "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]
AR_DIGITS = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

# السبكة: the lattice tile arkanji.com uses as its one ornament.
SEBKA = ('<pattern id="sebka" width="40" height="40" patternUnits="userSpaceOnUse">'
         '<g fill="none" stroke="{c}" stroke-width="1.1">'
         '<path d="M20 0 Q33 7 40 20 Q33 33 20 40 Q7 33 0 20 Q7 7 20 0 Z"/>'
         '<path d="M40 0 Q34 6 40 12 M0 12 Q6 6 0 0"/>'
         '<path d="M40 40 Q34 34 40 28 M0 28 Q6 34 0 40"/></g>'
         '<circle cx="20" cy="20" r="1.4" fill="{c}"/></pattern>')

# An archway: the cave's mark.
ARCH = "M4 22V11a8 8 0 0 1 16 0v11h-3.2V11a4.8 4.8 0 0 0-9.6 0v11Z"

BASE_CSS = """
.rise{animation:rise 1.1s cubic-bezier(.16,1,.3,1) both}
@keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
.pulse{animation:pulse 2.4s ease-in-out infinite;transform-box:fill-box;transform-origin:center}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.35;transform:scale(.7)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important}}
"""


def T(fc, text, x, y, size, anchor="start", fill=INK, tracking=0, attrs=""):
    d = fc.path(text, x, y, size, anchor, tracking)
    return f'<path d="{d}" fill="{fill}"{(" " + attrs) if attrs else ""}/>'


def wrap(fc, text, size, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if cur and fc.width(trial, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + ([cur] if cur else [])


def icon(name, x, y, size, fill):
    s = size / 24
    return f'<path d="{ICONS[name]}" fill="{fill}" transform="translate({x:.1f} {y:.1f}) scale({s:.3f})"/>'


def arch(x, y, size, fill):
    s = size / 24
    return f'<path d="{ARCH}" fill="{fill}" transform="translate({x:.1f} {y:.1f}) scale({s:.3f})"/>'


def arrow(x, y, size, color, way="ne", width=2):
    """↗ and ← drawn as strokes: neither glyph is in the cave's fonts.
    (x, y) is the bottom-left corner of the arrow's square."""
    s = size
    if way == "ne":
        d = f"M{x} {y}L{x + s} {y - s}M{x + s * .3} {y - s}H{x + s}V{y - s * .7}"
    else:  # west, the reading direction of an RTL list
        d = f"M{x + s} {y - s / 2}H{x}M{x + s * .4} {y - s * .9}L{x} {y - s / 2}L{x + s * .4} {y - s * .1}"
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
            'stroke-linecap="round" stroke-linejoin="round"/>')


def svg(w, h, body, title, css="", defs="", pad=0, rx=22, bg=PAPER):
    """A dark panel, inset by `pad` so cards placed side by side keep a gap."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{html.escape(title)}"><title>{html.escape(title)}</title>'
            f'<style>{BASE_CSS}{css}</style><defs>{defs}'
            f'<clipPath id="panel"><rect x="{pad}" y="{pad}" width="{w - 2 * pad}" height="{h - 2 * pad}" rx="{rx}"/></clipPath></defs>'
            f'<rect x="{pad}" y="{pad}" width="{w - 2 * pad}" height="{h - 2 * pad}" rx="{rx}" fill="{bg}"/>'
            f'<g clip-path="url(#panel)">{body}</g>'
            f'<rect x="{pad + .5}" y="{pad + .5}" width="{w - 2 * pad - 1}" height="{h - 2 * pad - 1}" rx="{rx}" '
            f'fill="none" stroke="{RULE}"/></svg>')


def write(name, content):
    path = os.path.join(ASSETS, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def label(x_left, x_right, y, ar, en, dot=False):
    """A section label: Arabic in gold on the right, English in mono on the left."""
    out = T(DISP_B(), ar, x_right, y, 28, "end", GOLD)
    lx = x_left
    if dot:
        out += f'<circle class="pulse" cx="{lx + 5}" cy="{y - 7}" r="5" fill="{GOLD}"/>'
        lx += 22
    out += T(MONO(), en, lx, y - 1, 15, "start", FAINT, 2.2)
    return out


# ── Hero ──────────────────────────────────────────────────────────────────

def hero():
    W, H = 1200, 600
    rnd = random.Random(7)
    dust = "".join(
        f'<circle cx="{rnd.uniform(60, W - 60):.0f}" cy="{rnd.uniform(H * .45, H - 30):.0f}" '
        f'r="{rnd.uniform(.7, 2.1):.1f}" fill="{PALE}" class="mote" '
        f'style="animation-duration:{rnd.uniform(7, 15):.1f}s;animation-delay:-{rnd.uniform(0, 15):.1f}s"/>'
        for _ in range(26))
    name = DISP_B().path("وليد أركنجي", W / 2, 302, 156, "middle")
    defs = (SEBKA.format(c=GOLD) +
            '<radialGradient id="torch" cx="50%" cy="100%" r="75%">'
            f'<stop offset="0" stop-color="{GOLD}" stop-opacity=".30"/>'
            f'<stop offset=".45" stop-color="{GOLD}" stop-opacity=".07"/>'
            f'<stop offset="1" stop-color="{GOLD}" stop-opacity="0"/></radialGradient>'
            '<radialGradient id="fade" cx="50%" cy="38%" r="60%">'
            '<stop offset="0" stop-color="#fff" stop-opacity=".9"/><stop offset=".7" stop-color="#fff" stop-opacity=".12"/>'
            '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
            '<mask id="sebkaMask"><rect width="100%" height="100%" fill="url(#fade)"/></mask>'
            '<radialGradient id="vignette" cx="50%" cy="45%" r="75%">'
            '<stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".7"/></radialGradient>'
            # A highlight that sweeps across the name, like torchlight on gilt.
            f'<linearGradient id="gilt" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{W}" y2="0">'
            f'<stop offset="0" stop-color="{QUIET}"/><stop offset=".40" stop-color="{GOLD}"/>'
            f'<stop offset=".50" stop-color="{PALE}"/><stop offset=".60" stop-color="{GOLD}"/>'
            f'<stop offset="1" stop-color="{QUIET}"/>'
            f'<animateTransform attributeName="gradientTransform" type="translate" values="-{W};{W};{W}" '
            'keyTimes="0;.55;1" dur="9s" repeatCount="indefinite"/></linearGradient>'
            '<filter id="glow" x="-20%" y="-40%" width="140%" height="180%">'
            '<feGaussianBlur stdDeviation="18" result="b"/><feColorMatrix in="b" type="matrix" '
            'values="0 0 0 0 .89  0 0 0 0 .72  0 0 0 0 .29  0 0 0 .55 0"/></filter>')
    css = """
.flicker{animation:flicker 5s ease-in-out infinite}
@keyframes flicker{0%,100%{opacity:1}18%{opacity:.82}22%{opacity:.95}47%{opacity:.78}52%{opacity:.92}74%{opacity:.85}}
.breathe{animation:breathe 9s ease-in-out infinite alternate}
@keyframes breathe{from{opacity:.10}to{opacity:.22}}
.mote{animation:mote linear infinite;opacity:0}
@keyframes mote{0%{opacity:0;transform:translateY(0)}15%{opacity:.75}100%{opacity:0;transform:translateY(-190px)}}
.draw{animation:draw 1.4s cubic-bezier(.65,0,.35,1) .9s both;transform-box:fill-box;transform-origin:center}
@keyframes draw{from{transform:scaleX(0)}to{transform:scaleX(1)}}
.d1{animation-delay:.15s}.d2{animation-delay:.55s}.d3{animation-delay:1.1s}.d4{animation-delay:1.45s}.d5{animation-delay:1.8s}
"""
    corners = "".join(
        f'<path d="M{x} {y + 34 * sy}V{y}H{x + 34 * sx}" fill="none" stroke="{QUIET}" stroke-opacity=".55"/>'
        for x, y, sx, sy in [(36, 36, 1, 1), (W - 36, 36, -1, 1), (36, H - 36, 1, -1), (W - 36, H - 36, -1, -1)])
    body = (
        f'<rect width="{W}" height="{H}" fill="url(#torch)" class="flicker"/>'
        f'<rect width="{W}" height="{H}" fill="url(#sebka)" mask="url(#sebkaMask)" class="breathe"/>'
        f'<rect width="{W}" height="{H}" fill="url(#vignette)"/>'
        f'{dust}{corners}'
        + T(MONO(), "~/the-cave", 72, 84, 15, "start", FAINT, 1.5)
        + f'<circle class="pulse" cx="{W - 72 - MONO().width("BUILDING IN SILENCE", 15, 2.2) - 18}" cy="79" r="4.5" fill="{GOLD}"/>'
        + T(MONO(), "BUILDING IN SILENCE", W - 72, 84, 15, "end", FAINT, 2.2)
        + f'<g class="rise d1"><path d="{name}" fill="{GOLD}" filter="url(#glow)" class="flicker"/>'
          f'<path d="{name}" fill="url(#gilt)"/></g>'
        + T(SANS_M(), "WALEED ARKANJI", W / 2, 368, 22, "middle", SOFT, 9, 'class="rise d2"')
        + f'<rect x="{W / 2 - 90}" y="400" width="180" height="1.5" fill="{GOLD}" opacity=".7" class="draw"/>'
        + T(DISP_R(), "أبني بصمت، أفكّر بصوت عالي", W / 2, 474, 42, "middle", INK, 0, 'class="rise d3"')
        + T(SANS_L(), "I build in silence. I think out loud.", W / 2, 522, 24, "middle", FAINT, .4, 'class="rise d4"')
    )
    write("hero.svg", svg(W, H, body, "Waleed Arkanji · وليد أركنجي — I build in silence. I think out loud.",
                          css, defs, rx=26))


# ── Link pills ────────────────────────────────────────────────────────────

def pills():
    H = 76
    items = [
        ("site", "arkanji.com", lambda x: arch(x, 26, 26, GOLD)),
        ("x", "@WaleedArkanji", lambda x: icon("x", x + 2, 28, 22, GOLD)),
        ("linkedin", "in/arkanji", lambda x: (
            f'<rect x="{x}" y="25" width="26" height="26" rx="6" fill="{GOLD}"/>'
            + T(SANS_M(), "in", x + 13, 45, 19, "middle", PAPER))),
        ("tools", "Tools", lambda x: icon("gumroad", x + 1, 26, 24, GOLD)),
    ]
    for key, text, mark in items:
        tw = SANS_M().width(text, 24)
        W = int(28 + 26 + 14 + tw + 22 + 13 + 28)
        body = (mark(28)
                + T(SANS_M(), text, 68, 46, 24, "start", INK)
                + arrow(W - 28 - 13, 45, 13, QUIET))
        write(f"links/{key}.svg", svg(W, H, body, text, rx=H / 2, bg=SUNK))


# ── iWork Studio feature ──────────────────────────────────────────────────

def iwork():
    W, H = 1200, 460
    chips, x = "", 56
    for name, color in [("Numbers", "#34c759"), ("Keynote", "#0a84ff"), ("Pages", "#ff9f0a")]:
        w = SANS_M().width(name, 19) + 56
        chips += (f'<rect x="{x}" y="304" width="{w:.0f}" height="44" rx="22" fill="{SUNK}" stroke="{RULE}"/>'
                  f'<circle cx="{x + 22}" cy="326" r="6" fill="{color}"/>'
                  + T(SANS_M(), name, x + 38, 333, 19, "start", INK))
        x += w + 12
    stats = ""
    for i, (value, en) in enumerate([("76/76", "tests green"), ("0", "repair prompts"),
                                     ("1:1", "Arabic byte-exact")]):
        y = 176 + i * 84
        stats += (T(DISP_B(), value, 1144, y, 46, "end", GOLD)
                  + T(SANS_R(), en, 1144, y + 25, 18, "end", FAINT, .3))
        if i:
            stats += f'<rect x="880" y="{y - 49}" width="264" height="1" fill="{RULE}"/>'
    body = (
        label(56, W - 56, 76, "أحدث إطلاق", "01 — NOW SHIPPING", dot=True)
        + f'<rect x="56" y="104" width="{W - 112}" height="1" fill="{RULE}"/>'
        + T(DISP_B(), "iWork Studio", 52, 214, 88, "start", INK)
        + T(SANS_R(), "Give your AI agent the keys to Apple iWork.", 56, 264, 25, "start", SOFT)
        + chips + stats
        + f'<rect x="56" y="388" width="{W - 112}" height="1" fill="{RULE}"/>'
        + T(MONO(), "PYTHON · MACOS · MIT · DROP-IN AGENT SKILL", 56, 424, 14, "start", FAINT, 2)
        + T(MONO(), "github.com/Arkanji/iwork-studio", W - 56 - 22, 424, 15, "end", QUIET, .5)
        + arrow(W - 56 - 11, 424, 11, QUIET, width=1.6)
    )
    write("iwork.svg", svg(W, H, body, "iWork Studio — give your AI agent the keys to Apple iWork"))


# ── Project cards ─────────────────────────────────────────────────────────

def project(fname, idx, name, desc, tags, mark):
    W, H, P = 600, 330, 6
    lines = wrap(SANS_R(), desc, 21, W - 2 * P - 92)
    text = "".join(T(SANS_R(), ln, 50, 184 + i * 31, 21, "start", SOFT) for i, ln in enumerate(lines[:3]))
    chips, x = "", 50
    for tag in tags:
        w = MONO().width(tag, 13, 1) + 28
        chips += (f'<rect x="{x}" y="262" width="{w:.0f}" height="32" rx="16" fill="{SUNK}" stroke="{RULE}"/>'
                  + T(MONO(), tag, x + 14, 283, 13, "start", QUIET, 1))
        x += w + 8
    body = (f'<circle cx="74" cy="72" r="26" fill="{SUNK}" stroke="{RULE}"/>{mark}'
            + T(MONO(), idx, W - 50 - 22, 79, 13, "end", QUIET, 2)
            + arrow(W - 50 - 11, 79, 11, QUIET, width=1.6)
            + T(DISP_B(), name, 48, 146, 38, "start", INK)
            + text + chips)
    write(fname, svg(W, H, body, f"{name} — {desc}", pad=P))


# ── Essays (from the blog's RSS) ──────────────────────────────────────────

def fetch_feed():
    src = os.environ.get("RSS_FILE")
    if src:
        return open(src, encoding="utf-8").read()
    req = urllib.request.Request(RSS_URL, headers={"User-Agent": "arkanji-profile"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def essays(n=5):
    xml = fetch_feed()
    items = []
    for it in re.findall(r"<item>(.*?)</item>", xml, re.S):
        link = re.search(r"<link>(.*?)</link>", it).group(1).strip()
        if "/posts/" not in link:
            continue
        title = html.unescape(re.search(r"<title>(.*?)</title>", it, re.S).group(1)).strip()
        date = email.utils.parsedate_to_datetime(re.search(r"<pubDate>(.*?)</pubDate>", it).group(1))
        items.append((date, title, link))
    items.sort(key=lambda t: t[0], reverse=True)
    items = items[:n]

    W, H = 1200, 132
    write("essays/head.svg", svg(W, H, label(56, W - 56, 76, "من الكهف", "02 — LATEST ESSAYS", dot=True)
                                 + T(MONO(), "AUTO-UPDATED DAILY FROM ARKANJI.COM", 56, 104, 12, "start", QUIET, 2),
                                 "Latest essays from arkanji.com"))
    today = dt.datetime.now(dt.timezone.utc)
    rows = []
    for i, (date, title, link) in enumerate(items):
        W, H = 1200, 104
        when = f"{AR_MONTHS[date.month - 1]} {date.year}"
        fresh = (today - date).days <= 14
        avail = W - 56 - 76 - 260 - (88 if fresh else 0)
        title_fit, size = DISP_M().fit(title, avail, 34, 24)
        tx = W - 56 - 64
        badge = ""
        if fresh:
            bx = tx - DISP_M().width(title_fit, size) - 24 - 66
            badge = (f'<rect x="{bx:.0f}" y="36" width="66" height="32" rx="16" fill="{GOLD}" fill-opacity=".14" stroke="{GOLD}" stroke-opacity=".5"/>'
                     + T(SANS_M(), "جديد", bx + 33, 58, 16, "middle", GOLD))
        body = (T(DISP_B(), f"{i + 1:02d}".translate(AR_DIGITS), W - 56, 64, 26, "end", QUIET)
                + T(DISP_M(), title_fit, tx, 65, size, "end", INK)
                + badge
                + T(SANS_R(), when, 96, 62, 19, "start", FAINT)
                + arrow(56, 63, 18, GOLD, "w"))
        write(f"essays/{i}.svg", svg(W, H, body, f"{title} — {when}", rx=18))
        rows.append((title, link, i))

    block = ['<!-- ESSAYS:START — rewritten by scripts/build.py, edits here are lost -->',
             '<a href="https://arkanji.com/posts/"><img src="assets/essays/head.svg" width="100%" alt="Latest essays from arkanji.com"></a>']
    block += [f'<a href="{link}"><img src="assets/essays/{i}.svg" width="100%" alt="{html.escape(title)}"></a>'
              for title, link, i in rows]
    block.append("<!-- ESSAYS:END -->")
    readme = os.path.join(ROOT, "README.md")
    text = open(readme, encoding="utf-8").read()
    text = re.sub(r"<!-- ESSAYS:START.*?<!-- ESSAYS:END -->", lambda _: "\n".join(block), text, flags=re.S)
    open(readme, "w", encoding="utf-8").write(text)


# ── Doctrine ──────────────────────────────────────────────────────────────

def element(kind, cx, cy, s=22):
    """The four alchemical elements the blog's README uses: 🜂 🜄 🜁 🜃."""
    up = kind in ("fire", "air")
    pts = (f"{cx},{cy - s} {cx + s * 1.1},{cy + s * .8} {cx - s * 1.1},{cy + s * .8}" if up
           else f"{cx},{cy + s} {cx + s * 1.1},{cy - s * .8} {cx - s * 1.1},{cy - s * .8}")
    bar = ""
    if kind in ("air", "earth"):
        by = cy + (s * .15 if up else -s * .15)
        bar = f'<line x1="{cx - s * .95}" y1="{by}" x2="{cx + s * .95}" y2="{by}"/>'
    return (f'<g fill="none" stroke="{GOLD}" stroke-width="2" stroke-linejoin="round">'
            f'<polygon points="{pts}"/>{bar}</g>')


def doctrine():
    W, H = 1200, 470
    cols = [  # right to left, as an Arabic reader meets them
        ("fire", "البناء بصمت", "SILENT BUILDING", "The work happens in the cave, not on the timeline."),
        ("water", "هوس البساطة", "SIMPLICITY", "The best products feel inevitable. Delete until only essence remains."),
        ("air", "الشغل الفوضوي", "MESSY WORK", "Talk. Build. Observe. No frameworks. No ceremony."),
        ("earth", "المخرجات تتكلم", "OUTPUT SPEAKS", "Don't announce. Ship. Let the thing itself do the talking."),
    ]
    cw = (W - 112) / 4
    body = label(56, W - 56, 76, "العقيدة", "03 — THE DOCTRINE")
    body += f'<rect x="56" y="104" width="{W - 112}" height="1" fill="{RULE}"/>'
    for i, (kind, ar, en, desc) in enumerate(cols):
        cx = W - 56 - cw * (i + .5)
        body += '<g>' + element(kind, cx, 170)
        body += T(DISP_B(), ar, cx, 258, 34, "middle", INK)
        body += T(MONO(), en, cx, 292, 13, "middle", QUIET, 2.5)
        for j, ln in enumerate(wrap(SANS_R(), desc, 21, cw - 40)[:3]):
            body += T(SANS_R(), ln, cx, 346 + j * 31, 21, "middle", SOFT)
        body += "</g>"
        if i:
            body += f'<rect x="{W - 56 - cw * i:.0f}" y="140" width="1" height="276" fill="{RULE}"/>'
    write("doctrine.svg", svg(W, H, body, "The Doctrine — silent building, simplicity, messy work, output speaks"))


# ── Tools ─────────────────────────────────────────────────────────────────

def stack():
    W, H = 1200, 290
    tools = [("claude", "Claude"), ("python", "Python"), ("typescript", "TypeScript"), ("hugo", "Hugo"),
             ("cloudflare", "Cloudflare"), ("obsidian", "Obsidian"), ("metabase", "Metabase"),
             ("posthog", "PostHog"), ("figma", "Figma"), ("apple", "Apple")]
    cw = (W - 112) / len(tools)
    css = ".lit{animation:lit 10s ease-in-out infinite}@keyframes lit{0%,8%,100%{fill:" + SOFT + "}4%{fill:" + GOLD + "}}"
    body = label(56, W - 56, 76, "العدّة", "04 — TOOLS I THINK WITH")
    body += f'<rect x="56" y="104" width="{W - 112}" height="1" fill="{RULE}"/>'
    for i, (key, name) in enumerate(tools):
        cx = 56 + cw * (i + .5)
        body += (f'<g class="lit" style="animation-delay:{i:.0f}s" fill="{SOFT}">'
                 f'<path d="{ICONS[key]}" transform="translate({cx - 20:.1f} 150) scale({40 / 24:.3f})"/></g>'
                 + T(SANS_R(), name, cx, 234, 18, "middle", FAINT))
    write("stack.svg", svg(W, H, body, "Tools: " + ", ".join(n for _, n in tools), css))


# ── Footer ────────────────────────────────────────────────────────────────

def footer():
    W, H = 1200, 330
    css = (".caret{animation:caret 1.1s steps(1) infinite}@keyframes caret{50%{opacity:0}}")
    en = "Outputs speak."
    ew = SANS_M().width(en, 20, 1)
    body = (f'<rect width="{W}" height="{H}" fill="url(#sebka)" opacity=".06"/>'
            + T(DISP_R(), "“إذا حذفتَ الجملة ولم يلاحظ أحد — احذفها.”", W / 2, 140, 44, "middle", INK)
            + T(MONO(), "— THE DELETION TEST", W / 2 - 8, 190, 14, "end", QUIET, 2.5)
            + T(SANS_M(), "اختبار الحذف", W / 2 + 8, 191, 17, "start", QUIET)
            + f'<rect x="{W / 2 - 24}" y="226" width="48" height="1" fill="{RULE}"/>'
            + T(SANS_M(), en, W / 2 - 8, 274, 20, "middle", FAINT, 1)
            + f'<rect class="caret" x="{W / 2 + ew / 2 - 2:.0f}" y="256" width="10" height="22" fill="{GOLD}"/>')
    write("footer.svg", svg(W, H, body, "If you delete the sentence and nobody notices, delete it. Outputs speak.",
                            css, SEBKA.format(c=GOLD)))


def main():
    hero()
    pills()
    iwork()
    project("card-metabase.svg", "OPEN SOURCE", "metabase-mcp-server",
            "Read-only MCP server for Metabase. Fourteen tools that let an AI agent query your databases "
            "through the Model Context Protocol.",
            ["TYPESCRIPT", "MCP", "METABASE"], icon("metabase", 61, 59, 26, GOLD))
    project("card-cave.svg", "LIVE SITE", "arkanji.com",
            "The cave, Arabic first. Short, sharp essays on product and building. Written in Obsidian, "
            "pushed to GitHub, shipped by Hugo.",
            ["HUGO", "OBSIDIAN", "CLOUDFLARE"], arch(61, 59, 26, GOLD))
    doctrine()
    stack()
    footer()
    essays()


if __name__ == "__main__":
    main()
