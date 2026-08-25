"""
One-shot fixer: the PowerShell editing quirk mangled non-ASCII glyphs in the
dashboard into U+FFFD/ASCII-'?' garbage. Restores the intended glyphs
contextually and verifies the file is clean UTF-8 without a BOM.
Run: .venv\\Scripts\\python.exe tests\\fix_ui_glyphs.py
"""
from __future__ import annotations

import re
from pathlib import Path

P = Path(__file__).resolve().parents[1] / "app" / "static" / "index.html"
s = P.read_text(encoding="utf-8")
orig = s

BAD = "[?\uFFFD]"  # mangled bytes render as ASCII '?' or U+FFFD

subs = [
    (r'online BAD \$\{h\.vectors\} vectors BAD \$\{h\.ledger_campaigns\} campaigns'
     .replace("BAD", BAD), "online \u25c6 ${h.vectors} vectors \u25c6 ${h.ledger_campaigns} campaigns"),
    (r'"\uFFFD \"+e\.message|"\"? \"\+e\.message', '"\u26a0 "+e.message'),
    (r'every rail BAD attack'.replace("BAD", BAD), "every rail \u2192 attack"),
    (r'>BAD held-out<'.replace("BAD", BAD), ">\u2605 held-out<"),
    (r"'BADBAD ox-alpha'".replace("BAD", BAD), "'\U0001f9e0 ox-alpha'"),
    (r"'BAD template'".replace("BAD", BAD), "'\u2699 template'"),
]
for pat, rep in subs:
    s = re.sub(pat, rep, s)

# ---- insert Round history + Detect playground panels after the vstats row ----
PANELS = (
    '  <div class="row2">\n'
    '    <div class="panel"><h2>Round history \u2014 blue-team evolution</h2>'
    '<div id="rounds" class="muted">loading\u2026</div></div>\n'
    '    <div class="panel">\n'
    '      <h2>Score transactions \u2014 live ensemble</h2>\n'
    '      <textarea id="detectInput" style="width:100%;height:150px;'
    'background:var(--panel2);border:1px solid var(--line);color:var(--txt);'
    'border-radius:8px;padding:8px;font:12px/1.4 Consolas,monospace"></textarea>\n'
    '      <button class="ghost" onclick="runDetect()">\u2696 Score with current ensemble</button>\n'
    '      <div id="detectOut" class="muted" style="margin-top:8px">Uses the ensemble '
    'persisted from the last round (survives server restarts).</div>\n'
    '    </div>\n'
    '  </div>\n'
)
if 'id="detectInput"' not in s:
    pat = re.compile(
        r'(  <div class="row2">\n\s*<div class="panel"><h2>Robustness Ledger.*?'
        r'<div id="vstats"[^\n]*</div>\n  </div>\n)', re.DOTALL)
    s, n = pat.subn(lambda m: m.group(1) + PANELS, s, count=1)
    print(f"[..] panel insertion applied: {n == 1}")
    if n != 1:
        raise SystemExit("panel anchor not found")

P.write_text(s, encoding="utf-8", newline="\n")

leftover = s.count("\uFFFD")
bom = P.read_bytes()[:3] == b"\xef\xbb\xbf"
print(f"[OK] glyphs fixed: {orig != s}; leftover U+FFFD: {leftover}; BOM: {bom}")
if leftover or bom:
    raise SystemExit(1)
