"""evals/ — 라이브 eval 하네스 패키지 (F21 live layer).

목적
----
- claude -p 헤드리스로 실제 스킬/agent를 시나리오에 돌리고 LLM-judge로 채점한다.
- 오프라인 pytest 스위트(tests/)와 완전히 분리된 별도 진입점이다 (F21).

실행 방법
---------
  # dry-run (API 크레딧 소비 없음):
  python evals/run_eval.py

  # 라이브 실행 (실제 API 크레딧 소비):
  python evals/run_eval.py --live

  # 특정 시나리오만 실행:
  python evals/run_eval.py --live --scenario comment_classification

  # 도움말:
  python evals/run_eval.py --help

분리 원칙 (F21)
--------------
- pytest tests/ 실행 시 이 디렉토리의 어떤 것도 실행되지 않는다.
- pytest.ini의 testpaths = tests 설정으로 강제 분리.
- claude -p 호출은 run_eval.py의 _run_judge_live() 함수에만 존재한다.
- 결정적 로직(시나리오 파싱, 집계)은 stdlib only.

디렉토리 구조
------------
  evals/
    __init__.py             — 이 파일 (목적/사용법 문서)
    run_eval.py             — 라이브 eval 진입점
    scenarios/              — JSON 시나리오 파일
      comment_classification.json
      clustering_quality.json
      critic_consistency.json
    results/                — 실행 결과 JSON (gitignore 대상)
      .gitkeep

⚠️  주의: --live 실행 시 실제 API 크레딧이 소비됩니다.
"""
