/* Slop Guard – popup controller */

const CIRC = 2 * Math.PI * 34; // circumference of score ring (r=34)

const BAND_COLORS = {
  clean:     '#4ade80',
  light:     '#a3e635',
  moderate:  '#fbbf24',
  heavy:     '#f97316',
  saturated: '#ef4444',
};

// DOM refs
const statusDot    = document.getElementById('statusDot');
const statusText   = document.getElementById('statusText');
const versionLabel = document.getElementById('versionLabel');
const inputText    = document.getElementById('inputText');
const analyzeBtn   = document.getElementById('analyzeBtn');
const grabSelBtn   = document.getElementById('grabSelBtn');
const grabPageBtn  = document.getElementById('grabPageBtn');
const clearBtn     = document.getElementById('clearBtn');
const scoreSection = document.getElementById('scoreSection');
const scoreArc     = document.getElementById('scoreArc');
const scoreNumber  = document.getElementById('scoreNumber');
const scoreBand    = document.getElementById('scoreBand');
const wordCount    = document.getElementById('wordCount');
const totalPenalty = document.getElementById('totalPenalty');
const density      = document.getElementById('density');
const violationsSection = document.getElementById('violationsSection');
const adviceList   = document.getElementById('adviceList');
const countsGrid   = document.getElementById('countsGrid');
const detailToggle = document.getElementById('detailToggle');
const violationDetail = document.getElementById('violationDetail');

let pyodide = null;
let ready = false;

// ── Initialization ──────────────────────────────────────────────────────────

async function init() {
  try {
    if (typeof loadPyodide === 'undefined') {
      setStatus('error', 'pyodide.js not found — run update.sh or update.ps1 first');
      versionLabel.textContent = 'setup needed';
      return;
    }

    setStatus('loading', 'Loading Pyodide runtime…');
    pyodide = await loadPyodide({
      indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/'
    });

    if (typeof PYTHON_FILES === 'undefined') {
      setStatus('error', 'python_bundle.js not found — run update.sh or update.ps1 first');
      versionLabel.textContent = 'setup needed';
      return;
    }

    setStatus('loading', 'Writing slop-guard to filesystem…');
    writePythonFiles();

    setStatus('loading', 'Importing slop-guard…');
    await pyodide.runPythonAsync(`
import slop_guard
_sg_version = slop_guard.PACKAGE_VERSION
    `);

    const version = pyodide.globals.get('_sg_version');
    versionLabel.textContent = `v${version}`;

    ready = true;
    enableButtons();
    setStatus('ready', 'Ready');

    // Check for pending text from context menu
    checkPendingText();
  } catch (err) {
    console.error('Init failed:', err);
    setStatus('error', `Init failed: ${err.message}`);
  }
}

function writePythonFiles() {
  // Detect Python version to find site-packages path
  const pyVer = pyodide.runPython('import sys; f"{sys.version_info.major}.{sys.version_info.minor}"');
  const sitePackages = `/lib/python${pyVer}/site-packages`;

  // Ensure directory structure
  const dirs = new Set();
  for (const relPath of Object.keys(PYTHON_FILES)) {
    const parts = relPath.split('/');
    for (let i = 1; i < parts.length; i++) {
      dirs.add(parts.slice(0, i).join('/'));
    }
  }
  for (const dir of [...dirs].sort()) {
    const fullDir = sitePackages + '/' + dir;
    try { pyodide.FS.mkdirTree(fullDir); } catch (_) { /* exists */ }
  }

  // Write files
  for (const [relPath, content] of Object.entries(PYTHON_FILES)) {
    const fullPath = sitePackages + '/' + relPath;
    pyodide.FS.writeFile(fullPath, content, { encoding: 'utf8' });
  }
}

// ── Analysis ────────────────────────────────────────────────────────────────

async function analyze(text) {
  if (!ready || !text.trim()) return;

  analyzeBtn.disabled = true;
  analyzeBtn.textContent = 'Analyzing…';
  setStatus('loading', 'Analyzing…');

  try {
    pyodide.globals.set('_input_text', text);
    await pyodide.runPythonAsync(`
import json as _json
_result = _json.dumps(slop_guard.analyze(_input_text))
    `);
    const resultStr = pyodide.globals.get('_result');
    const result = JSON.parse(resultStr);

    renderResult(result);
    setStatus('ready', 'Ready');
  } catch (err) {
    console.error('Analysis error:', err);
    setStatus('error', `Error: ${err.message}`);
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = 'Analyze';
  }
}

