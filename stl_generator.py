import json
import math
from pathlib import Path


SCAD_OUT_DIR = Path("scad_out")
SCAD_OUT_DIR.mkdir(exist_ok=True)


# -----------------------
# shape generators (pts)
# -----------------------
def _rotate_pts(pts, deg: float):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    out = []
    for x, y in pts:
        out.append([x * c - y * s, x * s + y * c])
    return out


def _scale_pts(pts, sx: float, sy: float):
    return [[x * sx, y * sy] for x, y in pts]


def _normalize_to_radius(pts, target_r: float = 22.0):
    max_r = 1e-9
    for x, y in pts:
        r = math.hypot(x, y)
        if r > max_r:
            max_r = r
    s = target_r / max_r
    return [[round(x * s, 4), round(y * s, 4)] for x, y in pts]


def _heart_pts(n: int, aspect: float, jitter: float, seed: int):
    """
    Classic param heart, then aspect/jitter.
    """
    n = max(260, min(340, int(n)))
    rnd = (seed % 10000) / 10000.0

    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * (math.sin(t) ** 3)
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)

        # mild jitter for uniqueness, but keep heart recognizable
        j = (jitter * 0.9) * (0.35 * math.sin(7 * t + 6.0 * rnd) + 0.25 * math.sin(11 * t + 3.0 * rnd))
        x *= (1.0 + j * 0.08)
        y *= (1.0 + j * 0.08)

        pts.append([x, y])

    # aspect (elongate one axis)
    pts = _scale_pts(pts, sx=1.0, sy=aspect)
    return pts


def _face_outline_pts(n: int, aspect: float, roundness: float, seed: int):
    """
    Face silhouette as a superellipse-like outline.
    roundness higher => rounder; lower => squarer but still soft.
    Unique by seed via tiny phase/asymmetry without breaking printability.
    """
    n = max(260, min(340, int(n)))
    roundness = max(0.25, min(1.2, float(roundness)))

    # superellipse exponent: bigger => squarer; smaller => rounder
    m = 2.8 + (1.0 / roundness) * 3.2   # ~5.5..15
    m = max(3.0, min(12.0, m))

    rnd = (seed % 100000) / 100000.0
    phase = 2 * math.pi * ((seed % 997) / 997.0)

    a = 22.0
    b = 22.0 * aspect

    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        ct, st = math.cos(t), math.sin(t)

        # slight asymmetry (unique) but tiny
        asym = 1.0 + 0.03 * math.sin(3 * t + phase) + 0.02 * math.sin(5 * t + 7 * rnd)

        denom = (abs(ct) / (a + 1e-9)) ** m + (abs(st) / (b + 1e-9)) ** m
        r = (1.0 / (denom + 1e-12)) ** (1.0 / m)

        x = r * ct * asym
        y = r * st * (1.0 - 0.02 * math.sin(2 * t + phase))  # tiny squash variation

        pts.append([x, y])

    return pts


def _starburst_pts(n: int, spikes: int, spikiness: float, jitter: float, seed: int):
    """
    Energetic radial burst (printable) - UNIQUE by seed.
    Adds seed-based phase shifts + secondary harmonic + per-lobe weighting.
    """
    n = max(260, min(360, int(n)))
    spikes = max(6, min(16, int(spikes)))
    spikiness = max(0.0, min(1.0, float(spikiness)))
    jitter = max(0.0, min(1.0, float(jitter)))

    rnd = (seed % 100000) / 100000.0
    phase1 = 2 * math.pi * ((seed % 997) / 997.0)
    phase2 = 2 * math.pi * ((seed % 611) / 611.0)

    k2 = spikes + 2 + (seed % 4)  # spikes+2..spikes+5
    base_r = 22.0

    lobe_w = []
    for i in range(spikes):
        w = 1.0 + 0.15 * math.sin(phase2 + i * (2 * math.pi / spikes))
        lobe_w.append(max(0.85, min(1.15, w)))

    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n

        spike_idx = int((t / (2 * math.pi)) * spikes) % spikes
        w = lobe_w[spike_idx]

        w1 = math.sin(spikes * t + phase1)
        w2 = 0.45 * math.sin(k2 * t + phase2)
        noise = 0.18 * jitter * math.sin((spikes + 7) * t + 9 * rnd)

        r = base_r * (1.0 + (0.18 + 0.22 * spikiness) * (w1 + w2) * w)
        r *= (1.0 + noise)

        pts.append([r * math.cos(t), r * math.sin(t)])

    return pts


