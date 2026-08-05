# 제안 — enforcement 훅 오탐 수정 (file-ownership 3중 버그 + 명령 문자열 훅)

**티어**: 하네스 · **사용자가 2026-08-05 세션에서 명시 승인** → 이 문서는 승인 대기가 아니라
**구현 스펙**이다. 승인 근거: 사용자가 두 훅에 막혀 Bash로 우회한 뒤 직접 버그를 보고하고
수정을 지시했다("이 버그는 5번으로 수정해줘").
**대상 파일**: `hooks/file-ownership.sh`, `hooks/dangerous-command.sh`
(`guard.is_protected()` = False이나 CLAUDE.md "게이트 스크립트" 규정상 사람 승인 대상 — 승인됨)
**critic 판정**: NARROW — 4개 조항 중 3개는 타당, **2개 조항에 결함**을 지적
**근거 엔트리**: `.harness/LEARNING.md`
- `## 2026-07-01 — harness-enforcement / file-ownership 라이프사이클`
- `## 2026-08-05 — harness-enforcement / file-ownership 오탐 재발 + dangerous-command heredoc 오탐`
**증거 강도**: **2 독립 신호** (배치 중 유일) · `has_cross_project=False` · 양쪽 모두 이번 세션 재현

---

## 확인된 결함 (critic이 코드로 검증)

`hooks/file-ownership.sh`:
1. `while IFS='|' read -r _ task files _` 가 **태스크-먼저-파일** 순서를 하드코딩하나,
   실제 표 헤더는 `| 파일 경로 | 소유 태스크 |` — 순서가 반대라 **설명 텍스트를 파일 목록으로 파싱**한다.
2. `[[ "$REL_PATH" == *"$owned"* ]]` — **앵커 없는 부분문자열 매칭**이라 산문 단어가 경로로 매칭된다.
   실제 사례: 설명문 "RenderFilmap pick 분기 원복"의 `pick`이 `release-cherry-pick`에 걸림.
3. `REL_PATH="${FILE_PATH#$PROJECT_DIR/}"` — 레포 밖 절대경로는 그대로 남아 그 상태로 매칭된다.

`hooks/dangerous-command.sh`: 명령 문자열만 보므로 **heredoc 본문에 문서로 적힌** 파괴적 git
명령을 실제 명령으로 오인한다.

이번 세션 재현 3건: `.claude-plugin/marketplace.json` Edit 차단("T-2 소유"), `naming.py` Edit 차단,
스크래치패드(`/private/tmp/...`, 레포 밖) Write가 `hooks/lib/kompound_snapshot/__init__.py` 소유로
차단. 그리고 이 교훈 엔트리를 heredoc으로 append하려는 시도 자체가 `dangerous-command.sh`에 차단됐다.

## 구현 규칙 (critic 좁힘 반영 — 이 텍스트대로 구현)

> **상태파일 기반 enforcement 훅 (ownership 등)** — repo 안의 상태 문서에서 권한을 끌어오는 훅은:
> (1) 그 문서의 **라이프사이클 상태를 읽어** 활성 구간(EXECUTING/PLANNING)에서만 enforce하고,
> 상태가 완료(COMPLETED 등)·부재·**해석 불가**면 **통과**한다(fail-open — 조정 보조 장치이므로
> 차단측으로 실패하지 않는다); (2) 표를 파싱할 때 컬럼을 **위치가 아니라 헤더 이름으로** 판별한다;
> (3) 매칭 대상을 **경로 형태 토큰**(`/` 포함 또는 알려진 확장자로 종료)으로 한정하고 경계 고정
> 비교를 쓴다 — 설명 산문의 단어가 경로로 매칭되면 안 된다; (4) 대상 경로가 `PROJECT_DIR` 밖이면
> 즉시 통과한다. (4)는 **상태파일 기반 훅에만** 적용된다 — secret-detect·sensitive-file 류 보안
> 훅은 레포 밖 쓰기(`~/.ssh`, `~/.aws`)를 계속 검사해야 하므로 이 조항을 적용하지 않는다.
>
> **명령 문자열 검사 훅** — heredoc 본문을 판정에서 제외할 때는 heredoc의 **수신자**를 확인한다.
> `cat > file`·`tee` 등 파일 쓰기 싱크로 가는 본문만 제외하고, `bash`/`sh`/`zsh`/`python3` 등
> **인터프리터로 파이프되는 heredoc 본문은 계속 검사**한다(그렇지 않으면 heredoc이 모든 검사의
> 우회로가 된다).

## critic이 지적한 원안의 결함 2건 (반드시 반영)

1. **조항 (iv) 원안이 오발화한다.** "enforcement 훅은 프로젝트 밖 경로를 검사하지 않는다"는
   *ownership*(레포 내 상태 파생, 조정 편의 게이트)엔 옳지만 `hooks/secret-detect.sh`·
   `hooks/sensitive-file.sh`엔 **적극적으로 해롭다** — `~/.aws/credentials`나 `~/.ssh/`에
   크리덴셜을 쓰는 건 절대 건너뛰면 안 되는 바로 그 케이스다. → **상태파일 기반 훅으로 범위 한정.**
2. **조항 (i)에 실패 방향이 빠졌다.** "EXECUTING/PLANNING일 때만 enforce"는 상태가 없거나
   인식 불가인 STATE 파일에 침묵한다. 여기선 fail-open이 옳지만(ownership은 안전 게이트가 아니라
   조정 보조), 명시하지 않으면 반대 구현을 유도해 영구 차단 버그를 새 이름으로 재생산한다.
3. **`dangerous-command.sh` 무조건 heredoc 제외는 위험하다** (원안에 없던 지적):
   `bash <<'EOF' … EOF` / `python3 <<'EOF' … EOF`는 본문을 인터프리터에 바로 먹인다. 무조건
   제외하면 heredoc이 스크립트 내 **모든 검사의 우회로**가 된다. → 비-인터프리터 싱크만 제외.
   (이 세션의 우회들이 정확히 `python3 - <<'PY'` 형태였다 — 무조건 제외 시 실제 구멍이 된다.)

## 구현 순서

1. `file-ownership.sh` — (4) PROJECT_DIR 밖 즉시 통과 가드(가장 저렴, 효과 큼) → (1) 상태 게이트
   fail-open → (2) 헤더 기반 컬럼 판별 → (3) 경로 형태 토큰 + 경계 고정 매칭.
2. `dangerous-command.sh` — heredoc 싱크 판별 후 파일 쓰기 싱크 본문만 제외.
3. 두 훅에 대한 회귀 테스트 추가(오탐 3케이스 + 정탐 유지 케이스 + 인터프리터 heredoc 우회 차단).
4. 완료된 SDD 사이클 STATE 아카이브 여부는 (1)이 해결하므로 **후속 선택 사항**으로 남긴다.
