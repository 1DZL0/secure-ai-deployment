"""Split the single module-02 Marimo file into one file per Part, sharing notebooks/lab02.py.

Content is not rewritten: cells are cut at the Part dividers they already carry. The hidden
lab cell becomes a plain importable module; each Part file imports what it needs from it.
Run from the repo root: python tools/split_02.py
"""
import pathlib, re

SRC = pathlib.Path("notebooks/02_prompt_injection_marimo.py")
OUT = pathlib.Path("notebooks")

LAB_EXPORTS = ["CUSTOMERS", "FACES", "MODERN", "PROFILES", "SWEEP_DESTRUCTIVE", "SWEEP_EXFIL",
               "TOOL_SCHEMAS", "bars_html", "console_html", "dispatch", "divider", "face_proof",
               "results_table", "run_agent", "score"]

src = SRC.read_text(encoding="utf-8")

# --- split into header + cells, strip the trailing footer ---
chunks = src.split("@app.cell\n")
assert chunks[0].lstrip().startswith("import marimo"), "unexpected header"
cell_sources = []
footer = 'if __name__ == "__main__":\n    app.run()\n'
for c in chunks[1:]:
    cell = "@app.cell\n" + c
    cell = re.sub(r"\n+if __name__ == .__main__.:\n    app\.run\(\)\n*$", "\n", cell)
    cell_sources.append(cell.rstrip("\n") + "\n")

def has(cell, *needles): return all(n in cell for n in needles)

# --- classify ---
css = title = lab = None
drop_coursemap = None
dividers = []  # (index, part_no, part_title)
for i, cell in enumerate(cell_sources):
    if has(cell, "<style>") and "mo.Html(" in cell and lab is None and title is None:
        css = cell
    elif has(cell, "Secure AI Deployment &middot; Module 02"):
        title = cell
    elif has(cell, "Course map &nbsp;"):
        drop_coursemap = i
    elif has(cell, "def dispatch("):
        lab = cell
    else:
        m = re.search(r"mo\.Html\(divider\((\d+),\s*\"([^\"]+)\"", cell)
        if m:
            dividers.append((i, int(m.group(1)), m.group(2)))

assert css and title and lab and len(dividers) == 6, f"classify failed: css={bool(css)} title={bool(title)} lab={bool(lab)} dividers={len(dividers)}"

# which cells belong to which part: from each divider index up to the next divider (or end)
part_cells = {}
bounds = [d[0] for d in dividers] + [len(cell_sources)]
for k, (di, pno, ptitle) in enumerate(dividers):
    part_cells[pno] = (ptitle, cell_sources[di:bounds[k+1]])

# --- write lab02.py from the lab cell body ---
lab_lines = lab.splitlines()
# drop "@app.cell" and the "def _(re):" line, and the final "return (...)" block
body_start = next(j for j, l in enumerate(lab_lines) if l.lstrip().startswith("def _(")) + 1
# the lab cell's FINAL return is the export tuple; nested helpers have their own `return (...)`
ret_start = next(j for j, l in enumerate(lab_lines) if l.strip().startswith("return (CUSTOMERS"))
body = "\n".join(l[4:] if l.startswith("    ") else l for l in lab_lines[body_start:ret_start])
(OUT / "lab02.py").write_text(
    '"""Shared lab for the module-02 Part notebooks: the agent, its policy layer, and the\n'
    'rendering helpers. Imported by each Part file (marimo bundles it into the WASM export)."""\n'
    "import re  # noqa: F401  (kept for parity with the original cell signature)\n\n"
    + body.rstrip() + "\n", encoding="utf-8")

# --- the uniform imports cell for every Part ---
imports_cell = (
    "@app.cell\n"
    "def _():\n"
    "    import marimo as mo\n"
    "    import re\n"
    "    from lab02 import (CUSTOMERS, FACES, MODERN, PROFILES, SWEEP_DESTRUCTIVE, SWEEP_EXFIL,\n"
    "                       TOOL_SCHEMAS, bars_html, console_html, dispatch, divider, face_proof,\n"
    "                       results_table, run_agent, score)\n"
    "    return (CUSTOMERS, FACES, MODERN, PROFILES, SWEEP_DESTRUCTIVE, SWEEP_EXFIL, TOOL_SCHEMAS,\n"
    "            bars_html, console_html, dispatch, divider, face_proof, mo, re, results_table, run_agent, score)\n"
)
footer_block = '\n\nif __name__ == "__main__":\n    app.run()\n'

summary = []
for pno in range(1, 7):
    ptitle, cells = part_cells[pno]
    head = ("import marimo\n\n"
            '__generated_with = "0.25.1"\n'
            f'app = marimo.App(width="medium", app_title="Part {pno}: {ptitle}")\n')
    blocks = [head, imports_cell, css]
    if pno == 1:
        blocks.append(title)   # the module hero + intro only opens Part 1
    blocks.extend(cells)
    out = "\n\n".join(b.rstrip("\n") for b in blocks) + footer_block
    (OUT / f"part{pno}.py").write_text(out, encoding="utf-8")
    summary.append(f"part{pno}.py  '{ptitle}'  {len(cells)} content cells")

print("wrote notebooks/lab02.py (" + str(len(body.splitlines())) + " lines)")
print("\n".join(summary))
