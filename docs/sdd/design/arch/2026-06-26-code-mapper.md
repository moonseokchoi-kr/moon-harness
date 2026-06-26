# code-mapper 아키텍처 (SDD Phase 2 — SIMPLE)

> 입력: `docs/sdd/spec/2026-06-26-code-mapper.md` (spec only). UI/API 스펙 없음 (SIMPLE).
> 산출물 성격: 실행 애플리케이션이 아니라 **Claude Code 플러그인 스킬 자산**(마크다운 절차 + 에이전트 프롬프트 단락 + 얇은 결정적 코어). 표준 native arch 템플릿을 이 성격에 맞게 변형함.

---

## 1. 아키텍처 요약

code-mapper는 **ephemeral 구조적 컨텍스트 제공기**다 (Aider repo map 모델). 작업 직전 대상 심볼의 실제 호출관계를 고정 커버리지 체크리스트(F6)로 surface 하고, 컨텍스트로 소비된 뒤 버려진다. **게이트가 아니라 컨텍스트**다 — 저장·계약·검증·종속·하드게이트는 전부 비목표다.

아키텍처는 단 3개의 경계로 구성된다:

```
┌─────────────────────────────────────────────────────────────┐
│  진입점 레이어 (프롬프트, LLM 실행)                            │
│   skills/code-mapper/SKILL.md  ← /code-mapper <심볼|파일> SSOT │
│   agents/sdd-implementer.md    ← 포인터 단락 1개 (전파 허브)    │
└───────────────┬─────────────────────────────────────────────┘
                │ (LLM이 절차를 따라 도구를 오케스트레이션)
                ▼
┌─────────────────────────────────────────────────────────────┐
│  오케스트레이션 레이어 (프롬프트가 지시, LLM이 판단/실행)       │
│   • codegraph_status 프로브 (MCP 도구 호출 — LLM만 가능)       │
│   • 3-상태 분기 → codegraph_* 체인  OR  Glob+structural grep   │
│   • F6 커버리지 체크리스트로 결과 surface                      │
└───────────────┬─────────────────────────────────────────────┘
                │ (선택적으로 호출하는 순수 함수)
                ▼
┌─────────────────────────────────────────────────────────────┐
│  결정적 코어 레이어 (Python stdlib-only, pytest 검증)          │
│   hooks/lib/code_mapper/                                      │
│   • probe 응답 텍스트 → 3-상태 분류 (순수 함수)                │
│   • F6 섹션 완전성/순서 검사 (순수 함수)                       │
│   • 확장자 → 언어/정의패턴 매핑 테이블 (순수 데이터)           │
└─────────────────────────────────────────────────────────────┘
```

핵심 데이터 흐름은 단방향이고 휘발성이다: **호출 → 프로브 → 분기 → surface → 폐기**. 영속 상태 0, 파일 쓰기 0, 디스크 산출물 0.

---

## 2. 가정 · 제약 · 목표

### 가정 (명시 — 틀리면 교정 요청)
- **A1**: codegraph는 사용자 개인 환경에만 있는 MCP다. 플러그인은 codegraph 존재를 **가정하지 않는다**. baseline 동작 = grep/Glob 폴백. (R2, R8)
- **A2**: 가용성 판별은 `codegraph_status` **MCP 도구 호출** 결과로만 한다. filesystem `.codegraph/` 디렉터리 체크는 **금지**(false negative). (R3, F4)
- **A3**: `/code-mapper`는 사람이 직접, 그리고 SDD 에이전트가 권고를 받아 호출하는 공용 진입점이다. 외부(다른 플러그인) 스킬에 호출 포인터를 주입하는 것은 범위 밖. (F7)
- **A4**: 테스트 프레임워크는 이 repo의 기존 선택(`pytest`, stdlib-only)을 그대로 따른다. 신규 프레임워크 도입 없음.

### 플랫폼 제약
- 산출물은 마크다운 + 얇은 Python. 컴파일 산출물 없음. **fast-scoped** repo (워밍업 빌드 불필요).
- 하네스 범용 — 레포 특화 명령/경로 하드코딩 **금지**. 언어 패턴 테이블도 일반 패턴(.py/.ts/.js/기타)만.
- protected set(`self-improve`, `pr-converge`, `harness-improvement-critic`, 게이트 스크립트) 자동 수정 금지.

