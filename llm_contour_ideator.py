import os
import json
import math
from typing import Any, Dict, Optional, List
from groq import Groq


# -----------------------
# helpers
# -----------------------
def _safe_json(s: str) -> Dict[str, Any]:
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.strip("`").strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    return json.loads(s)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v)))


def _max_abs_xy(pts: List[List[float]]) -> float:
    m = 0.0
    for x, y in pts:
        m = max(m, abs(float(x)), abs(float(y)))
    return m


def _rescale_pts_to_limit(pts: List[List[float]], limit: float = 60.0) -> List[List[float]]:
    m = _max_abs_xy(pts)
    if m <= limit:
        return [[round(float(x), 4), round(float(y), 4)] for x, y in pts]
    scale = limit / (m + 1e-9)
    return [[round(float(x) * scale, 4), round(float(y) * scale, 4)] for x, y in pts]


def _validate_spec(spec: Dict[str, Any]) -> None:
    for k in ["emotion_tag", "symbol", "seed", "pts", "holes"]:
        if k not in spec:
            raise ValueError(f"Missing key: {k}")

    pts = spec["pts"]
    if not isinstance(pts, list) or len(pts) < 160:
        raise ValueError("pts must be a list with at least 160 points")

    for p in pts:
        if not (isinstance(p, list) or isinstance(p, tuple)) or len(p) != 2:
            raise ValueError("each pts element must be [x,y]")
        x, y = p
        if abs(float(x)) > 80 or abs(float(y)) > 80:
            raise ValueError("pts coordinates too large; keep within [-80,80]")

    holes = spec["holes"]
    if not isinstance(holes, list) or len(holes) != 1:
        raise ValueError("holes must be a list with EXACTLY 1 hole")

    h = holes[0]
    for k in ["x_mm", "y_mm", "r_mm"]:
        if k not in h:
            raise ValueError(f"hole missing {k}")

    r = float(h["r_mm"])
    y = float(h["y_mm"])
    if not (2.2 <= r <= 3.0):
        raise ValueError("hole r_mm must be in [2.2, 3.0]")
    if y <= 0:
        raise ValueError("hole y_mm must be positive")


def _build_prompt(user_text: str, seed: int, pref_json: str, strict: bool) -> str:
    size_hint = (
        "MUST keep ALL coordinates within [-35,35]. "
        "MUST output 260..320 points. "
        if strict else
        "Keep coordinates roughly within [-45,45] (hard limit [-80,80]). "
        "Output 220..360 points. "
    )

    return f"""
User text: {user_text}
Seed (MUST use exactly): {seed}
Preferences: {pref_json}

Pick emotion_tag from:
love | energetic | depressed | calm | anxious | angry | joyful | neutral

Pick a recognizable symbol:
love->heart, energetic->bolt/sunburst, depressed->wave/droop,
calm->circle/smooth_drop, anxious->spike_wave, angry->spike/flame, joyful->star/flower, neutral->blob

Generate CLOSED contour as "pts" list of [x,y] points.
{size_hint}
- pts must be a smooth outline, not self-intersecting.
- Coordinates centered around (0,0).
- Even same emotion must differ across seeds (change lobes, angles, proportions).

Holes:
- EXACTLY 1 hole
- x_mm in [-6,6], y_mm in [10,22], r_mm in [2.2,3.0]

Return ONLY JSON with exactly keys:
{{
  "emotion_tag":"...",
  "symbol":"...",
  "seed":{seed},
  "pts":[[0,0],[1,0.2],...],
  "holes":[{{"x_mm":0.0,"y_mm":16.0,"r_mm":2.6}}],
  "thickness_mm":4.2
}}
""".strip()


