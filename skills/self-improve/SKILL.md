---
name: self-improve
description: "누적된 LEARNING.md 교훈을 읽고 하네스/프로젝트를 스스로 개선하는 회고 루프. SDD 사이클 종료 시 자동 실행되며, '자가개선', '회고', 'retro', 'self-improve', 'LEARNING 승격', '교훈 반영' 맥락에서 수동 호출한다."
---

# Self-Improve (자가개선 회고 루프)

`.harness/LEARNING.md`에 쌓인 raw 교훈을 읽고, **무엇을 어떻게 고칠지 스스로 진단·제안·검증·반영**하는 루프.

지금까지 LEARNING.md는 신호를 *모으기만* 했고, 그것을 읽고 어느 SKILL/agent/컨벤션을 어떻게 바꿀지 결정하는 일은 사람 몫이었다. 이 스킬이 그 2~4단계(진단 → 검증 → 반영)를 자동화한다.

> 📌 이 루프는 **하네스 SKILL이 "LEARNING.md를 정기적으로 리뷰해 lessons-learned.md로 승격한다"고 명시한 수동 단계**를 대체한다. 승격은 더 이상 사람이 손으로 하지 않는다 — 검증 게이트를 통과한 항목만 자동 반영된다.

## 핵심 원칙

- **2티어 분리 (위험도 격리).** 영향 범위가 현재 repo 안에 갇히는 변경만 자동 적용한다. 모든 프로젝트로 전파되는 하네스 플러그인 자체 변경은 *제안만* 하고 사람 승인을 받는다.
- **검증 게이트 필수.** eval 없이 자기 프롬프트를 고치면 drift로 망가진다. 모든 개선안은 반박(refutation) + 정합성 + 반복성 검사를 통과해야 반영된다.
- **롤백 가능.** 적용된 모든 변경은 before/after와 함께 `.harness/retro-log.md`에 기록되어 한 단계로 되돌릴 수 있다.
- **Anti-overfit.** 1회성 교훈으로 행동 규칙을 바꾸지 않는다. 독립 신호 2건 이상 또는 명시적 반복 신호가 있을 때만 규칙화한다.

## 사용 시점

- **자동 (주):** SDD Phase 4 종료 시 `sdd-orchestrator`가 호출한다.
- **수동 (폴백):** 자동이 안 돌았거나 즉시 회고하고 싶을 때 `/self-improve`.

---

## 2티어 정의

| 티어 | 대상 파일 | 영향 범위 | 자율성 |
|------|-----------|-----------|--------|
| **프로젝트 티어** | `docs/lessons-learned.md`, `docs/pitfalls.md`, `.harness/*` (설정/로그 외) | 현재 repo만 | **검증 후 자동 적용** |
| **하네스 티어** | moon-harness 플러그인의 `skills/**/SKILL.md`, `agents/*.md`, `hooks/**` | 설치된 모든 프로젝트 | **제안만 → 사람 승인** |

분류 규칙:
- 변경이 **이 repo 안에서만** 의미를 가지면 → 프로젝트 티어.
- 변경이 **에이전트/스킬/훅의 일반 동작**을 바꾸면 (= 다른 프로젝트에도 적용될 규칙) → 하네스 티어.
- 애매하면 **하네스 티어로 안전하게 분류**한다 (자동 적용 안 함).

> 📌 프로젝트 티어라도 사용자 `CLAUDE.md` 본문은 직접 편집하지 않는다. 교훈은 큐레이팅 문서(`docs/lessons-learned.md` / `docs/pitfalls.md`)에 반영한다. 단 그 문서가 매 세션 컨텍스트에 로드되려면 포인터(`@docs/...`)가 필요한데, 포인터가 `CLAUDE.md`·`CLAUDE.local.md` 어디에도 없으면 committed `CLAUDE.md`를 건드리지 말고 로컬 `CLAUDE.local.md`에 **자동 추가**한다(Phase D §10). 이 단계가 빠지면 승격 문서가 로드되지 않아 "적용 0"이 된다(가설-A 갭).

---

## 상태 파일

루프가 관리하는 파일 (전부 `.harness/` 아래, append-only 또는 커서):

