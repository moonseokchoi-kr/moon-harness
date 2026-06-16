# Self-Improving Harness — Phase 4 실행 결과

> SDD 사이클 완료 보고. spec: `docs/sdd/spec/2026-06-16-self-improving-harness.md` · arch: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md`

## 요약

moon-harness 플러그인에 **2계층 자가개선 시스템**을 구현했다. 11개 태스크 / 5 Wave 전부 완료, **463 pytest 전량 통과**, P1 이슈 0(수정 후), 결정적 로직 전부 stdlib-only.

- **pr-converge** (즉각 층위): PR을 CI/CD·테스트·빌드·린트·모든 리뷰 코멘트에 대해 green까지 수렴
- **self-improve** (메타 층위): 누적 교훈을 진단·검증·반영, 2티어 위험도 격리 + 오염격리
- **검증 = 벤치마크(fitness function)**: "루프 ≠ 개선"을 막는 frozen·held-out 측정 substrate

## Wave별 결과

| Wave | Phase | 태스크 | 결과 |
|------|-------|--------|------|
| 1-A | foundation | T-1 state_io, T-2 tier/guard/parser | ✅ 103/103, P1 0 |
| 1-B | foundation | T-3 cursor/recurrence/precheck, T-4 breaker/cap/cadence/router/ladder | ✅ 243/243, P1 0 |
| 1-C | foundation | T-5 오프라인 pytest 스위트 (conftest/socket 차단) | ✅ 243/243 |
| 2 | skill EXTEND | T-6 pr-converge(+F15), T-7 self-improve(+F16~19), T-8 critic(+F16/F22) | ✅ 322/322, P1 0 |
| 3 | 측정 substrate | T-9 benchmarks, T-10 evals, T-11 metrics | ✅ 463/463, P1 2건 발견·수정 |

## 핵심 불변식 (구현+리뷰로 검증)

- **결정↔판단 분리 (NFR-1)**: 결정 로직 전부 `hooks/lib/self_improve/`(13모듈, stdlib-only, 무네트워크/LLM, fail-safe). 판단(코멘트분류·클러스터링·critic 반박)만 SKILL/agent 프롬프트. claude -p 호출은 셸/격리 경로에만.
- **오염격리 (NFR-2)**: `apply_writer`가 HARNESS/protected 경로에 직접 쓰지 않음(이중 체크 + 경로 traverse 차단, 리뷰 실측). 단일 repo N건은 하네스 승격 불가(교차 프로젝트 2곳+ 필요). protected set(self-improve·pr-converge·critic·게이트) 자동수정 금지.
- **Phase 게이팅 (NFR-3)**: `gate_adoption`이 점수 하락·held-out 회귀·콜드스타트(데이터<5)를 전부 채택 거부 → Phase 3 하네스 자동승격은 Phase 2 측정 입증 전 구조적으로 불가(missing-input 게이트).
- **F4 케이던스**: 270/1200/None만, 300 절대 반환 안 함(코드+런타임 이중 assert).
- **F18 on-demand**: `@.harness/LEARNING.md` 통째 import 폐기, 태그 필터 라우팅.
- **F23 재발률**: retro-log 파싱으로 사람 수동집계 없이 자동 추출(핵심 앵커).
- **F21 eval 2계층**: 오프라인 pytest(`tests/`, CI·비용0) ↔ 라이브(`evals/`, claude -p, CLI 부재 시 graceful degrade)가 물리적 분리(pytest 수집 0건).

## Phase 3 실행 중 발견·수정한 P1 (리뷰 게이트 작동 증거)

1. `run_live.sh` held-out cold_start 채택 게이트 무력화(F22/F24 위반) → `gate_adoption()` 결정 함수로 분리 + 회귀 테스트.
2. `run_eval.py` judge 템플릿 `{}` 미이스케이프로 `--live` KeyError 크래시 → 시나리오 3종 `{{}}` 이스케이프 + 포맷 회귀 테스트.

## 산출물

- 코어 패키지 `hooks/lib/self_improve/` — 13 모듈, 공개 심볼 52
- 스킬 EXTEND: `skills/pr-converge/` `skills/self-improve/` (+ scripts/ 9개), `agents/harness-improvement-critic.md`
- 측정: `benchmarks/`(frozen train/held-out + bench_runner), `evals/`(라이브 하네스 + 시나리오 3), `metrics.py`
- 테스트: `tests/` 15파일 / **463 통과**

## 범위 밖 (의도적 deferral)

- **Phase 3 하네스 티어 자율 자동승격**: 제안 생성 + 사람 게이트(안전 경로)까지 구현. 자율 승격 트리거는 Phase 2 측정 입증 후 별도 사이클.
- 벤치 초기 골든셋 확장(현재 train 3 / held-out 2 — 콜드스타트), 사후검토 지표(오에스컬레이션률·critic precision/recall) 자동화.

## prior-art 처리

기존 초안(self-improve, pr-converge, harness-improvement-critic) 전부 **폐기 없이 EXTEND** — 산문을 Wave 1 코어 호출로 전환하고 F15~F22 신설 반영.
