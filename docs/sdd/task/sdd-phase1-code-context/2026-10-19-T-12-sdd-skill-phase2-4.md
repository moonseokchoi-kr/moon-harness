# T-12: skills/sdd/SKILL.md Phase 2·3·4·문서 구조·정책 갱신

## 관련 문서
- spec: `docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md` (단일 문서. arch/ui/api 문서는 없다: Phase 2 ARCH_SKIP)
- 구현하는 spec 요구사항: F9, F10, F11, F12, F13, F14
- Wave: Wave 2 (Wave 1 게이트 `tests/` 전체 통과 후 착수), 복잡도: 8/10

## 구현자
sdd-implementer

## 테스트 타입
| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| skills/sdd/SKILL.md (Markdown) | 단위(정적 pytest) | 금지 문자열·줄 수·키워드 |

(테스트 시나리오는 test-automator가 도출한다. 스킬/에이전트 Markdown 변경의 RED는 정적 pytest로 만든다. 모듈 전역 mock/patch 금지, fixture·tmp_path·환경변수 주입 사용.)

## 완료 조건
- [ ] Phase 2를 조건부 아키텍처(`PHASE2_ARCH_START`/`DONE`/`SKIP`, 리드가 설계 결정을 보고 판단, 별도 승인 게이트 없음)로 교체하고 arch 템플릿 절·FULL/SIMPLE 모드 판정·SIMPLE/FULL 모드 절 삭제 (F9, F11)
- [ ] worktree 격리를 Phase 3 진입으로 이동(`PHASE3_PLAN_START` → `PHASE3_WORKTREE_CREATED`, spec 이동 세 경우), Phase 3 진입 전 검증 2~5번을 단일 문서 기준(spec 존재 + BLOCKER_PASS + Phase 1 승인 기록 + 아키텍처 보강 여부 기록)으로 교체 (F10)
- [ ] 문서 구조에서 `design/{arch,ui,api}`, `context/`, `e2e-config.json` 삭제, Phase 판정 표(146행)·정밀 모드(context 의존 137행)·상태머신·에이전트 표·게이트 정책·스펙 변경 정책·하위호환 문장·task 템플릿(`## 검증 명령어` → 테스트 스코프만) 갱신 (F14)
- [ ] `E2E 필수`, `E2E 없이 DONE`, `e2e-config` 문자열 0건, "View/UI 구현 전 E2E RED" 규칙(369, 373행) 삭제 (F13)
- [ ] `FULL 모드`, `SIMPLE` 설계 모드 문자열 0건(87행 "FULL 태스크" 등 TDD 모드 용어는 유지) (F11)
- [ ] Phase 4 진입 검증 5번을 "Phase 2로 롤백 — architect가 프로파일 미발견" 없이 오케스트레이터 확보 절차로 교체하고 "프로파일 발견(Phase 2, architect)" 절을 오케스트레이터 기준으로 수정, 워밍업·증분·no-clean 3원칙 유지 (F12)
- [ ] 삭제 에이전트 4종 이름 0건, `docs/sdd/design/`·`docs/sdd/context/` 경로 지시 0건 (F9, F14)
- [ ] `skills/sdd/SKILL.md` 줄 수 ≤ 671 (`wc -l` 실측, F15)
- [ ] 모든 테스트 통과 (이 태스크의 테스트 스코프)

## 의존 태스크
T-5, T-6, T-7, T-9, T-11

## 예상 변경 파일
- `skills/sdd/SKILL.md` — Phase 2~4·문서 구조·정책 절 (Phase 1 절은 T-5 소유, 수정 금지)
- `tests/test_sdd_phase234_skill.py` — 신규 정적 테스트

(소유 파일 외 수정 금지. 커밋 시 소유 파일만 명시적 `git add`, `-A`/`.` 금지, 브랜치 전환 금지.)

## 비고
줄 수 예산(spec D19): 감소 약 -190, 증가 약 +145 추정. 초과하면 설명을 references로 옮기지 말고 문장을 압축한다.

## Steps
- [ ] RED: `tests/test_sdd_phase234_skill.py` 작성(금지 문자열, 키워드, 줄 수 ≤ 671) 후 실패 확인
- [ ] Phase 2 본문·arch 템플릿·FULL/SIMPLE 절 삭제 및 조건부 아키텍처 절 작성
- [ ] Phase 3 진입(worktree 이동)과 진입 전 검증 교체, task 템플릿 검증 명령어 → 테스트 스코프
- [ ] 문서 구조·Phase 판정 표·상태머신·에이전트 표·게이트/스펙 변경 정책·하위호환 문장 갱신
- [ ] E2E 규칙 삭제, Phase 4 진입 검증 5번과 프로파일 절 교체
- [ ] `wc -l` 실측으로 ≤ 671 확인, 스코프 테스트 통과
- [ ] T-5 테스트(`tests/test_sdd_phase1_skill.py`) 회귀 확인

## 검증 명령어
- 테스트 스코프: `tests/test_sdd_phase234_skill.py tests/test_sdd_phase1_skill.py`
- fast-scoped 레포(빌드 단계 없음): 스코프 테스트만 실행한다. 형식은 `<PY> -m pytest <테스트 스코프> -q`.
- `<PY>`는 CLAUDE.md "빌드 / 테스트" 절의 확정 절차로 정한다. 인터프리터 경로·`PATH=` prefix를 적지 않는다.
- 빌드·테스트는 bq light lane으로 실행한다: `bq submit --wait --lane light -- <PY> -m pytest <테스트 스코프> -q`
