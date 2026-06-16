# T-1: 공유 결정적 코어 패키지 뼈대 + 상태 I/O

## 관련 문서
- spec: `docs/sdd/spec/2026-06-16-self-improving-harness.md` — F20, 상태파일 계약 섹션
- arch: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md` — §3.1 (state I/O unit), §5 (atomic write), §6 (persistence/IO boundaries)

## Wave
**Wave 1** (Phase 1 foundation)

## 구현자
sdd-python-engineer

## 테스트 타입

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| `hooks/lib/self_improve/` 패키지 | 단위 (pytest) | 오프라인, 네트워크/LLM 무호출 |
| state I/O 함수 | 단위 (pytest, golden fixture) | `tests/fixtures/` 샘플 JSON 사용 |

## 완료 조건
- [ ] `hooks/lib/self_improve/__init__.py`가 존재하고 Python 3.9 이상에서 `import hooks.lib.self_improve` 가능
- [ ] `load_state(path)` 함수: JSON 파일을 읽어 dict 반환, 파일 없거나 파싱 오류 시 `None` 반환 (stop-pipeline.py 패턴 동일)
- [ ] `atomic_write(path, data)` 함수: `tempfile` + `shutil.move` 패턴으로 torn JSON 방지, 부모 디렉토리 없으면 생성
- [ ] `schema_version` guard: 로드된 dict의 `schema_version`이 기대값과 다를 때 구조화된 오류 반환 (예외 발생 금지)
- [ ] `now_iso()` 유틸: UTC ISO8601 문자열 반환
- [ ] `parse_iso(s)` 유틸: fromisoformat 래퍼, 파싱 실패 시 `None` 반환
- [ ] `pr-converge-state.json` 스키마(spec 상태파일 계약)에 맞는 초기값 생성 함수 제공
- [ ] `retro-state.json` 스키마에 맞는 초기값 생성 함수 제공
- [ ] 런타임 코드에서 stdlib 외 import 없음 (`import requests`, `import yaml` 등 금지)
- [ ] `pytest tests/test_state_io.py` 가 네트워크 없이 통과
- [ ] 스크립트 엔트리포인트에 fail-safe: `except Exception` → 상태 손상 없이 구조화된 오류 dict 반환

## 의존 태스크
없음 (Wave 1 시작점)

## 예상 변경 파일
- `hooks/lib/self_improve/__init__.py` — 패키지 초기화, 공개 API 노출
- `hooks/lib/self_improve/state_io.py` — load_state, atomic_write, schema_version guard, now_iso, parse_iso, 초기값 생성 함수
- `tests/__init__.py` — pytest 패키지 초기화 (없으면 생성)
- `tests/fixtures/pr_converge_state_v1.json` — pr-converge-state.json 골든 픽스처
- `tests/fixtures/retro_state_v1.json` — retro-state.json 골든 픽스처
- `tests/test_state_io.py` — 단위 테스트

## Steps
- [ ] `hooks/lib/self_improve/` 디렉토리 생성 및 `__init__.py` 작성 (공개 API: `load_state`, `atomic_write`)
- [ ] `stop-pipeline.py`의 `load_state` / `atomic_write` / `now_iso` / `parse_iso` 패턴을 `state_io.py`로 이식 및 schema_version guard 추가
- [ ] `pr-converge-state.json` / `retro-state.json` 스키마 초기값 생성 함수 구현
- [ ] `tests/fixtures/` 디렉토리 생성 및 골든 JSON 픽스처 작성
- [ ] `tests/test_state_io.py` 작성: load 성공/파일없음/파싱오류/schema 불일치, atomic_write 원자성(임시파일 삔 후 이동 확인), 초기값 구조 검증
- [ ] `pytest tests/test_state_io.py -v` 통과 확인

## 검증 명령어
```bash
cd /Users/moon/workspace/moon-harness/worktrees/self-improving-harness
python -c "from hooks.lib.self_improve import load_state, atomic_write; print('import OK')"
pytest tests/test_state_io.py -v
```
