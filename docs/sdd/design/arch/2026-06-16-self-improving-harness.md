# Architecture — Self-Improving Harness

> SDD Phase 2, Step 1 (architecture-first). SIMPLE mode (no UI / no REST API contract).
> Input: `docs/sdd/spec/2026-06-16-self-improving-harness.md` only.
> This document constrains the upcoming task breakdown (Phase 3). It defines module/library
> boundaries and the decision-vs-judgment split — NOT specific source file names.

---

## 1. Architecture Summary

The self-improving harness is a **plugin tooling system**, not a runtime application. It has no
process to "run" and no hot path. Its correctness axis is not throughput — it is **boundary
integrity**: every behavior must land on the correct side of three orthogonal cuts.

1. **Decision vs Judgment (NFR-1).** Anything with a definable correct answer — state-machine
   transitions, circuit breakers, cursors, cadence, caps, tier classification heuristics, tag
   parsing, recurrence counting, provenance extraction, benchmark scoring — lives in **Python
   stdlib scripts** that are pytest-verifiable, network-free, LLM-free. Everything requiring
   semantic interpretation — comment classification, clustering, critic refutation, change
   drafting — stays in **markdown skill/agent prompts**. The scripts are pure functions over
   files + JSON; the prompts orchestrate the scripts and supply the judgment the scripts cannot.

2. **Project tier vs Harness tier (NFR-2).** A change that only matters inside the current repo
   is auto-appliable; a change that alters agent/skill/hook behavior propagates to every install
   and is proposal-only. The default on ambiguity is harness tier. This cut is enforced
   structurally: the tier verdict is computed by a deterministic script, and the *write target*
   for each tier is physically different (repo `docs/` + `.harness/` vs `.harness/harness-proposals/`).

3. **Phase 1/2/3 maturity (NFR-3).** Phase 3 (harness-tier auto-promotion) is forbidden until
   Phase 2 (the measurement substrate: benchmarks, metrics, provenance) exists. This is enforced
   by making the Phase 3 promotion path *consume* Phase-2-only artifacts (benchmark deltas,
   recurrence metrics) that simply do not exist before Phase 2 ships — a missing-input gate, not
   a documentation footnote.

The system follows the `stop-pipeline.py` precedent throughout: a deterministic Python core that
reads state JSON, computes a verdict by pure logic, writes state atomically, and emits a structured
result that a prompt layer acts on. The prompt layer never re-implements the deterministic logic;
the deterministic layer never calls an LLM or the network.

Data flow across the two loops:

```
  development cycle
        │
   pr-converge (skill: observe→classify→fix→state-machine)
        │  repeated CI-fail / review patterns
        ▼
  .harness/LEARNING.md  ◀── (also: SDD engineers append during implementation)
        │  (append-only, read-only input; provenance + tags per entry)
        ▼
   self-improve (skill: collect→diagnose→gate→apply)
        │
        ├─ project tier ─▶ docs/lessons-learned.md, docs/pitfalls.md, .harness/* + retro-log rollback
        └─ harness tier ─▶ .harness/harness-proposals/*.md (human approval gate)
```

LEARNING.md is the only coupling between the loops, and it is one-directional (pr-converge writes,
self-improve reads). Neither loop calls the other's internals.

---

## 2. Assumptions, Constraints, Performance Goals

### Technology choices (flagged for confirmation at the approval gate)

These follow the spec and existing precedent; called out explicitly per the "make assumptions
explicit" rule:

- **Language: Python 3 stdlib only** for all deterministic logic. No third-party packages (no
  `requests`, no `pyyaml`, no `pydantic`). JSON via `json`, dates via `datetime`, atomic writes
  via `tempfile`+`shutil`, markdown parsed by hand. This is a hard constraint (R3.1, F20), matching
  `stop-pipeline.py` which imports only stdlib. **Confirm: Python ≥ 3.9** (the harness already
  ships 3.x stdlib hooks; pin the floor for type-hint/`fromisoformat` behavior).
