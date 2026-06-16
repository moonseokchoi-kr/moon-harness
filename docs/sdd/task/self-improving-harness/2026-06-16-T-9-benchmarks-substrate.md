# T-9: benchmarks/ frozen sets + 러너 (F22, F24)

## 관련 문서
- spec: `docs/sdd/spec/2026-06-16-self-improving-harness.md` — F22 (벤치마크 fitness function), F24 (벤치마크 규율: frozen, held-out, 콜드스타트), 미해결 2 (초기 골든셋 구성)
- arch: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md` — §3.5 (benchmarks/ substrate), §10 (Phase 2 컴포넌트), §11 (테스트 전략 — benchmark layer), §12 (Phase gate: Phase 1 stable → Phase 2)

## Wave
**Wave 3** (Phase 2 측정 substrate — Wave 2 의존)

## 구현자
sdd-python-engineer

## 테스트 타입

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| 벤치마크 러너 점수 산술 | 단위 (pytest) | 순수 점수 계산 — 네트워크 없음 |
| 결과 delta + held-out 회귀 판정 | 단위 (pytest, golden fixture) | baseline vs candidate 비교 |
| transcript 생성 (live) | 라이브 eval (integration) | `claude -p` 호출 — 별도 단계 |

## 완료 조건
- [ ] `benchmarks/sets/train/` 디렉토리 존재 + 초기 골든 케이스 최소 1개 이상 (F24 frozen 원칙 준수, 인간 레이블 제공)
- [ ] `benchmarks/sets/held-out/` 디렉토리 존재 + train과 분리된 held-out 케이스 (F24)
- [ ] 벤치마크 셋 파일이 eval 루프에서 수정되지 않음 (frozen 원칙 — 러너가 파일을 읽기만 하고 쓰지 않음)
- [ ] `hooks/lib/self_improve/bench_runner.py` (arch §3.5 지시에 따라 shared lib 내 배치): `score_baseline(set_path) -> dict`, `score_candidate(set_path, candidate_fn) -> dict`, `compute_delta(baseline, candidate) -> dict`
- [ ] `compute_delta` 결과: `{delta_pct: float, held_out_regression: bool, cold_start: bool}` 구조
- [ ] 데이터 5건 미만 시 `cold_start=True`, `delta_pct=None` 반환 — "콜드스타트, 측정 불가" 출력 (F24 Acceptance)
- [ ] held-out 셋 파일이 candidate 평가 루프 직접 수정 불가 (write 경로 없음)
- [ ] 점수 산술 (`compute_delta`) 이 `pytest tests/test_bench_runner.py` 로 오프라인 통과
- [ ] 실제 transcript 생성 (`claude -p`) 은 `benchmarks/run_live.sh` 또는 별도 단계로 분리 (pytest tests/ 포함 안 됨)
- [ ] Phase 3 harness-tier promotion 경로가 `compute_delta` 결과를 mandatory 입력으로 요구하는 구조 — 결과 없으면 cold-start short-circuit (arch §10 Phase 3 gate)

## 의존 태스크
- T-5 (pytest 인프라 완성 — tests/ 구조)
- T-7 (self-improve scripts — apply_writer가 벤치마크 델타를 인풋으로 사용)
- T-8 (critic EXTEND — F22 벤치마크 게이트 입력 준비)

## 예상 변경 파일
- `benchmarks/sets/train/` — 초기 훈련용 골든 케이스 파일들
- `benchmarks/sets/held-out/` — 분리된 held-out 케이스 파일들
- `hooks/lib/self_improve/bench_runner.py` — 점수 산술 함수 (arch §3.5에 따라 shared lib 배치)
- `benchmarks/run_live.sh` — transcript 생성 live 단계 스크립트 (pytest에서 분리)
- `tests/test_bench_runner.py` — 점수 산술 단위 테스트
- `tests/fixtures/bench_baseline.json` — 베이스라인 점수 골든 픽스처
- `tests/fixtures/bench_candidate.json` — 후보 점수 골든 픽스처

## Steps
- [ ] `benchmarks/sets/train/` + `benchmarks/sets/held-out/` 디렉토리 생성 + README 규칙(frozen, 수동 추가만)
- [ ] 초기 골든 케이스 설계: pr-converge 수렴 시나리오 최소 3개 (train), held-out 최소 2개 — 사람이 레이블링하는 방식으로 내용 주석 작성 (미해결 2 인정, 초기는 사람 레이블)
- [ ] `bench_runner.py` 구현: `score_baseline`, `score_candidate`, `compute_delta` (cold_start 5건 미만 체크 포함). 파일 읽기 전용 — write 경로 없음
- [ ] `tests/test_bench_runner.py` 작성: delta 양수 케이스, delta 음수 케이스, cold_start 케이스, held_out_regression=True 케이스
- [ ] `benchmarks/run_live.sh` 스켈레톤: `claude -p` 호출로 transcript 생성, 결과를 임시 파일에 저장, score 계산 호출
- [ ] `pytest tests/test_bench_runner.py -v` 통과 + `pytest tests/ --collect-only 2>&1 | grep bench_runner` 확인

## 검증 명령어
```bash
cd /Users/moon/workspace/moon-harness/worktrees/self-improving-harness
pytest tests/test_bench_runner.py -v
# live 단계는 별도 (pytest tests/에서 분리됨을 확인):
pytest tests/ --collect-only 2>&1 | grep -v bench_runner | head -5
```
