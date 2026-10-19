# T-9: sdd-taskmaster·taskrunner 단일 문서·구현 계획 전환

## 관련 문서
- spec: `docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md` (단일 문서. arch/ui/api 문서는 없다: Phase 2 ARCH_SKIP)
- 구현하는 spec 요구사항: F10, F11, F14(taskrunner)
- Wave: Wave 2 (Wave 1 게이트 `tests/` 전체 통과 후 착수), 복잡도: 4/10

## 구현자
sdd-implementer

## 테스트 타입
| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| agents/sdd-taskmaster.md, skills/sdd-taskrunner (Markdown) | 단위(정적 pytest) | 금지/필수 문자열 |

(테스트 시나리오는 test-automator가 도출한다. 스킬/에이전트 Markdown 변경의 RED는 정적 pytest로 만든다. 모듈 전역 mock/patch 금지, fixture·tmp_path·환경변수 주입 사용.)

## 완료 조건
- [ ] `agents/sdd-taskmaster.md`에 `design/arch`, `design/ui`, `design/api`, `FULL 모드`가 없고 `구현 계획`이 있음 (F10, F11)
- [ ] 정규식 `프로파일.*BLOCKED` 매치 0건이며 일반 반환 계약 `DONE | NEEDS_CONTEXT | BLOCKED`는 유지 (F10)
- [ ] 입력이 spec 단일 문서 경로 + worktree 경로 + feature + 모드로 바뀌고, 문서에 없는 설계 결정 금지 규칙이 spec 기준으로 유지됨 (F10)
- [ ] taskmaster는 빌드 프로파일을 찾지 않고 task 문서에는 테스트 스코프만 적으며 dag 모드는 프로파일을 STATE로 복사하지 않음 (F10)
- [ ] taskmaster가 `## 구현 계획`(순서·위험·테스트 스코프)만 쓰고 다른 섹션은 수정하지 않는 소유권 규칙(R11) (F10)
- [ ] `skills/sdd-taskrunner/assets/templates/task-document.md`에 증분 빌드·테스트 실행 명령 칸이 없고 `테스트 스코프`가 있으며 arch/ui/api 경로가 없음 (F14)
- [ ] `skills/sdd-taskrunner/SKILL.md`(77행)의 3종 설계 문서 경로 참조가 spec 단일 문서 참조로 교체 (F14)
- [ ] 모든 테스트 통과 (이 태스크의 테스트 스코프)

## 의존 태스크
T-5 (Wave 1 게이트 통과)

## 예상 변경 파일
- `agents/sdd-taskmaster.md` — 입력·10번 단계·dag 모드·규칙
- `skills/sdd-taskrunner/SKILL.md` — 77행 등 설계 문서 참조
- `skills/sdd-taskrunner/assets/templates/task-document.md` — 관련 문서·테스트 타입 주석·검증 명령어 칸
- `tests/test_sdd_task_docs.py` — 신규 정적 테스트

(소유 파일 외 수정 금지. 커밋 시 소유 파일만 명시적 `git add`, `-A`/`.` 금지, 브랜치 전환 금지.)

## 비고
`skills/sdd-taskrunner/SKILL.md`의 복잡도 기준은 변경하지 않는다. `assets/prompts/analyze.md`의 TDD 모드 FULL은 설계 모드가 아니므로 치환하지 않는다.

## Steps
- [ ] RED: `tests/test_sdd_task_docs.py` 작성 후 실패 확인
- [ ] taskmaster 입력/절차/dag/규칙 갱신(구현 계획 작성, 프로파일 미취급)
- [ ] taskrunner SKILL.md와 task 템플릿 갱신(테스트 스코프 칸)
- [ ] GREEN: 스코프 테스트 통과

## 검증 명령어
- 테스트 스코프: `tests/test_sdd_task_docs.py`
- fast-scoped 레포(빌드 단계 없음): 스코프 테스트만 실행한다. 형식은 `<PY> -m pytest <테스트 스코프> -q`.
- `<PY>`는 CLAUDE.md "빌드 / 테스트" 절의 확정 절차로 정한다. 인터프리터 경로·`PATH=` prefix를 적지 않는다.
- 빌드·테스트는 bq light lane으로 실행한다: `bq submit --wait --lane light -- <PY> -m pytest <테스트 스코프> -q`
