#!/usr/bin/env python3
"""
flap_logos.py - Soaring Symbols airline SVGs -> single-colour, flap-sized cut
files for a splitflap display (Scott Bezek v2 flaps, 54 x 42.8 mm).

For each airline it:
  1. finds the best source in a soaring-symbols checkout
     (icon-mono, icon, logo-mono, logo, unless you override it),
  2. flattens it to ONE colour by painting the shapes in document order:
     coloured/dark fills add vinyl, white-ish fills cut holes (knockouts),
  3. scales it into the 46 x 76.2 mm safe zone, centred on the seam,
  4. writes <CODE>_cut.svg      one black path, ready for Design Space
            <CODE>_preview.svg  how it looks split across two flaps, with
                                too-thin ink (red) and too-narrow gaps
                                (orange) highlighted
  5. writes index.html with every preview on one page.

Setup (once):
  git clone --depth 1 https://github.com/soaring-symbols/soaring-symbols
  python3 -m venv .venv && . .venv/bin/activate
  pip install svgelements "shapely>=2"

Run:
  python3 flap_logos.py --repo soaring-symbols --out flap_logos
  xdg-open flap_logos/index.html

  python3 flap_logos.py --repo soaring-symbols DAL UAL       # just these
  python3 flap_logos.py --repo soaring-symbols --type logo   # prefer logos
  python3 flap_logos.py --repo soaring-symbols --extra extra # extra/POE.svg etc.
  python3 flap_logos.py --repo soaring-symbols --ink-color "#ffffff" --flap-color "#000000"

Per-airline tweaks go in a JSON file passed with --overrides, e.g.
  {
    "DAL": {"type": "logo"},
    "UAL": {"colors": {"#ffffff": "ink", "#123456": "skip"}},
    "SWA": {"scale": 0.9, "offset": [0, -1.5]},
    "CJT": {"file": "my_svgs/cargojet.svg", "name": "Cargojet"},
    "FDX": {"split": 0.6},
    "FLE": {"split": "rows"},
    "POE": {"split": 0.3, "use": "first"}
  }
  type     icon | logo | tail     which asset to start from
  mono     true | false           use the -mono.svg when there is one
  colors   {"#rrggbb": "ink" | "paper" | "skip", "gradient": ...}
           ink = becomes vinyl, paper = cuts a hole, skip = ignored
  scale    multiplier on the fitted size (for optical tweaks)
  offset   [dx, dy] in mm after fitting (+y moves down)
  file     use this SVG instead of looking the airline up
  slug     soaring-symbols folder name, if the code lookup fails
  split    0-1   cut a one-line logo at the gap between letters nearest
                 this fraction of its width ("Fed" | "Ex")
           rows  cut a two-line logo between its lines
  use      both | first | second   what to do with the split pieces:
           both (default) puts the first piece on the top flap and the
           second on the bottom flap, each filling its own half; first or
           second keeps just that piece (e.g. a symbol beside a wordmark)
"""

import argparse
import html
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from svgelements import SVG, Shape, SVGText, Move, Close, Line
except ImportError:
    sys.exit("svgelements is missing: pip install svgelements")
try:
    from svgelements import SVGImage
except ImportError:
    SVGImage = None
try:
    from shapely.geometry import Polygon, LineString, LinearRing, box
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union
    from shapely.affinity import affine_transform, translate
    from shapely.validation import make_valid
except ImportError:
    sys.exit('shapely is missing: pip install "shapely>=2"')

# Air Canada, WestJet, Porter, Flair, Air Transat,
# Delta, United, American, Southwest, FedEx, UPS
DEFAULT_CODES = ["ACA", "WJA", "POE", "FLE", "TSC",
                 "DAL", "UAL", "AAL", "SWA", "FDX", "UPS", "General-Aviation"]
CORNER_R = 3.18  # CR80 card corner radius, mm
CAPS = {"butt": "flat", "round": "round", "square": "square"}
JOINS = {"miter": "mitre", "miter-clip": "mitre", "round": "round",
         "arcs": "round", "bevel": "bevel"}
