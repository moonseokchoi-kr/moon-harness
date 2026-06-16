# T-8: harness-improvement-critic.md EXTEND (F16 교차프로젝트 + F22 벤치마크 게이트)

## 관련 문서
- spec: `docs/sdd/spec/2026-06-16-self-improving-harness.md` — F12 (반박 검증), F16 (오염 격리 — 하네스 티어 교차프로젝트 무해성), F22 (벤치마크 fitness function — critic 보조화)
- arch: `docs/sdd/design/arch/2026-06-16-self-improving-harness.md` — §3.4 (critic agent — pure judgment, no scripts), §9 (critic EXTEND: F16 cross-project safety, F22 benchmark delta primary)

## Wave
**Wave 2** (Phase 1 skill EXTEND — Wave 1 의존 없음, T-7과 병렬 가능)

## 구현자
sdd-implementer

## 테스트 타입

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
| critic agent 판단 로직 | 라이브 eval (integration) | `evals/` — critic은 순수 판단 레이어, 결정적 스크립트 없음 |

## 완료 조건
- [ ] `agents/harness-improvement-critic.md`: 기존 5개 검증 기준(실재성, 일반성, 무모순, 무해성, 구체성) 보존
- [ ] F16 반영: 하네스 티어 후보 평가 시 "교차 프로젝트 2곳 이상 재현 근거" 여부를 무해성 기준의 명시적 하위 기준으로 추가. 교차 프로젝트 근거 없으면 무해성 기준 자동 실패 → REFUTED 또는 NARROW
- [ ] F22 반영: "입력에 벤치마크 델타가 제공된 경우 객관 점수를 주 판단 근거로, critic 주관 판정을 보조로 사용"을 판정 섹션에 명시. 벤치 델타가 없는 경우(Phase 1/콜드스타트) 기존 5기준으로만 판정하는 분기 명시
- [ ] F22의 "벤치마크 점수 하락 개선안은 UPHELD 판정에도 불구하고 채택 불가" 원칙이 critic 출력 포맷에 반영 (Acceptance 조건)
- [ ] 출력 포맷에 `벤치마크 델타: N/A (Phase 1) | +X% (채택) | -X% (기각)` 필드 추가
- [ ] 판단이 애매할 때 REFUTED/NARROW로 기우는 보수적 기본값 유지 (기존 규칙 보존)
- [ ] 스크립트 없음 — critic은 순수 판단 agent, Python 코드 추가 없음 (arch §3.4)
- [ ] 변경 후 critic 프롬프트가 `is_protected` 가드와 충돌하지 않음 (critic 자체가 protected set 멤버 — 이 EXTEND는 **사람 검토 하의 수동 EXTEND**)

## 의존 태스크
없음 (Wave 2, T-6/T-7과 병렬 가능)

## 예상 변경 파일
- `agents/harness-improvement-critic.md` — F16 무해성 하위 기준 추가, F22 벤치마크 델타 입력/판정 분기, 출력 포맷 필드 추가

## Steps
- [ ] 기존 `agents/harness-improvement-critic.md` 전문 읽기 + 변경 전후 diff 계획
- [ ] 입력 섹션에 "벤치마크 델타(선택, Phase 2 이후 제공)" 추가
- [ ] 무해성 기준 하위에 교차 프로젝트 재현 체크리스트 삽입 (하네스 티어만 해당, 프로젝트 티어 해당 없음)
- [ ] 판정 섹션에 벤치마크 델타 분기 추가: 델타 있음 → 점수 주도, 없음 → 5기준 주도
- [ ] 출력 포맷 템플릿에 `벤치마크 델타` 필드 삽입
- [ ] 전체 검토: 기존 5기준 언어 보존, 새 내용이 기존 내용과 모순 없음 확인

## 검증 명령어
```bash
# critic은 결정적 스크립트 없음 — 문서 변경 확인만
grep -n "교차 프로젝트" /Users/moon/workspace/moon-harness/worktrees/self-improving-harness/agents/harness-improvement-critic.md
grep -n "벤치마크 델타" /Users/moon/workspace/moon-harness/worktrees/self-improving-harness/agents/harness-improvement-critic.md
```
