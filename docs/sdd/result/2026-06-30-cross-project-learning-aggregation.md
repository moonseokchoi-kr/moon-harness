# cross-project-learning-aggregation — 실행 결과 (SDD Phase 4)

> feature: `cross-project-learning-aggregation` · 모드 SIMPLE · 완료 2026-06-30
> worktree: `worktrees/cross-project-learning-aggregation` · branch `feature/cross-project-learning-aggregation`

## 요약

self-improve의 하네스-티어 승격 게이트 `has_cross_project`가 **로컬 `.harness/LEARNING.md` 한 파일만 읽어 distinct provenance_repo가 항상 1 → 구조적으로 영구 False**였던 결함을, **판정 로직 무수정**으로 해소했다. 신규 I/O 집계 로더가 로컬 LEARNING.md + 외부 교차-repo store(`*.md`)를 합쳐 entries 리스트로 만들어 기존 `count_signals`에 넘긴다. provenance 태그가 2개 이상 repo에서 오면 게이트가 열린다.

## 태스크 결과

| T | 내용 | 결과 | 커밋 |
|---|------|------|------|
| T-1 | `learning_source.py` 신규 (I/O 집계 로더) | ✅ GREEN 17/17, compliance PASS(20/20), REVIEW_PASS(P1 0) | `f999203` (+ RED `ef2284c`) |
| T-3 | `SKILL.md` Phase B 배선 텍스트 | ✅ REVIEW_PASS(P1 0), Phase C/D·F17-19 무변경 | `fdd1701` |
| T-2 | 통합·회귀 테스트 | ✅ TEST_PASS, +4 테스트(F16 도메인 가드 등) | `d4f7a41` |

## 검증 (Step 3 통합)

- **전체 스위트**: `python3 -m pytest tests/ -q` → **533 passed / 0 failed** (기존 512 + 신규 21).
- **NFR-1 무수정 불변식**: `git diff 8cfa93c..HEAD -- hooks/lib/self_improve/` = **`learning_source.py` 신규 1파일(+98)만**. 기존 결정적 코어(recurrence.py/parser.py/state_io.py/`__init__.py`) **diff 0**.
- **핵심 회귀 (NFR-4)**: 로컬(`provenance_repo=moon-harness`) + store(`provenance_repo=Marvelous`) 동일 `domain=test-adequacy` → `has_cross_project(counter,"test-adequacy") == True`. 단일 repo 도메인은 False(F16 오염 가드 정상).

## 구현 형태

- **신규**: `hooks/lib/self_improve/learning_source.py` — `load_and_merge(local_learning_path, store_dir) -> list[dict]`. stdlib-only, raise 0, import 부작용 0. 로컬 먼저 → store(`*.md` 파일명 정렬) 뒤. fail-safe: (A) I/O 실패 catch&skip / (B) 파싱 0건 정상.
- **수정(텍스트)**: `skills/self-improve/SKILL.md` Phase A/B — 집계 로더 사용 + 5단계 시퀀스(config→store_dir→load_and_merge→count_signals→has_cross_project) + 하위호환 명시.
- **무수정(보수안)**: `__init__.py` export 안 함 → 호출부는 `from hooks.lib.self_improve.learning_source import load_and_merge` 직접 import (NFR-1 "git diff 0" 문자 충족).

## 활성화 방법 (opt-in)

교차-repo 탐지는 **`.harness/config.json`에 store 경로를 넣어야** 켜진다:
```json
{ "cross_project_store": "/Users/<user>/workspace/marvelous_kompound/harness-learning" }
```
- 파일/키 없으면 **로컬-only로 기존과 동일**(graceful degradation, 하위호환).
- 머신마다 자기 kompound 클론 경로를 가리키면 됨(경로 하드코딩 0).

## 범위 밖 / 후속

- **store 생성·유지**(누가 각 repo LEARNING을 kompound로 sync)는 범위 밖 — 이 기능은 "store가 있으면 읽는다"는 소비자만 구현. 현재 store(`harness-learning/`)는 수동 ingest로 유지.
- **`has_cross_project`를 cursor_runner가 직접 호출하도록 코드 배선**은 이번 범위 밖(SKILL 절차 레벨 배선까지). 완전 자동화는 후속 안건(protected gate script 수정 = 별도 사람 승인).
- store 파일 수 급증 시 성능(전량 재로드)은 미측정 — 후속.
