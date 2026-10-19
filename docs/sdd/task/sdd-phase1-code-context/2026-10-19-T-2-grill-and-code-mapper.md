# T-2: grill 스킬 신설 + code-mapper 구현 걸림돌 블록

## 관련 문서
- spec: `docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md` (단일 문서. arch/ui/api 문서는 없다: Phase 2 ARCH_SKIP)
- 구현하는 spec 요구사항: F2, F3
- Wave: Wave 1, 복잡도: 4/10

## 구현자
sdd-implementer

## 테스트 타입
| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| skills/grill, skills/code-mapper (Markdown) | 단위(정적 pytest) | 키워드 존재/부재, 기존 코어 테스트 무수정 통과 |

(테스트 시나리오는 test-automator가 도출한다. 스킬/에이전트 Markdown 변경의 RED는 정적 pytest로 만든다. 모듈 전역 mock/patch 금지, fixture·tmp_path·환경변수 주입 사용.)

## 완료 조건
- [ ] `skills/grill/SKILL.md` 존재, frontmatter `name == "grill"`, `description` 비어 있지 않음 (F2)
- [ ] grill 본문에 `frontier`, `하지 않을 것`, 비대화형(`/loop`·스케줄·CI) 지침, 명시적 yes 지침, 종료 예시 문장("다음에 물을 질문 3개…") 포함 (F2)
- [ ] grill 본문에 `pipeline.json`, `advance_label`, `set_waiting_for_user` 문자열 없음 (F2)
- [ ] interview-me 채택 범위(요약 5~8줄, 명시적 yes 게이트, 답 3개 예측 종료, 비대화형 미사용)만 반영하고 한 번에 한 질문 방식은 반영하지 않음 (F2)
- [ ] code-mapper SKILL.md에 "구현 걸림돌"과 "요구사항이 주어졌을 때만" 조건 존재, 섹션 1~6 순서·레이블·`비목표`·`영속 금지` 문구 유지 (F3)
- [ ] `tests/test_code_mapper_core.py`가 수정 없이 통과하고 `hooks/lib/code_mapper/` 무변경(`git diff --stat` 무변경을 결과 문서에 기록) (F3)
- [ ] 모든 테스트 통과 (이 태스크의 테스트 스코프)

## 의존 태스크
없음

## 예상 변경 파일
- `skills/grill/SKILL.md` — 신규
- `skills/code-mapper/SKILL.md` — 구현 걸림돌 블록 추가(섹션 1~6 불변)
- `tests/test_grill_skill.py` — 신규 정적 테스트
- `tests/test_code_mapper_blockers.py` — 신규 정적 테스트

(소유 파일 외 수정 금지. 커밋 시 소유 파일만 명시적 `git add`, `-A`/`.` 금지, 브랜치 전환 금지.)

## 비고
`tests/test_code_mapper_core.py`와 `hooks/lib/code_mapper/`는 수정 금지(Ask first).

## Steps
- [ ] RED: `tests/test_grill_skill.py`, `tests/test_code_mapper_blockers.py` 작성 후 실패 확인
- [ ] `skills/grill/SKILL.md` 작성(frontier 라운드, 번호+추천 답, 사실 직접 조사, 종료 조건, 5~8줄 요약 + 하지 않을 것 + 명시적 yes, 암묵적 동의 비승인, 비대화형 미사용, pipeline 상태 미취급)
- [ ] `skills/code-mapper/SKILL.md`에 요구사항 동반 호출 시에만 붙는 "구현 걸림돌" 블록(영향받는 호출자, 깨질 수 있는 불변식·테스트, 제약 구조) 추가. 비목표 절 불변
- [ ] GREEN: 스코프 테스트 + 기존 `tests/test_code_mapper_core.py` 통과, `git diff --stat -- hooks/lib/code_mapper` 무변경 확인

## 검증 명령어
- 테스트 스코프: `tests/test_grill_skill.py tests/test_code_mapper_blockers.py tests/test_code_mapper_core.py`
- fast-scoped 레포(빌드 단계 없음): 스코프 테스트만 실행한다. 형식은 `<PY> -m pytest <테스트 스코프> -q`.
- `<PY>`는 CLAUDE.md "빌드 / 테스트" 절의 확정 절차로 정한다. 인터프리터 경로·`PATH=` prefix를 적지 않는다.
- 빌드·테스트는 bq light lane으로 실행한다: `bq submit --wait --lane light -- <PY> -m pytest <테스트 스코프> -q`
