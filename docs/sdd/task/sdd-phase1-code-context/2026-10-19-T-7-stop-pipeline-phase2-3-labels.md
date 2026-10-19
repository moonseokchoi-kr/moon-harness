# T-7: stop-pipeline Phase 2·3 라벨, 별칭, worktree 전제 검사

## 관련 문서
- spec: `docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md` (단일 문서. arch/ui/api 문서는 없다: Phase 2 ARCH_SKIP)
- 구현하는 spec 요구사항: F9, F10(코드), F14(주석)
- Wave: Wave 2 (Wave 1 게이트 `tests/` 전체 통과 후 착수), 복잡도: 8/10

## 구현자
sdd-python-engineer

## 테스트 타입
| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| hooks/enforcement/stop-pipeline.py | 단위(pytest, stop_pipeline fixture + tmp_path) | 라벨 체인 닫힘, 별칭 동일성, 선행 파일 검사, decide() 경고 접미사 |

(테스트 시나리오는 test-automator가 도출한다. 스킬/에이전트 Markdown 변경의 RED는 정적 pytest로 만든다. 모듈 전역 mock/patch 금지, fixture·tmp_path·환경변수 주입 사용.)

## 완료 조건
- [ ] `DIRECTIVES`에 `PHASE2_ARCH_START`, `PHASE2_ARCH_DONE`, `PHASE2_ARCH_SKIP`, `PHASE3_WORKTREE_CREATED`와 구 PHASE2 8개 키(`PHASE2_START`, `PHASE2_WORKTREE_CREATED`, `PHASE2_ARCH_STRUCTURE_DONE`, `PHASE2_ARCH_USER_APPROVED`, `PHASE2_UI_DESIGN_COMPLETE`, `PHASE2_API_DESIGN_COMPLETE`, `PHASE2_DESIGN_USER_APPROVED`, `PHASE2_USER_APPROVED`) 모두 존재 (F9)
- [ ] `PHASE1_USER_APPROVED` directive가 `PHASE2_ARCH_START`와 `PHASE2_ARCH_SKIP`을 모두 언급, `PHASE2_ARCH_START` → `PHASE2_ARCH_DONE`, `PHASE2_ARCH_DONE`/`SKIP` → `PHASE3_PLAN_START` 언급 (F9)
- [ ] 구 PHASE2 8개 별칭 directive는 서로 동일 문자열이고 `PHASE3_PLAN_START`를 언급, 삭제 에이전트 4종 이름·`FULL 모드`·`SIMPLE` 문구 없음. 모든 DIRECTIVES 본문에 삭제 4종 이름 없음 (F9, F11)
- [ ] 구 PHASE2 라벨이 저장된 `pipeline.json`에서 `decide()`가 block + `DIRECTIVES[label]`(선행 파일 미충족이면 기존 경고 접미사) 반환 (F9)
- [ ] `PHASE3_PLAN_START` directive가 `Skill(git-worktree)`, `worktree_path`, `PHASE3_WORKTREE_CREATED`를 언급하고 worktree_path 존재 시 생성 건너뛰기 지시 (F10)
- [ ] `PHASE3_WORKTREE_CREATED` directive가 spec 이동(복사 아님)과 worktree 경로 기준 taskmaster 입력을 언급, `복사`로 지시하지 않고 세 경우(없음 → `mv`, 있고 `cmp` 동일 → 메인 사본 삭제 후 진행, 있고 다름 → 전이 중단 + `waiting_for_user=true` 사용자 보고, 정본 임의 결정 금지)를 각각 지시하며 `PHASE3_TASKMASTER_DONE`을 언급 (F10)
- [ ] `label_prerequisite_met`에 `PHASE3_WORKTREE_CREATED: has_worktree` 추가, `has_tasks`·`has_orchestrator_state`는 `worktree_path` 우선·`project_dir` 폴백(두 함수 시그니처에 worktree 경로 인자 추가). 각각 worktree 경로/폴백 경로로 met 검증 (F10)
- [ ] `PHASE3_WORKTREE_CREATED` + `worktree_path` 미존재에서 `decide()`가 block + 기존 형식 경고 접미사, 존재하면 경고 없음 (characterization 방식) (F10)
- [ ] `PHASE3_TASKMASTER_DONE` 이후 directive 문자열은 기존과 동일, 구 라벨 `checks` 항목(`has_arch` 등)과 `PHASE2_USER_APPROVED` + `mode="FULL"` 기존 테스트 그대로 통과 (F10, F11, Preserve)
- [ ] 라벨 그래프 닫힘 테스트: directive 본문의 `PHASE\d_[A-Z_]+` 토큰이 모두 DIRECTIVES 키로 존재(PHASE4 태스크 라벨 템플릿 제외) (W5)
- [ ] `stop-pipeline.py` 370행 주석의 경로 문자열을 경로 없이 고쳐 씀 (F14)
- [ ] 모든 테스트 통과 (이 태스크의 테스트 스코프)

