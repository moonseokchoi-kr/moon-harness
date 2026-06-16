"""Recurrence counter + cross-project detector (spec F16).

Two public functions:

``count_signals(entries)``
    Aggregate entries by cluster key and, within each cluster, count how many
    times each distinct repo appears.  Returns a dict of the shape::

        {
            cluster_key: {
                "same_repo": int,          # total entry count for this cluster
                "cross_repo_set": set[str] # distinct repo IDs seen
            },
            ...
        }

``has_cross_project(counter_result, cluster_key)``
    Return True if the cluster has been observed in **two or more distinct
    repos** (F16 cross-project criterion for harness-tier promotion).

Cluster key derivation:
    The cluster key is taken from the ``domain`` provenance field when present.
    If ``domain`` is absent or empty, the cluster key falls back to the raw
    entry ``marker`` string.  This keeps the function deterministic and
    LLM-free while still grouping related entries.

All functions are pure, deterministic, stdlib-only (F20).  No file I/O, no
network, no LLM calls, no raises (fail-safe).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from hooks.lib.self_improve.parser import extract_provenance


def _cluster_key_for(entry: Dict[str, Any]) -> str:
    """Derive a stable cluster key from an entry dict.

    Priority:
    1. ``tags.domain`` (most specific semantic grouping).
    2. ``marker`` (fallback when domain is absent).
    3. ``"unknown"`` (final fallback so we never return an empty key).
    """
    prov = extract_provenance(entry)
    domain: Optional[str] = prov.get("domain")
    if domain:
        return domain

    marker = entry.get("marker")
    if isinstance(marker, str) and marker:
        return marker

    return "unknown"


def count_signals(
    entries: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Aggregate entries into per-cluster recurrence counters.

    Args:
        entries: list of entry dicts as returned by ``parse_learning_entry``.
                 Non-list or non-dict elements are silently skipped (fail-safe).

    Returns:
        A dict mapping cluster_key → ``{"same_repo": int, "cross_repo_set": set}``.
        ``same_repo`` counts the total number of entries in the cluster.
        ``cross_repo_set`` is the set of distinct ``provenance_repo`` values
        seen; entries without a repo contribute the sentinel ``"__unknown__"``
        so they still register in the count without polluting real repo IDs.
    """
    result: Dict[str, Dict[str, Any]] = {}

    if not isinstance(entries, list):
        return result

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        key = _cluster_key_for(entry)
        prov = extract_provenance(entry)
        repo: str = prov.get("provenance_repo") or "__unknown__"

        if key not in result:
            result[key] = {
                "same_repo": 0,
                "cross_repo_set": set(),
            }

        result[key]["same_repo"] += 1
        result[key]["cross_repo_set"].add(repo)

    return result


def has_cross_project(
    counter_result: Dict[str, Any],
    cluster_key: str,
) -> bool:
    """Return True if ``cluster_key`` has been observed in ≥2 distinct repos.

    A cluster with entries only from one repo (no matter how many times)
    does NOT qualify for harness-tier promotion (F16 Acceptance criterion:
    "단일 repo에서 5회 반복된 패턴이 하네스 티어로 자동 승격되지 않는다").

    Args:
        counter_result: the dict returned by ``count_signals``.
        cluster_key: the key to check.

    Returns:
        True iff the cluster's ``cross_repo_set`` contains ≥2 distinct repo
        identifiers, excluding the ``"__unknown__"`` sentinel (unknown-repo
        entries do not count as cross-project evidence).
    """
    if not isinstance(counter_result, dict):
        return False

    cluster = counter_result.get(cluster_key)
    if not isinstance(cluster, dict):
        return False

    repo_set: Set[str] = cluster.get("cross_repo_set", set())
    if not isinstance(repo_set, set):
        return False

    # Exclude the sentinel used for entries without a known repo.
    real_repos = {r for r in repo_set if r != "__unknown__"}
    return len(real_repos) >= 2