```
.harness/
├── LEARNING.md              # 입력 — SDD agent가 append하는 raw 교훈 (이 루프는 읽기만)
├── retro-state.json         # 커서 — 마지막으로 처리한 LEARNING 엔트리 마커
├── retro-log.md             # append-only — 회고 1회 = 요약 1줄 + 적용 변경의 롤백 정보
└── harness-proposals/       # 하네스 티어 제안 큐 (사람 승인 대기)
    └── {YYYY-MM-DD}-{slug}.md
```

`retro-state.json` 스키마:
```json
{
  "schema_version": 1,
  "last_processed_marker": "## 2026-06-10 — auth-flow / T-03",
  "last_retro_at": "2026-06-16T00:00:00Z",
  "cumulative": { "applied_project": 0, "proposed_harness": 0, "dropped": 0 }
}
```

---

## 루프 절차

### Phase A — 수집 (Collect)

1. `.harness/LEARNING.md`를 읽는다. 없거나 헤더만 있으면 → "신호 없음" 보고하고 종료.
2. `.harness/retro-state.json`의 `last_processed_marker`를 읽는다. 그 마커 **이후**의 `##` 엔트리만 *신규*로 취급한다. state 파일이 없으면 전체가 신규.
3. 신규 엔트리가 0건이면 → "신규 교훈 없음" 보고하고 종료 (커서 갱신 없음).

### Phase B — 진단·클러스터 (Diagnose & Cluster)

4. 신규 엔트리를 **주제/대상별로 클러스터링**한다. 한 클러스터 = 반복되거나 일반화 가능한 하나의 교훈.
5. 각 클러스터에서 **구체적이고 반복 적용 가능한 개선**이 도출되는지 판단한다:
   - 독립 신호 **2건 이상** 또는 한 엔트리라도 명시적 반복 신호("또 그러네", 같은 종류 교정 누적)가 있으면 → **개선 후보**.
   - 1회성·맥락 한정이면 → 후보 아님. `docs/lessons-learned.md`에 *참고 노트로만* 기록하고 행동 규칙은 건드리지 않는다.
6. 각 후보에 대해 **대상 아티팩트**를 특정하고 **티어를 분류**한다 (위 표 기준).
7. 후보별로 **구체적 변경안**을 작성한다 — 추상적 조언 금지. 추가/수정할 정확한 텍스트(또는 diff)와 위치(파일:섹션)를 명시.

### Phase C — 검증 게이트 (Verify) — 필수

각 후보에 대해 순서대로:

8. **정합성 사전검사 (결정적, 코드 없이 읽기로):**
   - **충돌**: 대상 파일에 이미 모순되는 규칙이 있는가? → 충돌 내용 첨부.
   - **중복**: 이미 동일 취지가 적혀 있는가? → 후보 폐기 (drop, "중복").
   - **일반성**: 신호 2건 미만이고 반복 신호도 없으면 → 행동 규칙 변경에서 강등, 노트로만.
9. **반박 검증 — `harness-improvement-critic` agent 디스패치 (opus):**
   - 입력: 후보 변경안 + 근거 엔트리 + 대상 파일 현재 내용 + 충돌 사전검사 결과.
   - 판정: **UPHELD** (실재·일반·안전한 개선) / **REFUTED** (overfit·노이즈·기존 규칙과 모순·해악) / **NARROW** (방향은 맞지만 범위를 좁혀야 함).
   - REFUTED → 폐기 (사유 기록). NARROW → critic이 제시한 좁힌 버전으로 진행.

> 📌 현재 게이트는 **반박 + 정합성 + 반복성**이다. 수치 eval/replay가 아니다 — 프롬프트·컨벤션 변경은 자동 벤치마크가 어렵기 때문. 정직하게: 이 게이트는 "명백히 나쁜 자기수정"을 거르는 것이지 "최적임을 증명"하지 않는다. (Phase 2에서 수치 벤치마크 기반 확보 후 F22 벤치 게이트 보조로 발전한다. 하네스 티어 스킬 자동 승격은 Phase 2 벤치마크 측정 기반 확보 후에만 가능. 벤치마크 델타 입력 없으면 cold-start short-circuit → 제안 생성 불가.)

