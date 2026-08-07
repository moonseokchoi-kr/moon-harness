# 제안 — retro 커서 마커 형식 불일치 (문서 스키마 ↔ cursor.py)

> ✅ **적용 완료 (2026-08-06, 사용자 승인)** — C3a 정규화 + `marker_resolves()` 신설
> (`hooks/lib/self_improve/cursor.py`), C3b `marker_resolved`/`warning`
> (`cursor_runner.py`, protected), C3c 스키마 예시 + Phase A 3항 미해석 검사
> (`skills/self-improve/SKILL.md`, protected), C3d 회귀 13건. 라이브 검증: 접두형
> 마커가 14건→1건으로 정상 해석, 미해석 마커는 경고 + fail-safe 전량 유지.

**티어**: 하네스 · **자동 적용 없음**
**우선순위**: **최상** — self-improve 루프가 자기 커서를 신뢰할 수 없는 상태다.
**critic 판정**: **UPHELD** (이번 배치 유일)
**근거**: 이 회고(2026-08-06 retro #2) Phase A에서 라이브 발견. LEARNING 엔트리는 회고 종료 후 append.

**대상 파일 (protected 여부 — `guard.is_protected()` 실측)**

| 파일 | protected | 역할 |
|---|---|---|
| `hooks/lib/self_improve/cursor.py` | **False** | 비교 로직 (정규화 지점) |
| `skills/self-improve/SKILL.md:61` | **True** | 잘못된 스키마 예시 |
| `skills/self-improve/scripts/cursor_runner.py` | **True** | 관측성 추가 지점 (C3b) |
| `tests/fixtures/retro_state_v1.json:3`, `tests/test_state_io.py:269-271` | False | 접두형을 인코딩한 픽스처/테스트 |

> 📌 critic은 `cursor_runner.py`를 "protected 아님"으로 적었으나 **오류**다 — protected 집합이
> `skills/self-improve/`를 접두로 포함하므로 `is_protected()`가 `True`를 반환한다(실측 확인).
> 즉 이 제안은 protected 파일 **2개**를 건드린다. 사람 승인이 반드시 필요하다.

---

## 결함

`hooks/lib/self_improve/cursor.py`의 `get_new_entries`가 `entry["marker"] == last_marker`로
**완전일치** 비교를 한다. 그런데 `parser.py`가 만드는 `marker`에는 `## ` 접두가 **없다**.
반면 `skills/self-improve/SKILL.md:61`이 문서화한 `retro-state.json` 스키마 예시는

```json
"last_processed_marker": "## 2026-06-10 — auth-flow / T-03",
```

처럼 접두가 **있다**. 문서를 따라 적은 마커는 절대 매칭되지 않고, `cursor.py`의 fail-safe
("미발견 → 전체 반환, 누락보다 재처리가 낫다")가 발동해 **매 실행이 전체 파일을 재처리**한다.
에러도 경고도 없다.

**라이브 증거**: 1회차 회고가 접두형으로 저장했고(`.harness/retro-state.json`),
이번 회고 Phase A에서 커서가 **13/13건**을 "신규"로 반환했다. 같은 마커에서 `## `만 떼면 **1건**.
즉 커서가 한 번도 전진하지 않았다.

**저장소 내 형식이 이미 갈라져 있다** — 접두형: `SKILL.md:61`,
`docs/sdd/spec/2026-06-16-self-improving-harness.md:418`, `tests/fixtures/retro_state_v1.json:3`,
`tests/test_state_io.py:269-271` / 비접두형: `tests/test_self_improve_scripts.py:100`,
`tests/test_cursor.py` 전체.

## 심각도 (critic 교정 반영 — 원안보다 낮게 기록)

"이미 처리한 교훈을 재적용한다"는 **과장**이다. Phase C의 중복 사전검사가 실제 재적용을 막는다
(이번 라운드도 `duplicate=False`가 정상 판정됐다). 실제 피해는:

1. "신규 N건" 보고가 **거짓**이다.
2. 처리분 재triage 비용.
3. **이미 REFUTED된 후보의 재제안 위험** — 1회차 폐기 목록의 항목(예: 이미 수정된
   프리필터 대소문자 버그)이 다시 사람 승인 큐로 올라간다.

## 수정 방향 (critic 권고 = 정규화 채택)

문서만 고치면 안 되는 이유: (1) 이미 저장된 `.harness/retro-state.json`이 깨진 상태로 남아
별도 마이그레이션이 필요하다. (2) LEARNING.md 헤더가 눈에 `## 2026-…`로 보이므로 사람·에이전트가
손으로 마커를 적을 때 접두형을 다시 쓰는 것이 **자연스러운 실수**다(1회차 회고가 정확히 그랬다).

### C3a — 비교 시점 정규화 (`cursor.py`, 비protected)

선행 `#`와 공백을 양쪽에서 제거한 뒤 비교한다. 멱등이며 서로 다른 마커를 병합시킬 수 없다
(마커 본문이 `#`로 시작하는 H2는 실재하지 않는다).

**단, 정규화는 비교 시점에만 적용하고 저장 형식은 파서 산출 형식(비접두)으로 통일한다** —
두 형식을 다 저장 가능하게 두면 2차 진실원이 된다.

### C3b — 관측성 (`cursor_runner.py`, **protected**)

반환 dict에 `marker_resolved: bool`을 추가한다. `last_marker`가 비어 있지 않은데 매칭에
실패하면 `False` + 경고 문자열을 채우고, SKILL Phase A 3항이 그 값을 읽어
**"커서 미해석 — 전체 재처리 중"으로 보고**하게 한다. 이 관측성이 없으면 같은 계열 결함이
다시 조용히 재발한다.

`cursor.py`는 순수 리스트 반환 계약(arch:106 "무수정")을 유지하므로 반환형을 바꾸지 않는다.

### C3c — 문서 (`SKILL.md:61`, **protected**)

스키마 예시의 `## ` 접두를 제거하고, "마커는 파서 산출 형식(헤딩 마크 없음)으로 저장한다"를
한 줄 명시한다. `docs/sdd/spec/2026-06-16-self-improving-harness.md:418`은 완료된 사이클
산출물이므로 소급 수정하지 않는다.

### C3d — 테스트

- 접두형/비접두형 마커가 **동일한 결과**를 내는지 단언하는 회귀 테스트.
- `marker_resolved=False` 경로 단언.
- 기존 `tests/fixtures/retro_state_v1.json`(접두형)과 `tests/test_state_io.py:269-271`은
  정규화 후에도 통과해야 한다 — 이 두 곳이 접두형을 인코딩하므로 정규화가 옳은 방향임을
  역으로 뒷받침한다.

## fail-safe 방향은 그대로 유지

"미발견 → 전체 반환"을 뒤집으면 pruned/stale 마커가 교훈을 **영구 누락**시킨다. 지금 방향이
옳다. 문제는 방향이 아니라 **무관측성**이며 C3b가 그것을 메운다.

## 이번 회고의 임시 조치 (이미 적용됨)

`.harness/retro-state.json`의 마커를 비접두형으로 교체해 **이 repo의 커서는 지금 정상 동작**한다
(교체 후 신규 0건 확인). 이는 프로젝트 티어 상태 파일 수정이며, 위 하네스 수정을 대체하지 않는다 —
다른 클론·다른 프로젝트에서는 여전히 문서 스키마를 따라 접두형을 쓰게 된다.