- **Test framework: `pytest`** for deterministic logic (R3.1, F21). No `mockall`/gtest equivalents
  apply — this is a Python+markdown system, not Rust/C++. `pytest` is the only test dependency and
  must itself be the *only* allowed dev-time external package (it does not ship in the plugin
  runtime path). **Confirm: pytest is acceptable as a dev/CI-only dependency** given the
  "stdlib only" runtime rule (runtime scripts import no pytest).
- **Live eval: `claude -p` headless + LLM-judge** (R3.2, F21), run as a *separate* pipeline stage,
  never mixed with the offline pytest stage.
- **GitHub via `gh` CLI** only, and only from the skill prompt layer (gh assumed authenticated;
  non-GitHub remotes detected on first pass → BLOCKED). Deterministic scripts never shell out to
  `gh` (F20).

### Hard invariants (architectural, not optional)

- Deterministic scripts perform **no network and no LLM calls** (F20). Tests must pass with `gh`
  and the Claude API absent (F21 acceptance).
- LEARNING.md is **read-only input** to self-improve (F8). No script or prompt rewrites/deletes it;
  the only writer is pr-converge (append) and SDD engineers (append).
- **No force-push, no direct push to main** (F5). Push targets the PR head branch only.
- **No plugin file edited without human approval** (NFR-2). The `protected set` is never
  auto-generated or auto-modified.

### Performance goals

Not latency or throughput. The only quantitative budgets are token budgets (F18): always-on
memory ≤ ~800 tokens, on-demand searched layer ≤ ~500 tokens. The "performance" concern is
that the deterministic scripts stay O(entries) cheap and fully offline so CI eval cost is zero.

---

## 3. Module / Library Breakdown

All paths are relative to the worktree root
`/Users/moon/workspace/moon-harness/worktrees/self-improving-harness/`. Folder boundaries only —
specific file names are Phase 3 task decisions. Each "responsibility unit" below names a unit of
work, not a file.

### 3.1 Shared deterministic library — `hooks/lib/self_improve/`

A new shared Python package, sibling in spirit to `hooks/enforcement/lib/` (which is bash). Because
this logic is Python and shared by two skills, it lives in one importable place rather than being
duplicated under each skill's `scripts/`. Responsibility units:

- **state I/O** — load/atomic-write `pr-converge-state.json` and `retro-state.json`; schema_version
  guard. (Reuse the `load_state`/`atomic_write` pattern verbatim from `stop-pipeline.py`.)
- **tier classifier** — given a change descriptor (target path + scope flags), return
  `PROJECT | HARNESS`, defaulting to HARNESS on ambiguity. Single source of truth for the tier cut.
- **protected-set guard** — given a target artifact path, return whether it is in the protected set
  (self-improve, pr-converge, harness-improvement-critic, gate scripts). Pure predicate.
- **provenance + tag parser** — parse the `<!-- tags: domain=, stage=, provenance_repo= -->`
  metablock (spec "해결 1") and `##` entry markers from LEARNING.md.
- **cursor engine** — given LEARNING.md text + `last_processed_marker`, return the list of new
  entries (F8). Pure function; never mutates LEARNING.md.
- **recurrence + cross-project counter** — count independent signals per cluster, distinguish
  same-repo recurrence (N in one repo) from cross-project reproduction (≥2 distinct repos) (F16).
  This is the structural enforcement point for the cross-project invariant.
- **pre-check engine** — deterministic conflict / duplicate / generality checks over target-file
  text (F10), producing a structured result the critic prompt consumes.
- **cap + cadence + circuit-breaker engine** — 5-apply cap with explicit truncation report (F13),
  cadence mapping (270s / 1200s+ / none; never 300s) (F4), `fix_attempts ≥ 3` / `iterations > 15`
  → BLOCKED (F6). Same shape as `stop-pipeline.py`'s circuit breaker.
- **on-demand memory router** — given a work-context domain, filter LEARNING.md entries by tag and
  enforce the ≤800 / ≤500 token budgets (F18). Pure selection over parsed tags.
- **ladder router** — map a lesson + recurrence count to the next ladder rung L0→L4 (F17), pure
  table lookup; the *application* of a rung is a prompt/tier concern, not this script's.

