# Orchestrator State

## 메타
- spec 문서: `docs/sdd/spec/2026-06-16-self-improving-harness.md`
- arch 문서: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md`
- ui 문서: 해당 없음 (HARNESS 모드)
- api 문서: 해당 없음 (HARNESS 모드)
- 시작 시각: 2026-06-16T00:00:00Z
- 마지막 갱신: 2026-06-16T00:00:00Z
- 상태: EXECUTING

> 단일 오케스트레이터 모드 — Wave 1→2→3이 단일 선형 의존 체인. 독립 클러스터 없음. 팀 배정 생략.

---

## Wave 구성

| Wave | Phase | 태스크 | 의존성 | 동시 실행 최대 |
|------|-------|--------|--------|--------------|
| 1-A | Phase 1 foundation | T-1, T-2 | 없음 | 2 |
| 1-B | Phase 1 foundation | T-3, T-4 | T-2 (T-3), T-1+T-2 (T-4) | 2 |
| 1-C | Phase 1 foundation | T-5 | T-1, T-2, T-3, T-4 | 1 |
| 2   | Phase 1 skill EXTEND | T-6, T-7, T-8 | T-1+T-2+T-4 (T-6), T-1+T-2+T-3+T-4 (T-7), 없음→Wave 2 배치 (T-8) | 3 |
| 3   | Phase 2 substrate | T-9, T-10, T-11 | T-5+T-7+T-8 (T-9), T-5+T-9 (T-10), T-1+T-6+T-7 (T-11) | 2 (T-9·T-11 병렬, T-10은 T-9 완료 후) |

> **NFR-3 Phase 경계 정렬**
> - Wave 1 (1-A·1-B·1-C) = Phase 1 foundation: 결정적 코어 패키지 + 오프라인 pytest suite
> - Wave 2 = Phase 1 skill EXTEND: protected set (SKILL.md, agent.md) 수동 EXTEND
> - Wave 3 = Phase 2 측정 substrate: 벤치마크 러너 + 라이브 eval 하네스 + 텔레메트리
> - **Phase 3 harness-tier 자동 승격은 이 STATE.md 범위 밖.** Phase 2 벤치마크 측정 기반 확보 후 별도 게이트 통과 필요.

---

## 현재 진행
- 현재 Wave: 1-B
- 완료 Wave: 1-A (T-1, T-2 complete — 103/103 pytest, P1 0)

---

## 태스크 상태

| ID | Wave | 구현자 | Status | Iteration | Agent | 비고 |
|----|------|--------|--------|-----------|-------|------|
| T-1 | 1-A | sdd-python-engineer | complete | 1 | - | cb8c411. 103/103, REVIEW_PASS P1 0 |
| T-2 | 1-A | sdd-python-engineer | complete | 1 | - | a265023. 103/103, REVIEW_PASS P1 0 |
| T-3 | 1-B | sdd-python-engineer | impl-done | 1 | slot-1 | 62신규/243전체 통과(25200cd). ⚠️커밋에 T-4 partial 혼입 — T-4 완료후 정리 |
| T-4 | 1-B | sdd-python-engineer | implementing | 1 | slot-2 | 상한/케이던스/서킷브레이커 + 라우터 |
| T-5 | 1-C | sdd-python-engineer | pending | 0 | - | Wave 1 코어 전체 오프라인 pytest suite |
| T-6 | 2 | sdd-implementer | pending | 0 | - | [PROTECTED] pr-converge SKILL.md EXTEND + scripts/ — 사람 검토 하 수동 EXTEND, 자동생성루프 대상 아님 |
| T-7 | 2 | sdd-implementer | pending | 0 | - | [PROTECTED] self-improve SKILL.md EXTEND + scripts/ — 사람 검토 하 수동 EXTEND, 자동생성루프 대상 아님 |
| T-8 | 2 | sdd-implementer | pending | 0 | - | [PROTECTED] harness-improvement-critic.md EXTEND — 사람 검토 하 수동 EXTEND, 자동생성루프 대상 아님 |
| T-9 | 3 | sdd-python-engineer | pending | 0 | - | benchmarks/ frozen sets + 러너 |
| T-10 | 3 | sdd-python-engineer | pending | 0 | - | evals/ 라이브 eval 하네스 |
| T-11 | 3 | sdd-python-engineer | pending | 0 | - | 핵심 지표 텔레메트리 + retro-log |

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
- Engineer 슬롯 3: idle
- Engineer 슬롯 4: idle
- Reviewer: idle
- Test Automator: idle

---

## Protected Set 비고

Wave 2의 T-6, T-7, T-8은 **protected set** 파일을 직접 수정한다:
- T-6: `skills/pr-converge/SKILL.md` (protected set 멤버)
- T-7: `skills/self-improve/SKILL.md` (protected set 멤버)
- T-8: `agents/harness-improvement-critic.md` (protected set 멤버)

이 세 태스크는 **사람 검토 하의 수동 EXTEND**만 허용된다. 자동생성루프(Engineer Agent 자율 실행) 대상이 아니다. 오케스트레이터는 이 태스크 실행 전 사용자 승인 게이트를 거쳐야 한다.

---

## 파일 소유권

| 태스크 | 소유 파일/디렉토리 |
|--------|-------------------|
| T-1 | `hooks/lib/self_improve/__init__.py`, `hooks/lib/self_improve/state_io.py`, `tests/test_state_io.py`, `tests/fixtures/pr_converge_state_v1.json`, `tests/fixtures/retro_state_v1.json` |
| T-2 | `hooks/lib/self_improve/tier.py`, `hooks/lib/self_improve/guard.py`, `hooks/lib/self_improve/parser.py`, `tests/test_tier_classifier.py`, `tests/test_protected_guard.py`, `tests/test_tag_parser.py`, `tests/fixtures/sample_learning.md` |
| T-3 | `hooks/lib/self_improve/cursor.py`, `hooks/lib/self_improve/recurrence.py`, `hooks/lib/self_improve/precheck.py`, `tests/test_cursor.py`, `tests/test_recurrence.py`, `tests/test_precheck.py`, `tests/fixtures/sample_learning_with_markers.md`, `tests/fixtures/target_file_with_duplicate.md` |
| T-4 | `hooks/lib/self_improve/circuit_breaker.py`, `hooks/lib/self_improve/cap.py`, `hooks/lib/self_improve/memory_router.py`, `hooks/lib/self_improve/ladder.py`, `tests/test_cap_cadence.py`, `tests/test_memory_router.py`, `tests/test_ladder.py` |
| T-5 | `tests/conftest.py`, `pytest.ini` (또는 `pyproject.toml`) |
| T-6 | `skills/pr-converge/SKILL.md`, `skills/pr-converge/scripts/`, `tests/test_pr_converge_scripts.py`, `tests/fixtures/pr_converge_patterns.json` |
| T-7 | `skills/self-improve/SKILL.md`, `skills/self-improve/scripts/`, `tests/test_self_improve_scripts.py`, `tests/fixtures/harness_proposal_template.md` |
| T-8 | `agents/harness-improvement-critic.md` |
| T-9 | `hooks/lib/self_improve/bench_runner.py`, `benchmarks/sets/train/`, `benchmarks/sets/held-out/`, `benchmarks/run_live.sh`, `tests/test_bench_runner.py`, `tests/fixtures/bench_baseline.json`, `tests/fixtures/bench_candidate.json` |
| T-10 | `evals/`, `tests/test_eval_harness_structure.py` |
| T-11 | `hooks/lib/self_improve/metrics.py`, `tests/test_metrics.py`, `tests/fixtures/retro_log_sample.md`, `tests/fixtures/metrics_expected.json`, `.harness/metrics.json` (런타임 출력) |

---

## DAG 의존 그래프

```
T-1 ────────────────────────────────────────────────────────────────────► T-4 ──► T-6
  │                                                                         │       │
  └─────────────────────────────────────────────────────────► T-4           │       │
                                                                             │       │