EMPTY = Polygon()


@dataclass
class Result:
    code: str
    name: str = ""
    source: str = ""
    size: str = ""
    notes: list = field(default_factory=list)
    error: str = ""


def n(v):
    """Compact number formatting for SVG output."""
    return f"{v:.3f}".rstrip("0").rstrip(".")


# --------------------------------------------------------------- geometry

def polys_only(g):
    """Keep only the polygonal parts of a geometry, as one (Multi)Polygon."""
    if g is None or g.is_empty:
        return EMPTY
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return g
    parts = [p for p in getattr(g, "geoms", [])
             if p.geom_type in ("Polygon", "MultiPolygon")]
    return unary_union(parts) if parts else EMPTY


def iter_polygons(g):
    g = polys_only(g)
    if g.is_empty:
        return []
    return [g] if g.geom_type == "Polygon" else list(g.geoms)


def drop_specks(g, min_area):
    keep = [p for p in iter_polygons(g) if p.area >= min_area]
    return unary_union(keep) if keep else EMPTY


def drop_slivers(g, min_area=0.01):
    """Remove zero-area pieces and holes (mm²) left behind by the boolean
    ops and simplify; Design Space misreads the shapes around them."""
    out = []
    for p in iter_polygons(g):
        if p.area < min_area:
            continue
        holes = [r for r in p.interiors if Polygon(r).area >= min_area]
        out.append(Polygon(p.exterior, holes))
    return unary_union(out) if out else EMPTY


def clean_polygon(pts):
    try:
        p = Polygon(pts)
    except (ValueError, TypeError):
        return EMPTY
    return p if p.is_valid else polys_only(make_valid(p))


def flatten(segs, tol=None, fixed=None):
    """Path segments -> [(points, closed)] per subpath, with curves sampled."""
    rings, cur, closed = [], [], False

    def flush():
        nonlocal cur, closed
        if len(cur) >= 2:
            rings.append((cur, closed))
        cur, closed = [], False

    for s in segs:
        if isinstance(s, Move):
            flush()
            if s.end is not None:
                cur = [(s.end.x, s.end.y)]
            continue
        if not cur and getattr(s, "start", None) is not None:
            cur = [(s.start.x, s.start.y)]
        if isinstance(s, Close):
            if s.end is not None:
                cur.append((s.end.x, s.end.y))
            closed = True
            flush()
        elif isinstance(s, Line):
            cur.append((s.end.x, s.end.y))
        else:  # CubicBezier, QuadraticBezier, Arc
            steps = fixed
            if steps is None:
                try:
                    steps = int(math.ceil(s.length() / tol))
                except Exception:
                    steps = 16
                steps = max(2, min(512, steps))
            for i in range(1, steps + 1):
                p = s.point(i / steps)
                cur.append((p.x, p.y))
    flush()
    return rings


def fill_geometry(rings, rule):
    pieces = []
    for pts in rings:
        if len(pts) < 3:
            continue
        poly = clean_polygon(pts)
        if poly.is_empty or poly.area <= 0:
            continue
        try:
            ccw = LinearRing(pts).is_ccw
        except Exception:
            ccw = True
        pieces.append((poly.area, ccw, poly))
    if not pieces:
        return EMPTY

    g = EMPTY
    if rule == "evenodd":
        for _, _, p in pieces:
            g = g.symmetric_difference(p)
        return polys_only(g)

    # nonzero: approximate winding with ring orientation, biggest ring first
    pieces.sort(key=lambda t: -t[0])
    outer = pieces[0][1]
    for _, ccw, p in pieces:
        if ccw == outer or g.is_empty:
            g = g.union(p)
        elif g.intersection(p).area > 0.5 * p.area:
            g = g.difference(p)   # a hole drawn the other way round
        else:
            g = g.union(p)        # a separate shape that happens to wind backwards
        g = polys_only(g)
    return g


