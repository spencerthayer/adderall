# Install

## Claude Code

Either use the plugin marketplace:

```
/plugin marketplace add spencerthayer/adderall
/plugin install adderall@adderall
```

Or copy the skills directly:

```bash
git clone https://github.com/spencerthayer/adderall
mkdir -p ~/.claude/skills
cp -r adderall/skills/* ~/.claude/skills/
```

Sub-skills (`adderall-review`, `adderall-audit`, `adderall-debt`, `adderall-help`) are separate skills; copy all of them or just `adderall`.

## OpenCode

1. Copy the skills into your config:
   ```bash
   git clone https://github.com/spencerthayer/adderall
   mkdir -p ~/.config/opencode/skills
   cp -r adderall/skills/* ~/.config/opencode/skills/
   ```
2. Optionally register the plugin (always-on injection + slash commands): add to `opencode.json`:
   ```json
   { "plugin": ["<path-to-adderall>/.opencode/plugins/adderall.mjs"] }
   ```
   Cloning the repo at the project root is enough — the bundled `opencode.json` registers it.
3. Restart or reload the session, then confirm the skill is discoverable. It activates on coding tasks, on `/adderall`, or on the trigger words listed in its frontmatter description.

## Cursor

Copy the skill copies into the project (Cursor reads `.cursor/skills/`):

```bash
git clone https://github.com/spencerthayer/adderall
mkdir -p .cursor/skills
cp -r adderall/.cursor/skills/* .cursor/skills/
```

## Codex

1. Copy the skills into place: `.agents/skills/` (Codex reads the generic agent-standard directory):
   ```bash
   git clone https://github.com/spencerthayer/adderall
   mkdir -p .agents/skills
   cp -r adderall/.agents/skills/* .agents/skills/
   ```
2. For the marketplace metadata, `.codex-plugin/plugin.json` ships in the repo; the prompt commands live in `commands/*.toml`.
3. Codex has no slash-command skills, so invoke by asking: "Use adderall for this task."

## pi

```bash
pi install <path-or-url-to-adderall>/pi-extension
```

Or copy `pi-extension/` and the `hooks/adderall-*.js` modules it requires. The extension registers `/adderall lite|full|ultra|off`, `/adderall status`, `/adderall default <mode>`, and the `/adderall-review` / `/adderall-audit` / `/adderall-debt` / `/adderall-help` aliases, shows a status-bar indicator, and injects the ruleset into the system prompt at the active level every turn. It reads `skills/adderall/SKILL.md` directly, so the ruleset always matches the source.

## Any other agent

Point your agent at this repo and ask it to install from `AGENTS.md`:

```text
Install the adderall skill from https://github.com/spencerthayer/adderall, refer to the repo's AGENTS.md for instructions.
```

The generic layout is `.agents/skills/adderall/SKILL.md`; `.agents/rules/adderall.md` is a condensed, always-on version of the ruleset for agents that apply rules files automatically.

### Always-on (Claude Code / OpenCode)

The skill's ruleset persists per session once invoked, but it only loads when invoked. To inject it into every session without asking:

```bash
touch ~/.claude/.adderall-always          # Claude Code / Codex
touch ~/.config/opencode/.adderall-always # OpenCode
```

and wire the SessionStart hook from `hooks/hooks.json` (requires `node` on PATH). `hooks/always-on.sh` and `hooks/always-on.ps1` are POSIX and PowerShell fallbacks for environments without Node. With the OpenCode plugin registered, the flag alone is enough.

Remove the flag file to turn always-on off for good. Say "stop adderall" to turn it off for one session.

## Evals (optional)

The eval harness needs Python 3.10+ and a metered runner CLI (`claude` or `codex`). See `evals/README.md`. After editing any skill, run `python3 scripts/check-copies.py --fix` to sync the `.cursor/` and `.agents/` copies.
