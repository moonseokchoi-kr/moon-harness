# T-{{task_number}}: {{task_title}}

## 관련 문서
- spec: `docs/sdd/spec/{{date}}-{{feature}}.md`
- arch: `docs/sdd/design/arch/{{date}}-{{feature}}.md`
- ui: `docs/sdd/design/ui/{{date}}-{{feature}}.md`
- api: `docs/sdd/design/api/{{date}}-{{feature}}.md`

## 구현자
{{implementer}}

## 테스트 타입
이 태스크에서 변경되는 레이어와 테스트 방식:

| 레이어 | 테스트 타입 | 비고 |
|--------|-----------|------|
{{#each test_layers}}
| {{this.layer}} | {{this.type}} | {{this.note}} |
{{/each}}

(arch 문서의 테스트 전략 기반. test-automator가 이 정보를 참고하여 적합한 프레임워크로 RED 테스트 작성)

## 완료 조건
{{#each completion_conditions}}
- [ ] {{this}}
{{/each}}
{{#if has_tests}}
- [ ] 모든 테스트 통과 (단위/통합/E2E 해당 타입)
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