def stroke_geometry(rings, width, cap, join):
    parts = []
    for pts, closed in rings:
        line = pts + [pts[0]] if closed and pts[0] != pts[-1] else pts
        if len(line) >= 2:
            parts.append(LineString(line).buffer(width / 2, cap_style=cap,
                                                 join_style=join))
    return polys_only(unary_union(parts)) if parts else EMPTY


def stroke_width_of(e):
    for attr in ("implicit_stroke_width", "stroke_width"):
        try:
            w = getattr(e, attr)
        except Exception:
            continue
        if w:
            return float(w)
    return 0.0


# ------------------------------------------------------------- SVG -> ink

def paint_role(raw, color, colors, threshold):
    """-> (role, label); role is 'ink', 'paper', 'skip' or None (no paint)."""
    raw = str(raw).strip().lower() if raw is not None else ""
    if raw.startswith("url("):
        return colors.get("gradient", "ink"), "gradient"
    if color is None or getattr(color, "value", None) is None:
        return None, "none"
    if color.alpha == 0:
        return None, "transparent"
    hx = "#%02x%02x%02x" % (color.red, color.green, color.blue)
    role = colors.get(hx)
    if role is None:
        lum = (0.2126 * color.red + 0.7152 * color.green
               + 0.0722 * color.blue) / 255
        role = "paper" if lum >= threshold else "ink"
    return role, hx


def source_to_ink(src, colors, threshold):
    """Paint every shape in order; return the visible 'ink' as one geometry."""
    text = src.read_text(encoding="utf-8", errors="replace")
    notes = []
    if "<clipPath" in text or "<mask" in text:
        notes.append("uses clip paths/masks, which aren't applied; check the preview")
    if "Gradient" in text:
        notes.append("uses gradients (treated as ink unless overridden)")
    try:
        svg = SVG.parse(str(src), reify=True, color="black")  # currentColor -> black
    except TypeError:
        svg = SVG.parse(str(src), reify=True)

    items = []
    for e in svg.elements():
        if isinstance(e, SVGText):
            notes.append("text element ignored; convert text to paths")
            continue
        if SVGImage is not None and isinstance(e, SVGImage):
            notes.append("embedded bitmap ignored")
            continue
        if isinstance(e, Shape):
            try:
                segs = list(e.segments(transformed=True))
            except TypeError:  # older svgelements
                segs = list(e.segments())
            if segs:
                items.append((e, segs))
    if not items:
        raise ValueError("no drawable shapes found")

    # Pass 1: rough bounds, to pick a curve tolerance in the file's own units.
    xs, ys = [], []
    for _, segs in items:
        for pts, _ in flatten(segs, fixed=8):
            xs += [p[0] for p in pts]
            ys += [p[1] for p in pts]
    if not xs:
        raise ValueError("no drawable shapes found")
    tol = (math.hypot(max(xs) - min(xs), max(ys) - min(ys)) or 1.0) / 4000

    # Pass 2: painter's algorithm, fill then stroke, in document order.
    ink, seen = EMPTY, {}
    for e, segs in items:
        rings = flatten(segs, tol=tol)

        role, label = paint_role(e.values.get("fill"), e.fill, colors, threshold)
        if role:
            seen[label] = role
        if role in ("ink", "paper"):
            rule = str(e.values.get("fill-rule", "nonzero")).strip().lower()
            g = fill_geometry([pts for pts, _ in rings], rule)
            ink = ink.union(g) if role == "ink" else ink.difference(g)

        role, label = paint_role(e.values.get("stroke"), e.stroke, colors, threshold)
        width = stroke_width_of(e)
        if role and width > 0:
            seen[label] = role
        if role in ("ink", "paper") and width > 0:
            cap = CAPS.get(str(e.values.get("stroke-linecap", "butt")).strip(), "flat")
            join = JOINS.get(str(e.values.get("stroke-linejoin", "miter")).strip(), "mitre")
            g = stroke_geometry(rings, width, cap, join)
            ink = ink.union(g) if role == "ink" else ink.difference(g)

        ink = polys_only(ink)
    return ink, seen, sorted(set(notes))


# ------------------------------------------------------- fitting / checks

