# cross-project-learning-aggregation Spec

## 개요

- **한줄 요약:** self-improve의 하네스-티어 승격 게이트가 구조적으로 항상 False가 되는 근본 원인(로컬 LEARNING.md 단독 읽기)을 해소하기 위해, 외부 교차-repo 집계 store를 함께 읽어 단일 entries 리스트로 합치는 I/O 집계 로더를 추가한다.
- **타겟 사용자:** moon-harness self-improve 루프를 통해 하네스 플러그인 자체를 개선하려는 개발자
- **핵심 가치:** "로컬 repo 한 곳만 봐서는 `has_cross_project`가 영구 False" — 교차-repo 집계 배선을 통해 하네스-티어 승격 게이트가 실제로 열릴 수 있게 한다. 단, 배선만 추가하고 판정 로직(recurrence.py, parser.py)은 무수정을 유지한다.

---

## 플랫폼 / 스택 (SIMPLE 모드 판정)

| 항목 | 값 |
|------|----|
| 모드 | **SIMPLE** — UI 없음, REST API 계약 없음 |
| SIMPLE 판정 근거 | 산출물은 Python stdlib 모듈 1개(`learning_source.py`) + SKILL.md Phase B 텍스트 수정. 외부 사용자 인터페이스·API 엔드포인트 없음. 오프라인 pytest로 전량 검증 가능 |
| 언어/런타임 | Python 3 (stdlib only — json, pathlib, os) |
| 테스트 | pytest, 결정적·오프라인 (LLM/네트워크 무호출) |
| 외부 의존 | 없음 (marvelous_kompound는 로컬 경로로 접근, 네트워크 미사용) |
| 상태 파일 | `.harness/config.json` (읽기 전용 — 경로 설정 소비) |
| 변경 대상 | `hooks/lib/self_improve/learning_source.py` (신규), `skills/self-improve/SKILL.md` (Phase B 절차 수정) |
| 무수정 대상 (protected) | `hooks/lib/self_improve/recurrence.py`, `hooks/lib/self_improve/parser.py`, `hooks/lib/self_improve/state_io.py`, 및 모든 기타 hooks/lib/self_improve/*.py |

---

## 사용자 요구사항 원문 → 기능 매핑

| # | 사용자 요구 원문 | 기능 |
|---|----------------|------|
| R1 | "self-improve의 하네스-티어 승격(spec F16)은 `has_cross_project`(≥2 distinct provenance_repo)가 True여야 열린다" | F1, F3 |
| R2 | "`.harness/LEARNING.md`는 repo 스코프 전용이고, self-improve는 한 repo 안에서 자기 repo의 LEARNING.md만 읽는다 → distinct provenance_repo가 항상 1 → `has_cross_project`가 구조적으로 항상 False → 하네스-티어 승격 영구 봉인" | F1, F2 |
| R3 | "사용자가 이미 교차-repo 집계 store를 외부에 구축: marvelous_kompound repo의 `harness-learning/<repo-id>.md` 파일들. 각 파일은 moon-harness parser.py 계약(`## marker` H2 + `<!-- tags: ... -->`)을 따른다" | F2, F4 |
| R4 | "남은 일 = self-improve가 로컬 LEARNING.md만이 아니라 이 외부 집계도 함께 읽도록 '배선'" | F1, F2 |
| R5 | "신규 I/O 집계 로더 추가: 로컬 `.harness/LEARNING.md` + 교차-repo store 디렉터리의 `*.md`를 읽어 `parse_learning_entry`로 파싱·합쳐 단일 entries 리스트 반환. 경로는 인자로 주입" | F2 |
| R6 | "store 경로는 하드코딩 금지 → `.harness/config.json`의 `cross_project_store` 키에서 읽음(`state_io.load_state` 사용). 키/파일 없으면 로컬-only로 graceful degradation(fail-safe, 기존 동작 보존)" | F3 |
| R7 | "recurrence.py / parser.py 무수정. 합쳐진 entries를 기존 `count_signals`에 넘기면 provenance 태그 덕에 distinct repo가 자연 집계됨" | NFR-1 |
| R8 | "SKILL 배선: `skills/self-improve/SKILL.md` Phase B(클러스터링 시 count_signals 호출하는 부분)를 '로컬 LEARNING.md만 읽기' → '신규 로더로 합쳐 읽기'로 갱신" | F4 |
| R9 | "stdlib-only, 네트워크/LLM 무호출, 모든 함수 fail-safe(raise 금지, None/빈 리스트 반환), 경로 호출자 주입(하드코딩 0)" | NFR-2 |

---

## 기능 요구사항

### F1: 교차-repo entries 집계로 `has_cross_project` 게이트 해소

WHEN self-improve Phase B(클러스터링·진단)가 실행될 때 THE SYSTEM SHALL 로컬 `.harness/LEARNING.md`의 entries와 외부 교차-repo store의 entries를 합쳐 단일 리스트로 구성한 뒤 `count_signals`에 전달함으로써, 서로 다른 repo에서 온 entries의 `provenance_repo` 태그가 `cross_repo_set`에 누적되어 `has_cross_project`가 `True`로 평가될 수 있도록 한다.

WHILE 교차-repo store가 설정되지 않은 경우(config 없음 또는 키 없음) THE SYSTEM SHALL 로컬 entries만으로 기존과 동일하게 동작하며, `has_cross_project` 결과는 외부 store 없이 로컬 데이터만 반영한다.

- **Acceptance:**
  - 로컬 LEARNING.md에 `provenance_repo=moon-harness` 엔트리 1건, 외부 store에 동일 `domain=test-adequacy`이고 `provenance_repo=Marvelous` 엔트리 1건이 존재할 때, 합쳐진 entries로 `count_signals`를 호출하면 `has_cross_project(counter, "test-adequacy") == True`이다.
  - config 파일이 없거나 `cross_project_store` 키가 없는 경우, `count_signals` 호출 결과가 로컬 entries만 반영한 결과와 동일하다 (로컬-only 동작 보존).

---

### F2: I/O 집계 로더 (`learning_source.py`)

THE SYSTEM SHALL `hooks/lib/self_improve/learning_source.py` 모듈을 신규 생성하고, 다음 두 경로를 입력받아 합쳐진 entries 리스트를 반환하는 함수를 제공한다:
- `local_learning_path`: 로컬 `.harness/LEARNING.md` 파일 경로
- `store_dir`: 교차-repo store 디렉터리 경로 (없으면 `None`)

WHEN `local_learning_path`가 존재하고 읽기 가능할 때 THE SYSTEM SHALL 해당 파일 텍스트를 `parse_learning_entry`로 파싱하여 entries 리스트에 포함한다.

IF `local_learning_path`가 존재하지 않거나 읽기 실패할 때 THEN THE SYSTEM SHALL raise 없이 로컬 entries를 빈 리스트로 처리하고 계속 진행한다.

WHEN `store_dir`가 지정되어 있고 디렉터리로 접근 가능할 때 THE SYSTEM SHALL 해당 디렉터리 안의 `*.md` 파일을 열거하여 각각 `parse_learning_entry`로 파싱하고, 파싱된 entries를 로컬 entries 뒤에 이어붙인다.

IF `store_dir`가 존재하지 않거나 디렉터리가 아니거나 열거 중 오류가 발생할 때 THEN THE SYSTEM SHALL raise 없이 해당 파일을 건너뛰고, 로컬 entries만으로 구성된 리스트를 반환한다.

IF 개별 store `*.md` 파일 파싱 중 오류가 발생할 때 THEN THE SYSTEM SHALL 해당 파일을 건너뛰고 나머지를 계속 처리한다 (부분 실패가 전체를 차단하지 않는다).

THE SYSTEM SHALL 모든 경로를 함수 인자로만 받고, 모듈 내부에 특정 경로를 하드코딩하지 않는다.

THE SYSTEM SHALL stdlib(json, pathlib, os)만 사용하며, 네트워크 호출 및 LLM 호출을 수행하지 않는다.

- **Acceptance:**
  - 로컬 파일 1건 + store 디렉터리에 `*.md` 2건이 있을 때, 반환 entries 수가 세 파일의 파싱 결과 합과 같다.
  - store 디렉터리 경로가 존재하지 않는 임의 경로일 때 raise 없이 로컬 entries만 반환된다.
  - 잘못된 마크다운(H2 헤더 없는 파일)이 store에 포함되어 있어도 빈 리스트로 건너뛰고 나머지를 처리한다.
  - pytest에서 네트워크·LLM 없이 전량 통과한다.

---

### F3: config 기반 경로 주입 (`.harness/config.json`)

WHEN self-improve 루프가 집계 로더를 호출하기 전에 THE SYSTEM SHALL `state_io.load_state(".harness/config.json")`로 설정을 읽고, 반환된 dict에서 `cross_project_store` 키의 값을 `store_dir` 인자로 사용한다.

IF `.harness/config.json` 파일이 없을 때 THEN THE SYSTEM SHALL `store_dir=None`으로 처리하여 로컬-only 동작을 유지한다 (에러 보고 없이 graceful degradation).

IF `.harness/config.json`이 존재하지만 `cross_project_store` 키가 없거나 값이 `null`·빈 문자열일 때 THEN THE SYSTEM SHALL `store_dir=None`으로 처리한다.

THE SYSTEM SHALL `cross_project_store` 경로를 절대 경로 또는 호출자가 해석 가능한 경로로 간주하며, 경로 해석을 위한 하드코딩된 기준 디렉터리를 모듈 내부에 두지 않는다.

- **Acceptance:**
  - `.harness/config.json` 파일이 없는 환경에서 self-improve가 raise 없이 로컬 entries만으로 Phase B를 실행한다.
  - `.harness/config.json`에 `{"cross_project_store": "/some/path"}` 가 있을 때, 해당 경로가 `store_dir`로 F2 로더에 전달된다.
  - `state_io.load_state` 실패(파일 파싱 오류 등) 시 None이 반환되므로, F3 로직은 그것을 config 없음으로 처리하여 로컬-only로 진행한다.

---

### F4: SKILL.md Phase B 배선 갱신

WHEN `skills/self-improve/SKILL.md`의 Phase B(진단·클러스터 단계) 절차 설명에서 entries 수집 출처를 기술하는 부분이 "`.harness/LEARNING.md`만"으로 한정되어 있을 때 THE SYSTEM SHALL 해당 서술을 "집계 로더(`learning_source.py`)를 통해 로컬 LEARNING.md + 교차-repo store entries를 합쳐 읽기"로 갱신한다.

THE SYSTEM SHALL Phase B의 `count_signals()` 호출 지점에 대한 설명이 합쳐진 entries를 입력으로 사용함을 명시하도록 갱신한다.

THE SYSTEM SHALL Phase B에서 `store_dir` 미설정(config 없음) 시 로컬-only 동작이 기존과 동일함을 설명에 명시한다.

- **Acceptance:**
  - 갱신된 SKILL.md의 Phase B에 "집계 로더" 또는 동등한 표현과 `learning_source.py` 참조가 포함된다.
  - SKILL.md의 다른 Phase(A, C, D) 절차는 변경되지 않는다.
  - protected set(self-improve 스킬 자체)에 대한 수정은 SKILL.md 절차 텍스트에 국한되며, 결정적 로직 파일(recurrence.py, parser.py 등)을 변경하는 내용이 포함되지 않는다.

---

## 용어 정의

| 용어 | 정의 |
|------|------|
| 집계 로더 | `learning_source.py`가 제공하는 함수. 로컬 LEARNING.md와 교차-repo store `*.md`를 읽어 단일 entries 리스트로 반환한다 |
| 교차-repo store | 여러 repo의 LEARNING.md 내용을 `<repo-id>.md` 파일로 보관하는 외부 디렉터리. parser.py 계약(`## marker` H2 + `<!-- tags: ... -->`)을 따른다 |
| `cross_project_store` | `.harness/config.json`의 키. 교차-repo store 디렉터리 경로를 담는다. 없으면 로컬-only 동작 |
| graceful degradation | config/store 미설정·접근 실패 시 raise 없이 로컬 entries만으로 동작을 유지하는 fail-safe 원칙 |
| 로컬-only 동작 | `store_dir=None`일 때의 동작. 기존 self-improve가 LEARNING.md만 읽던 방식과 동일하며, 하위호환이 보장된다 |
| protected set | `recurrence.py`, `parser.py`, `state_io.py` 및 기타 `hooks/lib/self_improve/*.py` 전체. 이번 기능에서 무수정 불변 대상 |

---

## 비기능 요구사항

### NFR-1: protected set 무수정 불변식

THE SYSTEM SHALL `hooks/lib/self_improve/recurrence.py`, `hooks/lib/self_improve/parser.py`, `hooks/lib/self_improve/state_io.py`, 및 `hooks/lib/self_improve/` 아래 기존 모든 파일을 수정하지 않는다.

THE SYSTEM SHALL 합쳐진 entries를 기존 `count_signals(entries)` 함수에 그대로 전달하며, 해당 함수의 시그니처·동작·반환 타입을 변경하지 않는다.

THE SYSTEM SHALL `extract_provenance(entry)`, `parse_learning_entry(text)` 함수를 수정하지 않고 그대로 호출한다.

- **Acceptance:** 이번 기능 구현 후 `hooks/lib/self_improve/` 디렉터리의 기존 파일들에 대한 git diff가 없다.

### NFR-2: stdlib-only · fail-safe · 하드코딩 금지

THE SYSTEM SHALL `learning_source.py`가 Python 표준 라이브러리(json, pathlib, os, typing 등)만 사용하고, 외부 패키지·네트워크·LLM API를 호출하지 않는다.

THE SYSTEM SHALL `learning_source.py`의 모든 함수가 raise를 하지 않는다. 예외는 내부에서 포착하여 None 또는 빈 리스트로 반환한다.

THE SYSTEM SHALL `learning_source.py` 내부에 특정 경로(절대 경로, 사용자명, repo 이름 등)를 하드코딩하지 않는다. 모든 경로는 함수 인자로 주입된다.

- **Acceptance:** `pytest tests/`가 네트워크·LLM 없이 통과한다. 모듈 임포트 시 부작용(파일 읽기, 환경 변수 접근)이 없다.

### NFR-3: 하위호환 보장

THE SYSTEM SHALL config 미설정 환경에서 self-improve의 동작 결과가 이번 기능 추가 전과 동일하다.

THE SYSTEM SHALL 기존 `tests/` 아래 self_improve 관련 테스트가 이번 변경 후에도 전량 통과한다.

- **Acceptance:** 기존 테스트 파일에 수정 없이 `pytest tests/`가 통과한다. `.harness/config.json` 없는 환경에서 self-improve Phase B가 로컬 entries만으로 기존과 동일하게 실행된다.

### NFR-4: 오프라인 pytest 검증 가능

THE SYSTEM SHALL `learning_source.py`에 대한 오프라인 테스트가 `tests/` 아래에 작성 가능하고, fixture로 실제 `harness-learning/` 포맷(`## marker` H2 + tags 메타블록) 마크다운을 사용하여 `has_cross_project=True` 시나리오를 검증할 수 있다.

- **Acceptance:** fixture 기반 테스트에서 `test-adequacy` 도메인이 `moon-harness`와 `Marvelous` 두 repo에서 왔을 때 `has_cross_project(counter, "test-adequacy") == True`가 assert된다. 테스트에 LLM·네트워크가 없다.

---

## 검증 시나리오 (Acceptance 요약)

| 시나리오 | 입력 | 기대 결과 |
|----------|------|----------|
| 정상 집계 | 로컬 LEARNING.md(repo=moon-harness) + store에 Marvelous.md(repo=Marvelous), 동일 domain | `has_cross_project=True` |
| store 경로 없음 | config 파일 없음 | raise 없이 로컬-only, `has_cross_project=False` (단일 repo) |
| store 경로 잘못됨 | config에 존재하지 않는 경로 | raise 없이 로컬-only |
| store에 불량 파일 | `*.md` 중 H2 없는 파일 포함 | 해당 파일 건너뜀, 나머지 집계 정상 |
| config 키 없음 | `.harness/config.json` 존재, `cross_project_store` 키 없음 | 로컬-only 동작 |
| protected 무수정 | 이번 구현 후 | `hooks/lib/self_improve/` 기존 파일 git diff 없음 |

---

## 미해결 / 가정

### 가정 1: harness-learning store 파일 포맷

외부 store(`harness-learning/<repo-id>.md`)는 `parse_learning_entry`가 그대로 처리할 수 있는 포맷, 즉 `## marker` H2 헤더 + `<!-- tags: ... -->` 메타블록을 따른다고 가정한다. 포맷이 다른 파일은 파싱 결과 entries 0건으로 처리된다 (graceful degradation).

### 가정 2: store 경로 절대 경로 관례

`.harness/config.json`의 `cross_project_store` 값은 절대 경로를 사용하는 것을 권장한다. 상대 경로를 허용하되, 해석 기준 디렉터리는 호출자(SKILL.md 절차)가 명시적으로 처리한다. `learning_source.py`는 받은 경로를 그대로 `pathlib.Path`로 해석한다.

### 미해결 1: harness-learning store 생성·유지 책임

marvelous_kompound의 `harness-learning/` 디렉터리를 누가 어떻게 최신으로 유지하는지(수동 복사·별도 sync 스크립트·hook 등)는 이 spec의 범위 밖이다. 이 spec은 "store가 존재한다면 읽는다"는 소비자 역할만 기술한다.

### 미해결 2: store 파일 수 증가 시 성능

store 디렉터리에 `*.md` 파일이 수십 건 이상 존재할 때의 읽기 비용은 현 단계에서 측정하지 않는다. 성능이 문제가 될 경우 파일 수 상한 또는 lazy 로드를 Phase 2에서 검토한다.
