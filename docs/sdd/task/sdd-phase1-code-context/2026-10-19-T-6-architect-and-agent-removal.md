# T-6: architect 3종 보강 전용 전환 + 에이전트 4종 삭제

## 관련 문서
- spec: `docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md` (단일 문서. arch/ui/api 문서는 없다: Phase 2 ARCH_SKIP)
- 구현하는 spec 요구사항: F9, F14(architect)
- Wave: Wave 2 (Wave 1 게이트 `tests/` 전체 통과 후 착수), 복잡도: 4/10

## 구현자
sdd-implementer

## 테스트 타입
| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| agents/*-architect.md, 삭제 대상 4종 (Markdown) | 단위(정적 pytest) | 파일 부재·금지 문자열 |

(테스트 시나리오는 test-automator가 도출한다. 스킬/에이전트 Markdown 변경의 RED는 정적 pytest로 만든다. 모듈 전역 mock/patch 금지, fixture·tmp_path·환경변수 주입 사용.)

## 완료 조건
- [ ] `agents/`에 `sdd-ui-designer.md`, `sdd-api-designer.md`, `sdd-architect-reviewer.md`, `sdd-context-manager.md` 부재 (F9)
- [ ] architect 3종(`webapp-`/`flutter-`/`native-architect`) 본문에 `docs/sdd/design/arch/`, `Build Profile` 문자열 없음, "같은 문서의 설계 결정 섹션만 보강, 새 파일 금지" 지침 있음, 테스트 전략 지침은 유지 (F9)
- [ ] architect 3종 본문에 `ui-designer`, `api-designer` 문자열 없음 (webapp 24·26행, flutter 25·27행, native 24·26행 전제 문장을 "spec 설계 결정 보강"으로 교체) (F14)
- [ ] Phase 2 architect는 worktree 생성 전이므로 메인 체크아웃의 spec 파일을 보강한다는 문구 포함 (F9, D18)
- [ ] 모든 테스트 통과 (이 태스크의 테스트 스코프)

## 의존 태스크
T-5 (Wave 1 게이트 통과)

## 예상 변경 파일
- `agents/webapp-architect.md` — 저장 지시·Build Profile 제거, 보강 전용
- `agents/flutter-architect.md` — 동일
- `agents/native-architect.md` — 동일
- `agents/sdd-ui-designer.md` — 삭제
- `agents/sdd-api-designer.md` — 삭제
- `agents/sdd-architect-reviewer.md` — 삭제
- `agents/sdd-context-manager.md` — 삭제
- `tests/test_sdd_phase2_agents.py` — 신규 정적 테스트

(소유 파일 외 수정 금지. 커밋 시 소유 파일만 명시적 `git add`, `-A`/`.` 금지, 브랜치 전환 금지.)

## 비고
삭제 4종 이름이 skills/·hooks/·README 등에 남은 참조는 각 소유 태스크(T-7, T-8, T-12, T-13)가 제거한다. 파일 수 8개는 삭제 4개를 포함한 수치다(삭제는 기계적).

## Steps
- [ ] RED: `tests/test_sdd_phase2_agents.py` 작성(삭제 4종 부재, architect 3종 금지/필수 문자열) 후 실패 확인
- [ ] 삭제 4종을 `git rm`
- [ ] architect 3종에서 design/arch 저장 지시와 Build Profile 절 제거, 설계 결정 섹션 보강 전용 문구 + 테스트 전략 유지
- [ ] GREEN: 스코프 테스트 통과

## 검증 명령어
- 테스트 스코프: `tests/test_sdd_phase2_agents.py`
- fast-scoped 레포(빌드 단계 없음): 스코프 테스트만 실행한다. 형식은 `<PY> -m pytest <테스트 스코프> -q`.
- `<PY>`는 CLAUDE.md "빌드 / 테스트" 절의 확정 절차로 정한다. 인터프리터 경로·`PATH=` prefix를 적지 않는다.
- 빌드·테스트는 bq light lane으로 실행한다: `bq submit --wait --lane light -- <PY> -m pytest <테스트 스코프> -q`