def fit(ink, a, scale=1.0, offset=(0, 0)):
    """Scale uniformly into the safe zone and centre the artwork on the seam."""
    minx, miny, maxx, maxy = ink.bounds
    w, h = maxx - minx, maxy - miny
    if w <= 0 or h <= 0:
        raise ValueError("artwork has no area")
    s = min(a.safe_w / w, a.safe_h / h) * scale
    tx = a.flap_w / 2 - s * (minx + maxx) / 2 + offset[0]
    ty = a.flap_h - s * (miny + maxy) / 2 + offset[1]
    return affine_transform(ink, [s, 0, 0, s, tx, ty])


STACK_MARGIN = 2.0  # mm kept clear on each side of the seam when stacking


def gap_split(ink, frac, axis):
    """Cut at the clear gap between shapes nearest frac (0-1) of the extent
    along axis (0 = left/right, 1 = top/bottom). Returns (first, second)."""
    b = ink.bounds
    lo_i, hi_i = (0, 2) if axis == 0 else (1, 3)
    target = b[lo_i] + frac * (b[hi_i] - b[lo_i])
    merged = []
    for lo, hi in sorted((p.bounds[lo_i], p.bounds[hi_i]) for p in iter_polygons(ink)):
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    gaps = [(m1[1] + m2[0]) / 2 for m1, m2 in zip(merged, merged[1:])]
    if not gaps:
        raise ValueError("split: no clear gap between shapes to cut at")
    g = min(gaps, key=lambda v: abs(v - target))
    pad = (b[2] - b[0]) + (b[3] - b[1]) + 1
    if axis == 0:
        first = box(b[0] - pad, b[1] - pad, g, b[3] + pad)
        second = box(g, b[1] - pad, b[2] + pad, b[3] + pad)
    else:
        first = box(b[0] - pad, b[1] - pad, b[2] + pad, g)
        second = box(b[0] - pad, g, b[2] + pad, b[3] + pad)
    return polys_only(ink.intersection(first)), polys_only(ink.intersection(second))


def stack_layout(top, bottom, a, scale=1.0, offset=(0, 0)):
    """Put one piece on each flap at the same scale, each centred in its half
    of the safe zone, so the seam falls between them instead of through them."""
    half_h = a.safe_h / 2 - STACK_MARGIN
    b1, b2 = top.bounds, bottom.bounds
    w = max(b1[2] - b1[0], b2[2] - b2[0])
    h = max(b1[3] - b1[1], b2[3] - b2[1])
    if w <= 0 or h <= 0:
        raise ValueError("split produced an empty piece")
    s = min(a.safe_w / w, half_h / h) * scale
    cx = a.flap_w / 2 + offset[0]

    def place(g, bb, cy):
        return affine_transform(g, [s, 0, 0, s, cx - s * (bb[0] + bb[2]) / 2,
                                    cy - s * (bb[1] + bb[3]) / 2])

    cy_top = a.flap_h - STACK_MARGIN - half_h / 2 + offset[1]
    cy_bot = a.flap_h + STACK_MARGIN + half_h / 2 + offset[1]
    return polys_only(unary_union([place(top, b1, cy_top), place(bottom, b2, cy_bot)]))


def weeding_check(ink, min_feature):
    """Ink thinner than min_feature, and gaps narrower than it (both in mm)."""
    r = min_feature / 2
    if r <= 0:
        return EMPTY, EMPTY
    opened = ink.buffer(-r, join_style="mitre").buffer(r, join_style="mitre")
    closed = ink.buffer(r, join_style="mitre").buffer(-r, join_style="mitre")
    thin = polys_only(ink.difference(opened))
    gaps = polys_only(closed.difference(ink))
    return drop_specks(thin, r * r), drop_specks(gaps, r * r)


# ---------------------------------------------------------------- output

def path_d(g):
    # Design Space fills by winding direction and ignores fill-rule, so every
    # outline goes one way and every hole the other. Browsers render the same.
    parts = []
    for poly in iter_polygons(g):
        poly = orient(poly, sign=1.0)
        for ring in (poly.exterior, *poly.interiors):
            pts = list(ring.coords)[:-1]
            if len(set(pts)) >= 3 and Polygon(ring).area > 1e-4:
                parts.append("M" + " L".join(f"{n(x)},{n(y)}" for x, y in pts) + "Z")
    return " ".join(parts)


