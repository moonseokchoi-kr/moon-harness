# 제안 — 비수렴 실패를 `human_decision_required`로 분기 (report.py 메시지)

**티어**: 하네스 (`hooks/lib/` 결정적 코어) · **자동 적용 없음**
**대상 파일**: `hooks/lib/kompound_snapshot/report.py` (protected=False, tier=HARNESS)
**critic 판정**: **UPHELD** (C6b — 배치 중 유일한 무조건 UPHELD)
**근거 엔트리**: `.harness/LEARNING.md` `## 2026-08-05 — kompound-snapshot / 네이밍 중복 접기 (첫 실전 실행)`
**증거 강도**: 1신호 · `has_cross_project=False`. 단 critic이 **라이브 코드로 직접 확인**했다.

---

## 문제 (critic 라이브 확인)

`hooks/lib/kompound_snapshot/report.py:300-311`이 카탈로그 단계 **모든** 실패에
"…카탈로그 갱신 실패({reason}) → 다음 실행에서 재시도합니다"를 반환한다. 그런데 이번 실전
1회차가 맞은 `bidirectional_count` 실패는 **결정적으로 비수렴**이다 — raw는 이미 커밋됐고
다음 실행은 동일한 이름을 재생성하므로, 사람이 이름 정본을 결정하지 않으면 영구히 같은 결과다.
즉 도달 가능한 상태에서 사람 메시지가 **적극적으로 거짓**이다(부정확한 정도가 아니라).

이 세션의 실제 경과가 그 증거다 — 재시도가 아니라 사람 결정(어느 이름을 정본으로 삼을지)과
코드 수정(`naming.py` 후미 fold)이 있어야 풀렸다.

## 규칙 (프로젝트 티어로 이미 승격 — `docs/lessons-learned.md`)

> 게이트가 올바르게 차단했으나 **입력이 그대로인 채 재시도해도 영구히 같은 결과가 나오는**
> 상태는 retry 카운터를 올리지 말고 `human_decision_required`로 승격 보고한다. 사람 메시지에
> "다음 실행에서 재시도합니다" 류의 수렴 가능성을 시사하는 문구를 쓰지 않고, **무엇을 사람이
> 결정해야 하는가**를 적는다. 재시도로 수렴 가능한 상태(일시적 오류, 외부 의존 실패)와는
> 코드 경로를 분리한다.

## 적용 방법

1. `report.py`의 카탈로그 실패 메시지를 게이트 종류로 분기:
   - `bidirectional_count` 누락/유령 → 비수렴. "사람이 정본 이름을 결정해야 합니다" +
     충돌 목록 + 결정 선택지를 출력. `runtime_status`도 `CATALOG_PENDING`이 아닌
     별도 값(예: `HUMAN_DECISION_REQUIRED`)으로 구분.
   - 일시적 오류(파일 읽기 실패, 커밋 실패) → 기존 재시도 문구 유지.
2. `runtime_state.py`의 `catalog_lag_count` 증가 경로에서 비수렴 케이스를 제외
   (재시도 카운터가 무한 증가하지 않게).
3. 테스트: 두 분기 각각의 human 메시지와 `runtime_status`를 단언.
4. T-1 회귀 안전망(`tests/test_stop_pipeline_characterization.py` +
   `test_hooks_json_contract.py`, 82개)이 고정하는 동작을 건드리지 않는지 확인.
