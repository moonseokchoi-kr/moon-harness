# T-{{task_number}}: {{task_title}}

## 관련 문서
- spec: `docs/sdd/spec/{{date}}-{{feature}}.md`
- develop: `docs/sdd/develop/{{date}}-{{feature}}.md`

## 구현자
{{implementer}}

## TDD 수준
{{tdd_level}}
{{#if tdd_skip_reason}}사유: {{tdd_skip_reason}}{{/if}}

## 완료 조건
{{#each completion_conditions}}
- [ ] {{this}}
{{/each}}
{{#if tdd_full}}
- [ ] 모든 단위 테스트 통과
{{/if}}

{{#if tdd_full}}
## 테스트 시나리오
test-automator(tdd 모드)가 이 시나리오를 기반으로 테스트를 작성한다.

| # | 시나리오 | 입력 | 기대 결과 | 유형 |
|---|----------|------|----------|------|
{{#each test_scenarios}}
| {{this.number}} | {{this.scenario}} | {{this.input}} | {{this.expected}} | {{this.type}} |
{{/each}}
{{/if}}

## 의존 태스크
{{dependencies}}

## 예상 변경 파일
{{#each expected_files}}
- `{{this.path}}` — {{this.description}}
{{/each}}

## Steps
{{#each steps}}
- [ ] {{this}}
{{/each}}

## 검증 명령어
```bash
{{verification_command}}
```
