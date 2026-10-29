# Business lite implementation plan

## 2026-10-29 screenshot feedback

- Current primary checkout is reused on `fix/1029-ui-research`, base `822ad31`; root owns backend terminology/docs/integration, frontend Coder owns visible wording/intake cleanup/progress, retrieval Coder owns public research/profile/cache and its regressions. No new worktree.
- User outcome: administrator/preparatory wording everywhere in current product output; remove marked intake instructions; useful multi-source company research; actual generation progress visible. Keep existing API role/record identities and scoring/report modules.
- Composition invariant: summary and progress are read-only projections of the same persisted generation state; cache reuse must not turn a retriable or incomplete lookup into a seven-day claim that public information does not exist. No new progress writer, job manager, or company-specific hardcoded sources.
- Why: reproduce the screenshot's exact company and cache path → discriminate search/extraction/reuse failure → restore real evidence before advice; project current result state into steps/progress → make waiting and refresh understandable.
- Verification/exit: focused regressions, actual named-company cold/warm research in isolated state, Chrome screenshot feedback replay, independent diff review, then integrate/push. Source access failures stay explicit; never invent registry evidence. Remove the task branch after integration; retain primary checkouts.
- Acceptance: backend 264 passed / 2 skipped; frontend 86 passed, typecheck and production build passed on the final source. Independent review found no blocking findings. Actual Chrome replay passed intake wording/removal, 0/7 pending → 1/7 completed → 1/7 after refresh, and 390px no-overflow. Live 佛塑科技 research displayed the official site, 广新集团 and 爱企查 with extracted main business; cold query searched once, warm query searched zero times. An isolated unexpired legacy one-source cache also recovered through the real research service. Recent developments remain explicitly unconfirmed. Evidence: `E:/codex-acceptance/feedback-20261029/` (root, retrieval, review-demo); all QA databases and services are separate from production.

Why: persist and verify evidence-backed lite transitions → close R5/R6/R10 gaps without changing full → enable company-name-first innovation advice.

1. RED: service/API tests for company validation, real-source minimum, profile-before-advice, user ownership, persistent seven-day cache, concurrent claim, upload isolation, URL/redirect/content limits.
2. GREEN: add safe public HTTP/search adapter, additive lite persistence/service/routes and register model/router. Reuse intake extraction; preserve all existing defaults.
3. In parallel, RED/GREEN frontend entry, lite state screens, upload, sources, insufficient paths and full prefill. Existing frontend library only.
4. Run isolated service/API tests, full backend suite, frontend tests/typecheck/build. Repair failures at their owning boundary.
5. Run a real public company lookup into temporary test state; save scrubbed result evidence and source URLs. No deployment or production data/credentials.
6. Review diff, independent adversarial review, address findings, then commit/push only task files. Record requirement-to-test evidence and limitations.
