# T-11: F13 — CLI 통합 (`cli.py`) · 전체 파이프라인 조립 · 정적 검사 완결

## 관련 문서
- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` — F13(전문, stdlib-only 정적 검사 acceptance), F16(정적 검사 — 사용자 절대경로 리터럴 0)
- arch: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` — §6.2(CLI 계약 — 서브커맨드 표, 종료 코드 표, JSON 스키마 — 전부 단일 진실), §5.2.3(`gate` 서브커맨드가 소비하는 verdict/exit 매핑), §4(소유권과 의존 방향 — cli가 config→scan→naming→dedup→apply→registry/wiki_log→verify→git_state 순으로 조립), §3.1(`__init__.py`/`__main__.py`/`cli.py` 파일 역할)

## 구현자
sdd-python-engineer

## 테스트 타입
통합 (`main(argv)` 직접 호출 + 서브프로세스 1세트 — arch §9.1 "CLI 계약" 행) + 계약/정적 검사(F13·F16 acceptance)

## 완료 조건
- [ ] `hooks/lib/kompound_snapshot/cli.py`가 `build_parser()`와 `main(argv=None)`을 노출한다(서브프로세스 없이도 단위 테스트 가능 — `evals/run_eval.py` 관례).
- [ ] 서브커맨드 3종: `check`(read-only, 부작용 없음 — `--scope-root PATH` 반복 가능·`--scope=workspace`·`--json`), `apply`(2단 — `--scope-root`·`--scope=workspace`·`--json`), `gate`(내부적으로 check→apply 조건부 실행 — `--command STR`·`--json`). 하위호환용 `--check` 별칭은 두지 않는다.
- [ ] `check`는 `pending`(exit 10)을 반환할 수 있는 **유일한** 서브커맨드다. `gate`·`apply`는 exit 10을 반환하지 않는다(`pending≥1`이면 자체적으로 apply까지 진행해 `snapshotted`(0) 또는 실패 코드로 수렴).
- [ ] 종료 코드 표(arch §6.2)를 **그대로** 구현: `0`(`ok_no_pending`/`snapshotted`/`no_target`), `10`(`pending`, check 전용), `20`(`disabled`), `30`(`scan_error`, 차단), `40`(`precondition_failed`, 차단), `45`(`unmapped_blocking`, 차단), `50`(`verify_failed`, 통과·경고), `55`(`catalog_unparsed`, 통과·경고), `60`(`write_failed`, 차단), `70`(`busy`, 차단). `1`·`2`는 코어 verdict로 쓰지 않는다.
- [ ] **F9 선행 확인 순서**: `gate` verdict 우선순위가 `no_target` → `disabled` → `scan_error` → `unmapped_blocking` → `no_pending` → `precondition_failed`(F9) → `apply` 실행. F9가 걸리면 `apply`가 호출조차 되지 않음(부작용 0)을 검증하는 테스트가 있다.
- [ ] **`apply` 2단 결과 → verdict 매핑**: 성공/성공=`snapshotted`(0), 성공/F8실패=`verify_failed`(50), 성공/형상미인지=`catalog_unparsed`(55), **실패/미실행=`write_failed`(60)**.
- [ ] `--json` 모드: stdout에 한 줄 JSON(기계 파싱 전용), 사람이 읽는 리포트는 stderr. 기본(사람) 모드: stdout에 사람 리포트, stderr는 경고만.
- [ ] JSON 스키마가 arch §6.2 고정 키와 정확히 일치(`verdict`,`exit_code`,`config_source`,`scope_roots`,`anchors`,`raw_stage{...}`,`catalog_stage{...}`,`unmapped`,`pending`,`dirty`,`errors`,`runtime_status`,`catalog_lag_count`,`inherited_warning{kind,text}`,`human`).
- [ ] `runtime_status`의 값 집합이 T-7 `runtime_state.py`의 6종 상태값과 정확히 동일하다(단일 진실은 `runtime_state`).
- [ ] `gate` 서브커맨드가 판정 **전에** 런타임 상태의 `snapshot.status`를 읽고, 승계 대상(`FAILED`/`GIVEN_UP`=실패 톤, `CATALOG_PENDING`=정보 톤)이면 `inherited_warning`에 담아 출력 후 플래그를 소비(clear)한다. `DONE`/`PENDING`/`SKIPPED_UNCONFIGURED`는 승계하지 않는다.
- [ ] `hooks/`·`hooks/lib/`는 `__init__.py` 없는 implicit namespace package로 유지하고, `kompound_snapshot/__init__.py`는 공개 API를 재노출한다(`self_improve/__init__.py` 관례 — T-2가 만든 최소 스텁을 이 태스크에서 채운다).
- [ ] `hooks/lib/kompound_snapshot/__main__.py`가 `python3 -m hooks.lib.kompound_snapshot <subcommand>` 진입점으로 동작한다.
- [ ] **F13 정적 검사 완결**: `hooks/lib/kompound_snapshot/` 내 모든 `.py`(이제 12개 모듈 전체)에 대해 stdlib 외 import가 없음을 검사하는 테스트(T-2가 뼈대를 만든 `tests/test_kompound_snapshot_static_imports.py`)가 GREEN — 이 태스크에서 전 모듈이 갖춰진 뒤 최종 확인한다(테스트 자체 수정 불필요, 자동 확장).
- [ ] **F16 정적 검사 완결**: 사용자 고유 절대경로 리터럴(`/Users/<user>/...` 패턴) 0건을 검사하는 테스트가 있고, `hooks/lib/kompound_snapshot/` 전체에 대해 GREEN이다(T-3에서 뼈대가 있었다면 재사용, 없었다면 이 태스크에서 추가).
- [ ] `resolve_config()`를 테스트에서 임의의 스캔 루트/kompound 경로/prefix_map으로 오버라이드해 F3~F14 전 파이프라인(scan→naming→dedup→apply→registry/wiki_log→verify→git_state)을 `check`/`apply` 서브커맨드로 실제 실행할 수 있음을 검증하는 통합 테스트가 있다(`fake_kompound_env` 사용).
- [ ] 각 모듈은 예외를 밖으로 던지지 않는다는 계약을 `cli.main()`이 최종 방어선으로 보증한다 — 예상치 못한 예외는 `scan_error`류로 변환되어 반환된다(F13 fail-safe, F11 "조용한 0건 금지"와 무관한 예외를 조용히 0건 처리하지 않음).

