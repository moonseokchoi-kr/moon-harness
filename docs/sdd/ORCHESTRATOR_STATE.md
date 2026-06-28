# Orchestrator State

## 메타
- feature: `code-mapper`
- spec 문서: `docs/sdd/spec/2026-06-26-code-mapper.md`
- arch 문서: `docs/sdd/design/arch/2026-06-26-code-mapper.md`
- ui 문서: 해당 없음 (SIMPLE 모드)
- api 문서: 해당 없음 (SIMPLE 모드)
- 시작 시각: 2026-06-29T00:00:00Z
- 마지막 갱신: 2026-06-29T00:00:00Z
- 상태: COMPLETED
- 워밍업 완료: 미실행(fast-scoped)

> 단일 오케스트레이터 모드 — Wave 1→2→3이 단일 선형 의존 체인 (T-1/T-2 병렬 → T-3/T-4 직렬 의존). 독립 클러스터 2개 이상 없음. 팀 배정 생략.

---

## 빌드 프로파일

> 출처: `docs/sdd/design/arch/2026-06-26-code-mapper.md` § 빌드 프로파일 (2026-06-26 확인)

| 필드 | 값 | 비고 |
|------|-----|------|
| 유형 | fast-scoped | 컴파일 산출물 없음(마크다운 + stdlib python). 빌드 단계 없이 테스트 직접 실행. |
| 워밍업 빌드 | (생략) | fast-scoped — 콜드 빌드 비용 없음 |
| 증분 빌드 | (생략) | 빌드 산출물 없음 |
| 테스트 실행 | `PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q` | pytest는 homebrew python(3.14)에 설치, Xcode python3엔 없음 |
| 테스트 필터 문법 | `... pytest tests/test_code_mapper_*.py -q` 또는 `-k <name>` | 태스크별 스코프 지정 |
| clean 정책 | no-clean | 캐시(`.pytest_cache`) 보존 |

---

## Wave 구성

| Wave | 태스크 | 구현자 | 의존성 | 동시 실행 최대 |
|------|--------|--------|--------|--------------|
| 1 | T-1, T-2 | sdd-python-engineer (T-1), sdd-implementer (T-2) | 없음 | 2 |
| 2 | T-3 | sdd-implementer | T-2 | 1 |
| 3 | T-4 | sdd-implementer | T-1, T-2 | 1 |

**DAG 단순 표현:**
```
Wave 1: T-1 (코어+pytest)     T-2 (SKILL.md)    ← 병렬 가능
Wave 2: T-3 (agent inject)    ← T-2 완료 후
Wave 3: T-4 (evals)           ← T-1, T-2 완료 후
```

> **Wave 배치 근거:**
> - T-1, T-2: 상호 독립 (코어는 SKILL.md를 런타임 의존하지 않음). 단 분류 기준은 T-2 SKILL.md를 SSOT로 정의하고 T-1이 그것을 따르는 방향으로 구현자 간 조율 필요.
> - T-3: T-2(SKILL.md)가 존재해야 포인터 타겟이 유효함 → T-2 이후.
> - T-4: T-1(코어 패키지)과 T-2(SKILL.md) 모두 필요 → Wave 3. T-3와는 독립이나 T-1·T-2가 공통 전제라 Wave 3에 묶음.

---

## 태스크 상태

| ID | Wave | 구현자 | Status | Iteration | Agent | 비고 |
|----|------|--------|--------|-----------|-------|------|
| T-1 | 1 | sdd-python-engineer | complete | 1 | 03a2195 | 코어+pytest. compliance PASS, review PASS. SSOT 정합 수정 |
| T-2 | 1 | sdd-implementer | complete | 0 | 0d60e12 | SKILL.md SSOT. compliance PASS, review PASS |
| T-3 | 2 | sdd-implementer | complete | 0 | 7838759 | 단락 주입 +8/-0, 위치·문구 검증 |
| T-4 | 3 | sdd-implementer | complete | 0 | e73f20d | evals 폴백 시나리오 (2 cases, 코어 재사용) |

### Status 값
- `pending` — 아직 시작 안 됨
- `implementing` — Engineer Agent가 구현 중
- `reviewing` — Reviewer Agent가 리뷰 중
- `fixing` — Engineer Agent가 리뷰 피드백 반영 중
- `testing` — Test Automator Agent가 검증 중
- `complete` — 완료 (리뷰 + 테스트 통과)
- `interrupted` — 리밋/에러로 중단됨
- `escalated` — 3회 실패, 사용자 개입 필요

---

## 에이전트 배정
- 오케스트레이터: 메인 세션
- Engineer 슬롯 1: idle
- Engineer 슬롯 2: idle
- Reviewer: idle
- Test Automator: idle

---

## 파일 소유권

| 태스크 | 소유 파일/디렉토리 | git add 규칙 |
|--------|-------------------|-------------|
| T-1 | `hooks/lib/code_mapper/` (전체), `tests/test_code_mapper_core.py` | 이 경로만 명시적 add (`git add -A` 금지) |
| T-2 | `skills/code-mapper/SKILL.md` | 이 파일만 명시적 add |
| T-3 | `agents/sdd-implementer.md` | 이 파일만 명시적 add (단락 추가 1건만) |
| T-4 | `evals/scenarios/` 아래 신규 code-mapper 시나리오 파일 | 해당 파일만 명시적 add |

> **병렬 git 규율**: 공유 worktree이므로 각 에이전트는 위 소유 파일만 `git add <경로>` 로 명시 스테이징. `git add -A` / `git add .` 금지. 브랜치 전환 금지.

---

## 중요 제약 (Engineer에게 전달)

1. **결정↔판단 분리**: `hooks/lib/code_mapper/` 코어는 stdlib-only 순수함수만. MCP 호출·의미 판단 코드 삽입 금지.
2. **정체성 불변**: ephemeral. 어떤 코드도 코드맵을 디스크에 저장/파일에 쓰면 안 됨. 계약/검증/종속/하드게이트 금지.
3. **sdd-implementer 준-protected**: T-3는 단락 1개 추가만. 기존 섹션 0 변경. diff 최소.
4. **하네스 범용**: 레포 특화 경로·명령 하드코딩 금지.
5. **오프라인/라이브 비혼합**: `pytest tests/`는 `evals/`를 수집하지 않음.

---

## DAG 의존 그래프

```
T-1 (코어+pytest) ─────────────────────────► T-4 (evals)
                                               ▲
T-2 (SKILL.md) ────────────────────────────────┤
         │                                      │
         └──► T-3 (agent inject)                │
              (T-2 완료 후)               (T-1+T-2 완료 후)
```

---

## 이력
- [2026-06-29] ORCHESTRATOR_STATE.md 초기 생성 — code-mapper DAG/Wave 구성 완료, 상태 PLANNING
- [2026-06-29] Wave1 T-1·T-2 complete (compliance/review PASS, SSOT 정합 수정) → Wave2 T-3 complete (+8/-0) → Wave3 T-4 complete → 통합검증 512 passed → result 생성 → COMPLETED
