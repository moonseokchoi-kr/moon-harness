# T-10: compliance-checker·test-automator·blocker-checker·react-specialist 단일 문서 전환

## 관련 문서
- spec: `docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md` (단일 문서. arch/ui/api 문서는 없다: Phase 2 ARCH_SKIP)
- 구현하는 spec 요구사항: F11, F13, F14
- Wave: Wave 2 (Wave 1 게이트 `tests/` 전체 통과 후 착수), 복잡도: 5/10

## 구현자
sdd-implementer

## 테스트 타입
| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| agents/*.md (Markdown) | 단위(정적 pytest) | 금지/필수 문자열 |

(테스트 시나리오는 test-automator가 도출한다. 스킬/에이전트 Markdown 변경의 RED는 정적 pytest로 만든다. 모듈 전역 mock/patch 금지, fixture·tmp_path·환경변수 주입 사용.)

## 완료 조건
- [ ] `agents/sdd-compliance-checker.md`가 spec 단일 문서의 설계 결정·UI 링크·기능 요구사항 기준으로 검증하고 `design/api/`, `design/ui/`, `FULL 모드`가 없음 (F11, F14)
- [ ] `agents/sdd-test-automator.md`에서 "E2E 필수 확인"(142-144행)을 삭제해 `E2E 필수`, `E2E 없이 DONE`, `e2e-config` 문자열이 없고, 입력의 arch/api 명세 참조(54, 61, 66, 85, 183행)를 spec 단일 문서 기준으로 교체 (F13)
- [ ] `agents/sdd-blocker-checker.md`에 `ui-designer`가 없음(35행을 "Phase 2·3 설계 단계"로) (F14)
- [ ] `agents/sdd-react-specialist.md`에 `DESIGN.md`가 없고 UI 명세 입력 가정이 "spec의 UI 섹션 링크(있을 때만)"로 교체 (F14)
- [ ] `agents/sdd-reviewer.md`와 엔지니어 에이전트의 "develop 문서" 용어, TDD 모드 `[TDD == FULL]`은 변경하지 않음 (Preserve)
- [ ] 모든 테스트 통과 (이 태스크의 테스트 스코프)

## 의존 태스크
T-5 (Wave 1 게이트 통과)

## 예상 변경 파일
- `agents/sdd-compliance-checker.md` — 설계 문서 참조·FULL 모드 제거
- `agents/sdd-test-automator.md` — E2E 필수 확인 삭제·입력 참조 교체
- `agents/sdd-blocker-checker.md` — 35행
- `agents/sdd-react-specialist.md` — 60-67행
- `tests/test_sdd_agent_consumers.py` — 신규 정적 테스트

(소유 파일 외 수정 금지. 커밋 시 소유 파일만 명시적 `git add`, `-A`/`.` 금지, 브랜치 전환 금지.)

## 비고
TDD 모드 FULL(`[TDD == FULL]`, `tdd-gate.sh`)을 설계 모드로 오인해 치환하지 않는다(H12).

## Steps
- [ ] RED: `tests/test_sdd_agent_consumers.py` 작성 후 실패 확인
- [ ] compliance-checker 갱신
- [ ] test-automator 갱신(E2E 강제 삭제, 입력 spec 기준)
- [ ] blocker-checker·react-specialist 갱신
- [ ] GREEN: 스코프 테스트 통과

## 검증 명령어
- 테스트 스코프: `tests/test_sdd_agent_consumers.py`
- fast-scoped 레포(빌드 단계 없음): 스코프 테스트만 실행한다. 형식은 `<PY> -m pytest <테스트 스코프> -q`.
- `<PY>`는 CLAUDE.md "빌드 / 테스트" 절의 확정 절차로 정한다. 인터프리터 경로·`PATH=` prefix를 적지 않는다.
- 빌드·테스트는 bq light lane으로 실행한다: `bq submit --wait --lane light -- <PY> -m pytest <테스트 스코프> -q`