def flap_paths(fw, fh, r=CORNER_R):
    top = (f"M0,{n(fh)} V{n(r)} A{n(r)},{n(r)} 0 0 1 {n(r)},0 H{n(fw - r)} "
           f"A{n(r)},{n(r)} 0 0 1 {n(fw)},{n(r)} V{n(fh)} Z")
    bot = (f"M0,{n(fh)} V{n(2 * fh - r)} A{n(r)},{n(r)} 0 0 0 {n(r)},{n(2 * fh)} "
           f"H{n(fw - r)} A{n(r)},{n(r)} 0 0 0 {n(fw)},{n(2 * fh - r)} V{n(fh)} Z")
    return top, bot


def write_cut(path, ink, a):
    """One <path> per separate piece (an outline plus only its own holes), so
    nothing is nested inside a hole within the same path - e.g. the UPS
    letters inside the shield's knockout are their own paths."""
    w, h = a.flap_w, 2 * a.flap_h
    pieces = "\n".join(f'    <path d="{path_d(p)}"/>' for p in iter_polygons(ink))
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{n(w)}mm" '
        f'height="{n(h)}mm" viewBox="0 0 {n(w)} {n(h)}">\n'
        f'  <g fill="#000000" fill-rule="evenodd">\n{pieces}\n  </g>\n'
        f'</svg>\n', encoding="utf-8")


def write_preview(path, ink, thin, gaps, a):
    fw, fh, gap, pad = a.flap_w, a.flap_h, a.seam_gap, 3.0
    top_box, bot_box = box(0, 0, fw, fh), box(0, fh, fw, 2 * fh)

    def halves(g):
        t = polys_only(g.intersection(top_box))
        b = polys_only(translate(g.intersection(bot_box), 0, gap))
        return (path_d(t) + " " + path_d(b)).strip()

    top, bot = flap_paths(fw, fh)
    W, H = fw + 2 * pad, 2 * fh + gap + 2 * pad
    layers = [
        f'<rect x="{n(-pad)}" y="{n(-pad)}" width="{n(W)}" height="{n(H)}" fill="{a.bezel_color}"/>',
        f'<path d="{top}" fill="{a.flap_color}"/>',
        f'<path d="{bot}" transform="translate(0,{n(gap)})" fill="{a.flap_color}"/>',
        f'<path d="{halves(ink)}" fill="{a.ink_color}" fill-rule="evenodd"/>',
    ]
    if not thin.is_empty:
        layers.append(f'<path d="{halves(thin)}" fill="#e5484d" fill-opacity="0.9" fill-rule="evenodd"/>')
    if not gaps.is_empty:
        layers.append(f'<path d="{halves(gaps)}" fill="#f5a524" fill-opacity="0.9" fill-rule="evenodd"/>')
    body = "\n  ".join(layers)
    path.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{n(W)}mm" height="{n(H)}mm" '
        f'viewBox="{n(-pad)} {n(-pad)} {n(W)} {n(H)}">\n  {body}\n</svg>\n',
        encoding="utf-8")