> Rationale for one shared package vs per-skill `scripts/`: the tier classifier, protected-set
> guard, and provenance parser are invoked by *both* loops and by the benchmark runner. Duplicating
> them would let the two copies drift, which is exactly the contamination failure mode the spec
> guards against. A single import point keeps the invariant logic singular and testable in one place.

### 3.2 pr-converge skill — `skills/pr-converge/`

- `SKILL.md` (existing draft, to be extended — see §9) — the judgment + orchestration layer:
  observe (gh calls), classify comments (judgment), dispatch engineers, report.
- `scripts/` — pr-converge-specific deterministic glue that imports `hooks/lib/self_improve/`:
  state-machine transition (WORKING/WAITING/NEEDS_HUMAN/CONVERGED/BLOCKED), cadence calc,
  comment-dedup against `processed_comment_ids`, repeated-pattern detection that produces the
  LEARNING.md append payload (F15). The *append* of a provenance-tagged entry is deterministic
  (format is fixed); detecting *whether* a pattern is "the same" is the borderline — keep the
  exact-signal-key match deterministic, leave semantic "same review intent" to the prompt.

### 3.3 self-improve skill — `skills/self-improve/`

- `SKILL.md` (existing draft, to be extended — see §9) — the judgment + orchestration layer:
  cluster new entries (judgment), draft concrete changes (judgment), invoke the critic, route
  apply-vs-propose, report.
- `scripts/` — self-improve-specific glue importing the shared lib: run the cursor engine,
  run pre-checks, enforce the 5-apply cap, write retro-log rollback blocks, advance the cursor
  *only on clean completion* (F13: on error, do not advance).

### 3.4 critic agent — `agents/harness-improvement-critic.md`

Pure judgment. No scripts. Receives pre-check results + benchmark delta (when Phase 2 exists) as
prompt input and returns UPHELD/NARROW/REFUTED. Extended for F16 (stricter cross-project safety)
and F22 (benchmark delta as the primary signal, critic as secondary).

### 3.5 Benchmark substrate — `benchmarks/` (Phase 2)

- `benchmarks/sets/` — frozen, version-controlled benchmark sets, split `train/` vs `held-out/`
  (F24). Plain files, never modified by the eval loop.
- `benchmarks/` runner script (deterministic, in `hooks/lib/self_improve/` or a `benchmarks/scripts/`
  unit) — score baseline (OFF) vs candidate (ON), report delta + held-out regression flag, declare
  cold-start ("data < 5, 측정 불가") when data is insufficient (F22, F24). The runner computes
  scores deterministically; the *act of running a candidate* may invoke `claude -p` (live eval),
  which is why the runner separates "score arithmetic" (deterministic, tested) from "produce
  transcript" (live stage).

### 3.6 Tests — `tests/`

- `tests/` — pytest unit + offline golden eval for every deterministic unit in §3.1–§3.3. Runs in
  CI, zero cost, no network, no `gh`, no Claude API (F21 acceptance). Golden fixtures
  (sample LEARNING.md, sample state JSON, expected verdicts) live under `tests/fixtures/`.

### 3.7 Live eval — `evals/`

- `evals/` — `claude -p` headless harness + LLM-judge scenarios for the judgment layer (comment
  classification accuracy, clustering, critic precision). A **separate pipeline stage** from
  `tests/` (F21: never mixed). Gated behind an explicit flag/stage so `pytest tests/` never
  triggers it.

> Why three top-level test dirs (`tests/`, `evals/`, `benchmarks/`) instead of one: they have
> incompatible cost and dependency profiles. `tests/` is free/offline/CI-blocking. `evals/` costs
> API calls and is non-deterministic. `benchmarks/` is frozen fitness data, not test code. Merging
> them would re-introduce the offline/live mixing F21 explicitly forbids.

---

## 4. Ownership and Dependency Direction

Strict acyclic dependency, judgment depends on decision (never the reverse):

```
  agents/harness-improvement-critic.md   (pure judgment)
            ▲
  skills/self-improve/SKILL.md ──────────┐
  skills/pr-converge/SKILL.md  ──────────┤  (judgment + orchestration; call scripts, gh, claude)
            │                            │
            ▼                            ▼
  skills/*/scripts/  (per-skill deterministic glue)
            │
            ▼
  hooks/lib/self_improve/  (shared deterministic core — pure, stdlib-only, no network/LLM)
            ▲
  tests/  evals(stage-separated)  benchmarks/runner
```