# -----------------------
# fallback generators (no LLM) -> never fails
# -----------------------
def _fallback_pts(symbol: str, n: int, seed: int) -> List[List[float]]:
    # deterministic tiny variation by seed
    rnd = (seed % 1000) / 1000.0
    n = max(220, min(360, int(n)))

    pts = []

    if symbol == "heart":
        # classic parametric heart
        for i in range(n):
            t = 2 * math.pi * i / n
            x = 16 * math.sin(t) ** 3
            y = 13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t)
            # scale + slight variation
            s = 0.9 + 0.12 * rnd
            pts.append([x * s, y * s])
    elif symbol in ("bolt", "sunburst"):
        # star-ish burst
        k = 10 + int(4 * rnd)
        for i in range(n):
            t = 2 * math.pi * i / n
            r = 22 * (1 + 0.25 * math.sin(k * t))
            pts.append([r * math.cos(t), r * math.sin(t)])
    elif symbol in ("wave", "droop"):
        # wavy blob
        k = 5 + int(3 * rnd)
        for i in range(n):
            t = 2 * math.pi * i / n
            r = 22 * (1 + 0.18 * math.sin(k * t + 1.7))
            pts.append([r * math.cos(t), r * math.sin(t)])
    else:
        # default blob
        k = 6 + int(3 * rnd)
        for i in range(n):
            t = 2 * math.pi * i / n
            r = 22 * (1 + 0.12 * math.sin(k * t + 0.9))
            pts.append([r * math.cos(t), r * math.sin(t)])

    # clamp to float + scale small
    pts = _rescale_pts_to_limit(pts, limit=50.0)
    return pts


def _fallback_spec(user_text: str, seed: int) -> Dict[str, Any]:
    text = (user_text or "").lower()
    if "love" in text or "miss" in text or "warm" in text:
        emo, sym = "love", "heart"
    elif "ener" in text or "run" in text or "power" in text:
        emo, sym = "energetic", "bolt"
    elif "sad" in text or "depress" in text or "empty" in text:
        emo, sym = "depressed", "wave"
    else:
        emo, sym = "neutral", "blob"

    pts = _fallback_pts(sym, n=280, seed=seed)

    return {
        "emotion_tag": emo,
        "symbol": sym,
        "seed": int(seed),
        "pts": pts,
        "holes": [{"x_mm": 0.0, "y_mm": 16.0, "r_mm": 2.6}],
        "thickness_mm": 4.2,
    }


# -----------------------
# main
# -----------------------
def generate_contour_spec(
    *,
    user_text: str,
    seed: int,
    preferences: Optional[Dict[str, Any]] = None,
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 1.05,
) -> Dict[str, Any]:
    key = os.getenv("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY missing")
    client = Groq(api_key=key)

    pref_json = json.dumps(preferences or {}, ensure_ascii=False)

    system = (
        "You generate 2D CLOSED contours for 3D printable keychains. "
        "Return ONLY valid JSON. No markdown. No extra text."
    )

    # 3 attempts, then fallback
    attempts = [
        _build_prompt(user_text, seed, pref_json, strict=False),
        _build_prompt(user_text, seed, pref_json, strict=True),
        _build_prompt(user_text + " (IMPORTANT: output 300 points)", seed, pref_json, strict=True),
    ]

    last_err = None
    for prompt in attempts:
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                temperature=temperature,
            )
            raw = resp.choices[0].message.content or ""
            spec = _safe_json(raw)
            spec["seed"] = int(seed)

            if "thickness_mm" not in spec:
                spec["thickness_mm"] = 4.2
            spec["thickness_mm"] = _clamp(spec["thickness_mm"], 3.2, 5.2)

            # normalize coords if needed
            if isinstance(spec.get("pts"), list):
                spec["pts"] = _rescale_pts_to_limit(spec["pts"], limit=60.0)

            _validate_spec(spec)
            return spec

        except Exception as e:
            last_err = e

    # if all LLM attempts failed => guaranteed fallback (no more random 500s)
    fb = _fallback_spec(user_text=user_text, seed=seed)
    _validate_spec(fb)
    return fb