def write_index(out, results, a):
    cards = []
    for r in results:
        if r.error:
            pic = f'<div class="err">{html.escape(r.error)}</div>'
        else:
            pic = f'<img src="{html.escape(r.code)}_preview.svg" alt="{html.escape(r.code)}">'
        notes = "".join(f'<div class="note">{html.escape(x)}</div>' for x in r.notes)
        cards.append(
            f'<figure>{pic}<figcaption><b>{html.escape(r.code)}</b> {html.escape(r.name)}'
            f'<br><small>{html.escape(r.source)}</small>'
            f'<br><small>{html.escape(r.size)}</small>{notes}</figcaption></figure>')
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Flap logos</title>
<style>
  body {{ background:#161616; color:#ddd; font:14px/1.4 system-ui, sans-serif; margin:24px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill, minmax(170px, 1fr)); gap:24px; }}
  figure {{ margin:0; }}
  img {{ width:100%; height:auto; display:block; }}
  small {{ color:#999; }}
  .note {{ color:#f5a524; font-size:12px; }}
  .err {{ color:#e5484d; padding:40px 8px; border:1px dashed #555; }}
  .key span {{ display:inline-block; width:10px; height:10px; margin:0 4px 0 12px; }}
</style></head><body>
<h1>Flap logos</h1>
<p class="key">Minimum feature {n(a.min_feature)} mm:
<span style="background:#e5484d"></span>ink too thin
<span style="background:#f5a524"></span>gap too narrow</p>
<div class="grid">
{chr(10).join(cards)}
</div></body></html>
"""
    (out / "index.html").write_text(page, encoding="utf-8")


# ------------------------------------------------------------------ main

def load_airlines(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        if isinstance(data.get("airlines"), list):
            data = data["airlines"]
        else:  # keyed by slug
            data = [dict(v, slug=v.get("slug", k)) for k, v in data.items()
                    if isinstance(v, dict)]
    idx = {}
    for al in data if isinstance(data, list) else []:
        if not isinstance(al, dict):
            continue
        keys = [str(al.get("icao") or "").upper(),
                str(al.get("iata") or "").upper(),
                str(al.get("slug") or "").lower()]
        for k in filter(None, keys):
            prev = idx.get(k)
            # a code shared with a defunct airline belongs to the active one
            if prev is None or (prev.get("defunct") and not al.get("defunct")):
                idx[k] = al
    return idx


def pick_source(folder, kind, mono):
    order = [kind] + [k for k in ("icon", "logo") if k != kind]
    for k in order:
        names = [f"{k}-mono.svg", f"{k}.svg"] if mono else [f"{k}.svg", f"{k}-mono.svg"]
        for name in names:
            p = folder / name
            if p.is_file():
                return p
    return None


def process(code, ov, db, repo, out, a):
    res = Result(code)
    extra = Path(a.extra).expanduser() / f"{code}.svg" if a.extra else None
    if ov.get("file"):
        src = Path(ov["file"]).expanduser()
        res.name = ov.get("name", code)
    elif extra is not None and extra.is_file():
        src = extra
        res.name = ov.get("name") or db.get(code, {}).get("name", code)
    else:
        al = db.get(code) or (db.get(str(ov["slug"]).lower()) if ov.get("slug") else None)
        if al is None:
            raise LookupError(f"not in soaring-symbols; put {code}.svg in your --extra folder")
        res.name = al.get("name", code)
        slug = ov.get("slug", al.get("slug"))
        src = pick_source(repo / "assets" / slug, ov.get("type", a.type),
                          ov.get("mono", not a.no_mono))
        if src is None:
            raise FileNotFoundError(f"no icon/logo SVG in assets/{slug}/")
    if not src.is_file():
        raise FileNotFoundError(f"{src} not found")
    try:
        res.source = str(src.relative_to(repo))
    except ValueError:
        res.source = str(src)

    colors = {str(k).lower(): v for k, v in ov.get("colors", {}).items()}
    ink, seen, notes = source_to_ink(src, colors,
                                     ov.get("paper_threshold", a.paper_threshold))
    res.notes += notes
    if ink.is_empty:
        raise ValueError("nothing left to cut; every colour became paper or skip")

    scale, offset = ov.get("scale", 1.0), ov.get("offset", (0, 0))
    split, use = ov.get("split"), ov.get("use", "both")
    if split:
        if split == "rows":
            first, second = gap_split(ink, 0.5, axis=1)
        else:
            first, second = gap_split(ink, 0.5 if split is True else float(split), axis=0)
        if use == "first":
            ink = fit(first, a, scale, offset)
        elif use == "second":
            ink = fit(second, a, scale, offset)
        else:
            ink = stack_layout(first, second, a, scale, offset)
    else:
        ink = fit(ink, a, scale, offset)
    if a.thicken > 0:
        ink = polys_only(ink.buffer(a.thicken / 2, join_style="mitre"))
    ink = drop_slivers(polys_only(ink.simplify(0.005, preserve_topology=True)))
    thin, gaps = weeding_check(ink, a.min_feature)

    write_cut(out / f"{code}_cut.svg", ink, a)
    write_preview(out / f"{code}_preview.svg", ink, thin, gaps, a)

    minx, miny, maxx, maxy = ink.bounds
    res.size = f"{maxx - minx:.1f} x {maxy - miny:.1f} mm"
    if thin.area > 0:
        res.notes.append(f"thin ink: {thin.area:.1f} mm²")
    if gaps.area > 0:
        res.notes.append(f"narrow gaps: {gaps.area:.1f} mm²")
    roles = ", ".join(f"{k}->{v}" for k, v in sorted(seen.items()))
    print(f"{code:4} {res.name[:26]:26} {res.source[:38]:38} {res.size:15} {roles}")
    for x in res.notes:
        print(f"     - {x}")
    return res


def parse_args():
    p = argparse.ArgumentParser(
        description="Make flap-sized, single-colour cut files from Soaring Symbols SVGs.",
        epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("codes", nargs="*", help="ICAO or IATA codes (default: the 13 picks)")
    p.add_argument("--repo", default="soaring-symbols", help="soaring-symbols checkout")
    p.add_argument("--out", default="flap_logos", help="output folder")
    p.add_argument("--type", default="icon", choices=["icon", "logo", "tail"],
                   help="asset to prefer (default: icon)")
    p.add_argument("--no-mono", action="store_true",
                   help="start from the colour files instead of -mono.svg")
    p.add_argument("--safe-w", type=float, default=46.0, help="safe zone width, mm")
    p.add_argument("--safe-h", type=float, default=76.2, help="safe zone height, mm")
    p.add_argument("--flap-w", type=float, default=54.0, help="flap width, mm")
    p.add_argument("--flap-h", type=float, default=42.8, help="flap height, mm")
    p.add_argument("--paper-threshold", type=float, default=0.92,
                   help="luminance 0-1 at or above which a colour cuts a hole")
    p.add_argument("--min-feature", type=float, default=0.8,
                   help="mm; thinner ink or narrower gaps get flagged")
    p.add_argument("--thicken", type=float, default=0.0,
                   help="mm added to every stroke width (outset) in the cut file")
    p.add_argument("--seam-gap", type=float, default=1.0,
                   help="mm gap between the flaps in the preview")
    p.add_argument("--ink-color", default="#111111", help="preview vinyl colour")
    p.add_argument("--flap-color", default="#ffffff", help="preview flap colour")
    p.add_argument("--bezel-color", default="#2b2b2b", help="preview background")
    p.add_argument("--overrides", help="JSON file of per-airline tweaks")
    p.add_argument("--extra", help="folder of your own SVGs named <CODE>.svg, "
                                   "used instead of the repo (e.g. extra/POE.svg)")
    return p.parse_args()


def main():
    a = parse_args()
    repo = Path(a.repo).expanduser()
    db_file = repo / "airlines.json"
    if db_file.is_file():
        db = load_airlines(db_file)
    else:
        print(f"warning: {db_file} not found; only 'file' overrides will work",
              file=sys.stderr)
        db = {}
    overrides = {}
    if a.overrides:
        raw = json.loads(Path(a.overrides).expanduser().read_text(encoding="utf-8"))
        overrides = {k.upper(): v for k, v in raw.items()}
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    results, failed = [], 0
    for code in [c.upper() for c in (a.codes or DEFAULT_CODES)]:
        try:
            results.append(process(code, overrides.get(code, {}), db, repo, out, a))
        except Exception as ex:
            failed += 1
            print(f"{code:4} FAILED: {ex}", file=sys.stderr)
            results.append(Result(code, name=db.get(code, {}).get("name", ""),
                                  error=str(ex)))
    write_index(out, results, a)
    print(f"\n{len(results) - failed} done, {failed} failed -> {out / 'index.html'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())