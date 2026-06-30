# T-2: 코어 합류 통합 및 회귀 테스트

## 관련 문서
- spec: `docs/sdd/spec/2026-06-30-cross-project-learning-aggregation.md`
- arch: `docs/sdd/design/arch/2026-06-30-cross-project-learning-aggregation.md`

## 구현자
sdd-test-automator

## 테스트 타입
이 태스크에서 변경되는 레이어와 테스트 방식:

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| 통합 (코어 합류) | 통합 (RED 먼저 → GREEN) | `load_and_merge` → `count_signals` → `has_cross_project` 결선 |
| 2-repo 교차 회귀 (NFR-4 핵심) | 통합 | `test-adequacy` domain, moon-harness + Marvelous 두 repo → True |
| 하위호환 회귀 | 단위/통합 | `store_dir=None` → `has_cross_project == False` (단일 repo) |
| 기존 tests/ 회귀 | 단위 | 기존 self_improve 관련 테스트 무수정 전량 통과 |

(arch §9 테스트 전략 + NFR-4 기반. test-automator가 RED를 먼저 작성하고 T-1 GREEN 이후 결선 검증)

## 완료 조건
- [ ] fixture: 로컬 LEARNING.md에 `domain=test-adequacy, provenance_repo=moon-harness` 엔트리 1건 (arch §9 Fixture 전략)
- [ ] fixture: 임시 store 디렉터리(`tmp_path`)에 `domain=test-adequacy, provenance_repo=Marvelous` 엔트리 포함 `*.md` 1건 이상 (arch §9 Fixture 전략)
- [ ] `load_and_merge(local, store_dir)` → `count_signals(merged)` → `has_cross_project(counter, "test-adequacy") == True` assert 통과 (F1 Acceptance, NFR-4)
- [ ] `store_dir=None`일 때 `has_cross_project(counter, "test-adequacy") == False` (단일 repo, NFR-3 하위호환)
- [ ] `store_dir`이 존재하지 않는 경로일 때 raise 없이 로컬-only 결과 반환 확인 (F1 Acceptance)
- [ ] 로컬 1건 + store `*.md` 2건 → 반환 entries 수가 세 파일 파싱 결과 합과 같음 (F2 Acceptance)
- [ ] 기존 `tests/` 전량 수정 없이 `python3 -m pytest tests/ -q` 통과 (NFR-3 Acceptance)
- [ ] `from hooks.lib.self_improve.learning_source import load_and_merge` 직접 import 방식 사용 (arch §3 보수안)
- [ ] 모든 테스트 통과 (통합/단위)

## 의존 태스크
- T-1: `learning_source.py` 신규 구현 완료 후 실행 (GREEN 상태에서 결선 검증)

## 예상 변경 파일
- `tests/test_learning_source.py` — T-1의 단위 RED 테스트에 통합/회귀 시나리오 추가 (또는 별도 통합 테스트 파일)
- `tests/fixtures/` — 신규 store `*.md` fixture 파일 (harness-learning 포맷: `## marker` H2 + `<!-- tags: ... -->`)

## Steps
- [ ] arch §9 Fixture 전략을 참고하여 `tmp_path` 기반 임시 store 디렉터리 fixture 설계
- [ ] 실제 harness-learning 포맷(`## marker` H2 + `<!-- tags: domain=test-adequacy, stage=구현, provenance_repo=Marvelous -->`) fixture 마크다운 작성
- [ ] 2-repo 교차 통합 테스트 작성: `load_and_merge` → `count_signals` → `has_cross_project=True` (NFR-4 핵심 시나리오)
- [ ] 하위호환 회귀 테스트 작성: `store_dir=None` → `has_cross_project=False`
- [ ] `store_dir` 부재/잘못됨 테스트 작성: raise 없이 로컬-only 반환 확인
- [ ] `python3 -m pytest tests/test_learning_source.py -q` 실행 — T-1 GREEN 이후 전량 통과 확인
- [ ] `python3 -m pytest tests/ -q` 실행 — 기존 테스트 무수정 전량 통과 확인 (NFR-3 최종 검증)

## 검증 명령어
빌드 프로파일: fast-scoped — 테스트 실행만 (증분 빌드 없음, no-clean).

```bash
python3 -m pytest tests/test_learning_source.py -q
```

기존 회귀 전량 검증:

```bash
python3 -m pytest tests/ -q
```