### 목표 (성능/품질)
- **정체성 불변량**: ephemeral. 어떤 코드 경로도 코드맵을 디스크에 쓰면 안 된다.
- **포맷 불변량**: codegraph 경로와 grep 폴백 경로가 **동일한 F6 섹션 1~6 + "탐색 방법" 레이블**을 낸다.
- **거짓양성 억제**: callers/callees 수집 시 주석·문자열·타입힌트 이름 일치 제외 (code-mapper 존재 이유와 직결).
- **최소 침습**: sdd-implementer에 단락 1개. 기존 섹션 0 변경.

---

## 3. 모듈 / 디렉터리 경계 (라이브러리 레벨)

> 파일명이 아니라 디렉터리/모듈 경계만 정의한다. 파일 단위 결정은 엔지니어 몫.

| 경계 | 위치 | 책임 | 티어 |
|------|------|------|------|
| 스킬 절차 (SSOT) | `skills/code-mapper/` | `/code-mapper` 전체 절차(프로브→분기→폴백→F6). 판단 로직 거주지. | 하네스 |
| 에이전트 주입 | `agents/sdd-implementer.md` | 포인터 단락 1개 (전파 허브). | 하네스 (준-protected) |
| 결정적 코어 | `hooks/lib/code_mapper/` | 순수 함수: 상태 분류, 포맷 완전성 검사, 언어패턴 테이블. stdlib-only. | 하네스 |
| 코어 테스트 | `tests/` | 위 순수 함수의 pytest (오프라인). | 하네스 |
| 폴백 동작 eval | `evals/` | codegraph 미초기화 테스트 레포에서 라이브 실행(claude -p). | 하네스 |

**왜 `hooks/lib/code_mapper/`인가**: 기존 `hooks/lib/self_improve/`와 동일한 결정적-코어 패턴을 따른다(stdlib-only, 패키지 디렉터리, `tests/`에서 import). code-mapper 코어는 self_improve와 책임이 다르므로 별도 패키지로 격리한다. self_improve 패키지를 건드리지 않는다(혼입 방지).

---

## 4. 소유권 · 의존 방향

```
SKILL.md  ───(참조/포인터)──▶  hooks/lib/code_mapper/  ◀───(import)──  tests/
   ▲                                    ▲
   │                                    │ (런타임에 LLM이 선택적 호출)
agents/sdd-implementer.md ──(포인터)────┘
```

- 의존은 **위→아래 단방향**. 코어는 어떤 프롬프트도 import 하지 않는다(코어는 LLM·MCP·네트워크를 모른다).
- SSOT는 `SKILL.md` **하나**. sdd-implementer는 절차 본문을 복제하지 않고 포인터만 가진다(F7, F8).
- 코어는 **선택적**이다: 코어가 없어도(혹은 import 실패해도) LLM이 프롬프트 절차만으로 동작 가능해야 한다(fail-safe). 코어는 일관성 보조 도구이지 런타임 의존성이 아니다.

---

## 5. 제어 흐름 (스레딩/async 해당 없음 — 절차 흐름)

단일 동기 절차. 동시성·백그라운드 작업 없음.

```
/code-mapper <대상>
  │
  ├─ 1. codegraph_status 프로브 (MCP 도구 호출 — LLM 실행)
  │       └─ 응답 텍스트 → [코어] classify_probe_state() → {healthy | not_initialized | unavailable}
  │
  ├─ 2. 분기
  │     (a) healthy      → codegraph_context → codegraph_trace → codegraph_impact
  │     (b) not_initialized → "codegraph init -i 실행 제안" 메시지 출력 → 폴백(c)로 진행
  │     (c) unavailable  → Glob 정의탐색 → grep callers → grep callees (주석/문자열 제외)
  │
  ├─ 3. F6 커버리지 체크리스트로 결과 surface (섹션 1~6 + "탐색 방법" 레이블)
  │       └─ [코어] check_format_completeness() 로 섹션 누락/순서 자가검사 (선택)
  │
  └─ 4. 폐기 (저장 안 함)
```

분기 결정의 **입력**(status 텍스트)은 결정적이지만, 분기를 **트리거하는 MCP 호출 자체는 LLM만** 할 수 있다. 이 경계가 6절 설계 결정의 근거다.

---

## 6. 설계 결정 — 결정적 Python 코어가 정당한가? (핵심 질문)

