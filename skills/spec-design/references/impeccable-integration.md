# Impeccable 스킬 통합 레시피

Phase 2-B 품질 검증 루프와 디테일 강화 단계에서 호출하는 각 impeccable 스킬의 입력·출력·평가 기준.

## 품질 검증 루프 (iter 각 회차)

각 회차는 `Skill(...)` 으로 순차 호출. 결과는 `docs/spec-design/design/ui/iteration-reports/{feature}/iter-{N}.md` 에 누적 기록.

### 1. `Skill(impeccable:critique)` — UX 관점 평가

**입력 대상:**
- visual_tool=claude-design: `bundle_path/` 의 HTML 렌더
- visual_tool=stitch: Stitch 스크린 목록

**평가 항목:**
- 시각 계층 (hierarchy) — 중요한 것이 눈에 먼저 들어오는가
- 정보 구조 적합성 — IA 의 섹션/플로우가 시각적으로 구현되었는가
- 감정 반응 — 브랜드 톤에 맞는 인상을 주는가
- 인지 부하 — 한 화면에 정보 과다/부족
- 정량 점수 (1-10)

**출력:** `iter-{N}.md` 의 `## Critique` 섹션 (점수 + 구체 지적)

### 2. `Skill(impeccable:audit)` — 기술 품질 감사

**평가 항목:**
- 접근성 (WCAG 2.1 AA): 색상 대비, 키보드 접근, ARIA
- 성능 영향: 에셋 크기, 애니메이션 60fps 가능 여부
- 테마 일관성: 색상/타이포/간격 토큰 준수
- 반응형: 브레이크포인트 처리
- 안티패턴 탐지 (P0-P3 심각도)

**출력:** `iter-{N}.md` 의 `## Audit` 섹션 (P0-P3 별 이슈 목록)

### 3. `Skill(impeccable:normalize)` — 디자인 시스템 정합성

**평가 항목:**
- DESIGN.md 토큰 준수: 색상, 간격, 모서리 둥글기, 그림자
- 컴포넌트 패턴 일관성: 같은 목적의 UI 요소가 다른 모양이면 경고
- 타이포 스케일: modular scale 일관성
- 디자인 드리프트 탐지

**출력:** `iter-{N}.md` 의 `## Normalize` 섹션 (드리프트 항목 + 정합 제안)

## 사용자 게이트 응답 해석

iter USER_GATE 라벨에서 사용자 응답을 아래 규칙으로 분류:

| 응답 유형 | 예시 자연어 | 컨트롤러 행동 |
|---------|------------|-------------|
| 통과 | "통과", "ok", "approve", "승인", "좋아", "다음으로" | `advance_label PHASE2_UI_DESIGN_COMPLETE` |
| 재작업 | "재작업 + <지시>", "이거 고쳐", "다시 해봐 + <지시>", "개선 필요" | `inc_iteration`; `advance_label PHASE2_UI_ITER_{N+1}_CRITIQUE`; ui-designer 재디스패치 (프롬프트에 지시사항 + iter-{N}.md 포함) |
| 중단 | "중단", "취소", "관둬" | `cancel_pipeline` |
| 모호 | 위 세 카테고리에 안 맞는 응답 | 명시적 재질의 (통과/재작업/중단 중 하나 선택해달라) |

**iter 4 소진 시 재작업 요청:**
- "강제 통과하고 진행" → `advance_label PHASE2_UI_DESIGN_COMPLETE` + escalation 로그 기록
- "중단" → `cancel_pipeline`
- 그 외 재작업 지시 → 거부 + 위 두 선택지 재요청

## 디테일 강화 단계 (PHASE2_UI_DETAIL_ENRICHED)

iter 루프 통과 후 순차 호출. 각 결과를 UI 명세 문서 해당 섹션에 append.

### 1. `Skill(impeccable:animate)`

**입력:** UI 명세 + 번들/스크린
**목적:** 모션·마이크로 인터랙션 설계
**평가 기준:**
- 상태 전이(entrances/exits/feedback) 모션 명시
- 이징 함수: `ease-out-quart/quint/expo` 권장, bounce/elastic 금지
- 레이아웃 프로퍼티 애니메이션 금지 (width/height/padding/margin) — transform/opacity 만
- `prefers-reduced-motion` 대응

**출력:** UI 명세 문서의 `## 디테일 강화 > 모션 & 마이크로 인터랙션` 섹션

### 2. `Skill(impeccable:clarify)`

**목적:** UX 카피 개선
**평가 기준:**
- 명확성 (사용자가 한 번에 이해하는가)
- 중복 제거 (같은 정보를 다시 말하지 않는가)
- 에러 메시지 구체성 ("something went wrong" 금지, 어떤 작업이 왜 실패했고 다음 행동 제시)
- 빈 상태/로딩 상태 카피 (사용자를 가르치는가)

**출력:** UI 명세 문서의 `## 디테일 강화 > UX Copy` 섹션

### 3. `Skill(impeccable:harden)`

**목적:** 엣지 케이스·에러·i18n·overflow 처리
**평가 기준:**
- 긴 텍스트 overflow (말줄임, 줄바꿈, 2행 제한 등)
- 네트워크 실패·타임아웃 UI
- 빈 상태 / 에러 상태 / 성공 상태 (각 스크린마다)
- i18n: 다국어 시 레이아웃 확장 대응
- 권한 거부 경로

**출력:** UI 명세 문서의 `## 디테일 강화 > 엣지 케이스 & i18n` 섹션

### 4. `Skill(impeccable:adapt)`

**목적:** 반응형·다디바이스 적응
**평가 기준:**
- 브레이크포인트 기준 (container queries 권장)
- 터치 타겟 44px 이상 (모바일)
- 크리티컬 기능 모바일에서 숨김 금지
- 유동 스페이싱(clamp)

**출력:** UI 명세 문서의 `## 디테일 강화 > 반응형` 섹션

## impeccable 스킬 호출 전 확인

- `.impeccable.md` 가 존재해야 함 (`Skill(impeccable:teach-impeccable)` 로 수립)
- 없으면 디자인 컨텍스트 부족으로 generic output 이 나옴
- `phase-gate.sh` 가 UI 문서 + IA 문서 상호 존재를 경고함
