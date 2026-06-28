# T-1: 결정적 코어 패키지 + pytest

## 관련 문서
- spec: `docs/sdd/spec/2026-06-26-code-mapper.md`
- arch: `docs/sdd/design/arch/2026-06-26-code-mapper.md`

## 구현자
`sdd-python-engineer`

## 테스트 타입
이 태스크에서 변경되는 레이어와 테스트 방식:

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| 결정적 코어 (`hooks/lib/code_mapper/`) | 단위 | pytest, stdlib-only, 오프라인 (LLM/MCP 무호출) |

(arch 문서의 테스트 전략 기반. test-automator가 이 정보를 참고하여 적합한 프레임워크로 RED 테스트 작성)

## 완료 조건

- [ ] `hooks/lib/code_mapper/` 패키지가 존재하고 `__init__.py`를 포함한다
- [ ] `classify_probe_state(text: str) -> str` 순수 함수가 구현된다: 반환값은 `"healthy"` / `"not_initialized"` / `"unavailable"` 중 하나
  - healthy: 인덱스 통계(노드/엣지 수, ready 등)를 나타내는 텍스트 → `"healthy"`
  - not_initialized: "not initialized" 문자열(또는 동등 미초기화 신호) 포함 → `"not_initialized"`
  - 도구 미등록/연결 오류/빈 문자열/미지 신호 → `"unavailable"` (fail-safe)
- [ ] `check_format_completeness(text: str) -> tuple[bool, list[str]]` 순수 함수가 구현된다: F6 섹션 1~6 + "탐색 방법" 레이블의 존재와 순서를 검사, 누락 섹션 목록 반환
- [ ] `language_for(ext: str) -> str` 순수 함수: 확장자 → 언어 (`"python"`, `"js_ts"`, `"generic"`)
- [ ] `def_patterns(lang: str) -> list[str]` 순수 함수: 언어 → 정의 패턴 문자열 목록 (유효 정규식)
- [ ] 코어 데이터 테이블에 거짓양성 억제용 제외 패턴(주석/문자열/타입힌트) 조각이 포함된다
- [ ] 언어 예약어/제어구문 제외 목록이 코어 테이블에 존재한다 (generic callees grep용)
- [ ] 코어는 stdlib-only (네트워크/LLM/MCP 호출 0, 외부 패키지 import 0)
- [ ] `tests/test_code_mapper_core.py`에 pytest 단위 테스트가 존재한다:
  - `classify_probe_state()`: healthy/not_initialized/unavailable 각 케이스 + 경계 입력(빈 문자열, 미지 신호)
  - `check_format_completeness()`: 완전한 F6 텍스트 → (True, []) / 섹션 누락 → (False, [누락목록]) / 순서 오류 감지 / 탐색 레이블 누락 감지
  - `language_for()` + `def_patterns()`: 알려진 확장자 매핑 정확성 + 미지 확장자 → generic + 패턴이 `re.compile(p)` 통과
- [ ] `pytest tests/test_code_mapper_core.py -q` 전부 GREEN
- [ ] `pytest tests/` 전체 스위트 회귀 없음 (기존 테스트 0 깨짐)
- [ ] 모든 테스트 통과 (단위)

## 의존 태스크
없음 (Wave 1, T-2와 병렬 실행 가능)

## 예상 변경 파일
- `hooks/lib/code_mapper/` — 신규 패키지 디렉터리 (파일명은 엔지니어 결정)
- `tests/test_code_mapper_core.py` — pytest 단위 테스트 파일 (신규)

## Steps
- [ ] `hooks/lib/code_mapper/` 패키지 디렉터리 생성, `__init__.py` 작성 (public API export 포함)
- [ ] `classify_probe_state(text)` 순수 함수 구현 — healthy/not_initialized/unavailable 분류 + fail-safe(미지 → unavailable)
- [ ] `check_format_completeness(text)` 순수 함수 구현 — F6 섹션 1~6 순서 검사 + "탐색 방법" 레이블 검사
- [ ] `language_for(ext)` + `def_patterns(lang)` 구현 + 언어패턴 데이터 테이블 (`.py`, `.ts/.tsx/.js/.jsx/.mjs`, 기타 → generic)
- [ ] 거짓양성 억제 제외 패턴 테이블 구현 (주석마커/따옴표/타입힌트 위치 패턴 + 예약어 제외 목록)
- [ ] `tests/test_code_mapper_core.py` 작성 — 위 순수 함수 전체 단위 테스트 (경계 케이스 포함)
- [ ] `pytest tests/test_code_mapper_core.py -q` 실행 → 전부 GREEN 확인
- [ ] `pytest tests/ -q` 실행 → 기존 테스트 회귀 없음 확인

## 검증 명령어
빌드 프로파일: fast-scoped. 워밍업/증분 빌드 생략. 스코프 테스트만.

```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_code_mapper_core.py -q
```