Rules:
- The shared core (`hooks/lib/self_improve/`) depends on nothing but stdlib. It is the most-tested,
  most-stable layer and never imports skill glue.
- Skill glue imports the shared core; it never re-implements core logic inline.
- The prompt layer (SKILL.md / agent.md) *calls* scripts and *interprets* their structured output;
  it owns all `gh`/`claude` invocations and all semantic judgment.
- Ownership of state files: pr-converge owns `pr-converge-state.json`; self-improve owns
  `retro-state.json` + `retro-log.md` + `harness-proposals/`. LEARNING.md has *append-only* writers
  (pr-converge, SDD engineers) and one reader (self-improve) — no single owner, but exactly one
  cursor (`retro-state.json`) tracks consumption, mirroring the orchestrator's "only one writer of
  the state file" discipline.

---

## 5. Threading / Async / Event Flow

There is no thread model — these are one-shot scripts and prompt-driven skills. The relevant
"concurrency" concern is **re-entrancy and idempotency** of the loops, handled exactly like
`stop-pipeline.py`:

- pr-converge is `/loop`-driven: one invocation = one observe→fix pass. Between ticks there is no
  resident process. State lives entirely in `pr-converge-state.json`. Cadence (270s / 1200s+ / end)
  is computed deterministically and reported for `/loop` to reschedule (F4).
- self-improve is event-triggered (merge event via sdd-orchestrator Step 5) or manual
  (`/self-improve`). It is idempotent via the cursor: re-running with no new entries advances
  nothing and reports "신규 교훈 없음" (F8).
- Crash containment: if self-improve errors mid-run, the cursor is **not** advanced and partial
  applies are recorded in retro-log for rollback (F13) — the next run reprocesses the same entries
  safely. This is the same "fail-safe: on error, allow / don't corrupt state" stance as
  `stop-pipeline.py`'s exception handler.
- Atomic state writes (`tempfile` + `shutil.move`) prevent torn JSON on interruption — reuse the
  precedent verbatim.

Event flow (merge-event trigger, per spec 가정 1): pr-converge reports CONVERGED → human approves
merge → sdd-orchestrator Step 5 checks LEARNING.md for new entries → if present, calls
`Skill(self-improve)`. self-improve failure does not block cycle completion (F14).

---

## 6. Persistence, Serialization, IO Boundaries

| Artifact | Format | Writer | Reader | Mutability |
|---|---|---|---|---|
| `.harness/pr-converge-state.json` | JSON, schema_version=1 | pr-converge glue | pr-converge glue | cursor/atomic |
| `.harness/retro-state.json` | JSON, schema_version=1 | self-improve glue | self-improve glue | cursor/atomic |
| `.harness/LEARNING.md` | markdown, append-only, tagged | pr-converge, SDD engineers | self-improve (read-only) | append-only |
| `.harness/retro-log.md` | markdown, append-only | self-improve | human / metrics reader | append-only |
| `.harness/harness-proposals/{date}-{slug}.md` | markdown | self-improve | human (approval) | created, not edited by loop |
| `docs/lessons-learned.md`, `docs/pitfalls.md` | markdown | self-improve (project tier) | agents on-demand | edited (with rollback log) |
| `benchmarks/sets/{train,held-out}/` | frozen files | human/setup | benchmark runner | frozen during eval |

IO boundary rules:
- All JSON state through the shared state-I/O unit (atomic write, schema_version guard) — no ad-hoc
  `json.dump` scattered across scripts.
- Markdown append (LEARNING entry, retro-log block) is deterministic given a fixed template; the
  *content* of the entry may come from judgment but the *serialization* is a script.
- `gh` output (JSON via `--json`/`gh api`) is parsed in the prompt layer and handed to scripts as
  already-structured data — scripts never see raw `gh` invocations (F20).

### Tag format (spec 해결 1, load-bearing)

