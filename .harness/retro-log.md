# Retro Log (append-only)

`/self-improve` 회고 이력. 회고 1회 = 요약 1줄 + 적용된 프로젝트 티어 변경마다 롤백 블록.
사람이 직접 편집하지 않는다.

---

## 2026-08-05 retro — 신규 12건 처리 / 적용 3 · 제안 4 · 폐기 5

첫 회고 (`retro-state.json` 부재 → 전체가 신규). Phase A에서 **입력 채널 결함**을 먼저 발견:
main의 `.harness/LEARNING.md`에 사이클 교훈이 0건이었고, 아직 살아 있던
`worktrees/kompound-snapshot-hook/.harness/LEARNING.md`에서 4건(T-5/T-10/T-13/T-12)을 회수해
시간순 병합한 뒤 회고를 진행했다. 이번 세션 신호 2건(네이밍 중복 / 훅 오탐)을 추가해 총 12건.
클러스터 10개, **전부 `has_cross_project=False`**(단일 repo `moon-harness` 근거).
critic 배치 판정: UPHELD 1 · NARROW 6 · REFUTED 1.

### 적용 (프로젝트 티어, 자동)

- **`docs/lessons-learned.md`** (신규 생성) ← 결합 verdict 필드 / 네이밍 정합 감사 / 비수렴 승격
  - critic: NARROW(C1) · NARROW(C6a) · **UPHELD**(C6b)
  - 근거: `## 2026-07-30 — kompound-snapshot-hook / T-5-git-state`,
    `## 2026-08-05 — kompound-snapshot / 네이밍 중복 접기 (첫 실전 실행)`
  - rollback: `rm docs/lessons-learned.md` (신규 파일이므로 파일 삭제로 완전 원복)

- **`CLAUDE.local.md`** (신규 생성) ← `@docs/lessons-learned.md` 컨텍스트 포인터
  - 이유: 포인터가 `CLAUDE.md`·`CLAUDE.local.md` 어디에도 없어 승격 문서가 로드되지 않았다
    (Phase D §10 가설-A 갭). committed `CLAUDE.md`는 편집하지 않았다.
    `.gitignore:20`에 `CLAUDE.local.md`가 이미 있어 추가 불필요.
  - rollback: `rm CLAUDE.local.md`

- **`.harness/LEARNING.md`** ← 워크트리 교훈 4건 회수 병합 + T-13 엔트리에 누락된 provenance 태그 삽입
  - 이유: 입력 채널 복구(회고 자체가 불가능한 상태였음). LEARNING.md는 읽기 전용 입력이라는
    규칙의 예외 — 삭제·수정이 아니라 **소실된 엔트리 복원**이며 원문 그대로 병합했다.
  - rollback: `## 2026-07-30 — …T-5-git-state` ~ `## 2026-08-04 — …T-12-stop-pipeline` 4블록 제거
    (원본은 `worktrees/kompound-snapshot-hook/.harness/LEARNING.md`에 그대로 있음)

### 제안 (하네스 티어, 승인 대기)

- `harness-proposals/2026-08-05-learning-recovery-before-worktree-removal.md` —
  `skills/git-worktree/SKILL.md` + `skills/sdd-orchestrator/SKILL.md` /
  **최우선**: 워크트리 삭제 전 LEARNING 헤더-dedup 회수 (자가개선 입력 채널 복구)
- `harness-proposals/2026-08-05-enforcement-hook-false-positive-fixes.md` —
  `hooks/file-ownership.sh` + `hooks/dangerous-command.sh` / 오탐 수정
  (**2 독립 신호 · 사용자 명시 승인 완료 → 구현 스펙으로 사용**)
- `harness-proposals/2026-08-05-sdd-review-checklist-arch-self-verification.md` —
  `agents/sdd-reviewer.md` + `agents/sdd-test-automator.md` + `agents/sdd-architect-reviewer.md` /
  복구 경로 실행 증명 · 프리필터·코어 정합 · 콜드 프로세스 성능 단정 (3항목 통합)
- `harness-proposals/2026-08-05-report-nonconvergent-human-decision.md` —
  `hooks/lib/kompound_snapshot/report.py` / 비수렴 실패를 `human_decision_required`로 분기

### 폐기

