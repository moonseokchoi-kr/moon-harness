# Claude Design 수동 게이트 핸드오프 상세

Claude Design(https://claude.ai/design) 은 2026-04-17 출시된 Anthropic Labs 웹 제품. 현재 API/MCP 가 없어 사용자가 직접 웹 UI 에서 작업해야 한다. spec-design 파이프라인은 수동 게이트로 통합한다.

향후 Anthropic 이 API/통합을 제공하면 이 수동 게이트를 자동 디스패치로 교체 예정.

## 전체 흐름

```
[PHASE2_UI_IA_USER_APPROVED]
  ↓
  사용자에게 visual_tool 선택 요청 (미설정 시)
  "시각 디자인 도구: claude-design (기본) / stitch"
  set_visual_tool claude-design
  ↓
  Agent(ui-designer) 디스패치 (brief 모드)
  ↓
  ui-designer 가 BRIEF.md 생성
  → docs/spec-design/design/ui/claude-design/{feature}/BRIEF.md
  ↓
  ui-designer 가 NEEDS_USER_ACTION 반환
  ↓
  컨트롤러: set_waiting_for_user true claude_design_bundle
  advance_label PHASE2_UI_BRIEF_READY
  ↓
  [Stop 훅 멈춤 — 사용자 대기]
  ↓
  사용자 응답: "번들 준비됐어, 경로는 /abs/path/to/bundle"
  ↓
  컨트롤러: set_bundle_path /abs/path
  ui-designer 재디스패치 (verify 모드)
  ↓
  ui-designer: bundle_path/*.html 존재 확인
  - OK → advance_label PHASE2_UI_BUNDLE_RECEIVED
  - 실패 → BLOCKED + 사용자 재요청
  ↓
  [품질 루프 진입 → PHASE2_UI_ITER_1_CRITIQUE]
```

## 브리프 작성 규칙

`docs/spec-design/design/ui/claude-design/{feature}/BRIEF.md` 의 내용은 Claude Design 에 **그대로 붙여넣을 수 있는 형태**여야 한다. 사용자가 복사-붙여넣기만 하면 되도록.

필수 포함:
1. **디자인 컨텍스트** — `.impeccable.md` 의 타겟/톤/컨텍스트 인용
2. **정보 구조** — IA 의 네비게이션/섹션/레이블링
3. **스크린 목록** — IA 의 플로우에서 필요한 화면만
4. **제약사항** — arch 의 플랫폼/프레임워크
5. **Export 요청** — HTML 번들로 저장할 경로 지정
6. **Iteration 히스토리** (재작업 시) — 이전 iter-{N}.md 지적사항 요약

## 번들 디렉토리 구조

```
docs/spec-design/design/ui/claude-design/{feature}/
├── BRIEF.md                  # 사용자에게 전달하는 브리프
└── bundle/                   # 사용자가 HTML export 를 풀어놓는 곳
    ├── index.html            # Claude Design 이 기본 출력 (또는 가장 큰 HTML)
    ├── {screen-1}.html
    ├── {screen-2}.html
    ├── styles.css            # (옵션) 분리된 스타일
    └── assets/               # (옵션) 이미지/폰트
```

## 번들 검증 로직 (ui-designer verify 모드)

ui-designer 가 `set_bundle_path` 이후 재디스패치되면:

1. `bundle_path/` 디렉토리 존재 확인
2. 최소 1 개의 `.html` 파일 존재 확인
3. `index.html` 우선, 없으면 가장 큰 HTML 파일을 기본 entry 로
4. 각 HTML 의 `<html lang>` 속성 확인 (i18n 힌트)
5. `<style>` 태그 or 외부 CSS 링크 확인

검증 실패 시:
```markdown
## UI Design Report
**Status:** BLOCKED
**reason:** 번들 경로 {path} 에 HTML 파일이 없거나 유효하지 않습니다.
다시 Claude Design 에서 export 하고 경로를 재지정해주세요.
```

## DESIGN.md 추출 (claude-design 모드)

bundle/ 의 HTML/CSS 를 파싱해 `docs/spec-design/design/DESIGN.md` 생성.

추출 대상:
- **색상 팔레트**: CSS `--color-*` 변수 or 자주 등장하는 hex/rgb 값
- **타이포 스케일**: `font-family`, `font-size`, `font-weight` 조합
- **간격 토큰**: `margin/padding` 반복 값을 스케일로 정리 (4/8/12/16/24/32 등)
- **모서리 둥글기**: `border-radius` 값
- **그림자**: `box-shadow` 패턴
- **브레이크포인트**: `@media` 쿼리의 `min-width` 값

`design-md` 스킬을 HTML 입력 모드로 활용하거나, ui-designer 가 직접 파싱해 작성.

## 재작업(iteration) 시 브리프 업데이트

iter USER_GATE 에서 사용자가 "재작업 + 지시" 선택 시:

1. `inc_iteration` → ui_iteration.count 증가
2. ui-designer 재디스패치 (iteration 모드)
3. ui-designer:
   - `iter-{N}.md` 읽기 (critique/audit/normalize 지적사항)
   - 사용자 지시사항 받기
   - BRIEF.md 업데이트 — `## Iteration 히스토리` 섹션에 이전 지적 + 사용자 지시 추가
   - 사용자에게 "같은 번들 경로에 Claude Design 에서 개선판을 export 해서 덮어써주세요" 안내
4. 사용자가 덮어쓰기 후 확인 응답 → 검증 → 다음 iter

## 실패 모드

| 상황 | 처리 |
|------|------|
| Claude Design 접속 불가 (사용자 답변) | ui-designer BLOCKED + visual_tool 을 stitch 로 재선택 권고 |
| 번들 디렉토리에 HTML 없음 | BLOCKED + 재요청 |
| 사용자가 응답 없음 (장시간) | Stop 훅 waiting_for_user=true 로 계속 대기. 사용자가 /cancel 하거나 재개할 때까지 |
| iteration 3회째 같은 지적 반복 | UI Designer 가 DONE_WITH_CONCERNS 로 보고, escalation 로그에 기록 |

## 사용자 커뮤니케이션 톤

수동 게이트 메시지는 **사용자가 정확히 무엇을 해야 하는지 + 어디에 뭘 놓아야 하는지** 만 명확히 전달. 내부 파이프라인 세부는 숨김.

좋은 예:
> Claude Design 에서 아래 브리프로 작업해주세요:
> 📄 `docs/spec-design/design/ui/claude-design/money-tracker/BRIEF.md`
>
> 완료 후 Export > Standalone HTML 로 받은 파일들을 이 폴더에 풀어주세요:
> 📁 `docs/spec-design/design/ui/claude-design/money-tracker/bundle/`
>
> 준비되면 `번들 준비됐어, 경로는 <path>` 로 알려주세요.

나쁜 예:
> PHASE2_UI_BRIEF_READY 상태입니다. set_bundle_path 후 재디스패치하세요.
