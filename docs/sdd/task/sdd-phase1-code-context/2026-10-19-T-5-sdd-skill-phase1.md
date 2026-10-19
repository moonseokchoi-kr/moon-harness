# T-5: skills/sdd/SKILL.md Phase 1 인터뷰 흐름 + 자연어 승인 예외

## 관련 문서
- spec: `docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md` (단일 문서. arch/ui/api 문서는 없다: Phase 2 ARCH_SKIP)
- 구현하는 spec 요구사항: F4, F6(SKILL 측), F8(SKILL 측)
- Wave: Wave 1, 복잡도: 6/10

## 구현자
sdd-implementer

## 테스트 타입
| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| skills/sdd/SKILL.md (Markdown) | 단위(정적 pytest) | 키워드·순서·줄 수·스캔 범위 금지 문자열 |

(테스트 시나리오는 test-automator가 도출한다. 스킬/에이전트 Markdown 변경의 RED는 정적 pytest로 만든다. 모듈 전역 mock/patch 금지, fixture·tmp_path·환경변수 주입 사용.)

## 완료 조건
- [ ] SKILL.md가 `grill`, `why`, `code-mapper`, `sdd-spec-writer`, `subagent_type: Explore`, 비대화형 지침을 포함 (F4)
- [ ] Phase 1 프로세스(요구사항 → grill → 요약 → 명시적 yes → sdd-spec-writer → blocker-checker 1·2차 → 승인), 에이전트 표, 상태머신(PHASE1_INTERVIEW_START), Phase 2 진입 전 검증 1번 롤백 대상 갱신 (F4)
- [ ] `set_waiting_for_user true interview` 지침이 있고, "네"/"yes" 단독 예외 한 줄이 자연어 승인 표 바로 아래에 위치, 표의 다른 단계 처리는 불변 (F8)
- [ ] SKILL.md가 `references/spec-template.md`를 참조 한 줄로 가리키고 템플릿 본문을 포함하지 않으며 `타겟 사용자`·`핵심 가치` 없음 (F6)
- [ ] 스캔 범위(`skills/`, `agents/`, `hooks/`, `.claude-plugin/`, `README.md`, `CLAUDE.md`)에서 `ux-researcher` 0건 (F4, T-3·T-4 선행)
- [ ] `skills/sdd/SKILL.md` 줄 수 ≤ 671 (F15)
- [ ] Wave 1 게이트: 이 태스크 완료 후 `tests/` 전체 통과 확인 전에는 Wave 2에 착수하지 않는다
- [ ] 모든 테스트 통과 (이 태스크의 테스트 스코프)

## 의존 태스크
T-1, T-2, T-3, T-4

## 예상 변경 파일
- `skills/sdd/SKILL.md` — Phase 1·에이전트 표·상태머신·승인 예외·템플릿 참조만
- `tests/test_sdd_phase1_skill.py` — 신규 정적 테스트

(소유 파일 외 수정 금지. 커밋 시 소유 파일만 명시적 `git add`, `-A`/`.` 금지, 브랜치 전환 금지.)

## 비고
SKILL.md Phase 2~4·문서 구조·FULL/SIMPLE·E2E·빌드 프로파일 절은 T-12 소유이므로 건드리지 않는다. 단 줄 수 상한 보호를 위해 이 태스크에서 Phase 1 본문을 간결하게 쓴다. `ux-researcher` 잔존이 T-3·T-4 외 파일에서 발견되면 직접 고치지 말고 보고한다.

Wave 1 전체 게이트 검증: `<PY> -m pytest tests/ -q` (bq light lane)

## Steps
- [ ] RED: `tests/test_sdd_phase1_skill.py` 작성(키워드, 승인 예외 위치 = 표 직후, 템플릿 참조, 금지 문자열, 줄 수 ≤ 671, 스캔 범위 ux-researcher 0건) 후 실패 확인
- [ ] Phase 1 절을 인터뷰 흐름으로 교체하고 spec 템플릿 본문을 references 참조 한 줄로 대체
- [ ] 에이전트 표·상태머신·Phase 2 진입 전 검증 1번 롤백 대상 갱신
- [ ] 자연어 승인 표 직후 "네"/"yes" 단독 예외 한 줄과 `set_waiting_for_user true interview` 순서 지침 추가
- [ ] `wc -l`로 줄 수 실측(≤ 671), 스코프 테스트 통과
- [ ] Wave 1 게이트: `tests/` 전체 실행

## 검증 명령어
- 테스트 스코프: `tests/test_sdd_phase1_skill.py`
- fast-scoped 레포(빌드 단계 없음): 스코프 테스트만 실행한다. 형식은 `<PY> -m pytest <테스트 스코프> -q`.
- `<PY>`는 CLAUDE.md "빌드 / 테스트" 절의 확정 절차로 정한다. 인터프리터 경로·`PATH=` prefix를 적지 않는다.
- 빌드·테스트는 bq light lane으로 실행한다: `bq submit --wait --lane light -- <PY> -m pytest <테스트 스코프> -q`
