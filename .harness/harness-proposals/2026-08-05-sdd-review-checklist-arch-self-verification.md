# 제안 — sdd-reviewer / sdd-test-automator 체크리스트 3항목 추가

**티어**: 하네스 (설치된 모든 프로젝트에 전파) · **자동 적용 없음**
**대상 파일**: `agents/sdd-reviewer.md`, `agents/sdd-test-automator.md` (protected=False)
**critic 판정**: NARROW ×3 (C2, C3b, C4) — 원안 3건 모두 범위를 좁혀 채택 권고
**근거 엔트리**: `.harness/LEARNING.md`
- `## 2026-07-30 — kompound-snapshot-hook / T-10-apply` (C2)
- `## 2026-08-04 — kompound-snapshot-hook / T-13-t2-gate-hooks-registration` (C3b)
- `## 2026-08-04 — kompound-snapshot-hook / T-12-stop-pipeline` (C4)
**증거 강도**: 각 1신호 · `has_cross_project=False`(전부 `provenance_repo=moon-harness`) —
F16 기준 하네스 티어 **자동 승격 불가**, 사람 승인 필수. 벤치마크 델타 = N/A(콜드스타트).

critic이 C3b와 C4를 "arch가 두 산출물을 커플링하는 주장을 하면서 그 커플링의 검증 항목을
싣지 않는다"는 **동일 결함 클래스**로 묶었다. 따라서 두 항목은 별개 불릿이 아니라
**`arch 자체 검증 항목`이라는 한 헤딩 아래** 넣는다 — 그러지 않으면 세 번째 사례가
세 번째 불릿로 도착한다. C2·C4가 같은 두 파일을 대상으로 하므로 **한 건의 승인 항목**으로 제출한다.

---

## 추가할 텍스트

### (1) `sdd-test-automator` + `sdd-reviewer` 체크리스트 — 복구 경로 실행 증명

> **복구 경로 실행 증명** — 롤백/복구 코드(트랜잭션 저널, 원본 복원, 보상 트랜잭션)가 있는
> 모듈에서 "실패 시 되돌아간다" 테스트를 쓸 때는, 실패 유도 지점이 **복구 코드가 실제로
> 실행되는 지점 이후**인지 확인하고, 복구 경로를 밟았다는 것을 관측 가능한 단언(복원된
> 산출물이 원본과 바이트 동일 / 복구 로그·카운터)으로 증명한다. 복구 코드가 한 번도
> 실행되지 않는 더 쉬운 실패 지점(검증 단계 조기 반환 등)만으로 GREEN이 되면 커버리지
> 공백으로 판정한다.

critic이 원안("저널 / pre-write vs post-write / 3파일 바이트 동일")을 거부한 이유: 한 사건의
어휘를 모든 레포의 영구 체크리스트에 새기게 된다. 저널 패턴이 없는 레포에선 절대 발화하지 않고
(죽은 체크리스트 무게), 다른 복구 기제(temp-dir swap, DB 트랜잭션, `git stash`)를 쓰는 레포에선
pre/post-write 분류가 실패 표면을 잘못 서술해 리뷰어가 N/A 처리한다. 결함 클래스는 한 단계 위 —
**복구 코드를 한 번도 실행하지 않는 실패 유도 테스트**.

### (2) `sdd-architect-reviewer` 체크리스트 — arch 자체 검증 항목 / 프리필터·코어 정합

> **프리필터/코어 인식 집합 정합** — arch가 "저렴한 프리필터 + 정확한 코어" 2단 분리를 규정하고
> 두 단계의 인식 패턴을 **서로 다른 절에 따로** 적었다면, 두 집합을 **표로 나란히 대조**해
> 프리필터가 코어의 상위집합임을 보이는 acceptance 항목을 arch에 포함한다. 대조 표에는 최소한
> 대소문자·플래그 결합·구분자 변형 축을 각각 한 행으로 넣고, 상위집합이 아닌 입력 클래스는
> "승인된 미탐"으로 명시 분류한다(분류되지 않은 누락 = 결함).

**중요 — 원안의 절반은 폐기됐다.** T-13 엔트리가 보고한 실제 버그(`kompound-snapshot-gate.sh`의
bash `case`가 소문자만 매칭해 `rm -Rf <worktree>`가 T2 게이트를 우회)는 critic 검증 결과
**이미 main에서 수정돼 있다** — `hooks/enforcement/kompound-snapshot-gate.sh:50-62`가 `case` 문을
`shopt -s nocasematch` / `shopt -u nocasematch`로 감싸고 있고 인라인 주석이 이 LEARNING 엔트리를
인용한다("it.2 compliance 실질 결함 수정"). 이미 고쳐진 결함을 protected 스크립트 수정 제안으로
올리면 사람 승인 사이클을 낭비한다 — **REFUTED, 제안에서 제외.** 살아남은 것은 arch 리뷰
acceptance 항목(위 텍스트)뿐이다.

### (3) `sdd-reviewer` + `sdd-test-automator` 체크리스트 — 콜드 프로세스 성능 단정

> **콜드 프로세스 성능 단정** — 대상 코드가 **매 호출마다 새 프로세스로 기동**되는 부류(훅, CLI,
> pre-commit, 짧은 배치)라면: (a) arch의 성능 예산은 측정 방법을 함께 명시한다 — "콜드 서브프로세스
> 1회 실측 / N회 중위값" 형태로, 인터프리터·패키지 임포트 비용 포함 여부를 적는다. (b) 그 예산에
> 대한 통과 주장은 **콜드 서브프로세스 실측**으로 검증한다. in-process 반복 벤치마크는 임포트
> 비용을 1/N로 희석하므로 증거로 인정하지 않는다. 상시 프로세스의 hot path에는 적용하지 않는다
> (그쪽은 in-process 반복이 옳은 방법).

critic 평가: 배치 중 **가장 강한 일반화** — 기제가 레포 특이성이 아니라 언어 수준 사실
(`sys.modules` 캐싱이 임포트 비용을 1/N로 희석)이고 누락이 정량화됐다(in-process 12.66ms vs
콜드 +43.5ms, 예산 <20ms). 좁힌 두 지점: (i) "모든 arch 성능 목표에 측정 방법 명시"는 체크리스트
인플레이션 — 실패 모드는 매 호출이 새 프로세스인 코드에 한정된다, (ii) "in-process 반복 금지"를
절대 규칙으로 두면 상시 프로세스 hot path에서 틀린다(거기선 in-process가 옳은 방법).

---

## 적용 방법

1. 위 (1)(3)을 `agents/sdd-reviewer.md`·`agents/sdd-test-automator.md`의 체크리스트 절에 추가.
2. (2)를 `agents/sdd-architect-reviewer.md`에 **`## arch 자체 검증 항목`** 헤딩을 신설해 넣는다
   (향후 같은 클래스의 항목이 이 헤딩 아래로 모이도록).
3. 세 파일 모두 protected=False — 사람이 직접 편집하면 된다.
4. 플러그인 버전 patch bump + `plugin.json`/`marketplace.json` 동기화 후 재배포.
