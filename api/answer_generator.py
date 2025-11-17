"""Backend answer generator for Google Form auto-filling.

This module exposes ``get_page_answers`` which takes the questions and
page-level notes for a single Google Form page and returns answers for
all questions in one shot.  It uses stored personal facts plus the
OpenAI Responses API.  When OpenAI is unavailable, it falls back to a
simple deterministic heuristic.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Union

from openai import OpenAI

Facts = Dict[str, Union[str, List[str]]]
AnswerMapping = Dict[int, Union[str, List[str]]]
Question = Dict[str, Any]

DEFAULT_FACTS: Facts = {
    "full_name": "Cosine Cake",
    "preferred_name": "Cosine",
    "email": "student@example.com",
    "class_year": "2028",
    "concentration": "Computer Science",
    "house": "Mather House",
    "residence_number": "Mather Lowrise 214",
    "phone": "+1 (617) 555-0134",
    "hometown": "Cambridge, MA",
    "default_club": "Farmer's Fridge",
    "interests": [
        "entrepreneurship",
        "product design",
        "student leadership",
    ],
}

MODEL = os.getenv("FORM_FILLER_MODEL", "gpt-4o-mini")
API_KEY = os.getenv("OPENAI_API_KEY")

_client: Optional[OpenAI] = None
if API_KEY:
    _client = OpenAI(api_key=API_KEY)


def get_page_answers(
    questions: List[Question],
    page_notes: Optional[List[str]] = None,
    facts: Optional[Facts] = None,
) -> AnswerMapping:
    """Return answers for all questions in ``questions``.

    Args:
        questions: List of question payloads (same structure as the
            Chrome extension sends).
        page_notes: Optional list of strings describing the section.
        facts: Optional dict overriding/augmenting stored personal facts.
    """

    merged_facts = _merge_facts(facts)

    if not questions:
        return {}

    if _client is None:
        return _fallback_page_answers(questions, merged_facts)

    try:
        raw = _call_openai_for_page(questions, page_notes or [], merged_facts)
        parsed = _parse_page_response(raw, questions, merged_facts)
        if parsed:
            return parsed
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[answer_generator] OpenAI request failed: {exc}")

    return _fallback_page_answers(questions, merged_facts)


# ---------------------------------------------------------------------------
# OpenAI helpers
# ---------------------------------------------------------------------------


def _merge_facts(incoming: Optional[Facts]) -> Facts:
    merged: Facts = {**DEFAULT_FACTS}
    if incoming:
        merged.update(incoming)
    return merged


def _format_facts(facts: Facts) -> str:
    lines: List[str] = []
    for key, value in facts.items():
        pretty = ", ".join(value) if isinstance(value, list) else value
        lines.append(f"- {key.replace('_', ' ').title()}: {pretty}")
    return "\n".join(lines)


def _call_openai_for_page(
    questions: List[Question],
    page_notes: List[str],
    facts: Facts,
) -> str:
    assert _client is not None  # nosec - guarded by caller

    q_lines: List[str] = []
    for q in questions:
        idx = q.get("index")
        qtext = q.get("qtext", "")
        qtype = q.get("type", "unknown")
        options = q.get("options") or []
        q_lines.append(f"- index: {idx}, type: {qtype}, text: {qtext}")
        if options:
            q_lines.append("  options: " + "; ".join(str(o) for o in options[:20]))
        qnotes = q.get("question_notes") or []
        if qnotes:
            q_lines.append("  notes: " + " | ".join(qnotes[:4]))

    notes_str = ""
    if page_notes:
        notes_str = "Page notes:\n" + "\n".join(f"- {n}" for n in page_notes[:12]) + "\n"

    system_prompt = (
        "You answer Google Form pages using the provided personal facts. "
        "Return a JSON mapping of answers for all questions. When options are "
        "provided, choose from them. For checkbox questions you may pick multiple "
        "options. Keep answers concise and consistent."
    )

    instructions = (
        "Facts about me:\n"
        f"{_format_facts(facts)}\n\n"
        f"{notes_str}"
        "Questions on this page:\n"
        + "\n".join(q_lines)
        + "\n\n"
        "Respond ONLY in JSON with this schema:\n"
        "{\n"
        '  "answers": [\n'
        '    {"index": number, "answer": string},\n'
        '    {"index": number, "answers": [string, ...]}\n'
        "  ]\n"
        "}\n"
        "Do not include explanations."
    )

    response = _client.responses.create(
        model=MODEL,
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": instructions},
        ],
        temperature=0.3,
    )
    return response.output_text  # type: ignore[return-value]


def _parse_page_response(
    raw: str,
    questions: List[Question],
    facts: Facts,
) -> AnswerMapping:
    cleaned = raw.strip()
    if "{" in cleaned and "}" in cleaned:
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        cleaned = cleaned[start:end]

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return {}

    q_by_index: Dict[int, Question] = {
        int(q.get("index", idx)): q for idx, q in enumerate(questions)
    }

    answers: AnswerMapping = {}
    for item in payload.get("answers", []):
        try:
            idx = int(item.get("index"))
        except Exception:  # pragma: no cover - defensive
            continue
        qmeta = q_by_index.get(idx)
        if not qmeta:
            continue

        qtype = qmeta.get("type")
        options = qmeta.get("options") or []

        if qtype == "checkbox":
            raw_answers = item.get("answers") or item.get("answer")
            if isinstance(raw_answers, str):
                raw_answers = [raw_answers]
            if isinstance(raw_answers, list):
                cleaned_answers = [str(a).strip() for a in raw_answers if str(a).strip()]
                validated = _validate_options(cleaned_answers, options, allow_multiple=True)
                if validated:
                    answers[idx] = validated
            continue

        ans = item.get("answer")
        if isinstance(ans, list) and ans:
            ans = ans[0]
        if isinstance(ans, str):
            ans = ans.strip()
            if not ans:
                continue
            if options:
                validated = _validate_options([ans], options)
                if validated:
                    answers[idx] = validated[0]
            else:
                answers[idx] = ans

    return answers


def _validate_options(
    answers: List[str],
    options: List[str],
    allow_multiple: bool = False,
) -> List[str]:
    if not options:
        return answers

    normalized = {opt.lower().strip(): opt for opt in options}
    selected: List[str] = []

    for ans in answers:
        key = ans.lower().strip()
        if key in normalized:
            selected.append(normalized[key])
        else:
            for opt_key, original in normalized.items():
                if key in opt_key or opt_key in key:
                    selected.append(original)
                    break

        if not allow_multiple and selected:
            break

    return selected


# ---------------------------------------------------------------------------
# Fallback logic
# ---------------------------------------------------------------------------


def _fallback_page_answers(
    questions: List[Question],
    facts: Facts,
) -> AnswerMapping:
    mapping: AnswerMapping = {}
    for q in questions:
        idx = int(q.get("index", -1))
        if idx < 0:
            continue
        ans = _fallback_answer(q, facts)
        if ans is not None:
            mapping[idx] = ans
    return mapping


def _fallback_answer(
    question: Question,
    facts: Facts,
) -> Union[str, List[str], None]:
    qtext = str(question.get("qtext", "")).lower()
    qtype = question.get("type")
    options = question.get("options") or []

    if "email" in qtext:
        return facts.get("email")
    if "name" in qtext:
        return facts.get("full_name")
    if "class year" in qtext:
        return facts.get("class_year")
    if "team" in qtext:
        return facts.get("default_club") or (options[0] if options else None)
    if "house" in qtext or "hall" in qtext:
        return facts.get("house")
    if "residence" in qtext:
        return facts.get("residence_number")

    if qtype == "checkbox":
        return options[:1] if options else None
    if qtype in {"radio", "dropdown", "scale"}:
        return options[0] if options else None

    if qtype == "text":
        base = question.get("qtext", "this question")
        return f"I appreciate the opportunity to share more about {base.lower()}."

    return None