### 결론: **얇은 결정적 코어를 둔다 (정당). 단 최소 표면적으로.**

순수 프롬프트 스킬도 아니고, F9가 암시할 수 있는 "분기 전체를 python으로" 도 아니다. **MCP 호출과 surface는 LLM이, 그 사이의 순수 분류·검사 함수만 python이** 담당하는 경계를 명확히 긋는다.

### 냉정한 분해: python이 결정적으로 검증할 *순수 함수*가 실제로 존재하는가?

| 후보 로직 | 순수 함수인가? | 결정 |
|-----------|---------------|------|
| `codegraph_status` **호출** | ✗ — MCP 도구 호출. side-effect, LLM만 가능. | **프롬프트(LLM)**. python 불가. |
| status **응답 텍스트 → 3-상태 분류** | ✓ — `str → {healthy\|not_initialized\|unavailable}`. 동일 입력=동일 출력. | **코어 `classify_probe_state(text)`**. pytest 검증. |
| F6 산출물 **섹션 1~6 존재/순서 검사** | ✓ — `markdown str → (완전성, 누락목록)`. | **코어 `check_format_completeness(text)`**. pytest 검증. |
| 확장자 → 언어/정의패턴 **매핑** | ✓ — 순수 데이터 테이블 + lookup. | **코어 `language_for(ext)` / `def_patterns(lang)`**. pytest 검증. |
| "이 심볼 영향범위가 넓은가" **해석** | ✗ — 의미 판단. | **프롬프트(LLM)**. F9 명시적 비목표. |
| callers/callees가 주석/문자열인지 **실제 판정** | ✗(정확히는) — 실제 파싱은 grep 정규식 + LLM 판단. 코어는 *제외용 정규식 조각*만 데이터로 제공 가능. | **프롬프트가 grep 패턴 적용**; 코어는 패턴 문자열 테이블만 보유(검증은 패턴 자체의 형태 단위 테스트로). |

### 근거 (왜 순수 프롬프트가 아닌가)
1. **CLAUDE.md 결정↔판단 분리가 요구**한다: 상태 분류·포맷 강제는 동일입력=동일출력의 결정적 로직 → 프롬프트에 두면 회차마다 흔들린다. 이 repo는 이런 로직을 stdlib python + pytest로 고정하는 확립된 패턴(`self_improve/tier.py`)을 갖고 있고, code-mapper의 3-상태 분류는 `tier.py`의 분류 로직과 동형이다.
2. **spec F9 + 검증전략이 명시 요구**: "`tests/`에 가용성 분기 로직을 검증하는 pytest 테스트가 존재한다", "포맷 파서 단위 테스트". 순수 프롬프트로 가면 이 acceptance를 충족할 대상이 없다.
3. **회귀 방어**: 3-상태 분류 기준("not initialized" 신호 감지 등)이 흔들리면 폴백이 잘못 발동/미발동. 결정적 테스트가 이를 고정한다.

### 근거 (왜 과잉이 아닌가 — 표면적 최소화)
- 코어는 **3개의 작은 순수 함수 + 1개 데이터 테이블**뿐이다. 영속/계약/검증 게이트/종속 로직은 **전혀** 없다(전부 비목표).
- 코어는 **런타임 필수 의존이 아니다** — LLM이 프롬프트만으로도 동작 가능. 코어는 일관성 보조 + 테스트 가능 표면일 뿐.
- 사용자의 "과하게 짓지 마라"를 코어 **존재**가 아니라 코어 **크기**로 존중한다: 결정적인 것만, 딱 그만큼.

### 만약 반대 입장(순수 프롬프트)을 택했다면의 비용
acceptance F9가 충족 불가(`tests/` 대상 없음), 3-상태 분류가 회차마다 표류, repo의 확립된 결정↔판단 분리 규칙 위반. → **코어 채택이 우세**.

---

## 7. 폴백 grep 패턴 설계 (F5 — 범용, 하드코딩 금지)

코어 `hooks/lib/code_mapper/`의 **데이터 테이블**로 보유하고, 프롬프트가 이를 grep에 적용한다. 레포 특화 경로/명령은 일절 없음.

### 7.1 언어 판정 (확장자 → 언어)
순수 lookup 테이블. 미지 확장자 → `generic`로 폴백.