## 의존 태스크
T-3(config), T-4(scan/naming/dedup), T-5(git_state), T-6(wt_target/report), T-7(runtime_state), T-8(registry/wiki_log), T-9(verify), T-10(apply) — 전 코어 모듈

## 예상 변경 파일
- `hooks/lib/kompound_snapshot/cli.py` — 신규
- `hooks/lib/kompound_snapshot/__init__.py` — 수정(공개 API 재노출 — T-2가 만든 스텁 채움)
- `hooks/lib/kompound_snapshot/__main__.py` — 신규
- `tests/test_kompound_snapshot_cli.py` — 신규
- `tests/test_kompound_snapshot_static_imports.py` — 수정 없이 재실행(자동 확장 확인만)

## Steps
- [ ] `build_parser()` — 3개 서브커맨드(`check`/`apply`/`gate`) + 공통 옵션(`--scope-root`(반복)/`--scope=workspace`/`--json`/`--command`) 정의
- [ ] `main(argv)` — config→scan→naming→dedup→apply→registry/wiki_log(apply 내부)→verify(apply 내부)→git_state(apply 내부) 파이프라인 조립, verdict/exit_code 매핑(§6.2 표 그대로), stdout/stderr 분리
- [ ] `gate` 서브커맨드 — F9 선행 확인 우선순위 체인 + 승계 노출(`inherited_warning`) 로직
- [ ] `__init__.py` 공개 API 재노출(각 모듈의 주요 함수 re-export)
- [ ] `__main__.py` 엔트리포인트 작성
- [ ] `tests/test_kompound_snapshot_cli.py` 작성 — 종료 코드 표 전체(10개 verdict) × `main(argv)` 직접 호출 + 서브프로세스 1세트(`python3 -m hooks.lib.kompound_snapshot check --json`), F9 우선순위 체인(apply 미호출 mock 검증), 승계 노출 3종 상태, `resolve_config()` 오버라이드로 전체 파이프라인 실행
- [ ] `tests/test_kompound_snapshot_static_imports.py` 및 F16 리터럴 검사 재실행으로 최종 확인
- [ ] `pytest tests/test_kompound_snapshot_cli.py tests/test_kompound_snapshot_static_imports.py -v` GREEN 확인 후 전체 `pytest tests/ -q` 회귀 확인

## 검증 명령어
```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_kompound_snapshot_cli.py -q
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q
```

## 테스트 스코프
`tests/test_kompound_snapshot_cli.py` — 또는 `pytest tests/ -k "kompound"` (이 태스크는 패키지 전체의 최종 통합이므로 전체 kompound 스위트 재확인을 포함한다)
