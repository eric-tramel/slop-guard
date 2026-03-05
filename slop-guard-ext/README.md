# Slop Guard — Browser Extension

Score any text 0–100 for formulaic AI writing patterns, directly in your browser.  
Runs [slop-guard](https://github.com/eric-tramel/slop-guard) via Pyodide (Python-in-WebAssembly). No server, no API calls, fully offline after first load.

## Install

### 1. First-time setup (downloads pyodide.js + bundles slop-guard)

**Mac / Linux:**
```bash
cd slop-guard-ext
./update.sh
```

**Windows (PowerShell):**
```powershell
cd slop-guard-ext
.\update.ps1
```

This clones slop-guard, generates `python_bundle.js`, and downloads `pyodide.js` (~250 KB loader). Requires git and Python 3 on PATH.

### 2. Pick your browser manifest

Chrome and Firefox need different manifest files. Copy the right one:

**Chrome / Edge / Brave:**
```
cp manifest.chrome.json manifest.json        # Mac/Linux
Copy-Item manifest.chrome.json manifest.json  # Windows PowerShell
```

**Firefox:**
```
cp manifest.firefox.json manifest.json        # Mac/Linux
Copy-Item manifest.firefox.json manifest.json  # Windows PowerShell
```

### 3. Load the extension

**Chrome:**  `chrome://extensions` → enable Developer mode → Load unpacked → select this folder

**Firefox:**  `about:debugging#/runtime/this-firefox` → Load Temporary Add-on → select `manifest.json`

### 3. Use it

- Click the extension icon to open the popup
- Paste text, or click **Grab selection** / **Grab page text**
- Press **Analyze** (or Ctrl+Enter / Cmd+Enter)
- First launch downloads Pyodide (~10 MB), cached after that

## Updating slop-guard

When the upstream repo gets new patterns or scoring changes:

**Mac / Linux:**
```bash
./update.sh
```

**Windows (PowerShell):**
```powershell
.\update.ps1
```

To update from a local checkout instead:

```bash
./update.sh /path/to/slop-guard            # Mac/Linux
.\update.ps1 -Repo C:\path\to\slop-guard   # Windows
```

Then reload the extension in your browser.

## How it works

- `bundle.py` reads all Python source from slop-guard, embeds them as JSON in `python_bundle.js`, and downloads `pyodide.js` locally
- The popup loads Pyodide from the local `pyodide.js`; it fetches the ~10 MB WASM binary from CDN (cached after first load)
- Analysis runs the exact same Python code as the CLI/MCP server — same patterns, same scoring
- No `mcp` dependency needed; the bundle replaces `server.py` with a thin `analyze()` wrapper

## File structure

```
manifest.chrome.json   ← Chrome/Edge/Brave manifest
manifest.firefox.json  ← Firefox manifest
manifest.json          ← (you create this — copy from one of the above)
popup.html             ← Extension UI
popup.js               ← Pyodide bootstrap + UI controller
python_bundle.js       ← All slop-guard Python source as JS strings (generated)
pyodide.js             ← Pyodide loader (downloaded by bundle.py)
background.js          ← Context menu (right-click → Check with Slop Guard)
bundle.py              ← Regenerate python_bundle.js + download pyodide.js
update.sh              ← Pull upstream + bundle (Mac/Linux)
update.ps1             ← Pull upstream + bundle (Windows)
```

## Score bands

| Score  | Band      |
|--------|-----------|
| 80–100 | Clean     |
| 60–79  | Light     |
| 40–59  | Moderate  |
| 20–39  | Heavy     |
| 0–19   | Saturated |

## License

Extension wrapper: MIT  
slop-guard: MIT (Eric Tramel)