| 확장자 | 언어 | 정의 패턴 (개념) |
|--------|------|------------------|
| `.py` | python | `^\s*(def\|class)\s+<sym>\b` |
| `.ts` `.tsx` `.js` `.jsx` `.mjs` | js/ts | `(function\s+<sym>\b\|class\s+<sym>\b\|(const\|let)\s+<sym>\s*=.*=>\|<sym>\s*\()` |
| 기타 | generic | 식별자 경계 패턴 `\b<sym>\b` (정의/사용 구분 약함 — 근사 명시) |

### 7.2 Callers 근사 (역참조)
대상 심볼을 **import / 호출 / 상속**하는 파일을 grep으로 수집:
- import: `import .*<sym>` / `from .* import .*<sym>` / `require\(.*<sym>` / `import \{[^}]*<sym>`
- 호출: `\b<sym>\s*\(` (함수/메서드 호출)
- 상속: `class\s+\w+\(.*<sym>` (py) / `extends\s+<sym>` (ts/js)

### 7.3 Callees 근사
정의 파일 **본문 범위 내**에서 호출되는 외부 식별자 grep: `\b\w+\s*\(` 매칭 후 정의 심볼 제외. (근사 — best-effort 명시)

### 7.4 거짓양성 억제 (정체성 직결)
- **주석 제외**: 라인이 주석 마커(`#`, `//`, `/*` … `*/`, `*`)로 시작/감싸이면 제외.
- **문자열 리터럴 제외**: 매치가 따옴표(`"` `'` `` ` `)로 감싸인 경우 제외.
- **타입힌트 제외**: `: <sym>` / `-> <sym>` 위치 매치는 호출 아님 → callers/callees에서 제외(컨텍스트 참고로만).
- **언어 예약어/제어구문 제외** (m2): callees grep(`\b\w+\s*\(`)이 `if`/`for`/`while`/`switch`/`catch` 등 키워드를 잡지 않도록 예약어 제외 목록을 코어 테이블에 둔다 — generic 폴백 품질을 싸게 올림.
- 이들 제외 규칙은 패턴 조각으로 코어 테이블에 두되, **적용 판단(이 라인이 정말 주석/문자열인가)** 은 LLM이 grep 결과를 보고 수행. 코어는 패턴 형태만 단위 테스트.

### 7.5 폴백 출력 규약
- F6 섹션 1~6 **동일하게** 출력.
- "탐색 방법" 레이블 = `grep 근사 (codegraph 미사용)`.
- 각 근사 섹션에 `(grep 근사, codegraph 미사용)` 표기 + 산출물 말미에 `근사값 — 개발자 확인 권장` 주의.
- 결과 비어도 섹션은 `(없음)`으로 채움(생략 금지).

---

## 8. `skills/code-mapper/SKILL.md` 섹션 구성 (제안)

SSOT. 절차 본문 전부가 여기 산다. 제안 섹션:

```
---
name: code-mapper
description: "심볼/파일을 편집·호출하기 전 실제 호출관계를 구조적 컨텍스트로 surface. /code-mapper <심볼|파일>. 이름 기반 가짜 확신 감소. 게이트 아님 — ephemeral 컨텍스트."
---

# code-mapper — ephemeral 구조적 컨텍스트 제공기

## 정체성 (변하면 안 되는 축)
- ephemeral. 저장/계약/검증/종속/하드게이트 전부 금지. 게이트가 아니라 컨텍스트.

## 호출
- `/code-mapper <심볼-또는-파일>`

## 절차
### Step 1 — codegraph 가용성 프로브 (codegraph_status)
  - filesystem .codegraph/ 체크 금지(false negative). MCP 프로브만.
  - 응답 → 3-상태 분류 (분류 기준 표).
### Step 2 — 분기
  (a) healthy: codegraph_context → codegraph_trace → codegraph_impact
  (b) not_initialized: `codegraph init -i` 제안 메시지 → 폴백으로 진행 (자동 실행 금지)
  (c) unavailable: Glob + structural grep 폴백 (7절 패턴)
### Step 3 — F6 커버리지 체크리스트 surface (섹션 1~6 + 탐색 방법 레이블)
### Step 4 — 폐기 (저장 안 함)

## 3-상태 분류 기준 (결정적)
| status 응답 | 상태 | 행동 |
| 인덱스 통계(노드/엣지/ready) 반환 | healthy | codegraph 체인 |
| "not initialized"(동등 미초기화 신호) 포함 | not_initialized | init 제안 + 폴백 |
| 도구 미등록 / 연결 오류 | unavailable | grep 폴백 |
> 결정적 코어 hooks/lib/code_mapper/ 의 classify_probe_state()와 동일 기준. 코어는 보조 검증용.

## 폴백 grep 패턴 (범용 — 레포 하드코딩 금지)
  [7절 테이블: 언어판정 / callers / callees / 거짓양성 제외 / 출력규약]

## F6 커버리지 체크리스트 (ephemeral 출력 양식)
  [spec F6 섹션 1~6 그대로 — 진입점/Callers/Callees/Trace/Blast Radius/건드릴 파일 + 탐색 방법]
  - 섹션 5(Blast Radius)=변경 시 영향 전체 / 섹션 6(건드릴 파일)=이번 작업 추정(5의 서브셋, 계약 아님)
  - 빈 섹션은 (없음). 순서 변경 금지.

## 비목표 (정체성 보호)
  - 영속/계약/검증/종속/하드게이트/시각화/AST엔진 신규구현/codegraph 자동init 전부 금지.
```

