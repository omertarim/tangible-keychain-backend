import os
import json
from typing import Any, Dict, Optional
from groq import Groq



def _safe_json(s: str) -> Dict[str, Any]:
    s = (s or "").strip()
    if s.startswith("```"):
        s = s.strip("`").strip()
        if s.lower().startswith("json"):
            s = s[4:].strip()
    return json.loads(s)


def _clamp(v: float, lo: float, hi: float) -> float:
    try:
        v = float(v)
    except Exception:
        v = lo
    return max(lo, min(hi, v))


def _infer_hint(user_text: str) -> Dict[str, str]:
    """
    Deterministic hint so outputs are meaningful even if LLM is noisy.
    """
    t = (user_text or "").lower()

    if any(k in t for k in ["love", "sevgi", "aşk", "ask", "miss", "özledim", "sarıl", "hug", "warm"]):
        return {"emotion_tag": "love", "symbol": "heart"}

    if any(k in t for k in ["sad", "üzgün", "uzgun", "depress", "depressed", "empty", "kötü", "kotu", "down"]):
        return {"emotion_tag": "depressed", "symbol": "face"}

    if any(k in t for k in ["angry", "sinir", "öfke", "ofke", "rage", "hate", "kızgın", "kizgin"]):
        return {"emotion_tag": "angry", "symbol": "bolt"}

    if any(k in t for k in ["excited", "energetic", "happy", "mutlu", "joy", "joyful", "heyecan", "run", "power", "enerji"]):
        return {"emotion_tag": "energetic", "symbol": "starburst"}

    if any(k in t for k in ["anx", "kaygı", "kaygi", "panic", "stress", "stres"]):
        return {"emotion_tag": "anxious", "symbol": "blob"}

    if any(k in t for k in ["calm", "sakin", "rahat", "peace", "huzur"]):
        return {"emotion_tag": "calm", "symbol": "blob"}

    return {"emotion_tag": "neutral", "symbol": "blob"}


