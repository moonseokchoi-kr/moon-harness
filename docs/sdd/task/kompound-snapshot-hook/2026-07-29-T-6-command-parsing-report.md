# T-6: F2(명령 파싱) + F11 — Bash 명령 파싱 · verdict/리포트 (`wt_target.py` / `report.py`)

## 관련 문서
- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` — F2(§명령 파싱 규칙 언급), F11(조용한 0건 금지)
- arch: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` — §5.2.2(`wt_target` 명령 파싱 규칙 전문 — 패턴 A/B, 경계 표), §6.2(CLI 종료 코드 규약 — 단일 진실), §5.2.3(5분기 제어 흐름), §3.2(모듈 계약 — `wt_target`/`report` 행)

## 구현자
sdd-python-engineer

## 테스트 타입
단위 (순수 함수 — arch §9.1 "순수 함수" 행)

## 완료 조건

### `wt_target.py` (F2 명령 파싱)
- [ ] 명령을 `;` `&&` `||` `|`로 분해해 세그먼트별로 평가한다.
- [ ] **패턴 A**: `git [-C <dir>] worktree remove [--force|-f] <path>` — 플래그가 아닌 마지막 토큰을 경로로 본다. `-C <dir>`이 있으면 상대경로를 그 디렉토리 기준으로 해석.
- [ ] **패턴 B**: `rm` + 재귀 플래그(`-r`/`-R`/`-rf`/`-fr`/`-Rf`/`--recursive`) + 경로 오퍼랜드 1개 이상.
- [ ] 오퍼랜드가 워크트리인지 **이름이 아니라 사실**로 판정: (a) 디렉토리이고 그 안 `.git`이 파일이며 내용이 `gitdir:`로 시작 → 워크트리(최강 신호). (b) (a)가 아니지만 경로에 `worktrees/` 세그먼트가 있고 디렉토리로 존재 → 워크트리 취급(`.git` 이미 삭제된 잔해 케이스). 둘 다 아니면 무개입(빈 리스트 반환).
- [ ] 오퍼랜드 미존재 시 스캔 대상 0건(빈 리스트) 반환.
- [ ] **변수 확장·`eval`은 절대 하지 않는다** — 리터럴 문자열 파싱만.
- [ ] arch §5.2.2 경계 표의 케이스 전부를 pytest로 커버: `rm -rf build/`·`rm -rf node_modules`·`rm -rf ~/.cache`(무개입) / `rm -rf /Users/x/repo/worktrees/foo`(개입) / `git worktree prune`·`git worktree list`(무개입) / `git worktree remove ../already-gone`(통과, 대상 0건) / `rm -rf $WT`·`rm -rf worktrees/*`·`cd <wt> && rm -rf .`·`find -delete`(미탐 — 무개입으로 반환하되 이것이 "알려진 미탐"임을 테스트 docstring에 명시).
- [ ] 함수는 예외를 던지지 않고 항상 `[worktree_path, ...]`(빈 리스트 포함)를 반환한다.

### `report.py` (F11)
- [ ] arch §6.2의 종료 코드 표가 **단일 진실**이며, 이 표를 그대로 코드 상수(verdict ↔ exit_code 매핑)로 구현: `0=ok_no_pending/snapshotted/no_target`, `10=pending`(check 전용), `20=disabled`, `30=scan_error`, `40=precondition_failed`, `45=unmapped_blocking`, `50=verify_failed`, `55=catalog_unparsed`, `60=write_failed`, `70=busy`. `1`·`2`는 코어 verdict로 쓰지 않는다.
- [ ] "변경 없음"(`new`/`updated` 0 & `errors` 없음)과 "스캔 실패"(`errors` 존재)가 **서로 다른 verdict 값**으로 구분된다 — 동일 "0건" 문자열로 뭉뚱그려지면 실패(spec F11 Acceptance).
- [ ] JSON 스키마가 arch §6.2와 정확히 일치하는 키를 갖는다: `verdict`, `exit_code`, `config_source`, `scope_roots`, `anchors`, `raw_stage`(`ok`/`new`/`updated`/`unchanged`/`committed`/`commit`/`error`), `catalog_stage`(`ok`/`attempted`/`registry`/`index`/`log`/`committed`/`commit`/`failed_gates`/`unparsed`/`error`), `unmapped`, `pending`, `dirty`, `errors`, `runtime_status`, `catalog_lag_count`, `inherited_warning`(`{kind, text}` 객체 — 문자열이 아님), `human`.
- [ ] `pending[]`과 `unmapped[]`는 서로 배타적 집합으로 조립된다(F12/§5.1.3 J-11 — naming이 반환한 `unmapped` 신호는 `pending`에 합산되지 않는다).
- [ ] stdout/stderr 분리 계약: `--json` 모드는 stdout에 한 줄 JSON만, 사람이 읽는 리포트는 stderr. 기본(사람) 모드는 stdout에 사람이 읽는 리포트, stderr는 경고만.
- [ ] human 텍스트는 항상 "무엇이 왜 막혔는가 + 수동 절차 + 끄는 방법(`HARNESS_KOMPOUND_REPO` 비우기)" 3요소를 포함한다(차단 케이스에 한함 — 통과 케이스는 해당 없음).
- [ ] 함수는 예외를 던지지 않는다.

## 의존 태스크
T-2 (패키지 스켈레톤)

## 예상 변경 파일
- `hooks/lib/kompound_snapshot/wt_target.py` — 신규
- `hooks/lib/kompound_snapshot/report.py` — 신규
- `tests/test_kompound_snapshot_wt_target.py` — 신규
- `tests/test_kompound_snapshot_report.py` — 신규

## Steps
- [ ] `wt_target.py`: 명령 분해(`;`/`&&`/`||`/`|`) + 패턴 A/B 매칭 + `.git`/`gitdir:`/`worktrees/` 사실 판정
- [ ] `tests/test_kompound_snapshot_wt_target.py` — arch §5.2.2 경계 표 전체를 파라미터화 테스트로 이식
- [ ] `report.py`: verdict↔exit_code 상수 표 + JSON 스키마 조립 함수 + human 텍스트 조립 함수(3요소 포함) + stdout/stderr 라우팅 헬퍼
- [ ] `tests/test_kompound_snapshot_report.py` — 전 verdict 값에 대해 exit_code 매핑 정확성, "변경없음 vs 스캔실패" 구분, `pending`/`unmapped` 배타성, `inherited_warning` 객체 형태 검증
- [ ] `pytest tests/test_kompound_snapshot_wt_target.py tests/test_kompound_snapshot_report.py -v` GREEN 확인

## 검증 명령어
```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_kompound_snapshot_wt_target.py tests/test_kompound_snapshot_report.py -q
```

## 테스트 스코프
`tests/test_kompound_snapshot_wt_target.py` + `tests/test_kompound_snapshot_report.py` — 또는 `pytest tests/ -k "kompound and (wt_target or report)"`
