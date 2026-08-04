# T-10: F6 — 멱등 적용 + (i)/(ii) 커밋 경계 · 트랜잭션 저널 (`apply.py`)

## 관련 문서
- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` — F6(멱등성 전문)
- arch: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` — §6.3.0(`apply` 2단 분리와 커밋 경계 — A-5 핵심), §6.3(F6/F7/F10 쓰기 형태 규율, 트랜잭션 저널+부분 롤백), §5.2.4(3축 원칙과의 정합), §10.2 T-c(트레이드오프 — (ii)만 롤백+raw 커밋으로 조정된 경위)

## 구현자
sdd-python-engineer

## 테스트 타입
통합 (`fake_kompound_env` — arch §9.1 "멱등 적용" 행, "카탈로그 재시도" 행)

## 완료 조건
- [ ] **(i) raw 복사 단계**: canonical 문서를 `raw/<project>-<feature>-<kind>.md`로 verbatim 복사. 없으면 신규(카운트 증가) / 같으면(md5 동일) 무동작·무로그(카운트 0) / 다르면 덮어쓰기(갱신 카운트 증가) — F6 그대로.
- [ ] (i) 성공 시 **즉시 raw만 커밋**(T-5 `git_state.py`의 raw 전용 커밋 함수 호출, 메시지 `snapshot(raw): N new, M updated`).
- [ ] (i) 실패 시(`write_failed`) 저널로 **전량 롤백**하고 커밋하지 않는다.
- [ ] **(ii) 카탈로그 갱신 단계**: T-8의 `registry.py`(표 갱신 3단·열 추가·카운트 화이트리스트) + `wiki_log.py`(index prepend·log append)를 호출해 새 텍스트를 만들고 write → T-9의 `verify.py` 게이트 3종 실행 → 통과 시에만 **카탈로그 커밋**(T-5의 카탈로그 전용 커밋 함수, 메시지 `snapshot(catalog): ...`).
- [ ] (ii) 실패(F8 게이트 실패 `verify_failed` 또는 `catalog_unparsed`) 시 **(ii) 저널만 롤백**하고 **(i)은 그대로 유지·커밋된 상태로 남긴다**. 워킹트리는 커밋 경계 덕에 clean 유지(F9 자기 오염 없음).
- [ ] **트랜잭션 저널**: 쓰기 전에 (경로, 존재여부, 원본 바이트) 저널을 (i)/(ii) **단계별로 독립** 생성. 롤백은 해당 단계의 저널만 되돌린다.
- [ ] **핵심 케이스(arch §9.1 명시)**: (ii) 실패 시 raw가 롤백되지 않고 이미 커밋되어 있으며 워킹트리가 clean함을 검증하는 테스트가 있다.
- [ ] **재시도 이어짐**: (ii) 실패 후 다음 실행에서 (i)은 F6 멱등에 의해 `unchanged` 무동작이고 (ii)만 재시도됨을 2회 실행 시뮬레이션으로 검증한다.
- [ ] 동일 스캔을 연속 2회 실행했을 때 두 번째 실행에서 "신규"/"갱신" 카운트가 모두 0이고 kompound `git status --porcelain -- raw/`가 빈 문자열임을 확인하는 테스트가 있다(spec F6 Acceptance).
- [ ] **박제 0건 처리(F7 연동)**: 이번 실행에서 박제된 raw가 0건이면 registry/index/log 갱신과 F8 게이트 3종 실행을 **모두 스킵**하고 "변경 없음"으로 보고한다(스킵은 실패가 아니라 정상 종료). T-9의 verify 게이트 함수가 이 케이스에서 호출되지 않음(mock call count 0)을 검증한다.
- [ ] **F7 "배치 1건=로그 1줄"과 카탈로그 재시도 시나리오 결과 필드**: 결과 dict는 raw 커밋 sha 리스트(누적 가능)와 카탈로그 커밋 sha를 별도로 담아 T-8의 `wiki_log.py` 문자열 조립 함수에 그대로 전달할 수 있어야 한다.
- [ ] 결과 스키마가 arch §6.2의 `raw_stage`/`catalog_stage` 두 독립 필드로 구성된다(`raw_stage.ok=true` + `catalog_stage.ok=false`가 "문서는 보존, 카탈로그만 뒤처짐"을 표현하는 유일한 방법 — 단일 `ok`로 합치지 않는다).
- [ ] 배타 락(T-5 `git_state.py`)을 획득한 채로 (i)(ii) 전체를 수행하고, 종료 시(성공/실패 무관) 반드시 해제한다.
- [ ] 모든 단계가 예외를 밖으로 던지지 않는다(F13 fail-safe).

## 의존 태스크
T-4 (scan/naming/dedup — canonical 문서 리스트 입력), T-5 (git_state — 커밋/락), T-8 (registry/wiki_log — (ii) 텍스트 변환), T-9 (verify — (ii) 게이트)

## 예상 변경 파일
- `hooks/lib/kompound_snapshot/apply.py` — 신규
- `tests/test_kompound_snapshot_apply.py` — 신규

## Steps
- [ ] (i) raw 복사 로직 + 저널 생성 + `git_state` raw 커밋 호출 배선
- [ ] (i) 실패 시 전량 롤백 경로 구현
- [ ] (ii) 카탈로그 텍스트 생성(`registry.py`+`wiki_log.py` 호출) + write + `verify.py` 게이트 실행 + 통과 시 카탈로그 커밋 배선
- [ ] (ii) 실패 시 (ii) 저널만 롤백(raw 유지) 경로 구현
- [ ] 박제 0건 스킵 경로(registry/wiki_log/verify 미호출) 구현
- [ ] 배타 락 획득/해제를 감싸는 최상위 `apply()` 함수 조립 + `raw_stage`/`catalog_stage` 결과 스키마 조립
- [ ] `tests/test_kompound_snapshot_apply.py` 작성 — (i)(ii) 모두 성공 / (i) 실패 롤백 / (ii)만 실패(raw 유지+clean+카탈로그만 롤백) / 2회 실행 멱등(0건 카운트 재확인) / (ii) 실패 후 재시도로 이어짐(raw unchanged + catalog 성공) / 박제 0건 스킵(verify mock call 0) / 락 해제 보장(예외 발생 경로 포함)
- [ ] `pytest tests/test_kompound_snapshot_apply.py -v` GREEN 확인

## 검증 명령어
```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_kompound_snapshot_apply.py -q
```

## 테스트 스코프
`tests/test_kompound_snapshot_apply.py` — 또는 `pytest tests/ -k "kompound and apply"`
