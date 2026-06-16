"""skills/self-improve/scripts — deterministic glue runners for the self-improve loop.

Each runner module wraps one or more Wave 1 core functions
(hooks/lib/self_improve/) with the filesystem and state-I/O concerns
needed by the SKILL.md loop phases.

Modules:
  cursor_runner   — Phase A: load retro-state + call get_new_entries
  precheck_runner — Phase C: is_protected + classify_tier + run_prechecks
  apply_writer    — Phase D: write project-tier changes + harness proposals
  cap_runner      — Phase D: apply 5-entry cap + truncation report
  skill_scanner   — Phase C/F19: glob SKILL.md files + description dedup

All modules are stdlib-only, no network, no LLM.  Fail-safe: no unhandled
raises propagate to callers.
"""