### Phase D — 적용·기록 (Apply & Record)

10. **프로젝트 티어 (UPHELD/NARROW) → 검증 후 자동 적용:**
    - 대상 파일(`docs/lessons-learned.md` 등)에 변경을 직접 적용 (없으면 생성).
    - **컨텍스트 포인터 보장 (idempotent)**: 방금 쓴 큐레이팅 문서를 가리키는 import 포인터(예: `@docs/lessons-learned.md`)가 `CLAUDE.md`·`CLAUDE.local.md` **둘 다에 없을 때만** repo 루트 `./CLAUDE.local.md`에 한 줄 추가한다(없으면 생성). **committed `CLAUDE.md` 본문은 편집하지 않는다.** `.gitignore`에 `CLAUDE.local.md`가 없으면 추가. (근거: 자동 적용이 공유 committed 파일을 변경하지 않게 — 포인터 없으면 승격 문서가 로드 안 돼 적용 0이 되는 가설-A 갭 차단.)
    - `.harness/retro-log.md`에 before/after를 기록 (롤백용; 포인터 추가도 롤백 대상).
11. **하네스 티어 (UPHELD/NARROW) → 제안만:**
    - `.harness/harness-proposals/{YYYY-MM-DD}-{slug}.md`를 생성: 대상 파일 경로, 정확한 diff, 근거 엔트리, critic 판정, 적용 방법.
    - **플러그인 파일은 절대 편집하지 않는다.** 사용자에게 요약 + 경로만 보고.
12. `.harness/retro-state.json`의 `last_processed_marker`를 마지막 처리 엔트리로 갱신, `cumulative` 누적, `last_retro_at` 기록.
13. `.harness/retro-log.md`에 회고 요약 **1줄** append (아래 포맷).
14. 사용자에게 보고: 적용 N건(프로젝트) / 제안 M건(하네스, 승인 대기) / 폐기 K건(반박·1회성).

---

## retro-log.md 포맷

append-only. 회고 1회 = 요약 1줄 + 적용된 프로젝트 티어 변경마다 롤백 블록.

```markdown
## {YYYY-MM-DD} retro — 신규 {N}건 처리 / 적용 {A} · 제안 {P} · 폐기 {D}

### 적용 (프로젝트 티어, 자동)
- **{대상파일}** ← {교훈 한 줄}
  - critic: UPHELD | NARROW
  - 근거: {LEARNING 엔트리 마커들}
  - rollback: 아래 블록 제거 / 다음 diff 역적용
    ```diff
    + 추가된 정확한 텍스트
    ```

### 제안 (하네스 티어, 승인 대기)
- `harness-proposals/{date}-{slug}.md` — {대상 플러그인 파일} / {한 줄 요약}

### 폐기
- {교훈} — REFUTED: {critic 사유} | 1회성 | 중복
```

---

## 안전 규칙

- 한 회고에서 **프로젝트 티어 자동 적용은 최대 5건**. 초과분은 하네스 제안 큐로 보내거나 다음 회고로 미루고, 잘라낸 사실을 보고에 명시한다 (silent truncation 금지).
- 하네스 티어는 **회수와 무관하게 절대 자동 적용 없음**.
- LEARNING.md 원본은 **수정·삭제하지 않는다** (읽기 전용 입력). 커서는 retro-state.json에만.
- 회고 중 에러 → 커서 갱신하지 않고 중단 (다음 실행이 같은 엔트리를 다시 처리하도록). 부분 적용분은 retro-log에 남겨 롤백 가능하게.

---

## F16: 오염 격리 (provenance + 교차 프로젝트 기준)

결정적 로직: `hooks/lib/self_improve/recurrence.py` — `count_signals`, `has_cross_project`.

### Provenance 불변식

LEARNING.md의 모든 엔트리는 **provenance 태그를 필수**로 포함해야 한다:

```
<!-- tags: domain=<도메인>, stage=<발견단계>, provenance_repo=<repo식별자> -->
```

- `provenance_repo`: 신호를 생성한 repo 식별자 (예: `moon-harness`, `marvelous`).
- `stage`: `구현` | `pr-converge` | `회고` 중 하나.

