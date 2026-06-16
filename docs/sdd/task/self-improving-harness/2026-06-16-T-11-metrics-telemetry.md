# T-11: 핵심 지표 텔레메트리 + retro-log 머신리더블 기록 (F23)

## 관련 문서
- spec: `docs/sdd/spec/2026-06-16-self-improving-harness.md` — F23 (핵심 지표 측정: 자동 측정 가능 vs 사후 사람 검토 구분), F13 (retro-log rollback 블록 포맷), 가정 3 (오에스컬레이션률 측정 방식)
- arch: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md` — §8 (telemetry/metrics: auto-measurable from retro-log + state files; recurrence-rate anchor must be machine-readable), §10 (Phase 2 컴포넌트)

## Wave
**Wave 3** (Phase 2 측정 substrate — Wave 2 의존)

## 구현자
sdd-python-engineer

## 테스트 타입

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| 지표 계산 함수 | 단위 (pytest, golden fixture) | retro-log.md + state JSON 파싱 → 지표 dict |
| retro-log 파싱 | 단위 (pytest) | append-only 포맷 파싱 |

## 완료 조건
- [ ] `hooks/lib/self_improve/metrics.py`: 다음 자동 측정 지표를 `retro-log.md` + `pr-converge-state.json` + `retro-state.json`에서 계산하는 순수 함수들 (F23, 자동 측정 가능 항목만):
  - `convergence_rate(state_history: list) -> float`: CONVERGED/전체 실행 비율
  - `avg_iterations_to_green(state_history: list) -> float`: green까지 평균 iteration
  - `recurrence_rate(retro_log_text: str) -> float`: 동일 교훈 재발률 (핵심 앵커 — F23 Acceptance)
  - `skill_reuse_rate(state_history: list) -> dict`: 스킬별 호출/성공 집계 (기초 구조만)
- [ ] 재발률(`recurrence_rate`) 이 사람 수동 집계 없이 `retro-log.md` 파싱으로 측정 가능 (F23 Acceptance: 머신리더블)
- [ ] `retro-log.md` 포맷 파싱 함수: spec §상태파일계약 포맷의 `## {date} retro — 신규 N건 / 적용 A · 제안 P · 폐기 D` 헤더 파싱 → `{date, new, applied, proposed, dropped}` dict
- [ ] 지표를 `.harness/metrics.json` 또는 `retro-log.md`의 요약 헤더에서 추적 가능한 형태로 기록하는 `write_metrics(metrics: dict, path: Path)` 함수 (atomic_write 사용)
- [ ] 사후 사람 검토 지표(오에스컬레이션률, critic precision/recall)는 이 태스크에서 구현하지 않음 (F23 주석: Phase 2.5/3, 가정 3)
- [ ] 코멘트 분류 정확도는 측정 출처(사후 레이블)를 metrics.json의 `requires_human_label: true` 필드로 명시 (Minor② 반영)
- [ ] `pytest tests/test_metrics.py` 네트워크 없이 통과
- [ ] `.harness/metrics.json` 스키마에 `last_computed_at`, `cold_start` 플래그 포함 (데이터 부족 시 표시)

## 의존 태스크
- T-1 (atomic_write — metrics.json 기록)
- T-6 (pr-converge-state.json 구조 — convergence_rate, iterations 데이터 소스)
- T-7 (retro-log.md 포맷 — recurrence_rate 데이터 소스)

## 예상 변경 파일
- `hooks/lib/self_improve/metrics.py` — 지표 계산 함수, retro-log 파서, write_metrics
- `hooks/lib/self_improve/__init__.py` — 공개 API 추가
- `tests/test_metrics.py` — 지표 계산 단위 테스트
- `tests/fixtures/retro_log_sample.md` — retro-log.md 골든 픽스처 (여러 회고 이력)
- `tests/fixtures/metrics_expected.json` — 기대 지표 값 골든 픽스처

## Steps
- [ ] `retro_log_parser(text: str) -> list[dict]` 구현: `## {date} retro —` 패턴으로 헤더 파싱, N/A/P/D 숫자 추출
- [ ] `convergence_rate`, `avg_iterations_to_green` 구현: state_history(pr-converge-state JSON 이력 list)에서 계산
- [ ] `recurrence_rate` 구현: retro_log에서 동일 교훈 마커 재등장 횟수 추적 → 재발률 = 재발 건수 / 전체 적용 건수
- [ ] `skill_reuse_rate` 스텁 구현: state_history에서 skill 호출 집계 (데이터 없으면 cold_start 반환)
- [ ] `write_metrics` 구현: 지표 dict + `last_computed_at` + `cold_start` 플래그 → atomic_write
- [ ] `tests/fixtures/retro_log_sample.md` 작성 (3회 이상 회고 이력, 재발 패턴 1개 포함)
- [ ] `tests/test_metrics.py` 작성 (재발률 계산, cold_start 케이스, retro_log 파싱 경계)
- [ ] `pytest tests/test_metrics.py -v` 통과 확인

## 검증 명령어
```bash
cd /Users/moon/workspace/moon-harness/worktrees/self-improving-harness
pytest tests/test_metrics.py -v
```