def _blob_pts(n: int, aspect: float, roundness: float, jitter: float, seed: int):
    """
    Calm/neutral blob. Roundness controls how smooth (lower = more wavy).
    """
    n = max(240, min(340, int(n)))
    roundness = max(0.15, min(1.2, float(roundness)))
    jitter = max(0.0, min(1.0, float(jitter)))
    rnd = (seed % 10000) / 10000.0

    base_r = 22.0
    k1 = 4 + (seed % 4)    # 4..7
    k2 = 7 + (seed % 5)    # 7..11

    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        wav = (0.22 * (1.0 / roundness)) * math.sin(k1 * t + 2.2 * rnd) + (0.12 * jitter) * math.sin(k2 * t + 5.1 * rnd)
        r = base_r * (1.0 + wav)
        x = r * math.cos(t)
        y = r * math.sin(t)
        pts.append([x, y])

    pts = _scale_pts(pts, sx=1.0, sy=aspect)
    return pts


def _bolt_pts(aspect: float, jitter: float, seed: int):
    """
    Lightning bolt polygon (angular) - UNIQUE by seed.
    """
    rnd = (seed % 100000) / 100000.0
    j = 1.0 + 0.35 * jitter * (rnd - 0.5)

    dx1 = 2.5 * (rnd - 0.5)
    dx2 = 3.0 * math.sin(2 * math.pi * rnd)
    dy1 = 2.0 * math.cos(2 * math.pi * rnd)

    pts = [
        [-10 * j + dx1,  20 + dy1],
        [ -2 * j + dx2,  20],
        [-11 * j,         2 + dy1],
        [  2 * j,         2],
        [ -3 * j + dx1, -20],
        [ 10 * j + dx2,  -2 + dy1],
        [  2 * j,        -2],
        [ 10 * j,         20 + dy1],
        [  0 * j,         20],
        [  0 * j,         26 + dy1],
        [-14 * j + dx1,   26],
    ]

    pts = _scale_pts(pts, sx=1.0, sy=aspect)
    return pts


# -----------------------
# HOLE placement helpers (FIX)
# -----------------------
def _polygon_centroid(pts):
    # simple average centroid (good enough for our shapes)
    cx = sum(p[0] for p in pts) / max(1, len(pts))
    cy = sum(p[1] for p in pts) / max(1, len(pts))
    return cx, cy


def _shrink_polygon(pts, factor: float):
    cx, cy = _polygon_centroid(pts)
    out = []
    for x, y in pts:
        out.append([cx + (x - cx) * factor, cy + (y - cy) * factor])
    return out


def _point_in_poly(x, y, poly):
    # ray casting
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) + 1e-12) + xi)
        if intersect:
            inside = not inside
        j = i
    return inside


def _pick_hole_center(pts, hr: float):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)

    # güvenli iç bölge: kenardan ~ (hr + 3.5) mm uzak dur
    margin = hr + 3.5
    # target_r = 22 olduğuna göre factor ~ 0.7 civarı ideal
    factor = max(0.60, min(0.82, 1.0 - (margin / 22.0)))
    safe_poly = _shrink_polygon(pts, factor=factor)

    inward = hr + 6.5  # senin istediğin "daha içeri"
    candidates = [
        (0.0, maxy - inward),              # TOP-CENTER (en güvenlisi)
        (maxx - inward, maxy - inward),    # TOP-RIGHT
        (minx + inward, maxy - inward),    # TOP-LEFT
        (0.0, (maxy + miny) / 2.0),        # MID-CENTER
    ]

    for hx, hy in candidates:
        if _point_in_poly(hx, hy, safe_poly):
            return float(hx), float(hy)

    # hiçbir aday tutmazsa: merkezden yukarı doğru tarayıp ilk içeri gireni seç
    cx, cy = _polygon_centroid(pts)
    for step in range(0, 30):
        hy = cy + (maxy - cy) * (step / 30.0)
        hx = cx
        if _point_in_poly(hx, hy, safe_poly):
            return float(hx), float(hy)

    # worst-case fallback
    return 0.0, 16.0


