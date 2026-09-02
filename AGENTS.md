# AGENTS.md

This repository distributes the **adderall** agent skill: ponytail's laziest-solution ladder merged with i-have-adhd's action-first output shaping.

## What is here

- `skills/adderall/SKILL.md` — the core skill. This is the file that matters.
- `skills/adderall-review/`, `adderall-audit/`, `adderall-debt/`, `adderall-help/` — optional sub-skills (diff review for over-engineering, whole-repo audit, debt ledger, reference card).
- `.claude-plugin/` — Claude Code plugin manifest (`/plugin marketplace add spencerthayer/adderall`).
- `.codex-plugin/` + `commands/*.toml` — Codex plugin manifest and prompt commands.
- `.cursor/skills/` — Cursor copies of every skill (verbatim, synced by `scripts/check-copies.py`).
- `.agents/skills/` + `.agents/rules/` + `.agents/plugins/` — generic agent-standard copies, an always-on condensed rule, and a marketplace manifest.
- `pi-extension/` — pi coding-agent extension: mode switching, status indicator, per-turn system-prompt injection.
- `.opencode/` + `opencode.json` — OpenCode plugin (always-on + slash commands) and the command files.
- `hooks/` — always-on injection (Node + POSIX + PowerShell) and the shared config/instruction builders used by the pi extension.
- `examples/` — before/after model output for 11 everyday tasks.
- `evals/` + `scripts/` — paired, blind-judged eval harness (`python3 scripts/run_evals.py validate`); `scripts/check-copies.py` verifies the platform copies match `skills/`.

## Install (as an agent)

1. Fetch the files from this repo.
2. Copy `skills/adderall/SKILL.md` into the target's skills directory, preserving the folder name `adderall`:
   - Claude Code: `~/.claude/skills/adderall/SKILL.md`
   - OpenCode: `~/.config/opencode/skills/adderall/SKILL.md` (or `.opencode/skills/adderall/SKILL.md` per project)
   - Cursor: `.cursor/skills/adderall/SKILL.md`
   - Codex, pi, and generic agents: `.agents/skills/adderall/SKILL.md`
3. Copy `skills/adderall-review/`, `skills/adderall-audit/`, and `skills/adderall-debt/` alongside it if the host supports multiple skills.
4. For always-on activation, see INSTALL.md (flag file + SessionStart hook, or the OpenCode plugin).
5. Restart or reload the session, then confirm the skill is discoverable. It activates on coding tasks or the trigger words listed in its frontmatter description.

## Repo conventions

- `skills/adderall/SKILL.md` is the single source of truth for the ruleset. The hooks, plugin, pi extension, and eval harness all read it directly and strip its frontmatter — do not fork the ruleset into copies.
- `.cursor/skills/` and `.agents/skills/` hold verbatim copies for hosts that only read their own directory. Run `python3 scripts/check-copies.py` (or `--fix`) after editing any skill.
- Deliberate shortcuts in this repo are marked `adderall:` with a ceiling and upgrade path (`# adderall: O(n²) scan, index if the corpus grows`).
- Changes to the ruleset should ship with updated eval cases (`evals/cases.jsonl`); run the release gate in `evals/README.md` before publishing claims about behavior.
