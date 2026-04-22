# Stitch 모드 상세 절차

Stitch MCP 를 사용한 자동 화면 생성 옵션. `pipeline.json` 의 `visual_tool=stitch` 일 때 활성화.

Claude Design 보다 자동화 정도가 높지만(사용자 개입 불필요), 대화형 시각 편집성은 떨어진다. 빠른 반복·프로토타이핑에 적합.

## 사전 요구사항

- `mcp__stitch__*` MCP 툴 접근 가능
- Stitch 계정 (무료 티어 OK)

MCP 가 없으면 ui-designer 가 BLOCKED + visual_tool 을 claude-design 으로 재선택 권고.

## 전체 흐름

```
[PHASE2_UI_IA_USER_APPROVED]
  ↓
  set_visual_tool stitch
  ↓
  Agent(ui-designer) 디스패치 (stitch 모드)
  ↓
  ui-designer:
  1. 기존 Stitch 프로젝트 확인 (.stitch/ 디렉토리)
  2. 없으면 mcp__stitch__create_project (프로젝트명=feature)
  3. mcp__stitch__create_design_system (IA + .impeccable.md 기반)
  4. IA 의 플로우에서 스크린 목록 도출
  5. 1개면 mcp__stitch__generate_screen_from_text 직접 호출
  6. 2개+면 Skill(stitch-loop) 패턴 적용 — .stitch/SITE.md + .stitch/next-prompt.md
  7. 모든 스크린 생성 후 mcp__stitch__apply_design_system
  8. Skill(design-md) 로 DESIGN.md 추출
  ↓
  advance_label PHASE2_UI_STITCH_GENERATED
  ↓
  [품질 루프 진입 → PHASE2_UI_ITER_1_CRITIQUE]
```

## 디자인 시스템 설정

`mcp__stitch__create_design_system` 에 주입:
- **primaryColor**: `.impeccable.md` 의 브랜드 컬러 (없으면 spec 의 분위기에서 추론)
- **headlineFont / bodyFont**: 상용 폰트 2개 조합
- **roundness**: `sharp | soft | round` (앱 성격에 맞춰)
- **designMd**: `.impeccable.md` 요약을 마크다운 블록으로 전달

설정 후 `mcp__stitch__update_design_system` 로 프로젝트에 적용.

## 스크린 생성 전략

### 1개 화면
간단하므로 직접 호출:
```
Skill(enhance-prompt) 으로 프롬프트 최적화
→ mcp__stitch__generate_screen_from_text
→ mcp__stitch__apply_design_system
```

### 2개 이상 (stitch-loop 패턴)
자율 반복을 위해 다음 준비:
1. `.stitch/SITE.md` — 전체 사이트/앱의 비전 + 화면 로드맵
2. `.stitch/next-prompt.md` — 첫 화면용 enhance-prompt 결과
3. `.stitch/DESIGN.md` (선택) — 디자인 시스템 상세
4. `Skill(stitch-loop)` 호출 → 자율 루프

stitch-loop 은 각 iteration 마다:
- `next-prompt.md` 를 읽어 `mcp__stitch__generate_screen_from_text` 호출
- 결과를 `SITE.md` 와 비교해 다음 화면 프롬프트를 `next-prompt.md` 에 기록
- 로드맵이 소진되면 종료

## iteration 재작업 시

stitch 모드도 품질 루프를 돈다. iter USER_GATE 에서 재작업 지시 시:

1. `inc_iteration`
2. ui-designer 재디스패치
3. 이전 `iter-{N}.md` 의 지적사항 + 사용자 지시 통합
4. 옵션 선택:
   - 특정 스크린만 재생성: `mcp__stitch__generate_variants` 로 variant 생성 후 기존 교체
   - 전체 재생성: 새 프롬프트로 screen 다시 생성
   - 디자인 시스템 조정만 필요: `mcp__stitch__update_design_system` + `apply_design_system`

## 산출물 구조

```
docs/spec-design/design/ui/stitch/{feature}/
├── .stitch/
│   ├── SITE.md                  # (stitch-loop 사용 시) 비전·로드맵
│   ├── next-prompt.md           # (stitch-loop 사용 시) 다음 생성 프롬프트
│   └── DESIGN.md                # (옵션) 기존 디자인 시스템 복사본
├── project-info.json            # project_id, screen_ids 매핑
└── screens/                     # (옵션) 로컬 스냅샷
```

UI 명세 문서의 "시각 디자인 참조" 섹션에 `project_id` + screen_id 목록을 기록.

## MCP 부재 시 대응

`mcp__stitch__create_project` 가 실패하면 (MCP 미설치/오류):
```markdown
## UI Design Report
**Status:** BLOCKED
**reason:** Stitch MCP 가 사용 불가능합니다.
**해결:**
1. Claude Code settings 에서 Stitch 플러그인을 활성화하거나,
2. visual_tool 을 claude-design 으로 재선택하세요.
```

컨트롤러가 사용자에게 재선택 요청 → `set_visual_tool claude-design` → ui-designer 재디스패치.

## Claude Design 대비 장단점

| 항목 | Stitch | Claude Design |
|------|--------|---------------|
| 자동화 | ✅ MCP 로 완전 자동 | ❌ 사용자 수동 게이트 |
| 디자인 품질 | 보통 | 우수 (Opus 4.7 기반) |
| 대화형 편집 | 프롬프트 재생성 | 인라인 코멘트 + 슬라이더 |
| 디자인 시스템 | 수동 지시 | 자동 (코드베이스 읽음) |
| 반복 속도 | 빠름 (무인) | 느림 (사용자 개입) |
| 구독 필요 | 무료 티어 | Claude Pro/Max |
