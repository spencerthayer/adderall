---
name: adderall-help
description: >
  Quick-reference card for all adderall modes, skills, and commands.
  One-shot display, not a persistent mode. Trigger: /adderall-help,
  "adderall help", "what adderall commands", "how do I use adderall".
---

# Adderall Help

Display this reference card when invoked. One-shot, do NOT change mode,
write flag files, or persist anything.

## Levels

| Level | Trigger | What changes |
|-------|---------|-------------|
| **Lite** | `/adderall lite` | Build what's asked, name the lazier alternative in one line. Full sentences allowed. |
| **Full** | `/adderall` | The ladder + output rules enforced. Default. |
| **Ultra** | `/adderall ultra` | YAGNI extremist. One code block, one skipped-line, one next action. |

Level sticks until changed or session end.

## Dosages

Adherence is a tunable parameter, the way temperature tunes sampling. Seven
doses set how literally the ruleset (and any target skill) is followed:

| Dose | Adherence | Flexibility | Band |
|-------|-----------|-------------|-------|
| 5mg | 0.10 | 0.90 | lite |
| 7.5mg | 0.25 | 0.75 | lite |
| 10mg | 0.50 | 0.50 | full (default) |
| 12.5mg | 0.70 | 0.30 | full |
| 15mg | 0.85 | 0.15 | full |
| 20mg | 0.95 | 0.05 | ultra |
| 30mg | 1.00 | 0.00 | ultra |

A dose can also lens another skill: `/adderall-15mg /<target-skill> <task>`
keeps adderall's build, report, and voice rules active underneath while
tuning how literally the target skill is followed. The target skill may not
override system, user, platform, permission, or dosage instructions. Missing
target skills are asked about, never invented.

## Skills

| Skill | Trigger | What it does |
|-------|---------|--------------|
| **adderall** | `/adderall` | Focus mode itself. Laziest solution that works, reported action-first. |
| **adderall-review** | `/adderall-review` | Over-engineering review of a diff: `L42: yagni: factory, one product. Inline.` |
| **adderall-audit** | `/adderall-audit` | Whole-repo over-engineering audit: ranked list of what to delete. |
| **adderall-debt** | `/adderall-debt` | Harvest `adderall:` shortcut comments into a tracked ledger. |
| **adderall-help** | `/adderall-help` | This card. |

OpenCode ships all five as slash commands. Claude Code and Codex use the
`/adderall` skill form and the sub-skill names.

## Deactivate

Say "stop adderall" or "normal mode". Resume anytime with `/adderall`.

## Always-on

To make the ruleset active in every session without invoking anything:

```bash
touch ~/.claude/.adderall-always          # Claude Code / Codex
touch ~/.config/opencode/.adderall-always # OpenCode
```

Remove the flag file to turn it off for good.

## More

Full docs + examples: https://github.com/spencerthayer/adderall
