# T-10: evals/ 라이브 eval 하네스 (F21 live layer)

## 관련 문서
- spec: `docs/sdd/spec/2026-06-16-self-improving-harness.md` — F21 (eval 2계층 — 오프라인 pytest와 분리된 라이브 eval), F23 (코멘트 분류 정확도 등 판단 지표)
- arch: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md` — §3.7 (evals/ — `claude -p` headless + LLM-judge), §8 (profiling: live evals/benchmarks not in blocking CI path), §11 (라이브 eval 레이어: 판단 레이어 semantic correctness)

## Wave
**Wave 3** (Phase 2 측정 substrate — Wave 2 의존)

## 구현자
sdd-python-engineer

## 테스트 타입

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| 라이브 eval 하네스 | 라이브 eval (integration) | `claude -p` 헤드리스 + LLM-judge. pytest tests/에 포함 안 됨 |
| eval 하네스 스크립트 자체 구조 | 단위 (pytest) | 입력 포맷 파싱 등 결정적 부분만 |

## 완료 조건
- [ ] `evals/` 디렉토리 분리 — `tests/`와 물리적으로 별도 (F21: 혼합 금지)
- [ ] `evals/run_eval.sh` (또는 `evals/run_eval.py`): `claude -p` 헤드리스 실행 + LLM-judge 시나리오 실행 진입점. 명시적 플래그(예: `--live`) 없으면 실행 안 됨
- [ ] `evals/scenarios/` 아래 판단 레이어 시나리오 파일: 코멘트 분류 정확도(actionable vs escalation), 클러스터링 품질, critic 판정 일관성 — 최소 각 1개
- [ ] LLM-judge 결과를 구조화된 JSON으로 `evals/results/` 에 기록
- [ ] `pytest tests/` 실행 시 `evals/` 아래 어떤 것도 실행되지 않음 (F21 Acceptance: `pytest tests/` 가 gh CLI, claude API 없이 완료)
- [ ] `evals/run_eval.sh --help`가 사용 방법과 "별도 API 크레딧 비용 발생" 경고를 출력
- [ ] 시나리오 입력 파싱 등 결정적 로직은 `tests/test_eval_harness_structure.py`로 단위 테스트 가능
- [ ] 라이브 eval와 benchmark runner의 `claude -p` 호출이 동일 파이프라인 단계에서 혼합되지 않음

## 의존 태스크
- T-5 (pytest 인프라 — evals 분리 구조 확인)
- T-9 (benchmarks/ 구조 — 분리 원칙 동일하게 적용)

## 예상 변경 파일
- `evals/__init__.py` (또는 `evals/README.md`) — 목적, 실행 방법, pytest tests/와 분리됨을 명시
- `evals/run_eval.py` — 라이브 eval 진입점 (`--live` 플래그)
- `evals/scenarios/comment_classification.json` — actionable/escalation 분류 시나리오
- `evals/scenarios/clustering_quality.json` — 클러스터링 시나리오
- `evals/scenarios/critic_consistency.json` — critic 판정 일관성 시나리오
- `evals/results/.gitkeep` — 결과 디렉토리 (실제 결과는 .gitignore)
- `tests/test_eval_harness_structure.py` — 시나리오 파일 파싱 결정적 로직 단위 테스트

## Steps
- [ ] `evals/` 디렉토리 구조 생성 (scenarios/, results/, README.md)
- [ ] `evals/README.md` 작성: 목적, "이 디렉토리는 pytest tests/와 독립 실행됨", API 크레딧 소비 경고
- [ ] `evals/scenarios/` 아래 JSON 시나리오 파일 3개 작성 (각 시나리오: input, expected_label, judge_criteria)
- [ ] `evals/run_eval.py` 스켈레톤: 시나리오 파일 로드 → `claude -p` 헤드리스 호출 → LLM-judge 판정 → `evals/results/{date}-result.json` 기록. `--live` 플래그 없으면 dry-run 출력 + 종료
- [ ] `tests/test_eval_harness_structure.py`: 시나리오 JSON 포맷 검증 (필수 키 존재, 타입 체크) — claude 호출 없음
- [ ] `pytest tests/test_eval_harness_structure.py -v` 통과 + `pytest tests/ --collect-only 2>&1 | grep evals` 출력 없음 확인

## 검증 명령어
```bash
cd /Users/moon/workspace/moon-harness/worktrees/self-improving-harness
# 오프라인 구조 테스트만:
pytest tests/test_eval_harness_structure.py -v
# live eval 분리 확인:
pytest tests/ --collect-only 2>&1 | grep evals || echo "PASS: evals not in pytest tests/"
```
