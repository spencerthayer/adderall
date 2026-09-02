#!/usr/bin/env node
// adderall — shared configuration resolver
//
// Resolution order for default mode:
//   1. ADDERALL_DEFAULT_MODE environment variable
//   2. Config file defaultMode field:
//      - $XDG_CONFIG_HOME/adderall/config.json (any platform, if set)
//      - ~/.config/adderall/config.json (macOS / Linux fallback)
//      - %APPDATA%\adderall\config.json (Windows fallback)
//   3. 'full'

const fs = require('fs');
const path = require('path');
const os = require('os');

const DEFAULT_MODE = 'full';
const VALID_MODES = ['off', 'lite', 'full', 'ultra', 'review'];
const RUNTIME_MODES = ['off', 'lite', 'full', 'ultra'];

// Dosage ladder: adherence is a tunable parameter. Each dose maps to a band
// (lite/full/ultra) that selects behavior; the dose itself refines how
// literally a target skill is followed.
const DOSES = {
  '5mg':    { adherence: 0.10, flexibility: 0.90, band: 'lite' },
  '7.5mg':  { adherence: 0.25, flexibility: 0.75, band: 'lite' },
  '10mg':   { adherence: 0.50, flexibility: 0.50, band: 'full' },
  '12.5mg': { adherence: 0.70, flexibility: 0.30, band: 'full' },
  '15mg':   { adherence: 0.85, flexibility: 0.15, band: 'full' },
  '20mg':   { adherence: 0.95, flexibility: 0.05, band: 'ultra' },
  '30mg':   { adherence: 1.00, flexibility: 0.00, band: 'ultra' },
};

function normalizeDose(mode) {
  if (typeof mode !== 'string') return null;
  const normalized = mode.trim().toLowerCase().replace(/^adderall-/, '');
  return Object.prototype.hasOwnProperty.call(DOSES, normalized) ? normalized : null;
}

function doseBand(dose) {
  const normalized = normalizeDose(dose);
  return normalized ? DOSES[normalized].band : null;
}

function normalizeMode(mode) {
  if (typeof mode !== 'string') return null;
  const dose = normalizeDose(mode);
  if (dose) return DOSES[dose].band;
  const normalized = mode.trim().toLowerCase();
  return RUNTIME_MODES.includes(normalized) ? normalized : null;
}

function normalizeConfigMode(mode) {
  if (typeof mode !== 'string') return null;
  const normalized = mode.trim().toLowerCase();
  return VALID_MODES.includes(normalized) ? normalized : null;
}

function normalizePersistedMode(mode) {
  return normalizeMode(mode) || normalizeConfigMode(mode);
}

// "stop adderall" / "normal mode" turn adderall off, but only as a standalone
// command. Matching the phrase anywhere in the message turned it off mid-task
// for ordinary requests like "add a normal mode toggle" — so require the whole
// message to be the command, ignoring case and trailing punctuation.
function isDeactivationCommand(text) {
  const t = String(text || '').trim().toLowerCase().replace(/[.!?\s]+$/, '');
  return t === 'stop adderall' || t === 'normal mode';
}

function getConfigDir() {
  if (process.env.XDG_CONFIG_HOME) {
    return path.join(process.env.XDG_CONFIG_HOME, 'adderall');
  }
  if (process.platform === 'win32') {
    return path.join(
      process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'),
      'adderall'
    );
  }
  return path.join(os.homedir(), '.config', 'adderall');
}

function getConfigPath() {
  return path.join(getConfigDir(), 'config.json');
}

function getClaudeDir() {
  // CLAUDE_CONFIG_DIR overrides ~/.claude, matching Claude Code.
  return process.env.CLAUDE_CONFIG_DIR || path.join(os.homedir(), '.claude');
}

function getDefaultMode() {
  // 1. Environment variable (highest priority)
  const envMode = process.env.ADDERALL_DEFAULT_MODE;
  // A default must be a runtime level (off/lite/full/ultra); review is a
  // session-only mode, never a valid default.
  if (envMode && RUNTIME_MODES.includes(envMode.toLowerCase())) {
    return envMode.toLowerCase();
  }

  // 2. Config file
  try {
    const configPath = getConfigPath();
    // Strip UTF-8 BOM (common on Windows-saved files) so JSON.parse doesn't choke
    const config = JSON.parse(fs.readFileSync(configPath, 'utf8').replace(/^\uFEFF/, ''));
    if (config.defaultMode && RUNTIME_MODES.includes(config.defaultMode.toLowerCase())) {
      return config.defaultMode.toLowerCase();
    }
  } catch (e) {
    // Config file doesn't exist or is invalid — fall through
  }

  // 3. Default
  return DEFAULT_MODE;
}

// Silence the pi "Adderall loaded" startup toast while keeping adderall active.
// ADDERALL_QUIET_STARTUP=1 (or any truthy value; 0/false/empty mean "show it")
// takes precedence, else config.quietStartup === true.
function getQuietStartup() {
  const env = process.env.ADDERALL_QUIET_STARTUP;
  if (env !== undefined) {
    const v = env.trim().toLowerCase();
    return v !== '' && v !== '0' && v !== 'false' && v !== 'no';
  }
  try {
    const config = JSON.parse(fs.readFileSync(getConfigPath(), 'utf8').replace(/^\uFEFF/, ''));
    return config.quietStartup === true;
  } catch (_) {
    return false;
  }
}

// Hide the status-bar indicator while keeping adderall active.
// ADDERALL_HIDE_STATUS=1 (or any truthy value; 0/false/empty mean "don't hide")
// takes precedence, else config.hideStatus === true.
function getHideStatus() {
  const env = process.env.ADDERALL_HIDE_STATUS;
  if (env !== undefined) {
    const v = env.trim().toLowerCase();
    return v !== '' && v !== '0' && v !== 'false' && v !== 'no';
  }
  try {
    const config = JSON.parse(fs.readFileSync(getConfigPath(), 'utf8').replace(/^\uFEFF/, ''));
    return config.hideStatus === true;
  } catch (_) {
    return false;
  }
}

function writeDefaultMode(mode) {
  // Only a runtime level can be a default; review is session-only.
  const normalized = normalizeMode(mode);
  if (!normalized) return null;

  const configPath = getConfigPath();
  fs.mkdirSync(path.dirname(configPath), { recursive: true });
  let config = {};
  try {
    config = JSON.parse(fs.readFileSync(configPath, 'utf8').replace(/^\uFEFF/, ''));
    if (!config || typeof config !== 'object' || Array.isArray(config)) config = {};
  } catch (_) {}
  config.defaultMode = normalized;
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8');
  return normalized;
}

module.exports = {
  DEFAULT_MODE,
  VALID_MODES,
  RUNTIME_MODES,
  DOSES,
  doseBand,
  normalizeDose,
  getDefaultMode,
  getConfigDir,
  getConfigPath,
  getClaudeDir,
  getHideStatus,
  getQuietStartup,
  normalizeMode,
  normalizeConfigMode,
  normalizePersistedMode,
  isDeactivationCommand,
  writeDefaultMode,
};
