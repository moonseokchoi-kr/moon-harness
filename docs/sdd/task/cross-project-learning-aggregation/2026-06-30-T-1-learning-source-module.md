# T-1: learning_source.py 신규 구현 (I/O 집계 로더)

## 관련 문서
- spec: `docs/sdd/spec/2026-06-30-cross-project-learning-aggregation.md`
- arch: `docs/sdd/design/arch/2026-06-30-cross-project-learning-aggregation.md`

## 구현자
sdd-python-engineer

## 테스트 타입
이 태스크에서 변경되는 레이어와 테스트 방식:

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| I/O 글루 단위 (`load_and_merge`) | 단위 (RED 먼저 → GREEN) | test-automator가 RED 작성, engineer가 GREEN 달성 |
| fail-safe 분기 | 단위 | A부류(I/O 실패 catch&skip), B부류(파싱 0건 정상) 각각 |
| 로컬-only 하위호환 | 단위 | `store_dir=None` → 기존 결과와 동일 |

(arch §9 테스트 전략 기반. test-automator가 이 정보를 참고하여 `tests/test_learning_source.py`에 RED 테스트 작성)

## 완료 조건
- [ ] `hooks/lib/self_improve/learning_source.py` 신규 파일 생성됨
- [ ] `load_and_merge(local_learning_path, store_dir) -> list[dict]` 시그니처 구현 (arch §5.1)
- [ ] `local_learning_path`가 존재하고 읽기 가능할 때 `parse_learning_entry`로 파싱하여 entries에 포함 (F2)
- [ ] `local_learning_path`가 존재하지 않거나 읽기 실패 시 raise 없이 로컬 entries를 `[]`로 처리하고 계속 진행 (F2, 부류 A)
- [ ] `store_dir=None`일 때 store 기여 없이 로컬 entries만 반환 (F2, NFR-3)
- [ ] `store_dir`이 유효한 디렉터리일 때 `*.md` 파일을 파일명 정렬 순으로 열거하여 각각 `parse_learning_entry`로 파싱·이어붙임 (F2)
- [ ] `store_dir`이 존재하지 않거나 디렉터리 아닌 경우 raise 없이 store 기여 없음 처리 (F2, 부류 A)
- [ ] 개별 store `*.md` 파일 읽기/파싱 실패 시 해당 파일만 skip하고 나머지 계속 처리 (F2, 부류 A)
- [ ] 잘못된 마크다운(H2 없는 파일) → `parse_learning_entry`가 `[]` 반환 → 그 파일 0건 기여로 정상 진행 (F2, 부류 B)
- [ ] 모듈 최상위(import 시점)에서 파일 읽기·환경변수 접근·경로 계산 부작용 없음 (NFR-2)
- [ ] stdlib(`json`, `pathlib`, `os`, `typing`)만 사용, 외부 패키지·네트워크·LLM 호출 0 (NFR-2)
- [ ] 모든 경로가 함수 인자로만 주입되며, 모듈 내부에 경로 하드코딩 없음 (NFR-2)
- [ ] `hooks/lib/self_improve/` 기존 파일(recurrence.py, parser.py, state_io.py, `__init__.py` 등) git diff 없음 (NFR-1)
- [ ] `python3 -m pytest tests/test_learning_source.py -q` 전량 통과 (GREEN)
- [ ] 모든 테스트 통과 (단위)

## 의존 태스크
없음 (Wave 1 진입 태스크)

## 예상 변경 파일
- `hooks/lib/self_improve/learning_source.py` — 신규 I/O 집계 로더 모듈 (이 태스크의 유일한 신규 코드)
- `tests/test_learning_source.py` — test-automator가 RED 테스트 작성, engineer가 GREEN 달성용 구현 완성

## Steps
- [ ] arch §5.1의 `load_and_merge` 시그니처와 §7 fail-safe 에러 계약을 확인하여 구현 설계 파악
- [ ] `hooks/lib/self_improve/parser.py`의 `parse_learning_entry` 시그니처·반환 타입 확인 (import 대상)
- [ ] `tests/test_learning_source.py`의 RED 테스트 목록 확인 (test-automator가 먼저 작성한 상태)
- [ ] `hooks/lib/self_improve/learning_source.py` 파일 신규 생성 — 함수 스텁 단계
- [ ] 로컬 파일 읽기·파싱 로직 구현 (부류 A catch&skip 포함)
- [ ] store 디렉터리 열거·파일별 읽기·파싱·병합 로직 구현 (파일명 정렬, 부류 A/B 처리)
- [ ] `store_dir=None` 분기 처리 확인 (로컬-only 경로)
- [ ] `python3 -m pytest tests/test_learning_source.py -q` 실행하여 GREEN 확인
- [ ] `git diff hooks/lib/self_improve/` 실행하여 기존 파일 무수정(diff 없음) 검증

## 검증 명령어
빌드 프로파일: fast-scoped — 테스트 실행만 (증분 빌드 없음, no-clean).

```bash
python3 -m pytest tests/test_learning_source.py -q
```

전량 실행(회귀 포함):

```bash
python3 -m pytest tests/ -q
```
