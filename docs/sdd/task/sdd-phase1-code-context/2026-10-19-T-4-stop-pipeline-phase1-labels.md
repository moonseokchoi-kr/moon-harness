# T-4: stop-pipeline Phase 1 라벨(INTERVIEW_START·별칭)과 init_pipeline 초기 라벨

## 관련 문서
- spec: `docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md` (단일 문서. arch/ui/api 문서는 없다: Phase 2 ARCH_SKIP)
- 구현하는 spec 요구사항: F7, F8(훅 측)
- Wave: Wave 1, 복잡도: 6/10

## 구현자
sdd-python-engineer

## 테스트 타입
| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| hooks/enforcement/stop-pipeline.py DIRECTIVES/decide | 단위(pytest, stop_pipeline fixture) | 라벨·별칭·waiting_for_user 거동 |
| hooks/enforcement/lib/pipeline-utils.sh init_pipeline | 통합(임시 CLAUDE_PROJECT_DIR + bash) | 초기 라벨 |

(테스트 시나리오는 test-automator가 도출한다. 스킬/에이전트 Markdown 변경의 RED는 정적 pytest로 만든다. 모듈 전역 mock/patch 금지, fixture·tmp_path·환경변수 주입 사용.)

## 완료 조건
- [ ] `DIRECTIVES`에 `PHASE1_INTERVIEW_START` 추가, 구 `PHASE1_UX_RESEARCH_DONE`는 별칭으로 유지하며 두 directive 동일, `ux-researcher` 문자열 없음 (F7)
- [ ] directive가 인터뷰 흐름, 대기 규칙(`set_waiting_for_user true interview`), `sdd-spec-writer` 디스패치, 완료 후 `PHASE1_SPEC_DRAFT` 갱신을 지시 (F7, F8)
- [ ] `decide()`가 두 라벨에서 `{"decision": "block", "reason": DIRECTIVES[label]}` 반환, 구 라벨이 저장된 `pipeline.json`에서도 block 유지 (F7)
- [ ] `PHASE1_INTERVIEW_START` + `waiting_for_user=True`에서 `decide()`가 `continue: True` (F8)
- [ ] `init_pipeline` 실행 결과 `current_label == "PHASE1_INTERVIEW_START"` (임시 `CLAUDE_PROJECT_DIR`, F7). mode 처리는 이 태스크에서 건드리지 않는다(T-8)
- [ ] `tests/test_stop_pipeline_characterization.py`와 `tests/test_stop_pipeline_kompound_gate.py`를 새 라벨에 맞게 갱신: 단정 삭제·약화 금지, 구 라벨 케이스 유지 + 새 라벨 케이스 추가, 키 집합 동일성 단정 금지 (F7)
- [ ] 새 라벨 문자열이 DIRECTIVES와 directive 본문에서 닫혀 있음을 `tests/test_sdd_pipeline_labels.py`로 고정(W5) (F7)
- [ ] 모든 테스트 통과 (이 태스크의 테스트 스코프)

## 의존 태스크
없음

## 예상 변경 파일
- `hooks/enforcement/stop-pipeline.py` — DIRECTIVES 키·문자열만 변경 (protected, 승인 완료)
- `hooks/enforcement/lib/pipeline-utils.sh` — init_pipeline 초기 라벨 한 줄만 (Ask first 범위 밖 변경 금지)
- `tests/test_stop_pipeline_characterization.py` — 새 라벨 추가, 단정 약화 금지
- `tests/test_stop_pipeline_kompound_gate.py` — 417행 구 라벨 입력 갱신
- `tests/test_sdd_pipeline_labels.py` — 신규(이후 T-7이 확장)
- `tests/test_sdd_pipeline_init.py` — 신규(이후 T-8이 확장)

(소유 파일 외 수정 금지. 커밋 시 소유 파일만 명시적 `git add`, `-A`/`.` 금지, 브랜치 전환 금지.)

## 비고
protected 게이트 스크립트 `hooks/enforcement/stop-pipeline.py` 변경은 사용자 명시 승인 완료(spec 승인 기록, 2026-10-19). 승인 범위(DIRECTIVES 문자열·별칭 키·신규 라벨 키, `label_prerequisite_met`의 PHASE3_WORKTREE_CREATED 항목, `has_tasks`·`has_orchestrator_state`의 worktree_path 기준) 밖(decide() Step 순서, 서킷 브레이커, kompound 게이트, 기존 checks 항목)은 수정하지 않고 Ask first. 커밋 메시지에 "사용자 명시 승인 2026-10-19"를 적는다. 파일 6개로 목표(5개)를 1개 초과하나 stop-pipeline.py와 pipeline-utils.sh 소유를 Wave 1에서 한 태스크로 몰기 위한 것이다.

## Steps
- [ ] RED: 새 `tests/test_sdd_pipeline_labels.py`, `tests/test_sdd_pipeline_init.py` 작성 + characterization/kompound_gate 테스트에 새 라벨 케이스 추가 후 실패 확인
- [ ] `stop-pipeline.py` DIRECTIVES에 PHASE1_INTERVIEW_START 추가, PHASE1_UX_RESEARCH_DONE을 동일 문자열 별칭으로 변경(ux-researcher 삭제)
- [ ] `pipeline-utils.sh` init_pipeline 초기 라벨을 PHASE1_INTERVIEW_START로 변경
- [ ] 기존 테스트의 `_ALWAYS_MET_LABELS`/`_KNOWN_NON_TERMINAL_LABELS` 등에 새 라벨 추가(치환이 아니라 구 라벨 유지 + 추가)
- [ ] GREEN: 스코프 테스트 통과, `decide()` Step 순서·서킷 브레이커 무변경 확인

## 검증 명령어
- 테스트 스코프: `tests/test_stop_pipeline_characterization.py tests/test_stop_pipeline_kompound_gate.py tests/test_sdd_pipeline_labels.py tests/test_sdd_pipeline_init.py`
- fast-scoped 레포(빌드 단계 없음): 스코프 테스트만 실행한다. 형식은 `<PY> -m pytest <테스트 스코프> -q`.
- `<PY>`는 CLAUDE.md "빌드 / 테스트" 절의 확정 절차로 정한다. 인터프리터 경로·`PATH=` prefix를 적지 않는다.
- 빌드·테스트는 bq light lane으로 실행한다: `bq submit --wait --lane light -- <PY> -m pytest <테스트 스코프> -q`
