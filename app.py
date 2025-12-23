from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

import time
import hashlib

from llm_contour_ideator import generate_contour_spec
from stl_generator import generate_scad_from_spec  # SCAD-only writer

load_dotenv()

app = Flask(__name__)
CORS(app)


def normalize_text(s: str) -> str:
    s = (s or "").strip()
    s = " ".join(s.split())
    return s


@app.route("/")
def home():
    return "Tangible Empathy Backend (SCAD-only) is working properly"


@app.route("/scad", methods=["POST"])
def scad_from_text():
    data = request.get_json(silent=True) or {}
    text = normalize_text(data.get("text", ""))

    if not text:
        return jsonify({"error": "text is required"}), 400

    # Seed: her requestte farklı (aynı duygu olsa bile farklı şekil)
    salt = str(time.time_ns())
    seed = int(hashlib.sha256((text + salt).encode("utf-8")).hexdigest()[:8], 16)

    try:
        spec = generate_contour_spec(
            user_text=text,
            seed=seed,
            preferences=None
        )
    except Exception as e:
        return jsonify({"error": f"LLM contour generation failed: {str(e)}"}), 500

    out_name = f"keychain_{seed}"
    thickness_mm = 4.2

    try:
        scad_path = generate_scad_from_spec(spec, out_name, thickness_mm=thickness_mm)
    except Exception as e:
        return jsonify({"error": f"SCAD generation failed: {str(e)}"}), 500

    return send_file(
        scad_path,
        mimetype="text/plain",
        as_attachment=True,
        download_name=f"{out_name}.scad"
    )


if __name__ == "__main__":
    app.run(debug=True)
