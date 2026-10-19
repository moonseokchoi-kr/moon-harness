"""T-13: 버전 0.15.0, README/CLAUDE.md 단일 문서 흐름, 전체 정적 스캔 게이트 (F4,F6,F9,F11,F13,F14,F15)."""
import ast
import json
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCAN_ROOTS = ["skills", "agents", "hooks", ".claude-plugin", "README.md", "CLAUDE.md"]
EXCLUDED_PREFIX = "hooks/lib/kompound_snapshot/"
STOP_PIPELINE = "hooks/enforcement/stop-pipeline.py"
LEGACY_FUNCS = {"has_arch", "has_ui", "has_api", "has_context"}

FORBIDDEN_NAMES = [
    "ux-researcher",
    "sdd-ui-designer", "sdd-api-designer", "sdd-architect-reviewer", "sdd-context-manager",
    "ui-designer", "api-designer", "architect-reviewer", "context-manager",
]
PATH_PATTERNS = ["docs/sdd/design/", "docs/sdd/context/"]
F12_PATTERN = re.compile(r"docs/sdd/design/arch|Build Profile|arch 문서의 .*## 빌드 프로파일|taskmaster가 복사")
SIMPLE_PATTERN = re.compile(r"\bSIMPLE\b")


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _scan_files() -> list[Path]:
    files: list[Path] = []
    for entry in SCAN_ROOTS:
        base = ROOT / entry
        candidates = [base] if base.is_file() else sorted(base.rglob("*")) if base.is_dir() else []
        for p in candidates:
            if not p.is_file() or "__pycache__" in p.parts:
                continue
            rel = _rel(p)
            if rel.startswith(EXCLUDED_PREFIX) or p.suffix == ".pyc":
                continue
            files.append(p)
    return files


def _legacy_exempt_lines() -> set[int]:
    """stop-pipeline.py 의 구 라벨 호환 함수 정의 블록 줄 번호(함수 본문 위치 파싱)."""
    src = (ROOT / STOP_PIPELINE).read_text(encoding="utf-8")
    exempt: set[int] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.FunctionDef) and node.name in LEGACY_FUNCS:
            exempt.update(range(node.lineno, node.end_lineno + 1))
    return exempt


def _hits(matcher) -> list[str]:
    """matcher(line)->bool. 예외 블록 제외 후 'path:line' 목록."""
    exempt = _legacy_exempt_lines()
    out: list[str] = []
    for p in _scan_files():
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue  # 바이너리 제외
        rel = _rel(p)
        for no, line in enumerate(text.splitlines(), 1):
            if rel == STOP_PIPELINE and no in exempt:
                continue
            if matcher(line):
                out.append(f"{rel}:{no}: {line.strip()[:100]}")
    return out


# ---- 가드 ----
def test_scan_guard_nonempty_and_scoped():
    files = [_rel(p) for p in _scan_files()]
    assert len(files) > 20, "스캔 대상이 비정상적으로 적다(거짓 GREEN 방지)"
    assert "README.md" in files and "CLAUDE.md" in files
    assert any(f.startswith("skills/sdd/") for f in files)
    assert any(f.startswith("agents/") for f in files)
    assert STOP_PIPELINE in files
    assert not any(f.startswith(EXCLUDED_PREFIX) for f in files)
    assert not any("__pycache__" in f for f in files)


def test_legacy_exemption_is_exactly_four_function_blocks():
    exempt = _legacy_exempt_lines()
    src = (ROOT / STOP_PIPELINE).read_text(encoding="utf-8").splitlines()
    assert len(exempt) == 8, "has_arch/ui/api/context 4개 함수 def+return 각 2줄이어야 한다"
    for no in exempt:
        assert "docs/sdd/" in src[no - 1] or src[no - 1].lstrip().startswith("def has_")


# ---- 버전 (F15) ----
def test_plugin_json_version():
    data = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    assert data["version"] == "0.15.0"


def test_marketplace_json_version():
    data = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    assert data["metadata"]["version"] == "0.15.0"
    for plugin in data["plugins"]:
        assert plugin.get("version", "0.15.0") == "0.15.0"


# ---- README / CLAUDE.md (F14) ----
def _readme_pipeline_section() -> str:
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"^## 자동 파이프라인.*?(?=^---$|^## )", text, re.S | re.M)
    assert m, "README에 '자동 파이프라인' 절이 있어야 한다"
    return m.group(0)


def test_readme_gate_list_is_single_document_flow():
    section = _readme_pipeline_section()
    gate = next((l for l in section.splitlines() if "사용자 게이트" in l), None)
    assert gate, "사용자 게이트 줄이 있어야 한다"
    assert not re.search(r"arch|ui|api|design", gate), f"구 게이트 잔존: {gate}"
    assert "spec" in gate and "plan" in gate


def test_claude_md_docs_row_is_spec_task_result():
    row = next((l for l in (ROOT / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
                if l.startswith("| `docs/sdd/`")), None)
    assert row, "docs/sdd/ 행이 있어야 한다"
    assert "spec/task/result" in row
    assert "design" not in row


# ---- 전체 스캔 (F4,F6,F9,F11,F12) ----
@pytest.mark.parametrize("name", FORBIDDEN_NAMES)
def test_no_removed_agent_or_ux_researcher_names(name):
    pat = re.compile(r"(?<![\w-])" + re.escape(name) + r"(?![\w-])") if not name.startswith("sdd-") and name != "ux-researcher" else re.compile(re.escape(name))
    hits = _hits(lambda l: bool(pat.search(l)))
    assert not hits, "\n".join(hits)


@pytest.mark.parametrize("needle", PATH_PATTERNS)
def test_no_legacy_doc_paths(needle):
    hits = _hits(lambda l: needle in l)
    assert not hits, "\n".join(hits)


def test_no_simple_design_mode():
    hits = _hits(lambda l: bool(SIMPLE_PATTERN.search(l)))
    assert not hits, "\n".join(hits)


def test_no_f12_patterns():
    hits = _hits(lambda l: bool(F12_PATTERN.search(l)))
    assert not hits, "\n".join(hits)


# ---- 줄 수 / 무변경 (F3,F13,F15) ----
def test_sdd_skill_line_budget():
    n = len((ROOT / "skills/sdd/SKILL.md").read_text(encoding="utf-8").splitlines())
    assert n <= 671, f"skills/sdd/SKILL.md {n}줄"


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def test_untouched_paths_unchanged_vs_main():
    base = _git("merge-base", "HEAD", "main")
    if base.returncode != 0 or not base.stdout.strip():
        pytest.skip("main merge-base 없음")
    paths = ["hooks/enforcement/e2e-gate.sh", "hooks/hooks.json",
             "hooks/lib/code_mapper/", "hooks/lib/kompound_snapshot/"]
    diff = _git("diff", "--name-only", base.stdout.strip(), "--", *paths)
    assert diff.returncode == 0, diff.stderr
    assert diff.stdout.strip() == "", f"무변경 대상 변경됨:\n{diff.stdout}"
