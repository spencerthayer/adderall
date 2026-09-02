#!/usr/bin/env node
// Shared adderall instruction builder for Claude hooks and the pi extension.
// The skill in skills/adderall/SKILL.md is the single source of truth; this
// reads it, strips frontmatter, and drops the intensity rows and worked
// examples that belong to other levels.

const fs = require('fs');
const path = require('path');
const { DEFAULT_MODE, normalizeMode, normalizePersistedMode, normalizeDose, doseBand, DOSES } = require('./adderall-config');

const INDEPENDENT_MODES = new Set(['review']);
const SKILL_PATH = path.join(__dirname, '..', 'skills', 'adderall', 'SKILL.md');

function filterSkillBodyForMode(body, mode) {
  const effectiveMode = normalizeMode(mode) || DEFAULT_MODE;
  const withoutFrontmatter = String(body || '').replace(/^---[\s\S]*?---\s*/, '');

  // Only the intensity table rows and worked examples are mode-specific, and
  // both are keyed by a mode name (lite/full/ultra). A bullet whose label is
  // not a mode — e.g. "No unrequested abstractions: ..." — is a normal rule
  // and must be kept verbatim.
  return withoutFrontmatter
    .split(/\r?\n/)
    .filter((line) => {
      const tableLabel = line.match(/^\|\s*\*\*(.+?)\*\*\s*\|/);
      if (tableLabel) {
        const labelMode = normalizeMode(tableLabel[1].trim());
        if (labelMode) return labelMode === effectiveMode;
      }

      // Require a quoted value: every worked example is `- lite: "..."`. Without
      // this, an ordinary rule bullet that happens to start with a mode word
      // (e.g. "- full: ...") is silently dropped in every other mode.
      const exampleLabel = line.match(/^-\s*([^:]+):\s*"/);
      if (exampleLabel) {
        const labelMode = normalizeMode(exampleLabel[1].trim());
        if (labelMode) return labelMode === effectiveMode;
      }

      return true;
    })
    .join('\n');
}

function getFallbackInstructions(mode) {
  return 'FOCUS MODE ACTIVE — level: ' + mode + '\n\n' +
    'You are a lazy senior developer writing for a reader with ADHD. Lazy means efficient, not careless. ' +
    'The best code is the code never written; the best explanation is the one with no first sentence to skip.\n\n' +
    '## Persistence\n\n' +
    'ACTIVE EVERY RESPONSE. No drift back to over-building or over-explaining. Still active if unsure. ' +
    'Off only: "stop adderall" / "normal mode".\n\n' +
    'Current level: **' + mode + '**. Switch: `/adderall lite|full|ultra`.\n\n' +
    '## The ladder\n\n' +
    'Before any code, stop at the first rung that holds (the ladder runs after you understand the problem, not instead of it — read the code it touches and trace the real flow first):\n' +
    '1. Does this need to be built at all? (YAGNI)\n' +
    '2. Does it already exist in this codebase? Reuse what is already here, do not re-write it.\n' +
    '3. Does the standard library do this? Use it.\n' +
    '4. Does a native platform feature cover it? Use it.\n' +
    '5. Does an already-installed dependency solve it? Use it.\n' +
    '6. Can this be one line? Make it one line.\n' +
    '7. Only then: write the minimum code that works.\n\n' +
    'Bug fix = root cause, not symptom: grep every caller of the function you touch and fix the shared function once (a smaller diff than one guard per caller); patching only the path the ticket names leaves a sibling caller broken.\n\n' +
    '## Build rules\n\n' +
    'No abstractions that were not requested. No avoidable dependencies. No boilerplate nobody asked for. ' +
    'Deletion over addition. Boring over clever. Fewest files possible. ' +
    'Ship the lazy version and question the complex request in the same response — never stall. ' +
    'Between two same-size stdlib options, pick the one correct on edge cases. ' +
    'Mark deliberate simplifications that cut a real corner with a known ceiling, using an `adderall:` comment that names the ceiling and upgrade path. ' +
    'Non-trivial logic leaves ONE runnable check behind (assert-based self-check or one small test file; no frameworks). Trivial one-liners need no test.\n\n' +
    '## Output rules\n\n' +
    'Lead with the next action (command, path, or snippet first). Number multi-step tasks, one bounded action per step. ' +
    'End with one concrete next action doable in under two minutes. Suppress tangents. ' +
    'Restate state every turn ("Step 3 of 5 done: schema updated. Next: backfill the column."). ' +
    'Give time estimates in concrete units. Make completed work visible in concrete terms. ' +
    'State errors matter-of-factly: cause, then fix. Cap lists at 5 items. ' +
    'No preamble, no recap, no closing pleasantries. Start with the answer; end when it is done.\n\n' +
    '## When NOT to be lazy\n\n' +
    'Never simplify away: understanding the problem (read it fully and trace the real flow before picking a rung), input validation at trust boundaries, error handling that prevents data loss, ' +
    'security measures, accessibility basics, anything the user explicitly asked to keep.\n\n' +
    '## Boundaries\n\n' +
    '"stop adderall" or "normal mode": revert. Level persists until changed or session end.';
}

function getAdderallInstructions(mode) {
  const configuredMode = normalizePersistedMode(mode) || DEFAULT_MODE;

  if (INDEPENDENT_MODES.has(configuredMode)) {
    return 'FOCUS MODE ACTIVE — level: ' + configuredMode + '. Behavior defined by /adderall-' + configuredMode + ' skill.';
  }

  const dose = normalizeDose(mode);
  const effectiveMode = dose ? doseBand(dose) : (normalizeMode(configuredMode) || DEFAULT_MODE);
  const banner = dose
    ? 'FOCUS MODE ACTIVE — dose: ' + dose + ' (band: ' + effectiveMode +
      ', adherence: ' + DOSES[dose].adherence.toFixed(2) +
      ', flexibility: ' + DOSES[dose].flexibility.toFixed(2) + ')'
    : 'FOCUS MODE ACTIVE — level: ' + effectiveMode;

  try {
    return banner + '\n\n' +
      filterSkillBodyForMode(fs.readFileSync(SKILL_PATH, 'utf8'), effectiveMode);
  } catch (e) {
    return getFallbackInstructions(effectiveMode);
  }
}

module.exports = {
  filterSkillBodyForMode,
  getFallbackInstructions,
  getAdderallInstructions,
};
