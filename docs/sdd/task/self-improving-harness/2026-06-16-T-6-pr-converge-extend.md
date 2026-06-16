# T-6: pr-converge SKILL.md EXTEND + scripts/ (F1~F7 + F15)

## 관련 문서
- spec: `docs/sdd/spec/2026-06-16-self-improving-harness.md` — F1 (수렴 루프 진입점), F2 (전체 코멘트 수집), F3 (신호 분류/에스컬레이션), F4 (케이던스), F5 (main 보호), F6 (서킷브레이커), F7 (sdd-orchestrator 통합), F15 (LEARNING.md 교훈 기록), NFR-4 (prior art 정합)
- arch: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md` — §3.2 (pr-converge skill), §9 (prior-art reconciliation: pr-converge EXTEND 처리), §10 (Phase 1 컴포넌트)

## Wave
**Wave 2** (Phase 1 skill EXTEND — Wave 1 의존)

## 구현자
sdd-implementer

## 테스트 타입

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| `skills/pr-converge/scripts/` 결정적 글루 | 단위 (pytest, golden fixture) | gh 호출 없음 — 구조화된 데이터 입력 |
| SKILL.md 판단 로직 | 라이브 eval (integration) | `evals/` — 별도 단계, F21 분리 |

## 완료 조건
- [ ] `skills/pr-converge/SKILL.md`: 기존 F1~F7 내용 보존. F15 절차(반복 CI 실패/리뷰 패턴 감지 → LEARNING.md append) 추가
- [ ] LEARNING.md append 엔트리에 `provenance_repo`, `discovered_at: pr-converge` 포함 (F15 Acceptance)
- [ ] 동일 CI 체크 2회 실패 후 LEARNING.md에 패턴 엔트리 생성 절차가 SKILL.md에 명시
- [ ] `skills/pr-converge/scripts/state_machine.py`: WORKING/WAITING/NEEDS_HUMAN/CONVERGED/BLOCKED 전이 로직. `hooks.lib.self_improve`의 `check_circuit_breaker`, `compute_cadence` import 사용
- [ ] `skills/pr-converge/scripts/comment_dedup.py`: `processed_comment_ids` 대조 신규 코멘트 필터링. 순수 함수, gh 호출 없음
- [ ] `skills/pr-converge/scripts/pattern_detector.py`: 반복 CI 실패 패턴 감지 (동일 signal_key 2회 이상). LEARNING.md append 페이로드 생성 (태그 포함, 포맷은 spec 해결 1 / arch §6)
- [ ] `skills/pr-converge/scripts/learning_appender.py`: LEARNING.md에 provenance-tagged 엔트리를 append (결정적 포맷 직렬화). 파일 읽기/쓰기만, gh/LLM 호출 없음
- [ ] main/force-push 금지 로직이 SKILL.md에 명시 + scripts에 안전 push 절차 포함 (F5)
- [ ] sdd-orchestrator Step 4에서 main 직접 머지 대신 pr-converge 호출하도록 SKILL.md 참조 구조 확인 (F7, 변경 없이 확인만)
- [ ] 케이던스 300s 미사용이 SKILL.md 가이드에 명시 (F4)
- [ ] `pytest tests/test_pr_converge_scripts.py` 네트워크 없이 통과
- [ ] protected set 파일(`skills/pr-converge/SKILL.md` 자체) — 자동 수정 대상 아님. SKILL.md는 이 태스크에서 **수동 EXTEND**만 허용 (사람이 검토/승인하는 SDD Phase 4 흐름)

## 의존 태스크
- T-1 (state_io.py — atomic_write, load_state)
- T-4 (circuit_breaker.py — check_circuit_breaker, compute_cadence)
- T-2 (parser.py — LEARNING.md 태그 포맷)

## 예상 변경 파일
- `skills/pr-converge/SKILL.md` — F15 절차 추가, 300s 케이던스 경고 명시, scripts/ 참조 추가
- `skills/pr-converge/scripts/__init__.py` — 패키지 초기화
- `skills/pr-converge/scripts/state_machine.py` — 상태 전이 함수
- `skills/pr-converge/scripts/comment_dedup.py` — 신규 코멘트 필터
- `skills/pr-converge/scripts/pattern_detector.py` — 반복 패턴 감지 + LEARNING append 페이로드
- `skills/pr-converge/scripts/learning_appender.py` — LEARNING.md append
- `tests/test_pr_converge_scripts.py` — scripts/ 단위 테스트
- `tests/fixtures/pr_converge_patterns.json` — 반복 패턴 감지 골든 픽스처

## Steps
- [ ] `skills/pr-converge/scripts/` 디렉토리 생성 + `__init__.py`
- [ ] `state_machine.py` 구현: `transition_status(state, signals) -> dict` — `check_circuit_breaker` + `compute_cadence` 사용, 전이 테이블 명시
- [ ] `comment_dedup.py` 구현: `filter_new_comments(all_comments, processed_ids) -> list` 순수 함수
- [ ] `pattern_detector.py` 구현: `detect_repeated_ci_fail(fix_attempts) -> list[dict]` (signal 2회 이상) + LEARNING append 페이로드 포맷 생성
- [ ] `learning_appender.py` 구현: `append_learning_entry(learning_path, entry_dict) -> None` — 태그 포맷 직렬화 + 파일 append
- [ ] `skills/pr-converge/SKILL.md` EXTEND: Phase B 진단·분류 후 "반복 패턴 → LEARNING append" 절차 삽입, 케이던스 300s 경고, scripts/ 호출 흐름 명시
- [ ] `tests/test_pr_converge_scripts.py` 작성 (상태 전이 경계, 중복 코멘트 필터링, 반복 패턴 감지, LEARNING 엔트리 포맷)
- [ ] `pytest tests/test_pr_converge_scripts.py -v` 통과 확인

## 검증 명령어
```bash
cd /Users/moon/workspace/moon-harness/worktrees/self-improving-harness
pytest tests/test_pr_converge_scripts.py -v
```
