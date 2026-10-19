# T-8: pipeline-utils mode 폐지 + phase-gate design 블록 제거

## 관련 문서
- spec: `docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md` (단일 문서. arch/ui/api 문서는 없다: Phase 2 ARCH_SKIP)
- 구현하는 spec 요구사항: F11(셸), F14(phase-gate·주석)
- Wave: Wave 2 (Wave 1 게이트 `tests/` 전체 통과 후 착수), 복잡도: 6/10

## 구현자
sdd-implementer

## 테스트 타입
| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| hooks/enforcement/lib/pipeline-utils.sh | 통합(임시 CLAUDE_PROJECT_DIR + bash) | init_pipeline/show_pipeline |
| hooks/enforcement/phase-gate.sh | 통합(임시 프로젝트 디렉터리 + bash) | 경고 출력 유무 |

(테스트 시나리오는 test-automator가 도출한다. 스킬/에이전트 Markdown 변경의 RED는 정적 pytest로 만든다. 모듈 전역 mock/patch 금지, fixture·tmp_path·환경변수 주입 사용.)

## 완료 조건
- [ ] `init_pipeline demo`와 `init_pipeline demo FULL` 모두 종료 코드 0, 생성된 `pipeline.json`에 `mode` 키 없음, 완료 메시지에 모드 미출력 (F11)
- [ ] `show_pipeline`이 `mode` 없는 JSON에서 오류 없이 동작하고 `mode`가 있을 때만 출력 (F11)
- [ ] `pipeline-utils.sh:9` 주석, `lib/logging.sh:19` 예시의 구 라벨 문자열을 새 라벨로 교체 (F14)
- [ ] `phase-gate.sh`에서 `DESIGN_DIR`, `HAS_ARCH`, `architecture 설계 문서`, `e2e-config` 문자열과 `CONTEXT_DIR` 참조가 없고 SDD 미시작 판정은 `SPEC_DIR` 기준, 남는 검사는 spec 존재·task 존재·`4_active`일 때 task 문서 존재, 경고만 하는 성격 유지 (F14)
- [ ] phase-gate.sh가 새 흐름(design/ 없음)에서 오경고를 내지 않음을 임시 디렉터리 테스트로 검증, 삭제 에이전트 4종 이름 문자열 없음 (F14, F9)
- [ ] `hooks/enforcement/lib/constants.sh` 25행, `lib/state-reader.sh` 53-58행의 e2e 설정 읽기 호출처가 휴면인지 확인해 결과 문서용 기록을 남김(수정 판단용, 수정은 Ask first) (F14)
- [ ] `tests/test_enforcement_hook_false_positives.py`, `tests/test_hooks_json_contract.py` 수정 없이 통과; `e2e-gate.sh`·`hooks.json` 무변경 (F13)
- [ ] 모든 테스트 통과 (이 태스크의 테스트 스코프)

## 의존 태스크
T-4

## 예상 변경 파일
- `hooks/enforcement/lib/pipeline-utils.sh` — init_pipeline 두 번째 인자 무시·mode 미기록·show_pipeline·주석 (그 밖은 Ask first)
- `hooks/enforcement/lib/logging.sh` — 19행 예시 문자열만
- `hooks/enforcement/phase-gate.sh` — F14가 지정한 블록 제거만 (protected, spec 승인 게이트에서 승인 완료)
- `tests/test_sdd_pipeline_init.py` — T-4 파일 확장
- `tests/test_phase_gate_single_doc.py` — 신규

(소유 파일 외 수정 금지. 커밋 시 소유 파일만 명시적 `git add`, `-A`/`.` 금지, 브랜치 전환 금지.)

## 비고
`phase-gate.sh`는 protected 게이트 스크립트이며 F14 범위의 블록 제거는 spec 승인 게이트에서 사용자 승인을 받았다(승인 기록 2026-10-19). 그 밖의 변경은 Ask first. `e2e-gate.sh`, `hooks.json`은 수정 금지.

## Steps
- [ ] RED: init 테스트 확장(두 호출형, mode 키 부재, show_pipeline)과 `tests/test_phase_gate_single_doc.py`(오경고 부재·금지 문자열) 작성 후 실패 확인
- [ ] `pipeline-utils.sh` 수정(mode 미기록, 인자 무시, 완료 메시지, show_pipeline 조건부 출력, 주석)
- [ ] `logging.sh` 예시 문자열 교체
- [ ] `phase-gate.sh` design/E2E 경고 블록과 CONTEXT_DIR 의존 제거(SPEC_DIR 기준). case 분기 순서 결함은 고치지 않는다(범위 밖)
- [ ] constants.sh·state-reader.sh e2e 호출처 휴면 여부 확인 후 기록
- [ ] GREEN: 스코프 테스트 + 훅 회귀 테스트 통과

## 검증 명령어
- 테스트 스코프: `tests/test_sdd_pipeline_init.py tests/test_phase_gate_single_doc.py tests/test_enforcement_hook_false_positives.py tests/test_hooks_json_contract.py`
- fast-scoped 레포(빌드 단계 없음): 스코프 테스트만 실행한다. 형식은 `<PY> -m pytest <테스트 스코프> -q`.
- `<PY>`는 CLAUDE.md "빌드 / 테스트" 절의 확정 절차로 정한다. 인터프리터 경로·`PATH=` prefix를 적지 않는다.
- 빌드·테스트는 bq light lane으로 실행한다: `bq submit --wait --lane light -- <PY> -m pytest <테스트 스코프> -q`
