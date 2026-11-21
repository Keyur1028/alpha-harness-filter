"""Does a candidate belong to its theme? Cheap checks first; a model only when they are unsure.

Only ``aligned`` admits a candidate. An unsure verdict, or a model that fails, rejects it: an
unrelated alpha must never enter a theme's queue, so the default is no.
"""

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from ..db.models import ResearchAlignment, ResearchTheme

if TYPE_CHECKING:
    from ..db.sqlite import Database
    from ..llm.service import LLMService

#: Judged by a model that is not the expression writer, so the writer does not approve itself.
VERIFIER = "groq:openai/gpt-oss-120b"

#: Two theme terms in the candidate settle it. One is a guess, so the model decides.
ALIGNED_AT = 2

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["aligned", "rejected"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
    "required": ["status", "confidence", "reason"],
    "additionalProperties": False,
}

SYSTEM = (
    "You decide whether a quantitative research candidate belongs to a monthly research theme. "
    "Answer aligned only if the candidate's economic mechanism matches a direction of the theme. "
    "Answer rejected otherwise. Reply with the JSON object requested."
)


@dataclass(frozen=True, slots=True)
class Verdict:
    status: str  # aligned | rejected
    confidence: float
    reason: str
    method: str  # keywords | exclusion | semantic | error


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z]{3,}", text.lower()))


def cheap(text: str, blueprint: dict[str, Any]) -> Verdict | None:
    """Decide from the text alone, or None when the model has to."""
    lowered = text.lower()
    for phrase in blueprint["exclusions"]:
        if phrase.strip() and phrase.lower() in lowered:
            return Verdict("rejected", 1.0, f"matches the exclusion {phrase!r}", "exclusion")
    terms: set[str] = set()
    for key in ("financial_concepts", "data_categories", "signal_mechanisms", "alpha_families"):
        for item in blueprint[key]:
            terms |= words(item)
    shared = sorted(words(text) & terms)
    if len(shared) >= ALIGNED_AT:
        return Verdict(
            "aligned",
            min(1.0, len(shared) / 4),
            f"shares {', '.join(shared[:5])} with the theme",
            "keywords",
        )
    return None


async def check(
    db: Database, llm: LLMService, theme: ResearchTheme, text: str
) -> ResearchAlignment:
    """Judge one candidate against its theme and store the verdict, whatever it is."""
    text = text.strip()
    if not text:
        raise ValueError("the candidate is empty")
    verdict = cheap(text, theme.blueprint)
    if verdict is None:
        try:
            answer = await llm.generate(
                system=SYSTEM,
                user=f"THEME\n{theme.blueprint}\n\nCANDIDATE\n{text}",
                model_ref=VERIFIER,
                response_schema=SCHEMA,
                temperature=0,
            )
            data = json.loads(answer.text)
            status = data["status"]
            if status not in ("aligned", "rejected"):
                raise ValueError(f"status {status!r}")
            verdict = Verdict(status, float(data["confidence"]), str(data["reason"]), "semantic")
        except Exception as exc:  # noqa: BLE001 - any failure must reject, never admit
            verdict = Verdict("rejected", 0.0, f"could not be verified: {exc}", "error")
    row = ResearchAlignment(
        theme_id=theme.id,
        subject=text,
        status=verdict.status,
        confidence=verdict.confidence,
        reason=verdict.reason,
        method=verdict.method,
    )
    async with db.session() as session:
        session.add(row)
        await session.flush()
    return row


def admitted(row: ResearchAlignment) -> bool:
    """Only an aligned verdict enters the queue."""
    return row.status == "aligned"
