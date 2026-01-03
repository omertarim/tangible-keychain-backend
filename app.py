from flask import Flask, request, jsonify, send_file, make_response
from flask_cors import CORS
from dotenv import load_dotenv

import time
import hashlib

from llm_contour_ideator import generate_contour_spec
from stl_generator import generate_scad_from_spec

load_dotenv()

app = Flask(__name__)
CORS(app)


def normalize_text(s: str) -> str:
    s = (s or "").strip()
    s = " ".join(s.split())
    return s


def _sanitize_sliders(raw) -> dict:
    """
    Expect 5 sliders in [1..10].
    If missing, return defaults (5).
    """
    default = {"joy": 5, "sadness": 5, "anger": 5, "calm": 5, "energy": 5}

    if not isinstance(raw, dict):
        return default

    out = {}
    for k in default.keys():
        v = raw.get(k, default[k])
        try:
            v = int(v)
        except Exception:
            v = default[k]
        v = max(1, min(10, v))
        out[k] = v

    return out


@app.route("/")
def home():
    return "Tangible Empathy Backend (SCAD-only) is working properly"


@app.route("/scad", methods=["POST"])
def scad_from_text():
    data = request.get_json(silent=True) or {}
    text = normalize_text(data.get("text", ""))

    if not text:
        return jsonify({"error": "text is required"}), 400

    sliders = _sanitize_sliders(data.get("sliders"))

    salt = str(time.time_ns())
    seed = int(hashlib.sha256((text + salt).encode("utf-8")).hexdigest()[:8], 16)

   

    try:
        spec = generate_contour_spec(
            user_text=text,
            seed=seed,
            preferences=sliders  
        )
    except Exception as e:
        return jsonify({"error": f"LLM contour generation failed: {str(e)}"}), 500

    out_name = f"keychain_{seed}"
    thickness_mm = 4.2

    try:
        scad_path = generate_scad_from_spec(spec, out_name, thickness_mm=thickness_mm)
    except Exception as e:
        return jsonify({"error": f"SCAD generation failed: {str(e)}"}), 500

    resp = make_response(send_file(
        scad_path,
        mimetype="text/plain",
        as_attachment=True,
        download_name=f"{out_name}.scad"
    ))

    resp.headers["X-Emotion-Tag"] = str(spec.get("emotion_tag", ""))
    resp.headers["X-Symbol"] = str(spec.get("symbol", ""))
    resp.headers["X-Sliders"] = json_dumps_safe(sliders)

    return resp


def json_dumps_safe(obj) -> str:
    try:
        import json
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return ""


if __name__ == "__main__":
    app.run(debug=True)
