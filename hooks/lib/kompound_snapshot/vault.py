"""hooks/lib/kompound_snapshot/vault.py — kompound v2 볼트 레이아웃 계약 (단일 진실).

2026-10-07 kompound가 v1(`marvelous_kompound`, flat ``raw/`` + ``wiki/``, frontmatter
없음)에서 v2(`moon_kompound`, cmds-llm-wiki Obsidian 레이아웃)로 이관됐다. 이 모듈은
"v2 볼트의 어디에 무엇이 있는가"와 "박제 raw 한 장의 모양"을 한곳에 모은다 —
다른 모듈(apply/verify/cli/config)은 경로·형식을 직접 하드코딩하지 않고 여기서
가져다 쓴다.

## 경로 (볼트 루트 기준, 공백·``&`` 포함 — 항상 pathlib/인자 리스트로 다룬다)

| 무엇 | 경로 |
|---|---|
| raw 루트 | ``10. Raw Sources/`` (유형 → 도메인 2단: ``<NN. Type>/<Domain>/``) |
| 박제 raw 신규 위치 | ``10. Raw Sources/17. Specs/<Domain>/<YYYY-MM-DD>-<slug>.md`` |
| registry | ``20. Wiki/24. Maps/SDD Spec Registry.md`` |
| index | ``index.md`` (볼트 루트) |
| log | ``log.md`` (볼트 루트) |

``<slug>`` = ``<project>-<feature>-<kind>`` (v1 raw 파일명 stem과 동일). 박제 raw의
**raw 이름**(Obsidian wikilink 대상) = 파일 stem = ``<YYYY-MM-DD>-<slug>``.

## 기존 raw 찾기 (dedup/멱등의 근거)

같은 ``<slug>``의 raw는 ``10. Raw Sources/`` 아래 **어디에 있든** 찾아서 그 파일을
in-place 갱신한다(파일명·날짜·도메인 유지) — 두 번째 사본을 만들지 않는다.
매칭 규칙: 파일 stem이 ``<YYYY-MM-DD>-<slug>`` 이거나, frontmatter에
``legacySlug: <slug>`` 가 있다(v1 이관분). 둘 다 없으면 신규.

## raw 한 장의 모양 (v2 raw-source)

frontmatter → ``# <H1>`` → ``> [!info] Source`` callout → ``## Original Content``
(원본 문서 본문 verbatim, 원본 H1 줄은 파일 H1으로 올라간다) → ``## Metadata``.
갱신 시에는 ``## Original Content`` 본문만 교체하고 frontmatter의 ``date
modified``만 오늘로 올린다 — 사람이 고친 description/tags/Metadata는 보존된다.

이 모듈의 공개 함수는 예외를 던지지 않는 것을 원칙으로 하되, 텍스트 렌더링 같은
순수 함수는 입력이 문자열인 한 실패 경로가 없다. 파일시스템 탐색 함수는 OSError를
흡수한다(fail-safe, 패키지 공통 규약).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Iterator, List, Mapping, Optional, Tuple, Union

__all__ = [
    "RAW_ROOT",
    "SPECS_DIR",
    "REGISTRY_RELATIVE",
    "INDEX_RELATIVE",
    "LOG_RELATIVE",
    "WIKI_ROOT",
    "DOMAINS",
    "DEFAULT_DOMAIN_MAP",
    "FALLBACK_DOMAIN",
    "domain_for_project",
    "domain_tag",
    "slug_of",
    "raw_stem",
    "iter_raw_files",
    "build_raw_index",
    "find_raw",
    "new_raw_path",
    "split_source_doc",
    "render_raw",
    "extract_original_content",
    "replace_original_content",
    "is_vault",
    "is_v1_layout",
]

PathLike = Union[str, "Path"]

# ── 경로 상수 ────────────────────────────────────────────────────────────────
RAW_ROOT = Path("10. Raw Sources")
SPECS_DIR = RAW_ROOT / "17. Specs"
WIKI_ROOT = Path("20. Wiki")
REGISTRY_RELATIVE = WIKI_ROOT / "24. Maps" / "SDD Spec Registry.md"
INDEX_RELATIVE = Path("index.md")
LOG_RELATIVE = Path("log.md")

# ── 도메인 (볼트 CLAUDE.md "Moon Kompound Local Rules" — 철자 그대로 10종) ──
DOMAINS: Tuple[str, ...] = (
    "Pattern API",
    "CloCV",
    "CEF & WebView",
    "WebGPU & WASM",
    "CLOFab",
    "Rendering",
    "Marvelous App",
    "Build & Test",
    "AI Harness",
    "Org & Process",
)

# 프로젝트 프리픽스(config.DEFAULT_PREFIX_MAP의 값) → 신규 박제 raw의 기본 도메인.
# 데이터로 보유한다 — 설정 파일의 ``domain_map``으로 키 단위 오버라이드할 수 있다
# (config.resolve_config). 이미 존재하는 raw는 이 값과 무관하게 제자리에서 갱신된다
# (예: Pattern API 도메인에 있는 marvelous-* raw는 거기 그대로 남는다).
DEFAULT_DOMAIN_MAP: Dict[str, str] = {
    "marvelous": "Marvelous App",
    "clofab": "CLOFab",
    "graphify": "AI Harness",
    "autofix": "AI Harness",
    "crashai": "AI Harness",
    "codegraph": "AI Harness",
    "aireview": "AI Harness",
    "harness": "AI Harness",
    "rein": "AI Harness",
    "slack": "AI Harness",
}

# 매핑에 없는 프리픽스(사용자가 prefix_map으로 새 프로젝트를 추가했지만
# domain_map은 안 준 경우)의 기본 도메인. 하네스가 박제하는 SDD 문서의 대다수가
# 도구·자동화 프로젝트이므로 AI Harness로 둔다.
FALLBACK_DOMAIN = "AI Harness"

_PURPOSE_AXIS_HARNESS = "AI 하네스·자동화"
_PURPOSE_AXIS_MARVELOUS = "Marvelous 개발"

_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")
_LEGACY_SLUG_RE = re.compile(r"^legacySlug:\s*\"?([^\"\s]+)\"?\s*$", re.MULTILINE)
_DATE_MODIFIED_RE = re.compile(r"^date modified:.*$", re.MULTILINE)

_ORIGINAL_HEADING = "## Original Content"
_METADATA_HEADING = "## Metadata"


# ── 도메인 ───────────────────────────────────────────────────────────────────


def domain_for_project(project: str, domain_map: Optional[Mapping[str, Optional[str]]] = None) -> str:
    """프리픽스 → 도메인. ``domain_map``(병합 결과)에 유효한 값이 없으면
    ``DEFAULT_DOMAIN_MAP`` → ``FALLBACK_DOMAIN`` 순. 알 수 없는 도메인 문자열은
    받아들이지 않는다(볼트 규칙: 도메인 10종 고정)."""
    for source in (domain_map or {}, DEFAULT_DOMAIN_MAP):
        try:
            value = source.get(project)
        except AttributeError:
            value = None
        if value in DOMAINS:
            return value  # type: ignore[return-value]
    return FALLBACK_DOMAIN


def domain_tag(domain: str) -> str:
    """``"CEF & WebView"`` → ``"cef-webview"`` (볼트 실측 태그 규칙)."""
    tag = domain.lower().replace("&", " ")
    tag = re.sub(r"[^a-z0-9]+", "-", tag).strip("-")
    return tag


def _purpose_axis(domain: str) -> str:
    return _PURPOSE_AXIS_HARNESS if domain == "AI Harness" else _PURPOSE_AXIS_MARVELOUS


# ── 이름 ─────────────────────────────────────────────────────────────────────


def slug_of(name: str) -> str:
    """raw 파일명/stem/경로 → ``<slug>`` (``.md``와 ``YYYY-MM-DD-`` 접두 제거)."""
    stem = Path(str(name)).name
    if stem.endswith(".md"):
        stem = stem[: -len(".md")]
    return _DATE_PREFIX_RE.sub("", stem)


def raw_stem(date: str, slug: str) -> str:
    return f"{date}-{slug}"


# ── 탐색 ─────────────────────────────────────────────────────────────────────


def iter_raw_files(kompound_repo: PathLike) -> Iterator[Path]:
    """``10. Raw Sources/`` 아래 모든 ``*.md``(dot-dir 제외)를 결정적 순서로 낸다."""
    root = Path(kompound_repo) / RAW_ROOT
    if not root.is_dir():
        return
    found: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _e: None):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        for fname in filenames:
            if fname.endswith(".md") and not fname.startswith("."):
                found.append(Path(dirpath) / fname)
    for path in sorted(found):
        yield path


def _read_legacy_slug(path: Path) -> Optional[str]:
    """frontmatter(첫 ``---`` 블록)에서 ``legacySlug``를 읽는다. 없으면 None."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            first = fh.readline()
            if first.strip() != "---":
                return None
            lines: List[str] = []
            for _ in range(200):
                line = fh.readline()
                if not line or line.strip() == "---":
                    break
                lines.append(line)
    except OSError:
        return None
    match = _LEGACY_SLUG_RE.search("".join(lines))
    return match.group(1) if match else None


