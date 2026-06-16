# T-2: 티어 분류기 + protected-set guard + provenance/태그 파서

## 관련 문서
- spec: `docs/sdd/spec/2026-06-16-self-improving-harness.md` — F11 (2티어 분류), F16 (provenance), F19 (protected set), 해결 1 (태그 포맷), 용어 정의
- arch: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md` — §3.1 (tier classifier, protected-set guard, provenance+tag parser), §4 (ownership/dependency), §6 (tag format — load-bearing)

## Wave
**Wave 1** (Phase 1 foundation)

## 구현자
sdd-python-engineer

## 테스트 타입

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| 티어 분류기 | 단위 (pytest) | 경계 케이스: 모호 → HARNESS 기본값 |
| protected-set guard | 단위 (pytest) | 고정 상수 테이블 — 경로 매칭 |
| 태그/provenance 파서 | 단위 (pytest, golden fixture) | 샘플 LEARNING.md 파싱 |

## 완료 조건
- [ ] `classify_tier(target_path: str, scope_flags: dict) -> Literal["PROJECT", "HARNESS"]`: 모호하면 `"HARNESS"` 반환 (F11 보수적 기본값)
- [ ] 분류 근거: `skills/**/SKILL.md`, `agents/*.md`, `hooks/**` 경로 패턴 → HARNESS; `docs/lessons-learned.md`, `docs/pitfalls.md`, `.harness/*` (설정/로그 외) → PROJECT
- [ ] `is_protected(target_path: str) -> bool`: protected set 멤버(skills/self-improve, skills/pr-converge, agents/harness-improvement-critic, 게이트 스크립트)에 해당하면 `True` (하드코딩 상수 — 절대 자동 수정 불가)
- [ ] `parse_learning_entry(text: str) -> list[dict]`: LEARNING.md 텍스트에서 `##` 헤더 마커 + `<!-- tags: domain=, stage=, provenance_repo= -->` 메타블록 파싱. 태그 없는 엔트리도 파싱 실패 없이 처리 (tags=None)
- [ ] `extract_provenance(entry: dict) -> dict`: `provenance_repo`, `stage`, `domain` 키 추출
- [ ] 태그 포맷은 spec 해결 1 / arch §6 계약과 정확히 일치: `<!-- tags: domain={영역}, stage={구현|pr-converge}, provenance_repo={repo-id} -->`
- [ ] 런타임 코드에서 stdlib 외 import 없음 (정규식은 `re` 모듈 허용)
- [ ] `pytest tests/test_tier_classifier.py` + `pytest tests/test_protected_guard.py` + `pytest tests/test_tag_parser.py` 네트워크 없이 통과
- [ ] 티어 분류 함수에 LLM/gh 호출 없음 (F20)

## 의존 태스크
없음 (Wave 1, T-1과 병렬)

## 예상 변경 파일
- `hooks/lib/self_improve/tier.py` — classify_tier 함수, HARNESS/PROJECT 경로 패턴 상수
- `hooks/lib/self_improve/guard.py` — is_protected 함수, PROTECTED_SET 하드코딩 상수
- `hooks/lib/self_improve/parser.py` — parse_learning_entry, extract_provenance 함수
- `hooks/lib/self_improve/__init__.py` — 공개 API 노출 추가 (T-1에서 생성된 파일에 추가)
- `tests/fixtures/sample_learning.md` — 태그 있는/없는 엔트리 혼합 골든 픽스처
- `tests/test_tier_classifier.py`
- `tests/test_protected_guard.py`
- `tests/test_tag_parser.py`

## Steps
- [ ] `tier.py` 구현: HARNESS_PATTERNS / PROJECT_PATTERNS 상수 정의 + `classify_tier` 순차 매칭 로직 (no-match → HARNESS)
- [ ] `guard.py` 구현: `PROTECTED_SET` frozenset 상수(경로 접두사 기반) + `is_protected` predicate
- [ ] `tests/fixtures/sample_learning.md` 작성: 태그 완전한 엔트리 2개, 태그 없는 엔트리 1개, 멀티라인 엔트리 1개
- [ ] `parser.py` 구현: `##` 헤더로 엔트리 분할, `<!-- tags: ... -->` 정규식 파싱, 결과를 `{marker, body, tags, raw}` dict 리스트로 반환
- [ ] 단위 테스트 3개 파일 작성 (경계: 모호경로→HARNESS, protected set 멤버/비멤버, 태그없는엔트리 파싱 실패없음)
- [ ] `pytest tests/test_tier_classifier.py tests/test_protected_guard.py tests/test_tag_parser.py -v` 통과 확인

## 검증 명령어
```bash
cd /Users/moon/workspace/moon-harness/worktrees/self-improving-harness
pytest tests/test_tier_classifier.py tests/test_protected_guard.py tests/test_tag_parser.py -v
```