```markdown
## {YYYY-MM-DD} — {feature-slug} / {task-id}
<!-- tags: domain={영역}, stage={구현|pr-converge}, provenance_repo={repo-id} -->
```

The on-demand router and provenance counter parse exactly this metablock. The format is a contract
between the writers (pr-converge / SDD engineers) and the readers (self-improve router + critic).

---

## 7. Integration Architecture (memory, ladder, plugin evolution)

- **On-demand memory (F18) retires the `@.harness/LEARNING.md` whole-import.** This is the single
  genuinely-new mechanism. Today `skills/sdd/SKILL.md` mandates a `CLAUDE.md` line
  `@.harness/LEARNING.md` that loads the entire log every cycle. The new architecture replaces that
  with a tag-filtered on-demand router under the ≤800/≤500 budgets, across three scopes
  (user / repo / plugin) that must not be mixed. **This requires editing `skills/sdd/SKILL.md`'s
  LEARNING-capture section — that is itself a harness-tier change and must go through the human
  gate, not be auto-applied.**
- **Learning ladder (F17).** L0(LEARNING.md) → L1(lessons-learned) → L2(on-demand routing) →
  L3(enforcement hook) → L4(prompt/agent edit). Recurrence escalates one rung. L3+ are harness-tier
  (they alter cross-project behavior) and therefore proposal-only — the ladder router computes the
  *suggested* rung, but the tier classifier gates whether it can be applied automatically.
- **Skill crystallization (F19).** Project-tier crystallization auto-creates a skill in-repo;
  harness-tier produces a proposal with cross-project evidence + benchmark delta. The protected-set
  guard hard-blocks crystallization from touching self-improve / pr-converge / critic / gate
  scripts. Skill-count cap (미해결 3, number TBD at Phase 3) flags low-reuse skills for archive.
- **Enforcement-hook reuse.** Where a structural invariant can be enforced by a Stop/PreToolUse hook
  rather than a prompt rule (e.g. "no direct push to main", "protected-set not edited"), prefer the
  hook — it is the L3 rung and is deterministic. These reuse the `hooks/enforcement/` pattern.

---

## 8. Build, Testing, Profiling, Operational Concerns

- **Build/packaging:** none beyond the plugin's existing layout. Scripts ship as-is; no compile step.
- **CI:** `pytest tests/` must be the CI gate — offline, free, no `gh`/Claude (F21). The live
  `evals/` stage and `benchmarks/` runner are *not* in the blocking CI path (they cost API calls);
  they run on-demand / scheduled.
- **Profiling:** N/A (no hot path). The only budget to watch is the token budget of the on-demand
  router; that is asserted in eval, not profiled.
- **Telemetry / metrics (F23):** auto-measurable metrics (convergence rate, iterations-to-green,
  recurrence rate [the core anchor], comment-classification accuracy, skill reuse/success rate) are
  computed deterministically from `retro-log.md` + state files and written to a metrics record. The
  recurrence-rate anchor must be machine-readable so "the same lesson stops accumulating" is
  measurable without manual tallying (F23 acceptance). Human-review metrics (over-escalation rate,
  critic precision/recall) are explicitly **Phase 2.5/3**, not Phase 2 fitness inputs.
- **Crash diagnostics:** the fail-safe pattern from `stop-pipeline.py` (catch-all → don't corrupt
  state, report `_error`) applies to every script entry point.

---

## 9. Prior-Art Reconciliation (NFR-4)

Line-level disposition of each existing draft. None is discarded wholesale — all four are
structurally sound for what they cover; the gaps are *additive* (R2.6–2.8, F15, F16 were never in
scope of the drafts).

