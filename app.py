from __future__ import annotations
import os
from flask import Flask, request, jsonify, make_response
from api.answer_generator import get_page_answers  # reuse your existing logic

app = Flask(__name__)

def _with_cors(resp):
    allowed = os.getenv("ALLOWED_ORIGINS", "*").strip()
    origin = request.headers.get("Origin")
    if allowed == "*" or (origin and origin in {o.strip() for o in allowed.split(",")}):
        resp.headers["Access-Control-Allow-Origin"] = origin or "*"
    else:
        resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return resp

@app.route("/api/page_answers", methods=["OPTIONS"])
def options_page_answers():
    return _with_cors(make_response(("", 204)))

@app.route("/api/page_answers", methods=["POST"])
def page_answers():
    payload = request.get_json(force=True, silent=True) or {}
    facts = payload.get("facts") or {}
    questions = payload.get("questions") or []
    page_notes = payload.get("page_notes") or []
    if not isinstance(questions, list):
        return _with_cors(jsonify({"error": "questions must be a list"})), 400
    answers = get_page_answers(questions, page_notes=page_notes, facts=facts)  # type: ignore[arg-type]
    return _with_cors(jsonify({"answers": answers}))
