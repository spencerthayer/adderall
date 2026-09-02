// adderall — OpenCode plugin.
//
// The skill in `skills/adderall/SKILL.md` is the single source of truth for
// the ruleset.
//
//   • On demand   — registers the skills directory and the `/adderall`,
//                   `/adderall-audit`, `/adderall-review`, `/adderall-debt`
//                   commands so the ruleset applies for the rest of the session.
//   • Always-on   — when the opt-in flag file exists, the full ruleset is
//                   appended to the system prompt every turn.
//
// Opt in to always-on:   touch ~/.config/opencode/.adderall-always
// Opt back out:          rm ~/.config/opencode/.adderall-always
//
// Install — add to opencode.json:
//   { "plugin": ["./.opencode/plugins/adderall.mjs"] }

import fs from 'fs';
import os from 'os';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const skillsDir = path.resolve(__dirname, '../../skills');
const skillPath = path.join(skillsDir, 'adderall', 'SKILL.md');

// Always-on opt-in flag, mirroring Claude Code's ~/.claude/.adderall-always
// but under OpenCode's config dir so the two tools stay independent.
const flagPath = path.join(
  process.env.XDG_CONFIG_HOME || path.join(os.homedir(), '.config'),
  'opencode',
  '.adderall-always',
);

// Read SKILL.md and strip a leading YAML frontmatter block (--- ... ---).
function rulesetBody() {
  return fs
    .readFileSync(skillPath, 'utf8')
    .replace(/^---[^\S\r\n]*\r?\n[\s\S]*?\r?\n---[^\S\r\n]*(?:\r?\n|$)/, '')
    .replace(/(?:\r?\n)+$/, '');
}

// Minimal frontmatter parse for the command files: `---\ndescription: X\n---\nbody`.
function parseCommandFile(file) {
  const text = fs.readFileSync(file, 'utf8');
  const match = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/);
  if (!match) return { description: '', template: text.trim() };
  const description = (match[1].match(/^description:\s*(.+)$/m) || [, ''])[1].trim();
  return { description, template: match[2].trim() };
}

export default async () => {
  return {
    // Make the skills and slash commands discoverable.
    config: async (config) => {
      config.skills = config.skills || {};
      config.skills.paths = config.skills.paths || [];
      if (!config.skills.paths.includes(skillsDir)) config.skills.paths.push(skillsDir);

      if (!config.command) config.command = {};
      const commandDir = path.join(__dirname, '..', 'command');
      try {
        for (const file of fs.readdirSync(commandDir).filter((f) => f.endsWith('.md'))) {
          const name = path.basename(file, '.md');
          config.command[name] = parseCommandFile(path.join(commandDir, file));
        }
      } catch (e) {}
    },

    // Always-on: append the ruleset to the system prompt every turn while the
    // flag file exists. "stop adderall" turns it off for the session (the
    // model honours the skill's own Persistence rules); deleting the flag
    // turns always-on off for good.
    'experimental.chat.system.transform': async (_input, output) => {
      let on = false;
      try { on = fs.existsSync(flagPath); } catch (e) {}
      if (!on) return;

      let body;
      try { body = rulesetBody(); } catch (e) { return; }

      const header =
        'FOCUS MODE ACTIVE (always-on). The ruleset below applies to every ' +
        'response. "stop adderall" or "normal mode" turns it off for this ' +
        'session; delete ' + flagPath + ' to turn always-on off for good.';
      const injected = header + '\n\n' + body;

      if (output.system.length > 0) {
        output.system[output.system.length - 1] += '\n\n' + injected;
      } else {
        output.system.push(injected);
      }
    },
  };
};