| Draft | Disposition | What changes |
|---|---|---|
| `skills/pr-converge/SKILL.md` | **EXTEND** | Sound for F1–F7 (cadence avoids 300s ✓, independent `/pr-converge` ✓, circuit breaker ✓, safe push ✓). **Add F15**: emit a provenance-tagged LEARNING.md append on repeated CI-fail / review patterns. Extract the state-machine + cadence + dedup into `scripts/` calling the shared core (currently the SKILL describes them inline as prose). |
| `skills/self-improve/SKILL.md` | **EXTEND (largest delta)** | Sound for F8–F14 collect/diagnose/gate/apply skeleton, 2-tier table, 5-cap, rollback, cursor. **Missing and to be added**: F16 (provenance + cross-project criterion — same-repo recurrence ≠ harness-tier promotion), F17 (ladder), F18 (on-demand routing + scope split), F19 (crystallization + protected set + skill-count cap). The Phase-C gate note ("not numeric eval") must be **revised** to reflect F22 (benchmark delta becomes primary for harness tier, critic secondary). Extract deterministic steps (cursor, pre-checks, cap, retro-log) into `scripts/`. |
| `agents/harness-improvement-critic.md` | **EXTEND** | Sound 5-criteria refutation. **Add F22**: accept benchmark delta as prompt input and treat objective score as primary, critic verdict as secondary when a measurable delta exists. **Add F16**: for harness-tier candidates, require cross-project evidence; absent it, lean REFUTED/NARROW. Safety criterion already says "stricter for harness tier" — sharpen to the explicit cross-project rule. |
| `skills/sdd-orchestrator/SKILL.md` Step 4/5 | **CONFIRM (no change needed)** | F7 (PR-based instead of direct merge) already implemented in Step 4. F14 (merge-event self-improve trigger) already present in Step 5, and matches spec 가정 1 (merge-event, not linear wiring). Verified consistent. |
| New deterministic scripts (F20) | **NET-NEW** | Absent from all drafts. Created fresh in `hooks/lib/self_improve/` + per-skill `scripts/`. |
| `skills/sdd/SKILL.md` LEARNING capture | **EXTEND (harness-tier, human-gated)** | F18 retires the `@.harness/LEARNING.md` whole-import this section currently mandates. Add the tag metablock to the capture format and replace the import line with on-demand routing. This edit touches a plugin file → must pass the human approval gate. |

---

## 10. Phase Mapping (NFR-3) and Component Membership

| Phase | Components | Gate to enter |
|---|---|---|
| **Phase 1 — safe & immediate** | pr-converge full loop (F1–F7, F15 append); self-improve collect/diagnose/gate/apply for **project tier only** (F8–F14); pre-check engine, cursor, cap, rollback, tier classifier, protected-set guard; ladder L0–L2 + on-demand routing (F17, F18) and project-tier crystallization (F19 project scope). | spec approved |
| **Phase 2 — measurement substrate** | `benchmarks/` frozen sets + runner (F22, F24); auto-measurable metrics incl. recurrence anchor (F23); provenance + cross-project counter (F16); offline pytest eval + live `claude -p` eval split (F20, F21). | Phase 1 stable |
| **Phase 3 — advanced/risk** | harness-tier auto-promotion *proposals* with benchmark gating (F19 harness scope, F22 extended); L3/L4 ladder application proposals; skill-count cap enforcement (미해결 3). | **Phase 2 measurement substrate exists** — benchmark delta + recurrence metrics are *required prompt inputs* to the promotion path; absent them, the path produces a cold-start "측정 불가" and cannot promote. |

The Phase-3-blocked-without-Phase-2 rule is structural: the harness-tier proposal generator and the
critic both take benchmark delta as a mandatory input. Before `benchmarks/` ships, that input is
absent and the path short-circuits to "cold-start, cannot adopt" (F24) — no estimate-based promotion.

---

## 11. Test Strategy (layer-by-layer type)

All layers are tested; the **type** differs per layer. No layer is skipped. Specific scenarios are
test-automator's job (Phase 4), not this document.

