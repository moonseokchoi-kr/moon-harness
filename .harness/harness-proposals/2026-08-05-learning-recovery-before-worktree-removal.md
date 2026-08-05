# 제안 — 워크트리 삭제 전 LEARNING 회수 (자가개선 입력 채널 복구)

**티어**: 하네스 · **자동 적용 없음**
**우선순위**: **최상** — 이게 끊긴 동안 self-improve는 매 사이클 "신규 교훈 0건"으로
조용히 수렴한다. 실패가 아니라 정상 종료로 보이기 때문에 발견이 늦는다.
**대상 파일**: `skills/git-worktree/SKILL.md` (워크트리 제거 절차) +
`skills/sdd-orchestrator/SKILL.md` (머지 체크리스트) — **둘 다 protected=False**
**critic 판정**: NARROW
**근거 엔트리**: `.harness/LEARNING.md` `## 2026-08-05 — harness-learning-capture / 워크트리 사이클 교훈 소실`
**증거 강도**: 1신호 · `has_cross_project=False`. 다만 critic 평가 — 기제가 **git 일반**이라
단일 repo 근거가 통상보다 덜 치명적이고, 이번 세션에 **구체적으로 실증**됐다(main은 사이클 교훈
0건, 아직 살아 있던 워크트리에 4건).

---

## 문제

`.gitignore:28`이 `.harness/LEARNING.md`를 무시한다(`54da464` "per-clone 로컬 전용").
워크트리는 자기 작업 디렉터리를 갖고 gitignore된 파일은 디렉터리별로 독립이므로, SDD 표준
실행 모드인 워크트리 사이클에서 에이전트가 append한 교훈은 **브랜치 머지에 포함되지 않고
워크트리 삭제와 함께 소실**된다. self-improve의 유일한 입력이 이 파일이다.

실증: `git ls-files .harness/`는 비어 있고, main의 최신 엔트리는 2026-07-01이었으나
`worktrees/kompound-snapshot-hook/.harness/LEARNING.md`에 4건(T-5/T-10/T-13/T-12)이 살아 있었다.
워크트리가 아직 삭제되지 않아 이번 세션에 수동 회수했다. HANDOFF는 "신규 3건"이라 적었는데
실제로는 4건 — 사람 요약과 실제 파일이 이미 어긋나 있었다.

## 추가할 텍스트

> **워크트리 삭제 전 LEARNING 회수 (필수 단계)** — 워크트리를 삭제하거나 사이클을 머지 완료로
> 표시하기 전에, `<worktree>/.harness/LEARNING.md`를 읽어 메인 클론의 `.harness/LEARNING.md`에
> **없는 엔트리만** append한다. 동일성 판정은 엔트리 헤더(`## YYYY-MM-DD — <제목>`) 기준이며,
> 이미 존재하는 헤더는 건너뛴다(재실행 시 중복 append 금지 — 중복은 회고의 신호 카운트를
> 오염시킨다). 회수 건수를 삭제 보고에 명시하고, 워크트리 LEARNING이 비어 있으면 "0건"으로
> **명시 보고**한다(조용한 통과 금지). `.harness/LEARNING.md`는 계속 gitignore 상태로 두고
> 브랜치 머지에 의존하지 않는다.

## critic이 원안을 좁힌 이유 (3가지 — 그대로 채택 권고)

1. **원안이 상호배타적 대안 2개를 병렬 제시**했다(T2 게이트에서 flush vs gitignore 해제).
   하나를 고르지 않은 후보는 리뷰 가능한 diff가 아니다.
2. **T2 게이트 변형은 protected 스크립트를 편집**한다(`hooks/enforcement/`). 결정적 코어는
   자동 수정 대상에서 명시 제외된다. → **절차 단계(비-protected 스킬 문서)로 구현**하고,
   T2 게이트에 심는 안은 **별도 사람 승인 항목**으로 분리해 동시 채택하지 않는다.
3. **무조건 append는 멱등이 아니다.** 두 번 실행하면(삭제 재시도, 또는 그 워크트리에서 분기한
   두 번째 워크트리) 엔트리가 중복되고, 그건 회고가 의존하는 재발률/신호 카운트 입력을 직접
   오염시킨다 — 고치려는 루프 자체를 열화시킨다. → 헤더 기준 dedup 필수.
4. gitignore 해제는 **권장하지 않는다** — 3개 에이전트가 동시 append하는 파일에 per-clone
   머지 충돌을 초래한다.

## 적용 방법

1. 위 텍스트를 `skills/git-worktree/SKILL.md`의 워크트리 제거 절차에 필수 단계로 삽입.
2. `skills/sdd-orchestrator/SKILL.md` 머지 체크리스트에 같은 항목 참조 추가.
3. T2 게이트(`hooks/enforcement/kompound-snapshot-gate.sh`, protected)에 회수를 심는 안은
   **이 항목과 별도로** 승인받는다.
