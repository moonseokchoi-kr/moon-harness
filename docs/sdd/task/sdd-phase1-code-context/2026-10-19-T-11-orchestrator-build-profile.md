# T-11: 오케스트레이터 Phase 4 진입 빌드 프로파일 확보 + 단일 문서 프롬프트

## 관련 문서
- spec: `docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md` (단일 문서. arch/ui/api 문서는 없다: Phase 2 ARCH_SKIP)
- 구현하는 spec 요구사항: F12, F13, F14
- Wave: Wave 2 (Wave 1 게이트 `tests/` 전체 통과 후 착수), 복잡도: 5/10

## 구현자
sdd-implementer

## 테스트 타입
| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| skills/sdd-orchestrator (Markdown) | 단위(정적 pytest) | frontmatter·키워드 순서·금지 문구 |

(테스트 시나리오는 test-automator가 도출한다. 스킬/에이전트 Markdown 변경의 RED는 정적 pytest로 만든다. 모듈 전역 mock/patch 금지, fixture·tmp_path·환경변수 주입 사용.)

## 완료 조건
- [ ] `skills/sdd-orchestrator/SKILL.md` frontmatter `allowed-tools`에 `Skill` 포함 (F12, D17)
- [ ] Step 1에 확보 순서 키워드 `CLAUDE.md`, `CLAUDE.local.md`, `/build-notes`, 사용자 질문이 이 순서로 있고 "Phase 2 미발견" 문구 없음, STATE에 이미 있으면 재확보 안 함 (F12)
- [ ] 사용자 질문 불가 컨텍스트(sdd-team-leader, 팀원)는 `BLOCKED` 반환으로 리드가 중계, `build-notes` 부재를 정상 경로로 처리해 사용자 질문으로 폴백, `build-notes` 플러그인 이관 안 함 (F12)
- [ ] build-aware TDD 3원칙(워밍업 1회, per-task 증분 + 스코프 테스트, no-clean)과 프로파일 스키마 표 유지 (F12)
- [ ] `skills/sdd-orchestrator/references/state-schema.md`에 `taskmaster가 복사` 문구가 없고 "오케스트레이터가 Phase 4 진입 시 기록"으로 바뀌며 메타의 구 "develop 문서"가 spec 단일 문서로 교체 (F12)
- [ ] 오케스트레이터 SKILL.md 93·107행의 design/arch·ui·api 경로 주입을 spec 단일 문서 참조로 교체 (F14)
- [ ] UI 포함 변경(spec `## UI` 섹션 또는 task 테스트 타입에 E2E/UI)이면 Phase 4 result 문서(Step 4.1)에 `수동 테스트 시나리오`를 기록하고, 개발자 요청 시에만 E2E 작성한다는 지침 (F13)
- [ ] 모든 테스트 통과 (이 태스크의 테스트 스코프)

## 의존 태스크
T-5 (Wave 1 게이트 통과)

## 예상 변경 파일
- `skills/sdd-orchestrator/SKILL.md` — frontmatter·Step 1·93/107행·Step 4.1
- `skills/sdd-orchestrator/references/state-schema.md` — 18, 25-38행
- `tests/test_sdd_orchestrator_docs.py` — 신규 정적 테스트

(소유 파일 외 수정 금지. 커밋 시 소유 파일만 명시적 `git add`, `-A`/`.` 금지, 브랜치 전환 금지.)

## 비고
명령·경로 하드코딩 금지: 프로파일 확보 절차는 문서 파일명과 스킬명만 적고 인터프리터 경로·사용자 홈 경로를 적지 않는다(W4, W6).

## Steps
- [ ] RED: `tests/test_sdd_orchestrator_docs.py` 작성(frontmatter, 확보 순서 위치 비교, 금지 문구, 수동 테스트 시나리오) 후 실패 확인
- [ ] SKILL.md frontmatter에 Skill 추가, Step 1 빌드 프로파일 확보 5단계 + BLOCKED 경로 작성
- [ ] 93·107행 프롬프트 주입과 Step 4.1 result 수동 시나리오 지침 갱신
- [ ] state-schema.md 갱신
- [ ] GREEN: 스코프 테스트 통과

## 검증 명령어
- 테스트 스코프: `tests/test_sdd_orchestrator_docs.py`
- fast-scoped 레포(빌드 단계 없음): 스코프 테스트만 실행한다. 형식은 `<PY> -m pytest <테스트 스코프> -q`.
- `<PY>`는 CLAUDE.md "빌드 / 테스트" 절의 확정 절차로 정한다. 인터프리터 경로·`PATH=` prefix를 적지 않는다.
- 빌드·테스트는 bq light lane으로 실행한다: `bq submit --wait --lane light -- <PY> -m pytest <테스트 스코프> -q`
