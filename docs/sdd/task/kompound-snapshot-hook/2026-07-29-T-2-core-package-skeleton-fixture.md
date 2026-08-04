# T-2: 코어 패키지 뼈대 + 공용 오프라인 fixture (`fake_kompound_env`)

## 관련 문서
- spec: `docs/sdd/spec/2026-07-29-kompound-snapshot-hook.md` — F13 "오프라인 테스트용 fixture 구조" 절(§F13 마지막 블록)
- arch: `docs/sdd/design/arch/2026-07-29-kompound-snapshot-hook.md` — §3.1(디렉토리 경계), §9.3(공용 fixture)

## 구현자
sdd-python-engineer

## 테스트 타입
단위 + 통합(fixture 자체가 골든 텍스트/디렉토리 구조를 검증 가능해야 함)

## 완료 조건
- [ ] `hooks/lib/kompound_snapshot/` 패키지 디렉토리가 존재하고 `__init__.py`(최소 — 패키지 docstring만, 공개 API 재노출은 T-11에서 채움)가 있다. `hooks/`·`hooks/lib/`는 기존과 동일하게 implicit namespace package로 두고(`__init__.py` 없음 유지), `kompound_snapshot/`에만 `__init__.py`를 둔다(`self_improve/` 관례 동일).
- [ ] `tests/conftest.py`에 `fake_kompound_env(tmp_path)` fixture가 **정확히 1곳**에 정의되어 있고, 이후 모든 F3·F5·F6·F7·F8·F9·F11·F12·F16 테스트가 이를 재사용한다(중복 fixture 정의 없음 — grep으로 `def fake_kompound_env` 1회 등장 확인 가능).
- [ ] fixture가 반환하는 구조가 spec F13 명세와 정확히 일치한다: `{"kompound": Path, "workspace": Path, "config": dict}`.
- [ ] `<tmp>/fake_kompound/`가 `git init` + 초기 커밋되어 있고 `raw/`, `wiki/sdd-spec-registry.md`, `wiki/index.md`, `wiki/log.md`가 존재한다. registry는 **heterogeneous 3형상**(7열 (a) · 6열 (b) · 8열 통합표 (c))을 축약 재현하고, §6.3.3의 갱신 대상 카운트 문장 2종 + 날짜 박힌 불변 문장 1종 이상을 포함한다.
- [ ] `fake_kompound/raw/`에 §6.3.1 경계 케이스(프리픽스 미등록이면서 kind 접미사로 끝나는 파일, 실측 5건의 축약판 중 최소 1건)가 심어져 있다.
- [ ] `<tmp>/fake_workspace/<repo>/docs/sdd/{spec,design/arch,result}/`와 `<repo>/worktrees/<wt>/docs/sdd/spec/`(워크트리 전용 문서 케이스) 트리가 생성된다.
- [ ] fixture가 F9(dirty/diverge)와 F8(검증 게이트) 케이스도 동일 fixture 위에서 시뮬레이션 가능함을 보이는 스모크 테스트가 있다(예: fixture 반환 직후 `git status --porcelain`이 비어있음(clean) 확인).
- [ ] fixture는 `resolve_config()`(T-3에서 구현) 오버라이드 지점에 주입 가능한 `config` dict(스캔 루트=`fake_workspace`, kompound_repo=`fake_kompound`, `prefix_map` 등)를 반환한다 — T-3 완료 전이므로 이 dict는 config.py의 최종 스키마(§6.1 JSON 스키마)를 **미리 계약으로 고정**해 T-3가 그 계약에 맞춰 구현하도록 한다.
- [ ] 정적 검사 테스트(F13 acceptance) 뼈대: `hooks/lib/kompound_snapshot/` 내 모든 `.py`의 `import` 문에 stdlib 외 모듈이 없음을 ast로 검사하는 테스트가 존재한다(이 시점엔 `__init__.py`만 있어 자명하게 통과 — 이후 모듈이 추가될 때마다 이 테스트가 자동으로 커버 범위를 넓힌다).
- [ ] `PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q`가 여전히 전부 GREEN(fixture 추가만으로는 기존 테스트에 영향 없음).

## 의존 태스크
없음 (Wave 0, T-1과 병렬 — 파일 겹침 없음: T-1은 `stop-pipeline.py`/`hooks.json`을 읽고 새 테스트 파일만 추가, 이 태스크는 `tests/conftest.py`와 신규 패키지만 건드림)

**후속 관계**: T-3~T-11(코어 패키지 전 모듈)이 이 태스크의 `fake_kompound_env` fixture와 패키지 스켈레톤에 의존한다.

## 예상 변경 파일
- `hooks/lib/kompound_snapshot/__init__.py` — 신규(최소)
- `tests/conftest.py` — 수정(`fake_kompound_env` fixture 추가, 기존 fixture는 무변경)
- `tests/fixtures/` 하위 — registry/index/log 골든 텍스트 조각(필요 시)
- `tests/test_kompound_snapshot_static_imports.py` — 신규(stdlib-only 정적 검사 뼈대, 이후 태스크들이 이 파일에 항목을 추가하지 않고 이 파일이 패키지 전체를 스캔하므로 자동 확장됨)

## Steps
- [ ] `hooks/lib/kompound_snapshot/__init__.py` 생성(패키지 docstring만)
- [ ] `tests/conftest.py`에 `fake_kompound_env(tmp_path)` fixture 작성 — kompound git repo 초기화 + registry 3형상 골든 텍스트 + raw 시드 파일(§6.3.1 경계 케이스 포함) + workspace 트리 생성
- [ ] fixture 반환 dict 스키마(`kompound`/`workspace`/`config`) 확정 및 docstring에 명시(다른 태스크가 계약으로 참조)
- [ ] fixture 스모크 테스트 1개 작성(구조가 기대대로 생성됐는지, git이 clean한지)
- [ ] `tests/test_kompound_snapshot_static_imports.py` 작성 — `ast.parse`로 `hooks/lib/kompound_snapshot/*.py`의 `import`/`from import` 노드 전수 검사, stdlib 모듈 집합(`sys.stdlib_module_names` 또는 하드코딩 화이트리스트) 밖이면 실패
- [ ] `pytest tests/ -q`로 회귀 없음 확인

## 검증 명령어
```bash
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/test_kompound_snapshot_static_imports.py -q
PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q
```

## 테스트 스코프
`tests/conftest.py`(fixture 자체, 다른 파일의 테스트에서 간접 검증) + `tests/test_kompound_snapshot_static_imports.py`
