# T-3: sdd-spec-writer 개명·축소 + spec 단일 문서 템플릿 분리

## 관련 문서
- spec: `docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md` (단일 문서. arch/ui/api 문서는 없다: Phase 2 ARCH_SKIP)
- 구현하는 spec 요구사항: F5, F6, F13(템플릿 일부)
- Wave: Wave 1, 복잡도: 4/10

## 구현자
sdd-implementer

## 테스트 타입
| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| agents/sdd-spec-writer.md, skills/sdd/references/spec-template.md (Markdown) | 단위(정적 pytest) | frontmatter·섹션 제목·금지 문자열 |

(테스트 시나리오는 test-automator가 도출한다. 스킬/에이전트 Markdown 변경의 RED는 정적 pytest로 만든다. 모듈 전역 mock/patch 금지, fixture·tmp_path·환경변수 주입 사용.)

## 완료 조건
- [ ] `agents/sdd-spec-writer.md` 존재, frontmatter `name == "sdd-spec-writer"`, `tools`에 `Write` 포함, `agents/sdd-ux-researcher.md` 부재(`git mv`로 개명) (F5)
- [ ] 본문에 `페르소나`, `유스케이스`, `타겟 사용자` 없음, "미결 질문" 있음, 구 마커 미사용 (F5)
- [ ] spec-writer가 `docs/sdd/spec/{YYYY-MM-DD}-{feature}.md`를 Write로 직접 저장하도록 지시하고 `BLOCKER_PASS` 마크 처리를 유지하며 "구현 계획" 섹션은 쓰지 않음(섹션 소유권, R11) (F5)
- [ ] `skills/sdd/references/spec-template.md`에 13개 섹션(목표 / 사용자 요구사항(원문) / 가정 / 코드 조사 / 제약(Preserve·Change·Avoid·Risk) / 기능 요구사항 / 설계 결정 / 테스트 전략 / 적용 규칙 / 빌드·테스트 명령 / Boundaries(Always·Ask first·Never) / 범위 밖 / 미결 질문)을 이 순서로 포함 (F6)
- [ ] 조건부 섹션 `기능 지도`, `UI`, `구현 계획`과 `수동 테스트 시나리오` 문구 포함, `타겟 사용자`·`핵심 가치` 없음 (F6, F13)
- [ ] 템플릿이 빌드/테스트 명령·구조·스타일을 복사하지 않고 CLAUDE.md 링크로 대체, 경로·인터프리터 하드코딩 없음 (F6)
- [ ] 모든 테스트 통과 (이 태스크의 테스트 스코프)

## 의존 태스크
없음

## 예상 변경 파일
- `agents/sdd-spec-writer.md` — sdd-ux-researcher.md에서 개명·축소
- `agents/sdd-ux-researcher.md` — 삭제(개명)
- `skills/sdd/references/spec-template.md` — 신규
- `tests/test_sdd_spec_writer.py` — 신규 정적 테스트

(소유 파일 외 수정 금지. 커밋 시 소유 파일만 명시적 `git add`, `-A`/`.` 금지, 브랜치 전환 금지.)

## 비고
`skills/sdd/SKILL.md`는 이 태스크 소유가 아니다(T-5가 참조 한 줄을 건다).

## Steps
- [ ] RED: `tests/test_sdd_spec_writer.py` 작성(frontmatter, 부재 파일, 섹션 제목 순서, 금지 문자열) 후 실패 확인
- [ ] `git mv agents/sdd-ux-researcher.md agents/sdd-spec-writer.md` 후 name 변경, 페르소나/여정/유스케이스/경쟁 패턴 절차 제거, 저장 지시·섹션 소유권·BLOCKER_PASS 유지
- [ ] `skills/sdd/references/spec-template.md` 작성(13개 섹션 + 조건부 3개 + 수동 테스트 시나리오 안내)
- [ ] GREEN: 스코프 테스트 통과

## 검증 명령어
- 테스트 스코프: `tests/test_sdd_spec_writer.py`
- fast-scoped 레포(빌드 단계 없음): 스코프 테스트만 실행한다. 형식은 `<PY> -m pytest <테스트 스코프> -q`.
- `<PY>`는 CLAUDE.md "빌드 / 테스트" 절의 확정 절차로 정한다. 인터프리터 경로·`PATH=` prefix를 적지 않는다.
- 빌드·테스트는 bq light lane으로 실행한다: `bq submit --wait --lane light -- <PY> -m pytest <테스트 스코프> -q`
