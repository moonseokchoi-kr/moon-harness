# T-4: evals 폴백 동작 시나리오

## 관련 문서
- spec: `docs/sdd/spec/2026-06-26-code-mapper.md`
- arch: `docs/sdd/design/arch/2026-06-26-code-mapper.md`

## 구현자
`sdd-implementer`

## 테스트 타입
이 태스크에서 변경되는 레이어와 테스트 방식:

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| 폴백 동작 eval (`evals/`) | E2E | codegraph 미초기화 레포에서 `claude -p` 라이브 실행. `pytest tests/`로 수집되지 않음(비혼합 규율). |

(arch 문서의 테스트 전략 기반. test-automator가 이 정보를 참고하여 적합한 프레임워크로 RED 테스트 작성)

## 완료 조건

- [ ] `evals/scenarios/` 아래에 code-mapper 폴백 시나리오 파일이 존재한다 (파일명/구조는 기존 evals 패턴 따름)
- [ ] 시나리오가 다음 세 검증 기준을 명시한다:
  1. F6 포맷 완전성: 섹션 1~6 누락 없음
  2. callers/callees 개수 > 0 또는 "(없음)" 정합성 (빈 결과도 "(없음)"으로 처리됨 확인)
  3. 수집 파일경로 유효성: 존재하는 파일만 (없는 경로 0건)
- [ ] 시나리오가 codegraph 미초기화 환경(상태 c: unavailable)을 가정하고, `/code-mapper <심볼>` 호출을 트리거한다
- [ ] 시나리오 결과에 "(grep 근사, codegraph 미사용)" 레이블이 포함되는지 확인 기준이 있다
- [ ] `evals/scenarios/` 파일이 기존 시나리오 포맷과 일관성을 유지한다 (기존 패턴 답습)
- [ ] `pytest tests/` 실행 시 `evals/` 파일이 수집되지 않는다 (비혼합 규율 — `pytest.ini` 설정 확인)
- [ ] 모든 테스트 통과 (E2E — 라이브 실행은 Phase 4 이후 수동 검증)

## 의존 태스크
T-1 (코어 패키지 존재), T-2 (SKILL.md 존재 — 시나리오에서 절차 참조)

## 예상 변경 파일
- `evals/scenarios/` — 신규 code-mapper 폴백 시나리오 파일 (파일명은 엔지니어 결정)

## Steps
- [ ] `evals/scenarios/` 디렉터리 및 기존 시나리오 파일 패턴 확인 (기존 eval 구조 파악)
- [ ] `pytest.ini` 확인: `evals/` 수집 제외 설정이 있는지 검증 (없으면 `testpaths` 또는 `collect_ignore`로 보강)
- [ ] codegraph 미초기화(상태 c: unavailable) 환경 전제의 폴백 시나리오 파일 작성:
  - 대상 심볼/파일 지정 (예: `hooks/lib/self_improve/tier.py` 등 실존 파일)
  - `/code-mapper <심볼>` 호출 트리거 명시
  - 세 검증 기준(F6 완전성/callers-callees 정합/파일경로 유효성) 명시
  - "(grep 근사, codegraph 미사용)" 레이블 포함 여부 확인 기준 추가
- [ ] 시나리오 파일 기존 eval 포맷 정합성 검토
- [ ] `pytest tests/ -q` 실행 → evals 파일이 수집되지 않음 확인 (비혼합 규율)

## 검증 명령어
빌드 프로파일: fast-scoped. evals 자체는 라이브 실행(claude -p)이므로 pytest 대상 아님. 비혼합 규율 확인 + 회귀 방지용 전체 pytest 실행.

```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q
```
