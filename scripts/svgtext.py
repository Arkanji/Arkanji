"""Text as SVG paths.

GitHub shows README SVGs as <img>, and an SVG inside <img> can't load web
fonts, so any <text> falls back to whatever the viewer's machine has. Every
word here is shaped with HarfBuzz (so Arabic joins and ligates properly) and
drawn as vector outlines from the blog's own Thmanyah fonts instead.
"""
import os
import urllib.request

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

# The fonts arkanji.com already serves. Downloaded once into .cache/ so the
# repo never redistributes the font files themselves.
FONT_URL = "https://arkanji.com/fonts/{}.woff2"
CACHE = os.path.join(os.path.dirname(__file__), "..", ".cache", "fonts")


def _font_path(name):
    local = os.environ.get("FONT_DIR")
    if local and os.path.exists(os.path.join(local, name + ".woff2")):
        return os.path.join(local, name + ".woff2")
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name + ".woff2")
    if not os.path.exists(path):
        req = urllib.request.Request(FONT_URL.format(name), headers={"User-Agent": "arkanji-profile"})
        with urllib.request.urlopen(req, timeout=30) as r, open(path, "wb") as f:
            f.write(r.read())
    return path


class Face:
    def __init__(self, name):
        self.name = name
        path = _font_path(name)
        self.tt = TTFont(path)
        self.glyphs = self.tt.getGlyphSet()
        self.order = self.tt.getGlyphOrder()
        self.upem = self.tt["head"].unitsPerEm
        # HarfBuzz needs the sfnt bytes; fontTools has already decoded the woff2.
        import io
        buf = io.BytesIO()
        self.tt.flavor = None
        self.tt.save(buf)
        self.hbfont = hb.Font(hb.Face(hb.Blob(buf.getvalue())))
        self._cache = {}

    def _run(self, text, rtl):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        buf.direction = "rtl" if rtl else "ltr"
        hb.shape(self.hbfont, buf, {"kern": True, "liga": True})
        for info in buf.glyph_infos:
            if info.codepoint == 0:
                raise ValueError(f"{self.name} has no glyph for a character in {text!r}")
        return list(buf.glyph_infos), list(buf.glyph_positions)

    def _shape(self, text):
        """Glyphs in visual order, with a minimal bidi pass.

        HarfBuzz shapes one direction at a time, so a line like «أكتوبر 2026»
        is split into runs: Arabic letters RTL, Latin letters and all digits
        (Arabic-Indic too) LTR, spaces and punctuation joining the run before
        them. In a line that starts Arabic the runs are then laid out right to
        left, which is the order a reader meets them.
        """
        def kind(ch):
            o = ord(ch)
            if 0x0660 <= o <= 0x0669 or 0x06F0 <= o <= 0x06F9 or ch.isdigit():
                return "L"
            if 0x0590 <= o <= 0x08FF or 0xFB1D <= o <= 0xFEFC:
                return "R"
            if ch.isalpha():
                return "L"
            return "N"
        runs = []
        for ch in text:
            k = kind(ch)
            if runs and (k == "N" or k == runs[-1][0]):
                runs[-1][1] += ch
            elif not runs and k == "N":
                runs.append(["N", ch])
            elif runs and runs[-1][0] == "N":
                runs[-1] = [k, runs[-1][1] + ch]
            else:
                runs.append([k, ch])
        base_rtl = next((k == "R" for k, _ in runs if k != "N"), False)
        # Trailing neutrals after an LTR run inside RTL text belong to the line,
        # not the number: «2026 ،» must keep its comma on the Arabic side.
        fixed = []
        for k, t in runs:
            if base_rtl and k == "L" and t != t.rstrip():
                core = t.rstrip()
                fixed += [[k, core], ["R", t[len(core):]]]
            else:
                fixed.append([k, t])
        shaped = [self._run(t, k == "R" or (k == "N" and base_rtl)) for k, t in fixed]
        if base_rtl:
            shaped.reverse()
        infos, pos = [], []
        for i, p in shaped:
            infos += i
            pos += p
        return infos, pos

    def width(self, text, size, tracking=0):
        infos, pos = self._shape(text)
        s = size / self.upem
        return sum(p.x_advance for p in pos) * s + tracking * max(len(infos) - 1, 0)

    def path(self, text, x, y, size, anchor="start", tracking=0):
        """SVG path data for `text` with its baseline at y.

        anchor is start/middle/end in visual (left-to-right) terms, so an
        Arabic line anchored "end" sits flush right.
        """
        infos, pos = self._shape(text)
        s = size / self.upem
        w = self.width(text, size, tracking)
        x0 = {"start": x, "middle": x - w / 2, "end": x - w}[anchor]
        out, pen_x = [], 0.0
        for i, (info, p) in enumerate(zip(infos, pos)):
            gname = self.order[info.codepoint]
            gx = x0 + (pen_x + p.x_offset) * s + tracking * i
            gy = y - p.y_offset * s
            spen = SVGPathPen(self.glyphs, ntos=lambda v: ("%.1f" % v).rstrip("0").rstrip("."))
            self.glyphs[gname].draw(TransformPen(spen, (s, 0, 0, -s, gx, gy)))
            d = spen.getCommands()
            if d:
                out.append(d)
            pen_x += p.x_advance
        return "".join(out)

    def fit(self, text, max_w, size, min_size, tracking=0):
        """Largest size <= `size` at which `text` fits, else truncated with …"""
        while size > min_size and self.width(text, size, tracking) > max_w:
            size -= 1
        while self.width(text, size, tracking) > max_w and len(text) > 1:
            text = text[:-2].rstrip() + "…"
        return text, size


_faces = {}


def face(name):
    if name not in _faces:
        _faces[name] = Face(name)
    return _faces[name]