# -----------------------
# SCAD writer
# -----------------------
def generate_scad_from_spec(spec: dict, out_name: str, thickness_mm: float = 4.2) -> Path:
    """
    SCAD-only output.
    Spec contains: emotion_tag, symbol, seed, params, holes[1], thickness_mm
    """
    scad_path = SCAD_OUT_DIR / f"{out_name}.scad"

    symbol = (spec.get("symbol") or "blob").strip().lower()
    emotion = (spec.get("emotion_tag") or "neutral").strip().lower()
    seed = int(spec.get("seed", 0) or 0)
    p = spec.get("params", {}) or {}

    # params
    aspect = float(p.get("aspect", 1.0))
    roundness = float(p.get("roundness", 0.7))
    rotation_deg = float(p.get("rotation_deg", 0.0))
    spikes = int(p.get("spikes", 10))
    spikiness = float(p.get("spikiness", 0.5))
    jitter = float(p.get("jitter", 0.3))
    mouth_curve = float(p.get("mouth_curve", -0.6))
    eye_size = float(p.get("eye_size", 0.16))
    mouth_width = float(p.get("mouth_width", 0.55))

    # thickness
    t = float(spec.get("thickness_mm", thickness_mm))
    t = max(3.2, min(5.2, t))

    # hole radius from spec (keep your behavior)
    holes = spec.get("holes", [])
    if not isinstance(holes, list) or len(holes) != 1:
        hr = 2.6
    else:
        h = holes[0]
        hr = float(h.get("r_mm", 2.6))

    # build pts by symbol
    if symbol == "heart":
        pts = _heart_pts(n=300, aspect=aspect, jitter=jitter, seed=seed)
    elif symbol == "face":
        pts = _face_outline_pts(n=300, aspect=aspect, roundness=roundness, seed=seed)
    elif symbol == "starburst":
        pts = _starburst_pts(n=320, spikes=spikes, spikiness=spikiness, jitter=jitter, seed=seed)
    elif symbol == "bolt":
        pts = _bolt_pts(aspect=aspect, jitter=jitter, seed=seed)
    else:
        pts = _blob_pts(n=300, aspect=aspect, roundness=roundness, jitter=jitter, seed=seed)

    # rotate + normalize radius
    pts = _rotate_pts(pts, rotation_deg)
    pts = _normalize_to_radius(pts, target_r=22.0)

    # -----------------------
    # AUTO keychain hole placement (FIXED: always inside)
    # -----------------------
    hx, hy = _pick_hole_center(pts, hr)

    # offset_r controls smoothing & CGAL stability
    if emotion in ("energetic", "joyful", "angry"):
        offset_r = 0.18 + 0.18 * (1.0 - roundness)  # sharper
    elif emotion in ("depressed", "calm", "anxious"):
        offset_r = 0.65 + 0.35 * roundness          # rounder
    else:
        offset_r = 0.35 + 0.25 * roundness

    offset_r = max(0.12, min(1.15, offset_r))

    # Face engrave params (top carving, not holes)
    engrave_depth = 0.9  # mm
    eye_r = max(1.4, min(3.2, eye_size * 14.0))
    eye_x = 6.5
    eye_y = 4.8

    mouth_y = -6.5
    mouth_r = 10.0 + 6.0 * (1.0 - abs(mouth_curve))  # 10..16
    mouth_w = max(8.0, min(16.0, mouth_width * 20.0))
    mouth_thick = 1.6

    if mouth_curve > 0.15:
        mouth_y = -5.5
    if mouth_curve < -0.15:
        mouth_y = -7.5

    mouth_center_shift = 5.5 if mouth_curve < 0 else -5.5

    # SCAD output
    lines = []
    lines.append("$fn=96;")
    lines.append(f"thickness_mm = {round(t, 4)};")
    lines.append(f"pts = {json.dumps(pts)};")
    lines.append(f"hole = [{round(hx,4)}, {round(hy,4)}, {round(hr,4)}];")
    lines.append(f"offset_r = {round(offset_r,4)};")
    lines.append(f"engrave_depth = {round(engrave_depth,4)};")

    lines.append("module shape2d(){")
    lines.append("  // CGAL clean + controlled smooth/sharp")
    lines.append("  offset(r=offset_r) offset(r=-offset_r)")
    lines.append("    polygon(points=pts, paths=[[for(i=[0:len(pts)-1]) i]]);")
    lines.append("}")

    lines.append("module body(){")
    lines.append("  linear_extrude(height=thickness_mm, convexity=10)")
    lines.append("    shape2d();")
    lines.append("}")

    # face engrave (shallow carving)
    lines.append("module face_engrave(){")
    lines.append("  // eyes")
    lines.append(f"  translate([{eye_x}, {eye_y}, thickness_mm-engrave_depth]) cylinder(h=engrave_depth+0.2, r={round(eye_r,4)});")
    lines.append(f"  translate([{-eye_x}, {eye_y}, thickness_mm-engrave_depth]) cylinder(h=engrave_depth+0.2, r={round(eye_r,4)});")
    lines.append("")
    lines.append("  // mouth arc band (2D ring section extruded shallow)")
    lines.append(f"  translate([0, {round(mouth_y,4)}, thickness_mm-engrave_depth])")
    lines.append("    linear_extrude(height=engrave_depth+0.2)")
    lines.append("      intersection(){")
    lines.append(f"        square([{round(mouth_w,4)}, {round(mouth_w,4)}], center=true);")
    lines.append("        difference(){")
    lines.append(f"          translate([0,{round(mouth_center_shift,4)}]) circle(r={round(mouth_r,4)});")
    lines.append(f"          translate([0,{round(mouth_center_shift,4)}]) circle(r={round(mouth_r - mouth_thick,4)});")
    lines.append("        }")
    lines.append("      };")
    lines.append("}")

    lines.append("difference(){")
    lines.append("  body();")
    lines.append("  // keychain hole (exactly 1) - ALWAYS inside now")
    lines.append("  translate([hole[0], hole[1], -1]) cylinder(h=thickness_mm+2, r=hole[2]);")

    if symbol == "face":
        lines.append("  // shallow engrave details (not extra holes)")
        lines.append("  face_engrave();")

    lines.append("}")

    scad_path.write_text("\n".join(lines), encoding="utf-8")
    return scad_path
