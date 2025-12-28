import json
import subprocess
from pathlib import Path
import math
import random


# =========================
# (OPTIONAL / Legacy) STL pipeline - keep if you still want STL later
# =========================
OPENSCAD_BIN = r"C:\Program Files\OpenSCAD\openscad.exe"
TEMPLATE_SCAD = Path("scad") / "keychain_template.scad"
OUT_DIR = Path("generated_stl")
OUT_DIR.mkdir(exist_ok=True)

def generate_stl(recipe: dict, out_name: str) -> Path:
    """
    Legacy: recipe -> STL via OpenSCAD template.
    Not used in SCAD-only pipeline.
    """
    out_path = OUT_DIR / f"{out_name}.stl"

    deform = recipe.get("deformations", {}) or {}
    holes = recipe.get("holes", []) or []

    holes_arr = []
    for h in holes:
        c = h.get("center", {}) or {}
        holes_arr.append([
            float(c.get("x_mm", 0.0)),
            float(c.get("y_mm", 0.0)),
            float(h.get("radius_mm", 2.6)),
        ])

    base_form = str(recipe.get("base_form", "circle")).strip().lower()
    base_form_def = f'base_form="{base_form}"'

    sides = recipe.get("rounded_polygon_sides", 8)
    if sides is None:
        sides = 8

    sym = recipe.get("symmetry", {}) or {}
    sym_n = int(sym.get("n", recipe.get("sym_n", 7)) or 7)

    cmd = [
        OPENSCAD_BIN,
        "-o", str(out_path),
        "-D", base_form_def,
        "-D", f"size_mm={float(recipe.get('size_mm', 38))}",
        "-D", f"thickness_mm={float(recipe.get('thickness_mm', 4.0))}",
        "-D", f"rounded_polygon_sides={int(sides)}",
        "-D", f"fillet_mm={float(recipe.get('fillet_mm', 2.0))}",
        "-D", f"twist_deg={int(deform.get('twist_deg', recipe.get('twist_deg', 0)) or 0)}",
        "-D", f"noise_amp_mm={float(deform.get('noise_amp_mm', recipe.get('noise_amp_mm', 0.0)) or 0.0)}",
        "-D", f"noise_seed={int(deform.get('noise_seed', recipe.get('noise_seed', 1337)) or 1337)}",
        "-D", f"sym_n={sym_n}",
        "-D", f"holes={json.dumps(holes_arr)}",
        str(TEMPLATE_SCAD),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "OpenSCAD failed\n"
            f"CMD: {' '.join(cmd)}\n"
            f"STDERR:\n{result.stderr}\n"
            f"STDOUT:\n{result.stdout}"
        )
    return out_path


# =========================
# NEW: SCAD-only writer from LLM "pts"
# =========================
SCAD_OUT_DIR = Path("scad_out")
SCAD_OUT_DIR.mkdir(exist_ok=True)


def _normalize_pts(pts, target_radius_mm: float = 22.0):
    """
    Scales points so that max radius becomes target_radius_mm.
    This makes outputs consistent across LLM responses.
    """
    max_r = 1e-9
    for x, y in pts:
        r = math.sqrt(x*x + y*y)
        if r > max_r:
            max_r = r
    s = target_radius_mm / max_r
    return [[round(x*s, 4), round(y*s, 4)] for x, y in pts]


def generate_scad_from_spec(spec: dict, out_name: str, thickness_mm: float = 4.2) -> Path:
    """
    SCAD-only output.
    Input spec must include:
      - pts: [[x,y], ...] (closed contour)
      - holes: [{x_mm,y_mm,r_mm}] EXACTLY 1
      - thickness_mm optional (else argument)
    """

    scad_path = SCAD_OUT_DIR / f"{out_name}.scad"

    # ---- pts ----
    pts = spec.get("pts", None)
    if not isinstance(pts, list) or len(pts) < 160:
        raise ValueError("spec.pts missing or too short")

    pts_xy = []
    for p in pts:
        if not isinstance(p, list) or len(p) != 2:
            raise ValueError("Each pts entry must be [x,y]")
        x = float(p[0]); y = float(p[1])
        pts_xy.append([x, y])

    # normalize size (important: makes heart/bolt recognizable & printable)
    target_radius = float(spec.get("radius_mm", 22.0))
    pts_xy = _normalize_pts(pts_xy, target_radius_mm=target_radius)

    # ---- thickness ----
    t = float(spec.get("thickness_mm", thickness_mm))
    t = max(3.2, min(5.2, t))

    # ---- hole (exactly 1) ----
    holes = spec.get("holes", [])
    if not isinstance(holes, list) or len(holes) != 1:
        raise ValueError("spec.holes must be a list with EXACTLY 1 hole")

    h = holes[0]
    hx = float(h.get("x_mm", 0.0))
    hy = float(h.get("y_mm", 16.0))
    hr = float(h.get("r_mm", 2.6))

    # ---- build .scad ----
    lines = []
    lines.append("$fn=96;")
    lines.append(f"thickness_mm = {t};")
    lines.append(f"pts = {json.dumps(pts_xy)};")
    lines.append(f"hole = [{hx}, {hy}, {hr}];")

    lines.append("module shape2d(){")
    lines.append("  // Fix: clean self-intersections / bad contours for CGAL render")
    lines.append("  offset(r=0.35) offset(r=-0.35)")
    lines.append("    polygon(points=pts, paths=[[for(i=[0:len(pts)-1]) i]]);")
    lines.append("}")

    lines.append("module body(){")
    lines.append("  linear_extrude(height=thickness_mm, convexity=10)")
    lines.append("    shape2d();")
    lines.append("}")

    lines.append("difference(){")
    lines.append("  body();")
    lines.append("  translate([hole[0], hole[1], -1])")
    lines.append("    cylinder(h=thickness_mm+2, r=hole[2]);")
    lines.append("}")

    scad_path.write_text("\n".join(lines), encoding="utf-8")
    return scad_path
