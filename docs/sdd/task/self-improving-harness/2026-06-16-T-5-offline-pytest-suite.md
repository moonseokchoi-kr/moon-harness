# T-5: Wave 1 코어 전체 오프라인 pytest 테스트 스위트 완성

## 관련 문서
- spec: `docs/sdd/spec/2026-06-16-self-improving-harness.md` — F20 (결정적 로직 pytest 검증), F21 (오프라인 eval — 네트워크/LLM 무호출, CI-blocking)
- arch: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md` — §3.6 (tests/), §8 (CI: pytest tests/ must be CI gate), §11 (테스트 전략 — unit/offline golden)

## Wave
**Wave 1** (Phase 1 foundation)

## 구현자
sdd-python-engineer

## 테스트 타입

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| Wave 1 코어 통합 | 단위 + offline golden (pytest) | `tests/` 전체 — CI blocking, 네트워크/LLM 없음 |
| `conftest.py` | 인프라 | 공통 픽스처, tmp_path 활용 |

## 완료 조건
- [ ] `pytest tests/` 명령이 `gh` CLI, Claude API, 인터넷 연결 없이 전체 통과
- [ ] T-1~T-4에서 작성한 모든 단위 테스트가 `tests/` 아래 정리되어 있음
- [ ] `tests/conftest.py`에서 공통 픽스처(샘플 LEARNING.md, 상태 JSON, tmp_path wrapping) 제공
- [ ] `tests/fixtures/` 아래 골든 픽스처 파일 목록 완비: `pr_converge_state_v1.json`, `retro_state_v1.json`, `sample_learning.md`, `sample_learning_with_markers.md`, `target_file_with_duplicate.md`
- [ ] 각 테스트 파일이 `hooks.lib.self_improve.*`만 import (gh, claude, requests 등 외부 import 감지 시 실패)
- [ ] 테스트 커버리지: state I/O, tier 분류, guard, tag 파싱, 커서, 재발 카운터, 사전검사, 서킷브레이커, 케이던스, 상한, 메모리 라우터, 사다리 라우터 — 각 유닛에 최소 정상 경로 1개 + 경계/에러 케이스 1개 이상
- [ ] `pytest tests/ -v --tb=short` 출력에 네트워크 호출 없음 (mock 없이 순수 통과)
- [ ] `pytest.ini` 또는 `pyproject.toml`에 `testpaths = tests` 설정 (F21 Acceptance: `pytest tests/` 단일 명령으로 동작)
- [ ] 라이브 eval (`evals/`) 실행이 `pytest tests/` 명령에 포함되지 않음 (F21: 분리 유지)

## 의존 태스크
- T-1 (state_io.py 완성)
- T-2 (tier.py, guard.py, parser.py 완성)
- T-3 (cursor.py, recurrence.py, precheck.py 완성)
- T-4 (circuit_breaker.py, cap.py, memory_router.py, ladder.py 완성)

## 예상 변경 파일
- `tests/conftest.py` — 공통 픽스처 (tmp_dir, sample_learning_text, sample_state_dicts)
- `pytest.ini` 또는 `pyproject.toml` — testpaths, 최소 설정
- `tests/fixtures/` — 누락 픽스처 파일 보완 (T-1~T-4에서 생성된 것 포함)
- 기존 `tests/test_*.py` — import 경로 정리, conftest 픽스처 활용으로 중복 제거

## Steps
- [ ] `tests/conftest.py` 작성: `tmp_learning_file(tmp_path)`, `sample_state_json()`, `sample_entries()` 픽스처 정의
- [ ] `pytest.ini` (또는 `pyproject.toml [tool.pytest]`) 생성: `testpaths = tests`, `addopts = --tb=short`
- [ ] T-1~T-4 테스트 파일 전체 import 감사 — 외부 의존 없는지 확인, 있으면 제거
- [ ] 빠진 경계 케이스 테스트 보완 (목록: atomic_write 중단 후 원본 보존, cursor 마커 없음→전체, 사전검사 3단계 순서 보장)
- [ ] `pytest tests/ -v` 전체 실행 → PASSED 확인, FAILED 있으면 수정
- [ ] `pytest tests/ --collect-only 2>&1 | grep evals` 출력 없음 확인 (live eval 미포함)

## 검증 명령어
```bash
cd /Users/moon/workspace/moon-harness/worktrees/self-improving-harness
pytest tests/ -v --tb=short
```
