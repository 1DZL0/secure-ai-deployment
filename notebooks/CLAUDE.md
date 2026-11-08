# Working on the marimo notebooks

The project rules are in `../CLAUDE.md` (layout, commands, house style, browser limits). This file adds how to edit a marimo notebook here.

## Marimo basics

- Edit only inside `@app.cell` functions. Each cell's parameters are the names it reads and its `return` tuple the names it defines; keep both in step with the body.
- Cells form a graph and re-run when anything they read changes. A name may be defined in one cell only, with no cycles and no `global`.
- Names starting with `_` are local to their cell; use them for anything two cells would otherwise both define (`import json as _json`).
- The last expression of a cell is its output. Use `mo.output.append` or `mo.output.replace` when the output is not the last line.
- A `mo.ui` element's `.value` can only be read in a cell other than the one that defines it.
- Run `python -m marimo check <file>.py` after every edit (from this folder). Errors must be fixed; the `markdown-indentation` warnings in Module 01 are old and harmless.

## Patterns used in these notebooks

- First cell: `import marimo as mo` plus the engine imports (`koda_lab`, `koda_toolbox`, `koda_practice`, `koda_answer`). Only top-level imports get installed in the browser, and only pure-Python packages with a Pyodide build work. No plotly, polars or altair: hand-built SVG and HTML through the `koda_lab` helpers.
- Page chrome: `hero(...)` at the top, `divider(n, title, teaser)` between Parts, `exercise_html(...)` before each exercise, `recap_html(...)` at the end. Render HTML with `mo.Html(...)`; group controls with `mo.hstack` / `mo.vstack`, or `mo.Html(template).batch(**widgets)` for a compact form.
- Per-exercise state: `get_x, set_x = mo.state(...)`; the output cell reads and sets its own state so one box never re-runs another.
- Gate a page or section with `mo.stop(condition)` (the practice notebook gates each page with `mo.stop(page != N)`).
- Run buttons: `mo.ui.run_button`. Reset or counter buttons: `mo.ui.button(value=0, on_click=lambda v: v + 1)`. Step-through buttons: `on_change=lambda _: set_step(lambda s: s + 1)`.
- Calls to a model in the browser go through `koda_lab.post_for(...)` (pyfetch) or, on the practice pages, the real SDKs installed by `koda_practice.install_core()`. Treat a blank or `NA` key with `has_key()` and fall back to `RECORDED`.
- Callout text inside `mo.callout` is not visible to `document.body.innerText` in the browser build; check callouts by screenshot.