## 의존 태스크
T-4

## 예상 변경 파일
- `hooks/enforcement/stop-pipeline.py` — DIRECTIVES·checks·has_tasks/has_orchestrator_state 인자만 (protected, 승인 완료)
- `tests/test_stop_pipeline_characterization.py` — 새 라벨·worktree 선행 검사 케이스 추가
- `tests/test_sdd_pipeline_labels.py` — T-4에서 만든 파일 확장(체인 닫힘·별칭 동일성)
- `tests/test_sdd_pipeline_phase3.py` — 신규(worktree 경로 기준 has_tasks 등)

(소유 파일 외 수정 금지. 커밋 시 소유 파일만 명시적 `git add`, `-A`/`.` 금지, 브랜치 전환 금지.)

## 비고
protected 게이트 스크립트 `hooks/enforcement/stop-pipeline.py` 변경은 사용자 명시 승인 완료(spec 승인 기록, 2026-10-19). 승인 범위(DIRECTIVES 문자열·별칭 키·신규 라벨 키, `label_prerequisite_met`의 PHASE3_WORKTREE_CREATED 항목, `has_tasks`·`has_orchestrator_state`의 worktree_path 기준) 밖(decide() Step 순서, 서킷 브레이커, kompound 게이트, 기존 checks 항목)은 수정하지 않고 Ask first. 커밋 메시지에 "사용자 명시 승인 2026-10-19"를 적는다.

## Steps
- [ ] RED: 위 완료 조건의 테스트를 labels/phase3/characterization 테스트에 작성하고 실패 확인
- [ ] 새 Phase 2 라벨 3개 + 구 PHASE2 8개 공통 별칭 directive 추가(삭제 에이전트명·FULL/SIMPLE 문구 금지)
- [ ] `PHASE1_USER_APPROVED`, `PHASE3_PLAN_START` directive 갱신 + `PHASE3_WORKTREE_CREATED` 신규 directive(spec 이동 세 경우 명시)
- [ ] `label_prerequisite_met`: PHASE3_WORKTREE_CREATED 항목 추가, has_tasks/has_orchestrator_state worktree_path 우선 + project_dir 폴백
- [ ] 370행 주석 수정, 키 집합 동일성 단정이 없음을 확인
- [ ] GREEN: 스코프 테스트 통과 후 `tests/` 전체 실행(Always: stop-pipeline.py 변경 후)

## 검증 명령어
- 테스트 스코프: `tests/test_stop_pipeline_characterization.py tests/test_stop_pipeline_kompound_gate.py tests/test_sdd_pipeline_labels.py tests/test_sdd_pipeline_phase3.py`
- fast-scoped 레포(빌드 단계 없음): 스코프 테스트만 실행한다. 형식은 `<PY> -m pytest <테스트 스코프> -q`.
- `<PY>`는 CLAUDE.md "빌드 / 테스트" 절의 확정 절차로 정한다. 인터프리터 경로·`PATH=` prefix를 적지 않는다.
- 빌드·테스트는 bq light lane으로 실행한다: `bq submit --wait --lane light -- <PY> -m pytest <테스트 스코프> -q`