def build_raw_index(kompound_repo: PathLike) -> Dict[str, Path]:
    """``{<slug>: Path}`` — 같은 slug의 기존 raw를 어디서든 찾기 위한 색인.

    1순위: 파일 stem이 ``YYYY-MM-DD-<slug>`` (날짜 접두가 있어야 한다 — 날짜 없는
    파일은 이 볼트의 raw 규칙 밖이다). 2순위: frontmatter ``legacySlug``(파일명
    매칭이 없는 slug에만 채운다). 같은 slug가 여러 파일이면 정렬상 첫 파일
    (결정적) — 그 중복 자체는 verify 게이트(2)가 드러낸다.
    """
    by_name: Dict[str, Path] = {}
    by_legacy: Dict[str, Path] = {}
    for path in iter_raw_files(kompound_repo):
        stem = path.stem
        if _DATE_PREFIX_RE.match(stem):
            by_name.setdefault(slug_of(stem), path)
        legacy = _read_legacy_slug(path)
        if legacy:
            by_legacy.setdefault(legacy, path)
    index = dict(by_legacy)
    index.update(by_name)
    return index


def find_raw(kompound_repo: PathLike, slug: str) -> Optional[Path]:
    return build_raw_index(kompound_repo).get(slug)


def new_raw_path(kompound_repo: PathLike, domain: str, date: str, slug: str) -> Path:
    return Path(kompound_repo) / SPECS_DIR / domain / f"{raw_stem(date, slug)}.md"