- **T-13 프리필터 대소문자 버그 수정 제안 (C3a)** — REFUTED: **이미 main에서 수정됨**.
  `hooks/enforcement/kompound-snapshot-gate.sh:50-62`가 `case`를 `shopt -s nocasematch`로
  감싸고 인라인 주석이 해당 LEARNING 엔트리를 인용한다. 이미 고쳐진 결함을 protected 스크립트
  수정 제안으로 올리면 사람 승인 사이클을 낭비한다 — 게이트가 정확히 이걸 잡았다.
- `sdd-orchestration` (2신호) — 병렬 worktree `git add -A` / 브랜치 전환 금지.
  이미 `CLAUDE.md` "핵심 규칙"에 반영돼 있어 **중복**으로 폐기.
- `sdd-tdd` (1신호) — 거대 레포 build-aware TDD. 1회성·맥락 한정(레포 특화 빌드 프로파일)이라
  행동 규칙 변경에서 강등.
- `harness` (1신호) — CLAUDE.md 부재 시 `CLAUDE.local.md` 폴백. 이번 회고가 **그 규칙을 실제로
  실행**했으므로(위 적용 2번째 항목) 별도 규칙화 불필요.
- `two-stage-prefilter-parity` 중 arch 리뷰 항목은 제안으로 살아남았고, 그 원인이 된 코드 결함은
  위 C3a로 폐기 — 클러스터가 절반만 생존.

## 2026-08-06 retro — 신규 1건 처리 / 적용 2 · 제안 2 · 폐기 0

