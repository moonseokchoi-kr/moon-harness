# T-9: F8 — 검증 게이트 3종 (`verify.py`)

## 관련 문서
- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` — F8(검증 게이트 3종 전문)
- arch: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` — §6.3.1(`snapshot_set_rule` — F8 게이트(2)의 전제, 실측 117 vs 122 CRITICAL 대응), §5.2.4(3축 원칙 — 이 게이트 실패는 전부 (ii) 계열, T2 경고 후 통과), §3.2(모듈 계약 — `verify` 행)

## 구현자
sdd-python-engineer

## 테스트 타입
통합 (결함 주입 fixture — arch §9.1 "검증 게이트" 행)

## 완료 조건
- [ ] **`snapshot_set_rule`을 계약으로 구현**: SDD 스냅샷 집합 = `raw/<P>-<feature>-<kind>.md` where `P ∈ prefix_map.values()`(설정 병합 후 유효 프리픽스 집합, `null` 제거) and `kind ∈ {spec,arch,ui,api,context,result}`. 이 규칙을 만족하는 `raw/*.md`만 게이트 (1)(2)(3)의 모집단이다.
- [ ] **게이트 (1) 링크 무결성**: registry가 가리키는 **스냅샷 집합 한정** `../raw/*.md` 링크가 실재 파일을 가리키는지 확인. **검사 범위를 스냅샷 집합으로 한정** — 사람이 `/ingest`한 주제 문서를 가리키는 registry 외부 링크가 깨져도 게이트 (1)은 실패하지 않는다(C-1과 동일 구조 함정 회피, §6.3.1).
- [ ] **게이트 (2) 양방향 카운트 일치**: registry가 가리키는 스냅샷 집합 링크 집합과 `raw/`에서 `snapshot_set_rule`을 만족하는 파일 집합 사이의 **양방향 차집합이 정확히 0**(단순 개수 비교 아님 — 누락 1건 + 유령 링크 1건이 상쇄되어 통과하는 것을 막는다).
- [ ] **게이트 (3) flat 유지**: `raw/` 하위에 `assets/` 외 디렉토리가 생성되지 않았는지 확인.
- [ ] 게이트별 독립 실패 fixture 3종(끊긴 링크 1건 / 카운트 불일치 1건 / `raw/` 하위 서브디렉토리 1건) 각각에 대해 실패를 정확히 보고하는 테스트가 있다(spec F8 Acceptance).
- [ ] **모집단 한정 검증**: 프리픽스 미등록 repo에서 유래한(kind 접미사만 우연히 일치하는) raw 파일을 fixture로 섞어 넣었을 때 모집단 집계에서 **제외**되어 게이트가 여전히 통과함을 검증하는 테스트가 있다(T-2가 `fake_kompound_env`에 이미 심어둔 §6.3.1 경계 케이스를 재사용).
- [ ] **교차 케이스**: "개수는 같고 집합은 어긋나는" 케이스(누락 링크 1건 + 유령 링크 1건을 동시에 주입, 카운트는 동일하나 양방향 차집합은 비지 않음)를 추가해, 단순 개수 비교로는 놓치는 실패를 차집합 검사가 정확히 잡음을 검증한다.
- [ ] 게이트 리포트에 **사용된 프리픽스 목록**을 항상 함께 출력한다(경계가 안 보이면 카운트 불일치를 진단할 수 없다 — §6.3.1 마지막 항목).
- [ ] 3개 게이트 중 하나라도 실패하면 결과가 "실패 게이트명 + 사유"를 구조화된 형태로 반환한다(커밋 여부 판단은 이 모듈 책임이 아니다 — T-10 apply.py가 이 결과를 보고 (ii) 롤백을 결정한다. 이 모듈은 read-only 판정만).
- [ ] 박제 0건(신규/갱신 없음) 케이스에서 3개 게이트 함수가 **호출되지 않음**(mock call count 0)을 검증하는 테스트가 있다 — 단, 이 "호출 안 함" 판단 자체는 T-10(apply.py)의 오케스트레이션 책임이므로, 이 태스크에서는 verify 모듈이 "게이트 실행" 함수와 "실행 여부 판단"을 분리된 함수로 제공해 T-10이 스킵을 결정할 수 있게 한다.
- [ ] 예외를 던지지 않고 `[{"gate","ok","detail"}, ...]` 리스트를 반환한다(F13 fail-safe, read-only).

## 의존 태스크
T-3 (config — `prefix_map` 병합 결과), T-4 (naming — kind 접미사 규칙, raw 파일명 규약)

## 예상 변경 파일
- `hooks/lib/kompound_snapshot/verify.py` — 신규
- `tests/test_kompound_snapshot_verify.py` — 신규

## Steps
- [ ] `snapshot_set_rule` 구현 — `prefix_map.values()`(null 제외) ∩ kind 접미사 6종으로 raw 파일 모집단 필터링 함수
- [ ] 게이트 (1) 구현 — registry 파싱(또는 T-8 registry 모듈의 표 탐색 결과 재사용/공유 헬퍼) → 스냅샷 집합 한정 링크 추출 → 파일 존재 확인
- [ ] 게이트 (2) 구현 — registry 링크 집합 vs raw 모집단 집합의 양방향 차집합 계산
- [ ] 게이트 (3) 구현 — `raw/` 직속 자식 중 `assets/` 외 디렉토리 존재 검사
- [ ] 프리픽스 목록을 리포트에 포함하는 조립 함수
- [ ] `tests/test_kompound_snapshot_verify.py` 작성 — 게이트별 독립 실패 3종 + 모집단 한정(미등록 프리픽스 raw 섞기) + 교차 케이스(누락+유령 동시) + 3게이트 전부 통과 정상 케이스 + 사용 프리픽스 목록 포함 확인
- [ ] `pytest tests/test_kompound_snapshot_verify.py -v` GREEN 확인

## 검증 명령어
```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_kompound_snapshot_verify.py -q
```

## 테스트 스코프
`tests/test_kompound_snapshot_verify.py` — 또는 `pytest tests/ -k "kompound and verify"`