# ── 렌더링 ───────────────────────────────────────────────────────────────────


def split_source_doc(source_text: str) -> Tuple[Optional[str], str]:
    """원본 SDD 문서 → ``(H1 텍스트 | None, 본문)``.

    첫 비어있지 않은 줄이 ``# ``로 시작하면 그 줄을 H1으로 떼어내고(파일 H1으로
    올라간다 — v1 이관 raw와 같은 규칙: Original Content = "H1 뒤 본문"), 바로
    뒤의 빈 줄들도 떼어낸다. 본문 끝의 개행은 정규화(제거)한다 — 렌더링이
    정확히 한 번의 구분 개행을 붙인다.
    """
    text = source_text.replace("\r\n", "\n")
    lines = text.split("\n")
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    title: Optional[str] = None
    if i < len(lines) and lines[i].startswith("# "):
        title = lines[i][2:].strip() or None
        i += 1
        while i < len(lines) and lines[i].strip() == "":
            i += 1
        body = "\n".join(lines[i:])
    else:
        body = text
    return title, body.rstrip("\n")


def _yaml_str(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_raw(
    *,
    slug: str,
    project: str,
    feature: str,
    kind: str,
    domain: str,
    date: str,
    source_text: str,
    source_label: str,
    worktree: Optional[str] = None,
    md5: Optional[str] = None,
) -> str:
    """신규 박제 raw 한 장(v2 raw-source 형식)을 렌더링한다. 순수 함수.

    description은 결정적 영어 템플릿이다(이 훅은 문장을 "작성"하지 않는다 —
    arch §1 원칙 2). 필요하면 사람이 나중에 다듬는다(갱신 시 보존된다).
    """
    title, body = split_source_doc(source_text)
    if not title:
        title = f"{feature} {kind}"
    kind_label = kind
    origin = source_label + (f" (worktree `{worktree}`)" if worktree else "")
    fm = [
        "---",
        "type: raw-source",
        "aliases:",
        f"  - {_yaml_str(title)}",
        f"  - {_yaml_str(slug)}",
        f"description: {_yaml_str(f'SDD {kind_label} snapshot of {project} {feature}.')}",
        "author:",
        '  - "[[Moon]]"',
        '  - "Claude"',
        "model: unknown",
        "effort: default",
        f"date created: {date}",
        f"date modified: {date}",
        f"date ingested: {date}",
        "tags:",
        '  - "raw-source"',
        f"  - {_yaml_str(domain_tag(domain))}",
        '  - "sdd"',
        f"  - {_yaml_str(kind_label)}",
        '  - "snapshot"',
        f"source: {_yaml_str(origin)}",
        'category: "Specs"',
        f"domain: {_yaml_str(domain)}",
        f"collectionPurpose: {_yaml_str(f'{_purpose_axis(domain)} — SDD {kind_label} 스냅샷 보존')}",
        "status: ingested",
        "---",
    ]
    meta = [
        f"- **인제스트 일시**: {date}",
        "- **인제스트 경로**: moon-harness kompound-snapshot 훅 (자동 박제, verbatim)",
        f"- **원본 경로**: `{origin}`",
        f"- **SDD 종류**: {kind_label}",
    ]
    if md5:
        meta.append(f"- **원본 md5 (최초 박제 시점)**: `{md5}`")
    meta += ["- **원본 형태**: Markdown"]
    parts = [
        "\n".join(fm),
        "",
        f"# {title}",
        "",
        "> [!info] Source",
        f"> 원본 출처: {origin} — kompound-snapshot 훅 자동 박제 ({date})",
        "",
        "---",
        "",
        _ORIGINAL_HEADING,
        "",
        body,
        "",
        "---",
        "",
        _METADATA_HEADING,
        "",
        "\n".join(meta),
        "",
    ]
    return "\n".join(parts)


def _original_span(text: str) -> Optional[Tuple[int, int]]:
    """``## Original Content`` 본문의 ``(start, end)`` 문자 오프셋.

    start = 헤딩 다음 빈 줄들 뒤, end = 마지막 ``## Metadata`` 헤딩 앞의
    ``---`` 구분선(과 주변 빈 줄) 앞. 구조를 못 찾으면 None.
    """
    m = re.search(r"^## Original Content[ \t]*$", text, re.MULTILINE)
    if not m:
        return None
    start = m.end()
    while start < len(text) and text[start] in "\r\n":
        start += 1
    metas = [mm.start() for mm in re.finditer(r"^## Metadata[ \t]*$", text, re.MULTILINE) if mm.start() >= start]
    end = metas[-1] if metas else len(text)
    tail = text[start:end]
    tail_stripped = tail.rstrip()
    if tail_stripped.endswith("---"):
        tail_stripped = tail_stripped[: -len("---")].rstrip("\n")
    else:
        tail_stripped = tail.rstrip("\n")
    return start, start + len(tail_stripped)


def extract_original_content(text: str) -> Optional[str]:
    """raw 텍스트에서 ``## Original Content`` 본문을 꺼낸다. 없으면 None."""
    span = _original_span(text)
    if span is None:
        return None
    return text[span[0] : span[1]]


def replace_original_content(text: str, new_body: str, *, date_modified: Optional[str] = None) -> Optional[str]:
    """``## Original Content`` 본문만 ``new_body``로 교체한 새 텍스트. 구조가 없으면
    None(호출자가 실패로 보고 — 사람이 만든 파일을 통째로 덮어쓰지 않는다).
    ``date_modified``가 주어지면 frontmatter의 ``date modified:`` 줄도 갱신한다."""
    span = _original_span(text)
    if span is None:
        return None
    out = text[: span[0]] + new_body + text[span[1] :]
    if date_modified:
        fm_end = _frontmatter_end(out)
        if fm_end is not None:
            head, rest = out[:fm_end], out[fm_end:]
            head = _DATE_MODIFIED_RE.sub(f"date modified: {date_modified}", head, count=1)
            out = head + rest
    return out


def _frontmatter_end(text: str) -> Optional[int]:
    if not text.startswith("---"):
        return None
    m = re.search(r"^---[ \t]*$", text[3:], re.MULTILINE)
    if not m:
        return None
    return 3 + m.end()


# ── 볼트 식별 ────────────────────────────────────────────────────────────────


def is_vault(candidate: PathLike) -> bool:
    """v2 볼트 서명 — git 저장소 + ``10. Raw Sources/`` + ``20. Wiki/`` +
    루트 ``index.md``·``log.md``. 이름이 아니라 구조로 식별한다."""
    try:
        c = Path(candidate)
        return (
            c.is_dir()
            and (c / ".git").exists()
            and (c / RAW_ROOT).is_dir()
            and (c / WIKI_ROOT).is_dir()
            and (c / INDEX_RELATIVE).is_file()
            and (c / LOG_RELATIVE).is_file()
        )
    except OSError:
        return False


def is_v1_layout(candidate: PathLike) -> bool:
    """v1(flat ``raw/`` + ``wiki/index.md``) 레이아웃인가 — 진단 메시지용."""
    try:
        c = Path(candidate)
        return (c / "raw").is_dir() and (c / "wiki" / "index.md").is_file()
    except OSError:
        return False
