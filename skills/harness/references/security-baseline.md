# Security Baseline — 보안 기본선

하네스가 설치하는 최소 보안 규칙. 20개 규칙 + 3개 훅.
ECC의 1282 규칙이 아닌, "이것만 없으면 사고 나는" 최소 세트.

## 보안 훅 (harness 설치 시 자동 등록)

### Hook S1: 시크릿 탐지 (PreToolUse — Bash)

커밋, 파일 쓰기 전에 시크릿 패턴을 스캔한다.

탐지 패턴:
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` 등 API 키 환경변수
- `sk-` (OpenAI), `ghp_` (GitHub), `AKIA` (AWS) 등 토큰 접두사
- `.env`, `.pem`, `.key` 파일 직접 커밋 시도
- `password`, `secret`, `token` 변수에 하드코딩된 문자열

동작: exit 2 + 경고 (차단하지 않고 경고)

### Hook S2: 위험 명령 확인 (PreToolUse — Bash)

파괴적 명령어 실행 전 경고.

탐지 패턴:
- `rm -rf` (안전 대상 제외: node_modules, .next, dist, build)
- `DROP TABLE`, `DROP DATABASE`, `TRUNCATE`
- `git push --force`, `git reset --hard`
- `chmod -R 777`
- `curl | bash`, `curl | sh` (파이프 실행)

동작: exit 2 + "정말 실행하시겠습니까?" 경고

### Hook S3: 민감 파일 보호 (PreToolUse — Read|Edit|Write)

민감 파일 접근 시 경고.

보호 대상:
- `.env`, `.env.local`, `.env.production`
- `*.pem`, `*.key`, `*.cert`
- `.ssh/`, `.aws/`, `.config/gcloud/`
- `credentials.json`, `serviceAccountKey.json`

동작: exit 2 + 경고 (Read는 허용하되 Write/Edit은 차단 제안)

## 보안 규칙 (CLAUDE.md에 포함)

harness 설치 시 CLAUDE.md에 다음 섹션을 추가한다:

```markdown
# Security Rules
- .env 파일을 커밋하지 않는다. .gitignore에 포함되어 있는지 확인할 것.
- API 키를 코드에 하드코딩하지 않는다. 환경변수를 사용할 것.
- 새 의존성 추가 시 lock 파일(package-lock.json, Cargo.lock 등)도 함께 커밋할 것.
- SQL 쿼리에 사용자 입력을 직접 삽입하지 않는다. 파라미터 바인딩을 사용할 것.
- 에러 메시지에 내부 경로, 스택 트레이스, DB 스키마를 노출하지 않는다.
```

## 스킬별 보안 체크리스트

각 스킬이 작업 시 준수해야 할 항목:

### SDD Phase 3 (구현)
- [ ] 외부 입력 검증 (사용자 입력, API 응답)
- [ ] SQL 파라미터 바인딩
- [ ] 인증/인가 체크
- [ ] 에러 메시지에 민감 정보 미포함

### harness (환경 구성)
- [ ] .gitignore에 .env, *.key, *.pem 포함
- [ ] CLAUDE.md에 시크릿 미포함
- [ ] hook 스크립트에 하드코딩된 경로 미포함

### idea-workshop (리서치)
- [ ] WebSearch 결과에서 내부 URL 미노출
- [ ] 경쟁사 분석 시 저작권 준수
- [ ] 리뷰/커뮤니티 크롤링 시 개인정보(닉네임) 익명화
