# Implementation state

**Spec:** Alpha Harness — Autonomous Theme-Driven Alpha Research System (session attachment `3e39b569-attachment.txt`)
**Base commit:** `38d2965` (shallow clone, `--depth 1`)

## Current milestone

**M1 — Theme intelligence: module and table done. API route and UI not yet built.**
Article: user supplied the reference doc (`34849095-harness_engineering_article_agent_reference.md`); §0.3 mapping done (integration-map §6). Original Medium page still not retrievable.

## Completed

- [x] Clone repo (`/home/claude/alpha-harness-filter`).
- [x] Map existing capabilities to spec phases → `docs/integration-map.md`.
- [x] Article mapping (spec §0.3) using the supplied reference doc → integration-map §6.
- [x] Confirm: Gemini already wired; BRAIN quota and model quota already separate; SQLite already used; no hardcoded 4K+1K; no test suite.

## Remaining (by milestone)

- [x] M1 Theme intelligence (partial) — `research/theme.py` (`checked`, `draft`, `add`), table `research_theme`. Verified: self-check, temp-DB end-to-end with a fake model (no quota), ruff, basedpyright 0 errors.
- [ ] M1 remaining — theme alignment validator (`research/alignment.py`), API route for import, decomposition into directions.
- [ ] M2 Research memory — new tables in `db/models.py` via `migrate()`.
- [ ] M3 Specialist roles — prompt templates + Director function (no new processes).
- [ ] M4 Candidate generation — Power Pool/Template feeds + Vault theme pass.
- [ ] M5 Adaptive scheduler — cross-lab arbiter in `labs/scheduler.py`.
- [ ] M6 Evolution integration — theme gate on `labs/ga.py` children.
- [ ] M7 Learning loop.
- [ ] M8 Autonomous orchestration.
- [ ] M9 Dashboard.
- [ ] M10 Validation (live E2E needs approval — spends quota).

## Modified files

- `docs/integration-map.md` (new)
- `docs/implementation-state.md` (new)

## Tests executed

- None. No test suite in repo. `lefthook run check` not run (requires `uv`, `pnpm`, `lefthook`; not verified in this session).

## Known issues / blockers

- **Push refused**: GitHub App not installed for `keyur1028`. Commits stay local. Install at https://github.com/apps/claude/installations/select_target.
- **Medium article unreachable** (client error on fetch; not in search results).
- `register_repo_root` tool not available in this session; CLAUDE.md not present at repo root anyway.

## Next exact implementation task (M1, pending user answers)

Create `backend/src/alpha_harness/research/theme.py`:
1. `ingest(text | image_bytes) -> ThemeAnnouncement` (store original, no transform).
2. `blueprint(theme) -> dict` via one `LLMService` call, JSON schema with the 11 blueprint fields from spec §1.2.
3. Table `theme` in `db/models.py` (id, announcement, blueprint JSON, status, created_at), added via `migrate()`.

Open questions for the user before M1 (each changes the code):
- Which Gemini model should interpret themes? (spec: "Gemini"; the model registry has several.)
- Screenshot input: accept image upload in the API, or text-only first?
- Hypothesis registry (article §4.1) will be a new table. Confirm the required fields: claim, mechanism, expected observation, falsification conditions, theme rationale.
- Does BRAIN expose checks and time series as separate calls? Needed to track the platform completion contract (integration-map §6). Confirm against `brain/client.py` before implementing.

## Decisions (user, 2026-11-21)

- **Expression writing** (Power Pool, Template/Search suggestions, Evolution children) uses Gemini 3.1 or 3.5 Flash only.
- **Every other LLM job** (hypothesis drafting and verification, falsification checks, lesson summaries, theme blueprint, critic/analyst roles) uses a free-provider model configured in the app (Groq, Cerebras, OpenRouter, NVIDIA NIM, Mistral, Hugging Face). Models are set up by the user in the app.
- Implementation: one role→model-ref mapping. Each job passes its ref to `LLMService.generate`. Build it with M1, the first job that needs it. No mapping code before then.
- Failure of a subagent model must not stop the research loop: fall back to Gemini for that one call, and record which model answered.

## Routing proposal (received 2026-11-21, NOT adopted; pending user decision)

Conflicts with the decision above where marked (⚠).

- Theme interpretation, decomposition, hypothesis generation, evolution strategy, final review → gemini-3.8-flash ⚠ (user decision: non-expression jobs use free-provider models)
- Field matching, Vault verification, simulation-result analysis, candidate ranking → openai/gpt-oss-120b (Groq)
- Tagging/classification → llama-3.1-8b-instant (Groq). ⚠ Not needed: `vault/autotag.py` tags via BRAIN, no LLM.
- Vault retrieval → mistral-embed (Mistral). ⚠ No embedding code exists; new infrastructure. Defer to M4.
- Expression generation and repair → gemini-3.5-flash / gemini-3.1-flash (agrees with decision)
- Research memory summarization → gemini-3.5-flash-lite
- Fallback only → OpenRouter (nemotron-3-ultra:free, ernie-5.5-flash-preview:free, openrouter/free). Free variants: 50 requests/day without purchased credits. Model IDs unverified in this session.
- Deterministic (no LLM): syntax, field existence, operator compatibility, dedupe hash, metrics, filtering, queue, quota, retrieval filters. Agrees with spec §5.1.
- Principle to keep: expression writer (Gemini) and evaluator (Groq) are different models.

## Clarification (user, 2026-11-21 13:50) — supersedes "free-provider model" wording above

- "Free" means the free tiers of API providers (Google Gemini, Groq, Mistral, and the others). Gemini 3.8 Flash is allowed on theme, hypothesis, evolution and review jobs.
- Use each provider's free quota as fully as its rate limit allows, before any spill-over to another provider.
- Existing mechanism: `llm/keys.py` `KeyStore` and `llm/budget.py` `Ledger` count per-key, per-model daily and per-minute usage against the user's limits, and `labs/power_pool.py` already moves to the next runnable model when one is out of budget. New work: role-to-model preference order on top of this, not a new limiter.
- Writer and evaluator separation (Gemini writes, Groq evaluates) holds only while both have budget. A spill-over can put the same model on both; record which model wrote and which evaluated.
- Open: Llama tagging. `vault/autotag.py` already tags deterministically. Keep it deterministic unless you want LLM spend there.

## Decision (user, 2026-11-21 13:51): no LLM for tagging

- Do not spend LLM calls on tagging. Final alphas that pass BRAIN checks will be tagged by the user in one place.
- `vault/autotag.py` stays as it is (no LLM imports). The Llama 3.1 8B tagging job from the routing proposal is dropped.

## Answers received (user, 2026-11-21 13:54)

- Theme input: text only in M1.
- Theme interpretation and decomposition: gemini-3.8-flash.
- Hypothesis gate: on. A free verifier must pass a hypothesis before any expression is written. Verifier: openai/gpt-oss-120b (Groq).
- Tracking: this file (`RESEARCH_TRACKING.md`) is the committed tracker. `docs/` stays local because it is gitignored.
- M1 scope: theme ingestion and blueprint only. No simulations, no live BRAIN calls.

## M1 status (2026-11-21)

- Added `ResearchTheme` to `db/models.py` (created by `create_all`, no migration step needed).
- Added `backend/src/alpha_harness/research/theme.py`. Drafting uses one `LLMService.generate` call, temperature 0.2, strict schema, and the blueprint is kept only if `checked` passes.
- Not done in M1: API route (needs `lefthook run format` to regenerate `generated.ts`), alignment validator, decomposition. Live model call not run: no key or quota used.