---

## 9. sdd-implementer 주입 단락 (F8 — 최소 침습)

### 위치
`agents/sdd-implementer.md`의 **`## 작업 순서` 섹션 직후, `## 커밋 규칙` 섹션 직전**에 신규 단락 1개 삽입. 기존 섹션 본문은 일절 수정하지 않는다(작업순서·커밋규칙·완료판정 원문 보존).

> 근거: "구현" 단계(작업순서 5)와 인접해 읽히되, 기존 번호 매겨진 스텝 리스트 내부를 건드리지 않아 diff가 단락 추가 1건으로 한정됨. F8 acceptance(단락 1개 초과 금지, 기존 섹션 원문 동일, 절차 본문 없이 포인터만) 충족.

### 정확한 문구 (제안 — 절차 본문 없이 포인터만)
```markdown
## 구조적 컨텍스트 권고 (게이트 아님)

낯선 기존 심볼을 편집·호출하기 전, 이름 기반 추측 대신 실제 호출관계를
구조적 컨텍스트로 확보할 것을 **권고**한다(의무·차단 게이트 아님).
codegraph MCP가 가용하면 구조적 탐색을 우선 사용하고, 없으면 grep 폴백으로
동일한 컨텍스트를 얻는다. 절차 상세·포맷은 `skills/code-mapper/SKILL.md`
(`/code-mapper <심볼|파일>`)를 참조한다. 컨텍스트는 ephemeral이며 저장하지 않는다.
```

도달 범위(reach): **sdd-implementer 단독** (사용자 결정 2026-06-26). 언어별 engineer로의 자동 전파는 **없다** — SDD skill §659 "Engineer agents 일반 규칙"은 LEARNING 캡처 규칙만 전파하고, `sdd-ts-engineer` 등은 self-contained라 sdd-implementer 본문을 상속하지 않는다(architect-reviewer M1 정정). 언어별 engineer 전파는 v1 범위 밖. 최고 가치 소비자(버그 수정 워크플로우)는 `/code-mapper` 직호출이라 이 한정과 무관.

---

## 10. 빌드 / 테스트 / 운영

- 빌드 산출물 없음(마크다운 + python). 워밍업 빌드 불필요 — fast-scoped.
- 코어는 stdlib-only, import 시 side-effect 0, fail-safe(예외 시 폴백 상태로 수렴).
- 프로파일링/텔레메트리/크래시 진단 해당 없음(런타임 데몬 아님).

---

## 11. 테스트 전략 (레이어별 — FULL/SKIP 없음, 타입만 다름)