### 단일 repo vs. 교차 프로젝트 구분

| 상황 | 판정 |
|------|------|
| 동일 repo에서 N회 반복 | **프로젝트 티어** 유지 (하네스 승격 불가) |
| 서로 다른 repo 2곳 이상 재현 | 하네스 티어 승격 **후보** (critic 추가 검증 필요) |

`has_cross_project(counter, cluster_key)` 가 `False` 이면 → 하네스 티어 승격 경로 차단.
단일 repo 5회 반복은 `has_cross_project=False` 이므로 하네스 티어 자동 승격 대상이 아니다.

> 📌 Phase B 클러스터링 시 `count_signals()` 를 호출하여 교차 프로젝트 여부를 확인한다. `has_cross_project=True` 이어야만 하네스 티어로 에스컬레이션 경로를 열 수 있다.

---

## F17: 학습 사다리 (L0–L4 + 절차적 메모리) + 재발 에스컬레이션

결정적 로직: `hooks/lib/self_improve/ladder.py` — `get_next_ladder_rung`.

### 사다리 정의

| 단계 | 메커니즘 | 사람 게이트 |
|------|---------|------------|
| **L0** | passive — LEARNING.md 기록 (입력층) | 없음 |
| **L1** | 큐레이션/압축 — `docs/lessons-learned.md` 일반화 교훈 | 없음 (프로젝트 티어) |
| **L2** | 관련성 라우팅 — 태그 on-demand 로드 (progressive disclosure) | 없음 (프로젝트 티어) |
| **L3** | enforcement — 교훈을 `hooks/` 체크로 구현 | **필수** (하네스 티어) |
| **L4** | 프롬프트/agent 수정 | **필수** (하네스 티어) |
| **절차적** | 성공 절차 스킬 결정화 | **필수** (F19 경로) |

### 재발 에스컬레이션

Phase B 클러스터링 후, 각 클러스터에 대해:

1. `get_next_ladder_rung(current_rung, recurrence_count)` 호출.
2. 반환된 `escalated=True` 이고 `requires_human=False` → **자동 에스컬레이션** (L0→L1, L1→L2).
3. 반환된 `requires_human=True` (L3+) → **제안만**, critic 게이트 + 사람 승인 필수.

> 📌 교훈이 L1에 기록된 후 재발하면 L2(on-demand 라우팅) 적용이 제안된다. L3 이상은 하네스 티어이므로 F11 자율성 통제가 적용된다.

---

## F18: @LEARNING.md 통째 import 폐기 → 태그 on-demand 로드

결정적 로직: `hooks/lib/self_improve/memory_router.py` — `route_memory`.

### 폐기된 방식 (금지)

```
@.harness/LEARNING.md   ← 절대 사용 금지
```

CLAUDE.md 또는 skill 프롬프트에서 LEARNING.md 전체를 `@` import하는 방식은 **폐기**되었다. 파일이 커질수록 무관한 교훈까지 전부 컨텍스트에 적재되어 토큰을 낭비하고 노이즈를 유발한다.

### 대체: 태그 기반 on-demand 라우팅

Phase A 수집 후, 실제 작업 컨텍스트 도메인과 일치하는 엔트리만 로드한다:

```python
result = route_memory(
    entries=new_entries,
    context_domain="auth",          # 현재 작업 도메인
    always_on_budget=800,           # 토큰 상한 (always-on 계층)
    ondemand_budget=500,            # 토큰 상한 (on-demand 계층)
)
# result["always_on"]  → 도메인 무관, 예산 내 엔트리
# result["on_demand"]  → 도메인 일치 엔트리만
```

### 3-스코프 메모리 분리

| 스코프 | 위치 | 설명 |
|--------|------|------|
| 유저 | `~/.claude/CLAUDE.md` | 전역 사용자 규칙 |
| Repo | `.harness/LEARNING.md` | 이 repo의 raw 교훈 |
| 플러그인 | `skills/*/SKILL.md`, `agents/*.md` | 하네스 공유 지식 |

> 📌 플러그인 스코프 메모리를 유저 또는 repo 스코프에 혼합하지 않는다. LEARNING.md는 repo 스코프 전용이다.

