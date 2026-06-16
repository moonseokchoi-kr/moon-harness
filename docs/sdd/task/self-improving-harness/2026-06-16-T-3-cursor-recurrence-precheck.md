# T-3: 커서 엔진 + 재발/교차프로젝트 카운터 + 사전검사 엔진

## 관련 문서
- spec: `docs/sdd/spec/2026-06-16-self-improving-harness.md` — F8 (커서), F9 (진단/클러스터링), F10 (사전검사), F16 (오염 격리/교차프로젝트)
- arch: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md` — §3.1 (cursor engine, recurrence+cross-project counter, pre-check engine), §5 (idempotency via cursor), §6 (LEARNING.md read-only)

## Wave
**Wave 1** (Phase 1 foundation)

## 구현자
sdd-python-engineer

## 테스트 타입

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| 커서 엔진 | 단위 (pytest, golden fixture) | LEARNING.md 텍스트 + 마커 → 신규 엔트리 목록 |
| 재발/교차프로젝트 카운터 | 단위 (pytest) | 동일 repo N건 vs 다른 repo 2곳 판별 |
| 사전검사 엔진 | 단위 (pytest, golden fixture) | 충돌/중복/일반성 체크 |

## 완료 조건
- [ ] `get_new_entries(learning_text: str, last_marker: str | None) -> list[dict]`: `last_marker` 이후의 `##` 엔트리만 반환. `last_marker=None`이면 전체 반환. LEARNING.md 원본 수정 없음
- [ ] 커서 함수는 순수 함수 (파일 I/O 없음 — 호출자가 텍스트를 전달)
- [ ] `count_signals(entries: list[dict]) -> dict`: 엔트리 목록에서 `{cluster_key: {same_repo: int, cross_repo_set: set[str]}}` 반환
- [ ] `has_cross_project(counter_result: dict, cluster_key: str) -> bool`: `cross_repo_set`의 distinct repo가 2곳 이상이면 True (F16 교차프로젝트 기준)
- [ ] `run_prechecks(candidate: dict, target_file_text: str) -> dict`: 충돌(`conflict`), 중복(`duplicate`), 일반성(`too_sparse`) 결과를 구조화된 dict로 반환. LLM 호출 없음
- [ ] 중복 검사: 후보의 핵심 키워드/표현이 target_file_text에 이미 존재하면 `duplicate=True`
- [ ] 일반성 검사: 독립 신호 2건 미만 + 반복 신호 없으면 `too_sparse=True`
- [ ] 단일 repo에서 5회 반복된 패턴이 `has_cross_project` 기준으로 False를 반환함 (F16 Acceptance 조건)
- [ ] `pytest tests/test_cursor.py tests/test_recurrence.py tests/test_precheck.py` 네트워크 없이 통과
- [ ] 모든 함수에서 LEARNING.md 원본 파일 수정/삭제 없음 (F8 계약)

## 의존 태스크
- T-2 (parse_learning_entry 함수를 import하여 사용)

## 예상 변경 파일
- `hooks/lib/self_improve/cursor.py` — get_new_entries 순수 함수
- `hooks/lib/self_improve/recurrence.py` — count_signals, has_cross_project 함수
- `hooks/lib/self_improve/precheck.py` — run_prechecks 함수 (충돌/중복/일반성 3단계)
- `hooks/lib/self_improve/__init__.py` — 공개 API 추가
- `tests/fixtures/sample_learning_with_markers.md` — 마커 있는 LEARNING.md 골든 픽스처
- `tests/fixtures/target_file_with_duplicate.md` — 중복 검사용 픽스처
- `tests/test_cursor.py`
- `tests/test_recurrence.py`
- `tests/test_precheck.py`

## Steps
- [ ] T-2의 `parse_learning_entry`를 import하여 `cursor.py`의 `get_new_entries` 구현: 마커 비교 로직 (문자열 동등), 마커 없으면 전체 반환
- [ ] `recurrence.py` 구현: entries에서 `provenance_repo` 추출 → cluster별 카운팅, `has_cross_project` predicate
- [ ] `precheck.py` 구현: 3단계 순차 검사 (충돌→중복→일반성), 각 결과 boolean + 사유 문자열 반환
- [ ] `tests/fixtures/` 픽스처 보완: 마커 경계 케이스(마지막 엔트리가 마커와 일치), 단일 repo 다수 신호 케이스
- [ ] 단위 테스트 작성 (경계: 마커 없음, 마커가 마지막 엔트리, 단일 repo 5건 → cross=False, 중복 텍스트 → duplicate=True)
- [ ] `pytest tests/test_cursor.py tests/test_recurrence.py tests/test_precheck.py -v` 통과 확인

## 검증 명령어
```bash
cd /Users/moon/workspace/moon-harness/worktrees/self-improving-harness
pytest tests/test_cursor.py tests/test_recurrence.py tests/test_precheck.py -v
```
