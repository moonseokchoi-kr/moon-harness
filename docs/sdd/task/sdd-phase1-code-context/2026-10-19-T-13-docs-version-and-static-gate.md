# T-13: README·CLAUDE.md 갱신 + 버전 0.15.0 + 전체 정적 게이트

## 관련 문서
- spec: `docs/sdd/spec/2026-10-19-sdd-phase1-code-context.md` (단일 문서. arch/ui/api 문서는 없다: Phase 2 ARCH_SKIP)
- 구현하는 spec 요구사항: F14, F15 (+F4/F6/F9/F11/F13 전체 스캔 회귀)
- Wave: Wave 2 (Wave 1 게이트 `tests/` 전체 통과 후 착수), 복잡도: 5/10

## 구현자
sdd-implementer

## 테스트 타입
| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| README.md, CLAUDE.md, .claude-plugin/*.json | 단위(정적 pytest) | 버전·스캔 범위 전수 금지 문자열 |
| tests/ 전체 | 회귀 | Wave 2 종료 게이트 |

(테스트 시나리오는 test-automator가 도출한다. 스킬/에이전트 Markdown 변경의 RED는 정적 pytest로 만든다. 모듈 전역 mock/patch 금지, fixture·tmp_path·환경변수 주입 사용.)

## 완료 조건
- [ ] `.claude-plugin/plugin.json`과 `marketplace.json`의 `version`이 모두 `"0.15.0"` (F15)
- [ ] `README.md`(73행 게이트 목록)와 `CLAUDE.md`(15행 "spec/design/task/result")를 단일 문서 흐름(spec/task/result)으로 갱신 (F14)
- [ ] 스캔 범위(`skills/`, `agents/`, `hooks/`(단 `hooks/lib/kompound_snapshot/` 제외), `.claude-plugin/`, `README.md`, `CLAUDE.md`)에서 `ux-researcher`, 삭제 에이전트 4종 이름 0건 (F4, F9)
- [ ] 같은 스캔 범위에서 `docs/sdd/design/`, `docs/sdd/context/` 경로 문자열 0건. 예외는 `stop-pipeline.py:217-227`의 구 라벨 호환 `has_arch`/`has_ui`/`has_api`/`has_context`(218행 포함) 검사 제외뿐 (F6, F14)
- [ ] 같은 스캔 범위에서 `SIMPLE` 0건(TDD 모드 FULL 용례는 대상 아님), `rg -n "docs/sdd/design/arch|Build Profile|arch 문서의 .*## 빌드 프로파일|taskmaster가 복사" skills agents hooks --glob '!hooks/lib/kompound_snapshot/**'` 결과 0건(위 예외 제외) (F11, F12)
- [ ] `skills/sdd/SKILL.md` 줄 수 ≤ 671, `hooks/enforcement/e2e-gate.sh`·`hooks.json`·`hooks/lib/code_mapper/`·`hooks/lib/kompound_snapshot/` 무변경 (F3, F13, F15)
- [ ] `tests/test_kompound_snapshot_*.py` 전체 수정 없이 통과 (F14)
- [ ] Wave 2 종료 게이트: `tests/` 전체 통과. kompound 영향(I1, R7: registry arch 열 `—` 증가)과 E2E 수동 검증 수행 여부를 결과 문서용으로 기록 (F14, F15)
- [ ] 모든 테스트 통과 (이 태스크의 테스트 스코프)

## 의존 태스크
T-6, T-7, T-8, T-9, T-10, T-11, T-12

## 예상 변경 파일
- `README.md` — 73행 게이트 목록
- `CLAUDE.md` — 15행 문서 구성
- `.claude-plugin/plugin.json` — version 0.15.0
- `.claude-plugin/marketplace.json` — version 0.15.0
- `tests/test_sdd_static_docs.py` — 신규(전체 스캔·버전·줄 수·무변경 단정)

(소유 파일 외 수정 금지. 커밋 시 소유 파일만 명시적 `git add`, `-A`/`.` 금지, 브랜치 전환 금지.)

## 비고
버전 동기화는 마지막 태스크다. 커밋 메시지에 `stop-pipeline.py`/`phase-gate.sh` 변경이 사용자 명시 승인(2026-10-19) 범위임을 남긴다(F15).

## Steps
- [ ] RED: `tests/test_sdd_static_docs.py` 작성(버전, 스캔 범위 금지 문자열, 줄 수, kompound 제외 규칙) 후 실패 확인
- [ ] README·CLAUDE.md 갱신
- [ ] 두 JSON 버전을 0.15.0으로 동기화
- [ ] 전체 스캔 실패 항목이 남으면 해당 소유 태스크(T-6~T-12)로 되돌려 보고(이 태스크에서 타 소유 파일 수정 금지)
- [ ] Wave 2 종료 게이트: `tests/` 전체 실행

## 검증 명령어
- 테스트 스코프: `tests/test_sdd_static_docs.py (+ 전체 `tests/`)`
- fast-scoped 레포(빌드 단계 없음): 스코프 테스트만 실행한다. 형식은 `<PY> -m pytest <테스트 스코프> -q`.
- `<PY>`는 CLAUDE.md "빌드 / 테스트" 절의 확정 절차로 정한다. 인터프리터 경로·`PATH=` prefix를 적지 않는다.
- 빌드·테스트는 bq light lane으로 실행한다: `bq submit --wait --lane light -- <PY> -m pytest <테스트 스코프> -q`
