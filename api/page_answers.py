"""Vercel serverless entry point for Google Form page answers."""

from __future__ import annotations

import os
from typing import List

from flask import Flask, jsonify, make_response, request

from answer_generator import Facts, get_page_answers

app = Flask(__name__)


def _get_allowed_origins() -> List[str]:
    raw = os.getenv("ALLOWED_ORIGINS", "*").strip()
    if raw == "*" or not raw:
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _with_cors(response):
    origins = _get_allowed_origins()
    origin_header = "*"
    if origins != ["*"]:
        request_origin = request.headers.get("Origin")
        if request_origin and request_origin in origins:
            origin_header = request_origin
        else:
            origin_header = origins[0]
    response.headers["Access-Control-Allow-Origin"] = origin_header
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    return response


@app.route("/", methods=["OPTIONS"])
def options_root():
    return _with_cors(make_response(("", 204)))


@app.route("/", methods=["POST"])
def answer_page():
    payload = request.get_json(force=True, silent=True) or {}

    facts = payload.get("facts") or {}
    questions = payload.get("questions") or []
    page_notes = payload.get("page_notes") or []

    if not isinstance(questions, list):
        return _with_cors(jsonify({"error": "questions must be a list"})), 400

    answers = get_page_answers(questions, page_notes=page_notes, facts=facts)  # type: ignore[arg-type]

    response = jsonify({"answers": answers})
    return _with_cors(response)


# On Vercel, the module-level ``app`` object is used as the entry point.
# No ``if __name__ == '__main__'`` block is needed.