| Layer | What | Test type | Framework | Notes |
|---|---|---|---|---|
| Shared deterministic core (`hooks/lib/self_improve/`) | state I/O, tier classifier, protected-set guard, cursor, pre-checks, cap, cadence, circuit breaker, provenance/recurrence counter, ladder router, on-demand router | **Unit** | `pytest` | Offline, no network, no `gh`, no Claude. Pure functions over fixtures. CI-blocking. |
| Per-skill glue (`skills/*/scripts/`) | state-machine transitions, comment dedup, retro-log writing, cursor-advance-on-clean-completion | **Unit + offline golden** | `pytest` + golden fixtures under `tests/fixtures/` | Golden inputs (sample LEARNING.md, state JSON) → expected verdict/state. Deterministic; CI-blocking. |
| Judgment layer (comment classification, clustering, change drafting, critic refutation) | semantic correctness vs labeled cases | **Live eval (integration)** | `claude -p` headless + LLM-judge, under `evals/` | Costs API calls, non-deterministic. **Separate stage**, never in `pytest tests/` (F21). Flag/stage-gated. |
| Fitness function (`benchmarks/`) | candidate ON vs baseline OFF, held-out regression | **Benchmark (integration)** | benchmark runner; score arithmetic unit-tested in `pytest`, transcript generation via `claude -p` | Frozen sets (F24). Score math is deterministic (tested offline); running a candidate is live. |
| End-to-end loop | one full pr-converge pass; one full self-improve retro on a seeded LEARNING.md | **E2E validation boundary** | scripted, manual-or-CI-with-mocked-`gh` | E2E boundary = *script + state-file outcome*, not GitHub. Verify: cursor advances correctly, no plugin file edited for harness tier, retro-log rollback block present, cap truncation reported. Real `gh`/merge is out of the automated boundary (manual smoke). |

The two pipelines (offline pytest, live eval) are physically separate directories and separate
invocations — this is the F21 non-mixing requirement expressed as structure, not convention.

---

## 12. Risks, Trade-offs, Migration Plan

### Risks

- **R1 — Judgment leaking into scripts.** The biggest drift risk is a script "deciding" something
  semantic (e.g. classifying a comment) to save a prompt round-trip. Mitigation: the dependency
  rule (§4) and code review against the §3.1 responsibility list; scripts that import nothing
  semantic and call no `gh`/`claude` are structurally incapable of judgment.
- **R2 — Tier misclassification → contamination.** A harness-tier change mislabeled as project-tier
  auto-applies cross-project pollution. Mitigation: default-to-harness on ambiguity (encoded in the
  classifier), cross-project counter as a hard precondition for promotion (F16), protected-set guard,
  and an enforcement hook (L3) for the never-edit-plugin-without-approval invariant.
- **R3 — Benchmark gaming / Goodhart.** Mitigation: held-out split frozen during eval (F24),
  benchmark delta on held-out as the adopt gate (F19/F22), cold-start refusal under 5 data points.
- **R4 — Cold-start (미해결 2).** Initial golden set construction is unresolved. Phase 2 entry must
  decide human-labeling vs past-cycle-log extraction. Until then, harness-tier promotion is blocked
  by design (the cold-start gate), which is acceptable.
- **R5 — pytest as a dependency vs "stdlib only".** pytest is dev/CI-only and never imported by
  runtime scripts; flagged for confirmation (§2). If even a dev dependency is unacceptable, the
  fallback is stdlib `unittest`, at the cost of fixture ergonomics.

### Trade-offs

- **Shared lib vs per-skill duplication:** chose one shared `hooks/lib/self_improve/` to keep the
  invariant logic singular (anti-contamination) at the cost of a cross-skill import dependency.
- **Three test dirs vs one:** chose separation to honor F21's offline/live non-mixing at the cost of
  more directories.
- **Merge-event trigger vs CONVERGED-trigger:** chose merge-event (spec 가정 1) because human merge
  approval is asynchronous; self-improve keys off the merge, not the CONVERGED report.

### Migration plan

1. Land the shared deterministic core + `tests/` first (Phase 1 foundation), fully offline.
2. Extract pr-converge and self-improve inline prose into `scripts/` calling the core; extend the
   two SKILLs (F15, F16–F19) and the critic (F16, F22) — these are EXTEND, not rewrite.
3. Route the `skills/sdd/SKILL.md` LEARNING-import retirement (F18) through the human gate as a
   harness-tier change — do not auto-edit.
4. Phase 2: add `benchmarks/` + `evals/` + metrics; only then unlock Phase 3 harness-tier promotion.
5. At no point does an incomplete phase enable a later-phase risky path — the missing-input gates
   enforce ordering.
```