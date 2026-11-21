"""Research themes: a monthly announcement, and the blueprint a model drafts from it.

The announcement is stored exactly as given. The blueprint is one structured model call, and
it is kept only if it passes :func:`checked`. Run this module directly for its self-check.
"""

import json
from typing import TYPE_CHECKING, Any

from ..db.models import ResearchTheme

if TYPE_CHECKING:
    from ..db.sqlite import Database
    from ..llm.service import LLMService

#: Field name -> the type it must hold: ``str``, or a list of strings.
FIELDS: dict[str, type] = {
    "title": str,
    "objective": str,
    "financial_concepts": list,
    "data_categories": list,
    "signal_mechanisms": list,
    "alpha_families": list,
    "operators": list,
    "scope": str,
    "exclusions": list,
    "regions": list,
    "directions": list,
    "hypotheses": list,
}

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        key: {"type": "string"} if kind is str else {"type": "array", "items": {"type": "string"}}
        for key, kind in FIELDS.items()
    },
    "required": list(FIELDS),
    "additionalProperties": False,
}

SYSTEM = (
    "You turn a monthly quantitative research theme into a research blueprint. Describe economic "
    "mechanisms and testable hypotheses in plain language. Do not write alpha expressions or "
    "name fields that are not in the announcement. Split the theme into independent research "
    "directions, then state hypotheses under them. Answer only with the JSON object requested."
)


def checked(raw: str) -> dict[str, Any]:
    """The blueprint, if ``raw`` is JSON with every field of the right type; else ValueError."""
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != set(FIELDS):
        keys = sorted(data) if isinstance(data, dict) else type(data).__name__
        raise ValueError(f"blueprint fields are {keys}, expected {sorted(FIELDS)}")
    for key, kind in FIELDS.items():
        value = data[key]
        if kind is str:
            ok = isinstance(value, str) and value.strip() != ""
        else:
            ok = isinstance(value, list) and all(isinstance(item, str) for item in value)
        if not ok:
            raise ValueError(f"blueprint field {key!r} must be a non-empty {kind.__name__}")
    if not data["directions"] or not data["hypotheses"]:
        raise ValueError("blueprint needs at least one direction and one hypothesis")
    return data


async def draft(llm: LLMService, announcement: str, model_ref: str) -> dict[str, Any]:
    """One model call: the announcement in, a checked blueprint out."""
    answer = await llm.generate(
        system=SYSTEM,
        user=announcement,
        model_ref=model_ref,
        response_schema=SCHEMA,
        temperature=0.2,
    )
    return checked(answer.text)


async def add(db: Database, llm: LLMService, announcement: str, model_ref: str) -> ResearchTheme:
    """Store a theme with its drafted blueprint. Nothing is stored if the blueprint fails."""
    text = announcement.strip()
    if not text:
        raise ValueError("the announcement is empty")
    blueprint = await draft(llm, text, model_ref)
    row = ResearchTheme(announcement=text, blueprint=blueprint, model=model_ref)
    async with db.session() as session:
        session.add(row)
        await session.flush()
    return row


if __name__ == "__main__":
    import sys

    good: dict[str, Any] = {key: "x" if kind is str else ["x"] for key, kind in FIELDS.items()}
    if checked(json.dumps(good)) != good:
        raise SystemExit("theme self-check: a valid blueprint was changed")
    broken = [
        "[]",
        json.dumps({**good, "title": 3}),
        json.dumps({**good, "hypotheses": []}),
        json.dumps({k: v for k, v in good.items() if k != "scope"}),
        "not json",
    ]
    for raw in broken:
        try:
            checked(raw)
        except ValueError, json.JSONDecodeError:
            continue
        raise SystemExit(f"theme self-check: accepted a bad blueprint: {raw[:60]}")
    sys.stdout.write(f"{len(broken)} bad blueprints rejected\n")