---

## F19: 자동 스킬 결정화 (스킬 생성/진화)

결정적 글루: `skills/self-improve/scripts/skill_scanner.py`.

### 트리거 조건 (3종)

1. **성공 패턴 5회 이상**: 동일 tool 사용 성공 절차가 LEARNING.md에 5회 이상 기록됨.
2. **오류-막다른길 후 작동 경로 발견**: 실패 후 성공 패턴이 기록됨.
3. **사용자 교정 기록**: 명시적 사용자 교정이 엔트리에 기재됨.

### 티어링

| 스킬 대상 티어 | 처리 |
|--------------|------|
| **프로젝트 티어** | 스킬 초안 자동 생성 (사람 게이트 없음) |
| **하네스 티어** | 스킬 초안 + 교차 프로젝트 근거 + 벤치마크 델타 포함 **제안만** |

> 📌 **Phase 3 경계**: 하네스 티어 스킬 자동 승격은 Phase 2 벤치마크 측정 기반 확보 후에만 가능. 벤치마크 델타 입력 없으면 cold-start short-circuit → 제안 생성 불가. Phase 1에서는 프로젝트 티어 스킬 자동 생성만 지원한다.

### Protected Set 절대 금지

다음 protected set 멤버는 **자동 생성·자동 수정 대상에서 영구 제외**된다:

```
skills/self-improve/    ← 이 루프 자체
skills/pr-converge/     ← 수렴 루프
agents/harness-improvement-critic.md
hooks/enforcement/      ← 게이트 로직
```

`is_protected(target_path)` 가 `True` 이면 → 즉시 폐기, 사람 검토 하 수동 EXTEND만 허용.

> 📌 protected set은 하드코딩된 상수(`hooks/lib/self_improve/guard.py`)이며, 데이터 파일로 설정하거나 자동화 로직의 입력으로 삼지 않는다.

### Dedup / Merge 제안

`skill_scanner.py`가 기존 스킬의 description 텍스트 겹침을 감지하면:
- 중복 생성 대신 **기존 스킬과의 dedup/merge 제안**을 생성한다.
- 실제 merge는 사람이 검토 후 수행한다.

### 다윈식 Prune

스킬 총 목록이 운영 기준 상한을 초과할 때:
- `skill_scanner.py` 결과로 저재사용 스킬을 식별한다.
- **아카이브 대상 제안**만 생성한다 — 자동 삭제 금지.

---

## Phase D apply_writer 흐름

결정적 글루: `skills/self-improve/scripts/apply_writer.py`.

```
apply_change(tier, target_path, append_text, harness_dir, ...)
    ├─ tier == "PROJECT"
    │   ├─ apply_project_change(target_path, ...)   ← 파일 직접 append
    │   │   └─ 하네스/protected 경로 → 즉시 거부 (defence-in-depth)
    │   └─ retro-log.md에 rollback 블록 append
    └─ tier == "HARNESS"
        └─ write_harness_proposal(harness_dir, ...)
            └─ .harness/harness-proposals/{date}-{slug}.md 생성만
               (플러그인 파일 절대 편집하지 않음)
```

> 📌 하네스 티어 UPHELD 판정이라도 플러그인 파일(skills/, agents/, hooks/) 편집은 발생하지 않는다. `apply_project_change`는 `classify_tier`로 재검증하여 harness 경로이면 `ok=False` 반환한다 (defence-in-depth).

---

## 참조

- 입력 캡처 규칙: [skills/sdd/SKILL.md — LEARNING 캡처](../sdd/SKILL.md)
- 검증 agent: [agents/harness-improvement-critic.md](../../agents/harness-improvement-critic.md)
- 자동 트리거 지점: [skills/sdd-orchestrator/SKILL.md — Step 4 완료 처리](../sdd-orchestrator/SKILL.md)
- 결정적 글루 스크립트: `skills/self-improve/scripts/` (cursor_runner, precheck_runner, apply_writer, cap_runner, skill_scanner)
- Wave 1 코어 라이브러리: `hooks/lib/self_improve/` (cursor, recurrence, precheck, tier, guard, cap, ladder, memory_router)