T-2 ──► T-3 ──────────────────────────────────────────────────────────────► T-7    │
  │       │                                                                   │       │
  │       └──────────────────────────────────────────────────► T-7            │       │
  │                                                                             │       │
  └─────────────────────────────────────────────────────────► T-4 ─────────► T-6    │
                                                                                       │
T-1,T-2,T-3,T-4 ──────────────────────────────────────────────────────────► T-5 ──► T-9 ──► T-10
                                                                                       │
T-8 (Wave 2, 독립) ────────────────────────────────────────────────────────────────► T-9

T-1,T-6,T-7 ──────────────────────────────────────────────────────────────────────► T-11
```

**단순 표현:**
```
Wave 1-A: T-1  T-2
Wave 1-B: T-3(←T-2)  T-4(←T-1,T-2)
Wave 1-C: T-5(←T-1,T-2,T-3,T-4)
Wave 2:   T-6(←T-1,T-2,T-4)  T-7(←T-1,T-2,T-3,T-4)  T-8(←없음)
Wave 3:   T-9(←T-5,T-7,T-8)  T-11(←T-1,T-6,T-7)  [동시 가능]
          T-10(←T-5,T-9)     [T-9 완료 후]
```

---

## 이력
- [2026-06-16] ORCHESTRATOR_STATE.md 초기 생성 — DAG/Wave 구성 완료, 상태 PLANNING
