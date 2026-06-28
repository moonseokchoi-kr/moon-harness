# code-mapper — SDD 사이클 결과

> feature: `code-mapper` · branch: `feature/code-mapper` · 모드: SIMPLE · 완료: 2026-06-29

## 한줄 요약
구현/문서 작업 직전에 심볼의 실제 호출관계를 **ephemeral 구조적 컨텍스트**로 제공해 이름 기반 가짜 확신을 줄이는 `/code-mapper` 스킬. 저장·계약·검증·종속·하드게이트 없음 (Aider repo map 모델).

## 산출물

| 태스크 | 산출물 | 커밋 |
|--------|--------|------|
| T-1 | `hooks/lib/code_mapper/` (probe/format_check/patterns + __init__) + `tests/test_code_mapper_core.py` (49 케이스) | `bc3484e`, `03a2195` |
| T-2 | `skills/code-mapper/SKILL.md` (SSOT 절차) | `0d60e12` |
| T-3 | `agents/sdd-implementer.md` 권고 단락 1개 (+8/-0) | `7838759` |
| T-4 | `evals/scenarios/code_mapper_fallback.json` (폴백 2 cases) | `e73f20d` |

## 검증
- 전체 pytest: **512 passed**, 회귀 0.
- compliance PASS (정체성 축 위반 0), review REVIEW_PASS ([P1] 0).
- 오프라인/라이브 비혼합 유지(`pytest tests/`는 evals 미수집).
- 폴백 라이브 eval: `python evals/run_eval.py --live --scenario code_mapper_fallback` (수동 실행 대기).

## 설계 핵심 (검증으로 깎인 스코프)
- **codegraph 옵셔널**: 가용성은 `codegraph_status` MCP 프로브로 판별(`.codegraph/` 디렉터리 체크 금지). 없으면 grep 폴백.
- **결정↔판단 분리**: 코어 = stdlib-only 순수함수 3개 + 데이터 테이블(상태분류·포맷검사·언어패턴). MCP 호출·의미판단은 프롬프트. 코어는 비필수(LLM이 프롬프트만으로도 동작).
- **reach = sdd-implementer 단독** (언어별 engineer 자동 전파는 거짓 주장이라 정정, v2 범위).
- **최고 가치 소비자 = 버그 수정 워크플로우** — `/code-mapper` 직호출.

## v2 후보 (이번에 명시적으로 제외)
영속 계약 / diff의 blast-radius 검증 / DAG 파일소유권 종속 / 하드 게이트 — 업계가 스테일·과잉제약 비용으로 회피하는 패턴. 별도 측정(벤치마크=fitness function) 후에만 검토.

## LEARNING
이번 사이클 신규 LEARNING.md 엔트리 0건 (반복 사용자 교정 없음) → self-improve 회고 skip.
