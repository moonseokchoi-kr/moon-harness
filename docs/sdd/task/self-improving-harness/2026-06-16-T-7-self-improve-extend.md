# T-7: self-improve SKILL.md EXTEND + scripts/ (F8~F14 + F16~F19)

## 관련 문서
- spec: `docs/sdd/spec/2026-06-16-self-improving-harness.md` — F8~F14 (수집~트리거 전체), F16 (오염 격리), F17 (학습사다리), F18 (on-demand 로드), F19 (스킬 결정화), NFR-2 (오염 격리 불변식), NFR-4 (prior art EXTEND)
- arch: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md` — §3.3 (self-improve skill scripts/), §7 (메모리/사다리/스킬 결정화), §9 (self-improve: EXTEND largest delta), §10 (Phase 1 컴포넌트), §12 (Phase 1→2→3 migration)

## Wave
**Wave 2** (Phase 1 skill EXTEND — Wave 1 의존)

## 구현자
sdd-implementer

## 테스트 타입

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| `skills/self-improve/scripts/` 결정적 글루 | 단위 (pytest, golden fixture) | LLM/gh 호출 없음 |
| SKILL.md 판단 로직 (클러스터링, critic 디스패치) | 라이브 eval (integration) | `evals/` — 별도 단계 |

## 완료 조건
- [ ] `skills/self-improve/SKILL.md`: 기존 F8~F14 내용 보존. 다음 신규 섹션 추가: F16 (provenance + 교차 프로젝트 기준), F17 (학습사다리 L0~L4 + 재발 기반 에스컬레이션), F18 (on-demand 라우팅 절차, @LEARNING.md 전체 import 폐기 명시), F19 (스킬 결정화 조건/절차, protected set 금지, dedup 제안)
- [ ] F19에서 Phase 3 경계 명시: "하네스 티어 스킬 자동 승격은 Phase 2 벤치마크 측정 기반 확보 후에만 가능. 벤치마크 델타 입력 없으면 cold-start short-circuit → 제안 생성 불가"
- [ ] `skills/self-improve/scripts/cursor_runner.py`: `get_new_entries` (T-3 import) 호출 + retro-state.json 로드/갱신. 오류 시 커서 갱신 안 함 (F13)
- [ ] `skills/self-improve/scripts/precheck_runner.py`: `run_prechecks` (T-3 import) 호출 + `classify_tier` + `is_protected` (T-2 import) 적용. 구조화된 결과 반환
- [ ] `skills/self-improve/scripts/apply_writer.py`: 프로젝트 티어 변경 적용 (`docs/lessons-learned.md`, `docs/pitfalls.md`) + `retro-log.md` rollback 블록 append. 하네스 티어는 `harness-proposals/{date}-{slug}.md` 생성만
- [ ] `skills/self-improve/scripts/cap_runner.py`: `apply_cap` (T-4 import) 호출, 트런케이션 보고 포함
- [ ] `skills/self-improve/scripts/skill_scanner.py`: 기존 스킬 목록 스캔 (파일 글로브로 `skills/**/SKILL.md` 수집), description 텍스트 중복 감지 (F19 minor①). 순수 파일 스캔, LLM 호출 없음
- [ ] 하네스 티어 UPHELD 시 플러그인 파일 편집 없음 (F11 Acceptance 조건 — `apply_writer.py`에서 하네스 티어 쓰기 경로 차단)
- [ ] 자동 수정 대상에서 protected set 제외 (is_protected 호출 — precheck_runner.py에서 검증)
- [ ] `pytest tests/test_self_improve_scripts.py` 네트워크 없이 통과
- [ ] 단일 repo 5회 반복 패턴이 하네스 티어 자동 승격 경로에 도달하지 않음 (has_cross_project 체크 포함)

## 의존 태스크
- T-1 (state_io — atomic_write, load_state, retro-state 초기값)
- T-2 (tier.py, guard.py, parser.py)
- T-3 (cursor.py, recurrence.py, precheck.py)
- T-4 (cap.py, memory_router.py, ladder.py)

## 예상 변경 파일
- `skills/self-improve/SKILL.md` — F16/F17/F18/F19 섹션 추가, Phase C 게이트 주석 갱신(벤치마크 델타 → Phase 2), Phase 3 경계 명시
- `skills/self-improve/scripts/__init__.py`
- `skills/self-improve/scripts/cursor_runner.py`
- `skills/self-improve/scripts/precheck_runner.py`
- `skills/self-improve/scripts/apply_writer.py`
- `skills/self-improve/scripts/cap_runner.py`
- `skills/self-improve/scripts/skill_scanner.py`
- `tests/test_self_improve_scripts.py`
- `tests/fixtures/harness_proposal_template.md` — 하네스 제안 출력 픽스처

## Steps
- [ ] `cursor_runner.py` 구현: retro-state.json 로드 → `get_new_entries` → 결과 반환. 오류 시 None 반환 (커서 갱신 불가 신호)
- [ ] `precheck_runner.py` 구현: 후보별 `is_protected` 체크 → 보호 파일이면 즉시 폐기. `classify_tier` → `run_prechecks` → 결과 구조화 반환
- [ ] `apply_writer.py` 구현: 프로젝트 티어 → 파일 직접 수정 + retro-log rollback 블록 포맷 append. 하네스 티어 → harness-proposals/ 파일 생성만 (플러그인 파일 쓰기 경로 없음)
- [ ] `cap_runner.py` 구현: `apply_cap` 호출, 초과분 처리(harness 제안 큐 또는 다음 회고 예약) + 트런케이션 보고
- [ ] `skill_scanner.py` 구현: glob으로 `skills/**/SKILL.md` 수집 → frontmatter description 추출 → 유사도 단순 텍스트 겹침 감지
- [ ] `skills/self-improve/SKILL.md` EXTEND: Phase B에 F16/F17/F18 절차 삽입, Phase C에 F19 스킬 결정화 + Phase 3 경계 명시, Phase D apply_writer 흐름 명시
- [ ] `tests/test_self_improve_scripts.py` 작성 (하네스 티어 UPHELD 시 플러그인 파일 쓰기 없음, 커서 오류 시 갱신 안 함, cap 트런케이션, protected 파일 폐기)
- [ ] `pytest tests/test_self_improve_scripts.py -v` 통과 확인

## 검증 명령어
```bash
cd /Users/moon/workspace/moon-harness/worktrees/self-improving-harness
pytest tests/test_self_improve_scripts.py -v
```
