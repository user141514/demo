# DEMO feedback acceptance — 2026-10-29

Source: user-supplied `DEMO反馈意见.docx` (11 items and annotated screenshots).
Scope: `E:/company_work/demo`; verify existing talent-app work in `E:/company_work/MAHID五类人才评测` without rewriting it.

## Requirements and decisions

| Item | Implementation / verified state |
| --- | --- |
| 1 | User-facing `讲师` / `课前` wording was already changed to `管理员` / `前置`. The remaining old role label in the auth schema is an input-compatibility mapping, not rendered copy. Internal role and API identifiers stay compatible. |
| 2 | Talent repo commit `123669f` already uses the main talent type for the five-axis radar and its title, including PDF rendering. Mixed-type results keep a separately labeled fallback. Verified by the talent test suite. |
| 3 | The boxed intake-mode explanation and internal Assessment wording were already absent. The unboxed instruction about completing missing fields remains. |
| 4 | Public research searches the exact legal entity, then business/annual-report evidence. It still requires fetched, entity-matched source text, deduplicates evidence, and does not count search snippets or verification challenges as sources. |
| 5 | Breakthrough Top 3 follows the same descending normalized-score order as the nine-module preview. Risk labels remain visible, but no longer silently change ranking. The screenshot's core-resources abbreviation is KR, not KP. |
| 6 | A single breakthrough is valid throughout request validation, persistence, progress, refresh, direction generation, competitiveness, and final-report generation. Maximum remains three. |
| 7 | QS/LPS formula explanations moved beside their corresponding values in the scenario page's left-side live preview. The BMC save button stays in the Top 3 selection panel. |
| 8 | Users can reselect breakthrough elements from all nine modules and any three scenarios from the active candidate pool. Saved choices survive reload. Explicit calibration/pool changes recalculate recommendations; the UI now states this, and users can reselect afterward. |
| 9 | Quoted transformation subtitles no longer retain a dangling trailing suffix after the completed from/to phrase. |
| 10 | Removed chain-logic and VP-transition display fields. The AI-native-competitor response no longer concatenates the short-/long-term paths already shown elsewhere. Web and deterministic export templates are aligned. |
| 11 | The endgame page, editor, dashboard, workflow labels, and report section use `核心竞争力推进策略`. Removed the upper industry/private-domain/ecosystem/OPC presentation. Retained the lower three-stage plan, risks, and alternative strategic paths. Existing storage/API keys are preserved. |

## Correctness fixes found during verification

- The backend progress calculation still required two breakthroughs after the save schema allowed one. Unified it with the one-item contract.
- Outside-Top-3 manual module choices were stored as keys but could not be resolved on reload. Candidate snapshots now contain all submitted scored modules.
- Re-selecting breakthroughs now invalidates the entire downstream chain, not just directions and scenarios.
- Unknown module keys, duplicate module rows, duplicate selections, and selections absent from the submitted scores are rejected. Partial canonical scoring sets remain an existing API contract; the UI submits all nine.
- Scenario regeneration invalidates competitiveness, endgame, cases, and reports. Manual selection, pool edits, calibration, and regeneration persist their new source and invalidate dependent outputs in one transaction. An injected invalidation failure proves rollback to the previous selection.
- An independent read-only OMP review and a scoped follow-up found no remaining blocker in the reviewed validation/persistence paths. A suggestion to delete strategic paths was rejected because the user's screenshot requires retaining that lower content.

## Verification results

| Check | Result |
| --- | --- |
| DEMO backend full suite | 274 passed, 2 skipped |
| DEMO frontend | 92 tests passed across 31 files |
| Frontend TypeScript | Passed |
| Frontend production build | Passed, Next.js 15.5.9 |
| Talent app full suite | 64 passed |
| Live Chrome + real local HTTP API | Passed; isolated temporary database, mock LLM/payment, no production customer data |
| Diff whitespace check | Passed; Git only noted existing LF/CRLF conversion settings |

The skipped backend checks are an intentionally superseded calibration/LLM packaging test and an opt-in live-LLM test. These results do not claim verification of a live LLM provider.

Live Chrome verified:
1. Top-3 rank order and a single selected breakthrough, save/reload, then navigation into directions.
2. An initially saved choice outside automatic Top 3 is restored.
3. A different scenario can replace an automatic recommendation; the real PUT endpoint stores ordered IDs and refreshed cards match.
4. QS/LPS explanations sit beside their preview values.
5. Strategy page and results dashboard retain the three-stage plan and omit the removed design/redundant fields.
6. No browser page errors.

Optional web fonts delayed Playwright's default load/screenshot wait. The test now waits for DOM readiness plus explicit business assertions, and captures the rendered Chrome pixels through CDP without waiting for those optional fonts. No business-page workaround was added.

Reproduce from the repository root, with local Chrome and free ports 8000/3001:

```text
cd frontend
npm run typecheck
npm run test
npm run build
cd ..
uv run --no-project --python 3.12 --with-requirements backend/requirements.txt --with playwright python scripts/verify_demo_feedback.py
```

Backend:

```text
cd backend
uv run --no-project --python 3.12 --with-requirements requirements.txt python -m pytest tests -q --tb=short
```

The browser script uses a temporary SQLite database, synthetic credentials, local services, and a temporary evidence directory. It stops its own server process trees; it refuses to stop pre-existing listeners.

## Public research live check

The application research function successfully retrieved two valid sources for `佛山佛塑科技集团股份有限公司`:
- Official company introduction: `https://www.fspg.com.cn/nzb/about/c1/`
- Aiqicha company facts: `https://aiqicha.baidu.com/company_basic_31778541612718`

The accepted official-source text supplied the main-business description about functional polymer films and composite materials. An earlier network attempt failed transiently; success is not a guarantee that every provider or company will always be accessible. Login/captcha failures must remain distinguishable from verified absence of evidence.

## Release boundary

This verifies the local checkout and built application, not deployment at the user's remote public address. No production database, real payment, email, or external account was changed. Existing frozen reports are not silently rewritten: regenerate them after deployment to obtain the revised report content. No database schema migration is required for these changes.
