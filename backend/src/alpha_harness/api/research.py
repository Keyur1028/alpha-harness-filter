"""Research themes: import a monthly announcement, read its blueprint, check candidates.

The model that drafts a blueprint is named in the request, and must be one the user has set up
under LLM Integration. Nothing here calls BRAIN or submits anything.
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..db.models import ResearchTheme
from ..llm.keys import LLMError
from ..research import alignment, theme
from ..schemas import Out
from .deps import State

router = APIRouter(prefix="/api/research", tags=["research"])

#: A monthly announcement is a page of text; anything longer is a mistake, not a theme.
MAX_ANNOUNCEMENT = 20_000

DEFAULT_MODEL = "google:gemini-3.8-flash"


class ThemeIn(Out):
    announcement: str
    model: str = DEFAULT_MODEL


class ThemeOut(Out):
    id: int
    announcement: str
    blueprint: dict[str, Any]
    model: str


class CandidateIn(Out):
    text: str


class AlignmentOut(Out):
    id: int
    theme_id: int
    subject: str
    status: str
    confidence: float
    reason: str
    method: str
    admitted: bool


def _theme_out(row: ResearchTheme) -> ThemeOut:
    return ThemeOut(
        id=row.id,
        announcement=row.announcement,
        blueprint=row.blueprint,
        model=row.model,
    )


@router.post("/themes", status_code=201)
async def add_theme(body: ThemeIn, state: State) -> ThemeOut:
    if len(body.announcement) > MAX_ANNOUNCEMENT:
        raise HTTPException(413, f"the announcement is over {MAX_ANNOUNCEMENT} characters")
    try:
        row = await theme.add(state.db, state.llm, body.announcement, body.model)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc
    return _theme_out(row)


@router.get("/themes")
async def list_themes(state: State) -> list[ThemeOut]:
    async with state.db.session() as session:
        rows = await session.scalars(select(ResearchTheme).order_by(ResearchTheme.id.desc()))
        return [_theme_out(row) for row in rows]


@router.post("/themes/{theme_id}/check")
async def check_candidate(theme_id: int, body: CandidateIn, state: State) -> AlignmentOut:
    async with state.db.session() as session:
        row = await session.get(ResearchTheme, theme_id)
    if row is None:
        raise HTTPException(404, f"theme {theme_id} does not exist")
    try:
        verdict = await alignment.check(state.db, state.llm, row, body.text)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return AlignmentOut(
        id=verdict.id,
        theme_id=verdict.theme_id,
        subject=verdict.subject,
        status=verdict.status,
        confidence=verdict.confidence,
        reason=verdict.reason,
        method=verdict.method,
        admitted=alignment.admitted(verdict),
    )