def _prefs01(preferences: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """
    Convert slider values 1..10 -> 0..1
    expected keys: joy, sadness, anger, calm, energy
    """
    base = {"joy": 5, "sadness": 5, "anger": 5, "calm": 5, "energy": 5}
    if isinstance(preferences, dict):
        for k in base.keys():
            if k in preferences:
                try:
                    base[k] = int(preferences[k])
                except Exception:
                    pass

    out = {}
    for k, v in base.items():
        v = max(1, min(10, int(v)))
        out[k] = (v - 1) / 9.0  
    return out


def _build_prompt(user_text: str, seed: int, hint: Dict[str, str], pref_json: str) -> str:
    """
    LLM ONLY returns params (no pts).
    We hard-require the symbol from hint to keep semantics stable.
    """
    forced_emotion = hint["emotion_tag"]
    forced_symbol = hint["symbol"]

    return f"""
User text: {user_text}
Seed (MUST use exactly): {seed}
Preferences (5 sliders, 1..10): {pref_json}

You MUST return ONLY valid JSON. No markdown. No extra text.

FORCED MEANING (DO NOT CHANGE):
- emotion_tag MUST be "{forced_emotion}"
- symbol MUST be "{forced_symbol}"

Your job: output param values that make the shape UNIQUE but still meaningful.
Use Preferences to bias parameters (not override the forced symbol).

Allowed symbol:
heart | face | bolt | starburst | blob

Return JSON with EXACT keys:
{{
  "emotion_tag":"{forced_emotion}",
  "symbol":"{forced_symbol}",
  "seed":{seed},
  "params":{{
    "aspect": 1.0,           // 0.70..1.55
    "roundness": 0.7,        // 0.15..1.20  (higher = rounder)
    "rotation_deg": 0.0,     // -20..+20

    "spikes": 10,            // 6..16 (starburst)
    "spikiness": 0.5,        // 0..1  (starburst)
    "jitter": 0.3,           // 0..1

    "mouth_curve": -0.6,     // -1..+1 (face)
    "eye_size": 0.16,        // 0.10..0.24 (face)
    "mouth_width": 0.55      // 0.35..0.80 (face)
  }},
  "holes":[{{"x_mm":2.0,"y_mm":10.0,"r_mm":2.6}}],
  "thickness_mm":4.2
}}

Preference mapping hints:
- higher energy -> higher spikiness / more spikes / slightly more jitter
- higher calm -> higher roundness, lower spikiness
- higher joy -> slightly higher energy-feel but rounder than anger
- higher sadness -> for face: mouth_curve more negative, slightly rounder
- higher anger -> sharper: lower roundness, higher spikiness/jitter
""".strip()


def _fallback_params(seed: int, symbol: str, emotion_tag: str) -> Dict[str, Any]:
    """
    Always works, still unique by seed.
    """
    rnd = (seed % 10000) / 10000.0

    params = {
        "aspect": 0.85 + 0.70 * rnd,      
        "roundness": 0.45 + 0.55 * (1 - rnd),
        "rotation_deg": float((seed % 41) - 20),
        "spikes": 8 + (seed % 9),        
        "spikiness": 0.25 + 0.65 * rnd,
        "jitter": 0.15 + 0.65 * (1 - rnd),
        "mouth_curve": -0.75 + 1.5 * rnd, 
        "eye_size": 0.12 + 0.10 * rnd,
        "mouth_width": 0.45 + 0.25 * (1 - rnd),
    }

    if emotion_tag in ("depressed", "anxious"):
        params["mouth_curve"] = -abs(params["mouth_curve"])

    if emotion_tag == "love":
        params["roundness"] = max(0.65, params["roundness"])

    if emotion_tag in ("energetic", "joyful", "angry"):
        params["spikiness"] = max(0.55, params["spikiness"])
        params["roundness"] = min(0.55, params["roundness"])

    return params


def _validate_and_clamp(spec: Dict[str, Any], forced_emotion: str, forced_symbol: str, seed: int) -> Dict[str, Any]:
    spec["emotion_tag"] = forced_emotion
    spec["symbol"] = forced_symbol
    spec["seed"] = int(seed)

    if "params" not in spec or not isinstance(spec["params"], dict):
        spec["params"] = {}

    p = spec["params"]
    p["aspect"] = _clamp(p.get("aspect", 1.0), 0.70, 1.55)
    p["roundness"] = _clamp(p.get("roundness", 0.7), 0.15, 1.20)
    p["rotation_deg"] = _clamp(p.get("rotation_deg", 0.0), -20.0, 20.0)

    p["spikes"] = int(_clamp(p.get("spikes", 10), 6, 16))
    p["spikiness"] = _clamp(p.get("spikiness", 0.5), 0.0, 1.0)
    p["jitter"] = _clamp(p.get("jitter", 0.3), 0.0, 1.0)

    p["mouth_curve"] = _clamp(p.get("mouth_curve", -0.5), -1.0, 1.0)
    p["eye_size"] = _clamp(p.get("eye_size", 0.16), 0.10, 0.24)
    p["mouth_width"] = _clamp(p.get("mouth_width", 0.55), 0.35, 0.80)

    holes = spec.get("holes")
    if not isinstance(holes, list) or len(holes) != 1:
        spec["holes"] = [{"x_mm": 2.0, "y_mm": 10.0, "r_mm": 2.6}]
    else:
        h = holes[0]
        spec["holes"] = [{
            "x_mm": _clamp(h.get("x_mm", 2.0), -6.0, 6.0),
            "y_mm": _clamp(h.get("y_mm", 10.0), 10.0, 22.0),
            "r_mm": _clamp(h.get("r_mm", 2.6), 2.2, 3.0),
        }]

    t = spec.get("thickness_mm", 4.2)
    spec["thickness_mm"] = _clamp(t, 3.2, 5.2)

    return spec


def _apply_slider_bias(spec: Dict[str, Any], preferences: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Keep existing logic. Just nudge params based on 5 sliders.
    This guarantees sliders visibly affect output, even if LLM ignores them.
    """
    p01 = _prefs01(preferences)
    joy = p01["joy"]
    sadness = p01["sadness"]
    anger = p01["anger"]
    calm = p01["calm"]
    energy = p01["energy"]

    p = spec.get("params", {}) or {}

    roundness = float(p.get("roundness", 0.7))
    roundness += 0.35 * calm + 0.15 * sadness - 0.35 * anger
    p["roundness"] = _clamp(roundness, 0.15, 1.20)

    spikiness = float(p.get("spikiness", 0.5))
    spikiness += 0.45 * energy + 0.35 * anger - 0.45 * calm
    p["spikiness"] = _clamp(spikiness, 0.0, 1.0)

    spikes = int(p.get("spikes", 10))
    spikes = int(_clamp(spikes + round(3 * energy - 1 * calm), 6, 16))
    p["spikes"] = spikes

    jitter = float(p.get("jitter", 0.3))
    jitter += 0.25 * energy + 0.20 * anger - 0.25 * calm
    p["jitter"] = _clamp(jitter, 0.0, 1.0)

    mouth_curve = float(p.get("mouth_curve", -0.4))
    mouth_curve += 0.75 * joy - 0.90 * sadness
    p["mouth_curve"] = _clamp(mouth_curve, -1.0, 1.0)

    spec["params"] = p
    return spec



def generate_contour_spec(
    *,
    user_text: str,
    seed: int,
    preferences: Optional[Dict[str, Any]] = None,
    model: str = "llama-3.3-70b-versatile",
    temperature: float = 0.9,
) -> Dict[str, Any]:
    """
    Returns a spec with meaning locked by text-hint, uniqueness via params.
    Sliders bias params but do not break forced symbol/emotion.
    """
    hint = _infer_hint(user_text)
    forced_emotion = hint["emotion_tag"]
    forced_symbol = hint["symbol"]

    key = os.getenv("GROQ_API_KEY")
    if not key:
        spec = {
            "emotion_tag": forced_emotion,
            "symbol": forced_symbol,
            "seed": int(seed),
            "params": _fallback_params(seed, forced_symbol, forced_emotion),
            "holes": [{"x_mm": 2.0, "y_mm": 10.0, "r_mm": 2.6}],
            "thickness_mm": 4.2,
        }
        return _apply_slider_bias(spec, preferences)

    client = Groq(api_key=key)
    pref_json = json.dumps(preferences or {}, ensure_ascii=False)

    system = (
        "You generate parameter JSON for 3D printable keychain shapes. "
        "Return ONLY valid JSON. No markdown."
    )

    prompt = _build_prompt(user_text, seed, hint, pref_json)

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            temperature=temperature,
        )
        raw = resp.choices[0].message.content or ""
        spec = _safe_json(raw)
        spec = _validate_and_clamp(spec, forced_emotion, forced_symbol, seed)
        spec = _apply_slider_bias(spec, preferences)
        return spec

    except Exception:
        spec = {
            "emotion_tag": forced_emotion,
            "symbol": forced_symbol,
            "seed": int(seed),
            "params": _fallback_params(seed, forced_symbol, forced_emotion),
            "holes": [{"x_mm": 2.0, "y_mm": 10.0, "r_mm": 2.6}],
            "thickness_mm": 4.2,
        }
        return _apply_slider_bias(spec, preferences)
