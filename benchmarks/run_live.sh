#!/usr/bin/env bash
# benchmarks/run_live.sh — 라이브 벤치 실행 진입점
#
# 역할:
#   1. claude -p 헤드리스 실행으로 transcript를 생성한다 (라이브 eval 레이어).
#   2. 생성된 transcript를 임시 파일에 저장한다.
#   3. bench_runner.py (결정적 산술)로 점수를 계산한다.
#
# 분리 원칙 (F21):
#   - 이 스크립트는 pytest tests/ 스위트에 포함되지 않는다.
#   - claude -p 호출(네트워크/LLM)은 이 셸 레이어에만 존재한다.
#   - bench_runner.py는 순수 산술만 담당하며 네트워크 호출 없음.
#
# 사용법:
#   ./benchmarks/run_live.sh [--baseline | --candidate <skill_path>]
#
# 옵션:
#   --baseline               baseline(OFF) 점수만 측정
#   --candidate <path>       지정 스킬로 candidate(ON) 점수 측정
#   --train-set <path>       train 셋 경로 (기본: benchmarks/sets/train)
#   --held-out-set <path>    held-out 셋 경로 (기본: benchmarks/sets/held-out)
#   --output <path>          결과 JSON 출력 경로 (기본: /tmp/bench_result.json)
#
# 주의:
#   - 이 스크립트를 직접 실행하려면 claude CLI가 PATH에 있어야 한다.
#   - CI 환경에서는 별도 단계(live-eval stage)로 실행한다. pytest tests/ 에서 호출하지 않는다.

set -euo pipefail

# ── 기본값 ──────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

TRAIN_SET="${REPO_ROOT}/benchmarks/sets/train"
HELD_OUT_SET="${REPO_ROOT}/benchmarks/sets/held-out"
OUTPUT_PATH="/tmp/bench_result_$(date +%s).json"
MODE="baseline"
SKILL_PATH=""

# ── 인자 파싱 ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --baseline)
            MODE="baseline"
            shift
            ;;
        --candidate)
            MODE="candidate"
            SKILL_PATH="${2:-}"
            shift 2
            ;;
        --train-set)
            TRAIN_SET="${2:-}"
            shift 2
            ;;
        --held-out-set)
            HELD_OUT_SET="${2:-}"
            shift 2
            ;;
        --output)
            OUTPUT_PATH="${2:-}"
            shift 2
            ;;
        -h|--help)
            head -40 "$0" | grep '^#' | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "알 수 없는 옵션: $1" >&2
            exit 1
            ;;
    esac
done

# ── 환경 확인 ────────────────────────────────────────────────────────────────
log() { echo "[run_live] $*"; }

if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 를 찾을 수 없습니다." >&2
    exit 1
fi

# ── transcript 생성 (claude -p 호출 레이어) ──────────────────────────────────
# NOTE: 실제 운영 시 아래 주석을 해제하고 케이스별 프롬프트를 구성한다.
# 현재는 스켈레톤 — live eval 통합 시 구현 완성.
#
# TRANSCRIPT_DIR="$(mktemp -d)"
# for case_file in "${TRAIN_SET}"/*.json; do
#     case_id="$(jq -r .id "${case_file}")"
#     prompt_file="${SCRIPT_DIR}/prompts/eval_prompt.md"
#     transcript_path="${TRANSCRIPT_DIR}/${case_id}.md"
#
#     log "케이스 ${case_id} transcript 생성 중..."
#     claude -p "$(cat "${prompt_file}")" \
#         --input "$(cat "${case_file}")" \
#         --output "${transcript_path}" \
#         || { log "WARNING: ${case_id} transcript 생성 실패, 건너뜀"; continue; }
# done

# ── 점수 계산 (bench_runner.py — 결정적 산술 레이어) ──────────────────────────
log "점수 계산 시작 (mode=${MODE})"

BENCH_SCRIPT="${REPO_ROOT}/hooks/lib/self_improve/bench_runner.py"

python3 - <<PYEOF
import json
import sys
from pathlib import Path

sys.path.insert(0, "${REPO_ROOT}")

from hooks.lib.self_improve.bench_runner import (
    score_baseline,
    score_candidate,
    compute_delta,
    is_adoptable,
    gate_adoption,
)

train_set = Path("${TRAIN_SET}")
held_out_set = Path("${HELD_OUT_SET}")
mode = "${MODE}"

# baseline 측정
baseline_train = score_baseline(train_set)
baseline_held = score_baseline(held_out_set)

if mode == "baseline":
    result = {
        "mode": "baseline",
        "train": baseline_train,
        "held_out": baseline_held,
    }
else:
    # candidate 모드: 실제 candidate_fn은 claude -p transcript 결과를
    # 파싱하여 outcome을 반환하는 함수로 교체한다.
    # 현재 스켈레톤: baseline_fn(항상 레이블 그대로 반환)
    def candidate_fn(inp):
        return inp.get("status", "CONVERGED")  # placeholder

    candidate_train = score_candidate(train_set, candidate_fn)
    candidate_held = score_candidate(held_out_set, candidate_fn)

    delta_train = compute_delta(baseline_train, candidate_train)
    delta_held = compute_delta(baseline_held, candidate_held)

    # held-out 회귀는 delta_held를 기준으로 판정 (F22/F24: cold_start 포함 검사)
    adoptable = gate_adoption(delta_train, delta_held)

    result = {
        "mode": "candidate",
        "skill_path": "${SKILL_PATH}",
        "train": {
            "baseline": baseline_train,
            "candidate": candidate_train,
            "delta": delta_train,
        },
        "held_out": {
            "baseline": baseline_held,
            "candidate": candidate_held,
            "delta": delta_held,
        },
        "adoptable": adoptable,
        "summary": (
            "ADOPTABLE" if adoptable
            else ("COLD_START" if delta_train.get("cold_start") else "NOT_ADOPTABLE")
        ),
    }

output_path = "${OUTPUT_PATH}"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2, ensure_ascii=False)

print(f"결과 저장: {output_path}")
print(f"요약: {result.get('summary', result.get('mode'))}")
if result.get("adoptable") is not None:
    print(f"채택 가능: {result['adoptable']}")
PYEOF

log "완료. 결과: ${OUTPUT_PATH}"