| 레이어 | 대상 | 프레임워크 | 테스트 타입 | 검증 경계 |
|--------|------|-----------|------------|-----------|
| 결정적 코어 | `classify_probe_state()` 3-상태 분류 | `pytest` (stdlib) | **단위** | healthy/not_initialized/unavailable 각 입력 + 경계(빈 문자열, 미지 신호 → fail-safe unavailable) |
| 결정적 코어 | `check_format_completeness()` F6 검사 | `pytest` | **단위** | 섹션 1~6 누락/순서뒤바뀜/탐색레이블 누락 검출 |
| 결정적 코어 | 언어/정의패턴 테이블 + 폴백 패턴 형태 | `pytest` | **단위** | 확장자→언어 매핑, 미지 확장자→generic, 패턴 문자열이 유효 정규식 |
| 스킬 절차 정합성 | `SKILL.md` 절차 일관성 | 수동 리뷰 | **통합(리뷰)** | harness-improvement-critic 게이트 |
| 주입 최소 침습 | sdd-implementer diff | 수동 리뷰 | **통합(리뷰)** | 주입 전/후 diff: 단락 1개, 기존 섹션 원문 동일, 포인터만 |
| 폴백 동작 | 라이브 `/code-mapper <심볼>` | `evals/` (claude -p) | **E2E** | codegraph 미초기화 테스트 레포에서 ① 섹션 1~6 완전성 ② callers/callees 개수>0 또는 "(없음)" 정합 ③ 수집 파일경로 유효성(존재 파일만) |

- 오프라인(`tests/`)과 라이브(`evals/`) **비혼합** 규율 준수 — `pytest tests/`는 `evals/`를 수집하지 않는다.
- 구체 시나리오 작성은 test-automator 몫. 여기서는 타입·경계만 정의.
- **책임 경계(m3)**: 코어 `check_format_completeness()`는 *보조 검증*이다(코어는 비필수 설계). F6 포맷 불변량의 1차 방어는 **SKILL.md 절차 + evals E2E**가 담당하고, 코어 단위 테스트는 검사 함수 자체의 정확성만 보증한다.

---

## 빌드 프로파일

> 출처: CLAUDE.md (2026-06-26 확인)

| 필드 | 값 | 비고 |
|------|-----|------|
| 유형 | fast-scoped | 컴파일 산출물 없음(마크다운 + stdlib python). 빌드 단계 없이 테스트 직접 실행. |
| 워밍업 빌드 | (생략) | fast-scoped — 콜드 빌드 비용 없음 |
| 증분 빌드 | (생략) | 빌드 산출물 없음 |
| 테스트 실행 | `PATH="/opt/homebrew/bin:$PATH" python3 -m pytest tests/ -q` | pytest는 homebrew python(3.14)에 설치, Xcode python3엔 없음 |
| 테스트 필터 문법 | `... pytest tests/test_code_mapper_*.py -q` 또는 `-k <name>` | 태스크별 스코프 지정 |
| clean 정책 | no-clean | 캐시(`.pytest_cache`) 보존 |

---

## 12. 리스크 · 트레이드오프 · 마이그레이션

| 리스크 | 영향 | 완화 |
|--------|------|------|
| 코어를 "결정적이니까" 자꾸 키워 계약/검증으로 번짐 | 정체성(ephemeral 컨텍스트) 붕괴 | 6절 표면적 동결: 3함수+1테이블. 영속/계약/검증/종속은 비목표로 SKILL.md에 명시. v2 별도 측정 후에만 검토. |
| codegraph_status 응답 포맷 변경 | 3-상태 분류 표류 | 분류 기준을 "통계 반환 / 'not initialized' 포함 / 미등록" 의미 단위로 정의(특정 텍스트 정확매치 아님) + 미지 신호는 fail-safe로 unavailable(grep 폴백)로 수렴 → 최악도 동작. |
| grep 폴백 거짓양성(주석/문자열/타입힌트) | 가짜 확신 재발(정체성 역행) | 7.4 제외 규칙 + "근사값, 개발자 확인 권장" 명시로 과신 차단. |
| sdd-implementer 주입이 준-protected 파일 변경 | 리뷰 마찰 | 단락 추가만, 기존 섹션 0 변경. diff 리뷰 게이트. |
| 코어 import 실패 시 스킬 동작 불가 오해 | 폴백 불능 | 코어를 비필수로 설계 — LLM이 프롬프트만으로 동작 가능(코어는 보조). |

### 마이그레이션 (레거시 없음)
신규 자산. 기존 코드 마이그레이션 불필요. 기존 `hooks/lib/self_improve/` 패턴을 답습하되 별도 패키지로 격리하여 혼입 0.

---

## 후속 게이트
이 arch 승인 후 — SIMPLE 모드이므로 ui-designer/api-designer 불필요. 바로 Phase 3(태스크 분해)로 진행. 태스크는 (1) 코어 패키지+pytest, (2) SKILL.md 작성, (3) sdd-implementer 주입, (4) evals 폴백 시나리오로 자연 분할된다.