두 번째 회고. **Phase A에서 커서 결함을 발견**해 그것부터 처리했다 — 저장된 마커가
`## ` 접두형이라 `cursor.get_new_entries`의 완전일치 비교가 실패하고, fail-safe가 발동해
**13/13건을 "신규"로 반환**했다(접두 제거 시 1건). 즉 1회차 이후 커서가 한 번도 전진하지 않았다.
실제 신규는 `## 2026-08-06 — harness-docs / 인터프리터 경로 하드코딩이 무해→유해로 전환` 1건.
클러스터 `toolchain-path-hardcoding` — `same_repo=1`이지만 본문에 명시적 반복 신호("같은 지적이
이미 두 번")가 있어 `run_prechecks`의 `too_sparse=False` 통과. `has_cross_project=False`.
critic 판정: UPHELD 1 · NARROW 2 · REFUTED 0.

### 적용 (프로젝트 티어, 자동)

- **`docs/lessons-learned.md`** ← "인터프리터·툴 경로를 적지 말고 확정 절차를 적는다" (§문서에 적는 실행 명령 신설)
  - critic: NARROW
  - 근거: `## 2026-08-06 — harness-docs / 인터프리터 경로 하드코딩이 무해→유해로 전환`
  - 좁힌 이유: 원안("문서의 빌드/테스트 명령은 경로를 하드코딩하지 말 것")은 CI 러너 핀·컨테이너
    이미지·lockfile·shebang처럼 **경로 고정이 목적인** 곳까지 금지로 읽힌다. 적용 범위를
    "문서의 복사-실행 명령"으로 한정. 이 머신의 pytest 실측 사례는 `CLAUDE.md` 빌드/테스트 절에
    이미 있으므로 재기술하지 않고 일반 원칙만 승격.
  - rollback: `docs/lessons-learned.md`의 `## 문서에 적는 실행 명령` 섹션 전체 제거

- **`.harness/retro-state.json`** ← 마커를 비접두형으로 교체 (커서 복구)
  - critic: 판정 대상 아님 (규칙 변경이 아니라 상태 파일 수리)
  - before: `"last_processed_marker": "## 2026-08-05 — harness-enforcement / file-ownership 오탐 재발 + dangerous-command heredoc 오탐"`
  - after: `"last_processed_marker": "2026-08-06 — harness-docs / 인터프리터 경로 하드코딩이 무해→유해로 전환"`
  - 검증: 교체 후 `get_new_entries` 신규 0건 (정상 전진)
  - rollback: 위 before 값으로 복원 (단 커서가 다시 전량 재처리 상태로 돌아간다)

### 제안 (하네스 티어, 승인 대기)

- `harness-proposals/2026-08-06-cursor-marker-prefix-mismatch.md` —
  `hooks/lib/self_improve/cursor.py`(비protected) + `skills/self-improve/SKILL.md`(**protected**) +
  `skills/self-improve/scripts/cursor_runner.py`(**protected**) /
  **최우선**: 비교 시점 마커 정규화 + `marker_resolved` 관측성 + 문서 스키마 예시 수정.
  critic **UPHELD**. protected 2개를 건드리므로 사람 승인 필수.
- `harness-proposals/2026-08-06-ssot-command-divergence-capture.md` —
  `skills/sdd/SKILL.md` §LEARNING 캡처 / "SSOT 명령 불일치"를 캡처 대상에 추가.
  critic NARROW — **target 교체**(원안 `sdd-orchestrator` Step 4/5는 오케스트레이터가 서브에이전트
  셸을 못 보므로 탐지 불가) + `:636` "단순 트러블슈팅" 조항과의 충돌 해소 필수.

### 폐기

- 없음. (1회차와 달리 REFUTED 0건 — 신규 신호가 1건뿐이었고 그 1건이 인용 가능한 선행 2건을 동반)

### 다음 라운드 후보 (critic 부수 발견 — 이번 라운드 판정 대상 아님)

- **`run_prechecks` 충돌 오탐이 영구화됐다.** `docs/lessons-learned.md`의 preamble(3–9행,
  "사람이 직접 규칙을 추가하지 말고 회고 루프를 통해 승격할 것")은 고정이고 `근거`는 모든 엔트리의
  보일러플레이트 키워드다. ±3행 슬라이딩 윈도우라 **프로젝트 티어 주 타깃 파일을 겨냥한 모든
  후보에서 앞으로 100% `conflict=True`**가 뜬다 — 일시적 오탐이 아니라 신호가 영구 무용화된 상태.
  좁은 수정 방향: 충돌 스캔에서 첫 `##` 헤딩 이전 preamble 제외(파서가 이미 쓰는 규약과 동일).
- **`PROTECTED_SET`이 self-improve의 결정적 코어(`hooks/lib/self_improve/`)를 포함하지 않는다.**
  프롬프트(`skills/self-improve`)는 보호하면서 같은 루프의 판정 로직은 보호하지 않는다 —
  이번 커서 결함이 자기 커서 엔진을 대상으로 삼은 상황이 그 비대칭을 처음 실증했다.
  보호를 넓히면 자가수정 여력이 줄어드는 트레이드오프가 있어 별건 판정 필요.

### 승인·적용 (2026-08-06, 사용자 승인 후)

위 하네스 제안 2건을 사용자가 승인해 **같은 날 적용**했다. 제안서에 `✅ 적용 완료` 스탬프를 남겼다.

- `cursor.py` — 비교 시점 마커 정규화(선행 `#`/공백 제거, 저장 형식은 비접두형 유지) +
  `marker_resolves()` 신설. `cursor_runner.py`(protected) — `marker_resolved`/`warning` 필드.
  `self-improve/SKILL.md`(protected) — 스키마 예시 접두 제거 + Phase A 3항에 "커서 미해석 검사(필수)".
  회귀 13건. 라이브: 접두형 마커가 14건→1건으로 정상 해석, 미해석 마커는 경고 + fail-safe 전량 유지.
- `sdd/SKILL.md` — 캡처 대상에 **SSOT 명령 불일치** 행, `:636` 트러블슈팅 예외 명시,
  트리거 규칙(1회 캡처 + `문서 경로:line`·문서 명령·실제 성공 명령·`SSOT 수정 후보` 기재),
  엔트리 포맷 `유형` 목록 확장. `sdd-orchestrator/SKILL.md`는 critic 지적대로 미변경.

테스트 스위트 1111 → 1124 passed. 플러그인 0.12.1 → 0.13.0.

**작성 중 발견한 자기모순 (다음 라운드 후보 추가)**: `skills/sdd/SKILL.md:615,624`는
`@.harness/LEARNING.md` import를 지시하는데 `skills/self-improve/SKILL.md` **F18은 그 방식을
"폐기 · 절대 사용 금지"**로 명시한다(태그 on-demand 라우팅으로 대체). 두 하네스 스킬이 정면
충돌하며, 이번 승인 범위 밖이라 손대지 않았다. F18이 옳다면 sdd/SKILL.md의 로딩 절을 고쳐야 하고,
그러면 "다음 사이클 시작 시 자동 로드" 서술의 대체 경로도 함께 정의해야 한다.