// ── Rendering ───────────────────────────────────────────────────────────────

function renderResult(r) {
  const color = BAND_COLORS[r.band] || BAND_COLORS.moderate;

  // Score ring
  const offset = CIRC * (1 - r.score / 100);
  scoreArc.style.strokeDashoffset = offset;
  scoreArc.style.stroke = color;
  scoreNumber.textContent = r.score;
  scoreNumber.style.color = color;

  // Band label
  scoreBand.textContent = r.band;
  scoreBand.style.color = color;

  // Stats
  wordCount.textContent = r.word_count;
  totalPenalty.textContent = r.total_penalty;
  density.textContent = r.density;

  scoreSection.classList.add('visible');

  // Advice
  adviceList.innerHTML = '';
  if (r.advice && r.advice.length) {
    for (const tip of r.advice) {
      const li = document.createElement('li');
      li.textContent = tip;
      adviceList.appendChild(li);
    }
  } else {
    const li = document.createElement('li');
    li.textContent = 'No issues found.';
    li.style.color = '#4ade80';
    adviceList.appendChild(li);
  }

  // Category counts
  countsGrid.innerHTML = '';
  if (r.counts) {
    const entries = Object.entries(r.counts).sort((a, b) => b[1] - a[1]);
    for (const [key, val] of entries) {
      const row = document.createElement('div');
      row.className = 'count-row';
      const label = document.createElement('span');
      label.className = 'count-label';
      label.textContent = key.replace(/_/g, ' ');
      const value = document.createElement('span');
      value.className = 'count-value' + (val === 0 ? ' zero' : '');
      value.textContent = val;
      row.appendChild(label);
      row.appendChild(value);
      countsGrid.appendChild(row);
    }
  }

  // Violation details
  violationDetail.innerHTML = '';
  violationDetail.classList.remove('visible');
  detailToggle.textContent = 'Show all violations';
  if (r.violations && r.violations.length) {
    detailToggle.style.display = '';
    for (const v of r.violations) {
      const item = document.createElement('div');
      item.className = 'violation-item';
      item.innerHTML =
        `<span class="v-match">${esc(v.match)}</span> ` +
        `<span class="v-penalty">${v.penalty}</span>` +
        `<div class="v-context">${esc(v.context)}</div>`;
      violationDetail.appendChild(item);
    }
  } else {
    detailToggle.style.display = 'none';
  }

  violationsSection.classList.add('visible');
}

function esc(s) {
  const el = document.createElement('span');
  el.textContent = s;
  return el.innerHTML;
}

// ── UI Helpers ──────────────────────────────────────────────────────────────

function setStatus(state, msg) {
  statusDot.className = 'status-dot ' + state;
  statusText.textContent = msg;
}

function enableButtons() {
  analyzeBtn.disabled = false;
  grabSelBtn.disabled = false;
  grabPageBtn.disabled = false;
}

async function grabSelection() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => window.getSelection().toString(),
    });
    if (result) {
      inputText.value = result;
    } else {
      setStatus('ready', 'No text selected on page');
    }
  } catch (err) {
    // Fallback for Firefox or restricted pages
    setStatus('ready', 'Cannot access page — paste text manually');
  }
}

async function grabPageText() {
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const [{ result }] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => document.body.innerText,
    });
    if (result) {
      inputText.value = result.substring(0, 50000); // Cap at 50k chars
    }
  } catch (err) {
    setStatus('ready', 'Cannot access page — paste text manually');
  }
}

async function checkPendingText() {
  try {
    const { pendingText } = await chrome.storage.local.get('pendingText');
    if (pendingText) {
      inputText.value = pendingText;
      await chrome.storage.local.remove('pendingText');
      chrome.action.setBadgeText({ text: '' });
      analyze(pendingText);
    }
  } catch (_) { /* storage might not be available */ }
}

// ── Events ──────────────────────────────────────────────────────────────────

analyzeBtn.addEventListener('click', () => analyze(inputText.value));
grabSelBtn.addEventListener('click', grabSelection);
grabPageBtn.addEventListener('click', grabPageText);
clearBtn.addEventListener('click', () => {
  inputText.value = '';
  scoreSection.classList.remove('visible');
  violationsSection.classList.remove('visible');
});

detailToggle.addEventListener('click', () => {
  const visible = violationDetail.classList.toggle('visible');
  detailToggle.textContent = visible ? 'Hide violations' : 'Show all violations';
});

inputText.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    analyze(inputText.value);
  }
});

// ── Boot ────────────────────────────────────────────────────────────────────

init();
