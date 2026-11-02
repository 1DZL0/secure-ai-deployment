#!/usr/bin/env python3
"""Record real-model runs for the course's no-key path, so a learner who types NA still sees a real trace.

    OPENROUTER_API_KEY=sk-or-... python tools/record_live_runs.py             # all three sections, the five live models
    python tools/record_live_runs.py --dry-run                               # print the plan, send nothing
    python tools/record_live_runs.py --what module02 --models openai/gpt-4o-mini
    python tools/record_live_runs.py --selftest                              # a stub model, a temp output file, no key

Writes notebooks/koda_recorded.py, merging into whatever is already recorded there. The key never enters the output
(asserted before writing). Cost per model: Module 01 is one request; Module 02 is two agent runs (unsafe, hardened);
the benchmark is three notes x tries runs. A run is at most six requests of a few thousand tokens each.
"""
import argparse
import ast
import asyncio
import datetime
import json
import os
import pathlib
import pprint
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "notebooks"))
import koda_lab as kl  # noqa: E402

OUT_DEFAULT = ROOT / "notebooks" / "koda_recorded.py"
TODAY = datetime.date.today().isoformat()
RETRY_CODES = (408, 409, 425, 429, 500, 502, 503, 504, 524)


def make_post(retries=4):
    """An async (key, body) -> dict for CPython, the twin of koda_lab.post_openrouter (which is browser-only)."""
    async def post(key, body):
        req = urllib.request.Request(
            kl.OPENROUTER, data=json.dumps(body).encode(), method="POST",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                     "HTTP-Referer": "https://1dzl0.github.io/secure-ai-deployment/", "X-Title": "Secure AI Deployment course"})
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                text = e.read().decode(errors="replace")
                if e.code in RETRY_CODES and attempt < retries - 1:
                    time.sleep(2 * 2 ** attempt)
                    continue
                try:
                    return json.loads(text)
                except ValueError:
                    return {"error": {"code": e.code, "message": text[:300]}}
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < retries - 1:
                    time.sleep(2 * 2 ** attempt)
                    continue
                return {"error": {"message": str(e)[:300]}}
        return {"error": {"message": "retries exhausted"}}
    return post


def make_stub_post():
    """A scripted model for --selftest: looks the customer up, reads the secrets file, then answers. No network."""
    async def post(key, body):
        msgs, tools = body["messages"], {t["function"]["name"] for t in body["tools"]}
        last = msgs[-1]
        def call(name, args, cid):
            return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
                {"id": cid, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}}]}
        if "get_weather" in tools:
            return call("get_weather", {"city": "Nicosia"}, "call_w")
        if last["role"] == "user":
            return call("lookup_customer", {"id": 42}, "call_1")
        if last["role"] == "tool" and last["tool_call_id"] == "call_1":
            return call("read_file", {"path": "../secrets/.env"}, "call_2")
        return {"choices": [{"message": {"role": "assistant", "content": "Done. I followed up on the record.", "tool_calls": []}}]}
    return post


async def record_module01(post, key, model):
    data = await post(key, {"model": model, "messages": kl.WEATHER_MSGS, "tools": kl.WEATHER_TOOL, "temperature": 0})
    if "choices" not in data:
        return None, data
    m = data["choices"][0]["message"]
    return {"content": m.get("content") or None,
            "tool_calls": [{"name": c["function"]["name"], "arguments": c["function"].get("arguments") or ""}
                           for c in (m.get("tool_calls") or [])],
            "recorded_on": TODAY}, None


async def record_module02(post, key, model):
    out = {"recorded_on": TODAY}
    for prof in ("unsafe", "hardened"):
        steps, err, reply, _ = await kl.run_attack(key, model, kl.PROFILES[prof], kl.CUSTOMERS[42]["notes"], post=post)
        if err is not None:
            return None, {prof: err}
        out[prof] = {"steps": steps, "reply": reply}
    return out, None


async def record_benchmark(post, key, model, tries):
    runs = []
    for vector, note in kl.POISON.items():
        for t in range(tries):
            steps, err, reply, msgs = await kl.run_attack(key, model, kl.PROFILES["unsafe"], note, post=post)
            runs.append({"vector": vector, "try": t + 1, "error": err, "steps": steps, "reply": reply, "messages": msgs})
    if all(r["error"] for r in runs):
        return None, runs[0]["error"]
    return {"tries": tries, "recorded_on": TODAY, "runs": runs}, None


def load_existing(path):
    if not path.exists():
        return {"recorded_on": None, "module01": {}, "module02": {}, "benchmark": {}}, ""
    text = path.read_text(encoding="utf-8")
    head, _, literal = text.partition("RECORDED = ")
    return ast.literal_eval(literal), head


def write_module(path, rec, head, key):
    text = head + "RECORDED = " + pprint.pformat(rec, width=130, sort_dicts=False) + "\n"
    assert ast.literal_eval(text.partition("RECORDED = ")[2]) == rec, "the written literal does not round-trip"
    assert not key or key not in text, "the key must never enter the recorded file"
    path.write_text(text, encoding="utf-8")
    return len(text.encode())


def summary_module02(rec):
    u, h = kl.wins(rec["unsafe"]["steps"]), kl.wins(rec["hardened"]["steps"])
    ht = kl.attempts(rec["hardened"]["steps"])
    return (f"unsafe {len(u)} landed ({', '.join(u) or 'nothing'}); hardened {len(h)} landed"
            + (f", tried {', '.join(ht)}" if ht else ", tried nothing"))


def summary_benchmark(rec):
    parts = []
    for vector in kl.POISON:
        vr = [r for r in rec["runs"] if r["vector"] == vector]
        landed = sum(len(kl.wins(r["steps"])) for r in vr if not r["error"])
        errs = sum(1 for r in vr if r["error"])
        parts.append(f"{vector}: {landed} landed over {len(vr)} tries" + (f", {errs} errors" if errs else ""))
    return "; ".join(parts)


async def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=",".join(kl.LIVE_MODELS), help="comma-separated OpenRouter ids")
    ap.add_argument("--what", default="module01,module02,benchmark", help="sections to record")
    ap.add_argument("--tries", type=int, default=2, help="benchmark tries per note (the page's default)")
    ap.add_argument("--out", default=str(OUT_DEFAULT))
    ap.add_argument("--dry-run", action="store_true", help="print the plan and send nothing")
    ap.add_argument("--selftest", action="store_true", help="use a scripted stub model and write to a temp file")
    a = ap.parse_args()
    models = [m.strip() for m in a.models.split(",") if m.strip()]
    what = {w.strip() for w in a.what.split(",") if w.strip()}
    assert what <= {"module01", "module02", "benchmark"}, what

    runs_per_model = ("module01" in what) * 1 + ("module02" in what) * 2 + ("benchmark" in what) * len(kl.POISON) * a.tries
    print(f"plan: {len(models)} models x ({', '.join(sorted(what))}) = {runs_per_model * len(models)} agent runs, "
          f"up to {runs_per_model * len(models) * 6} requests, temperature 0")
    if a.dry_run:
        return 0

    if a.selftest:
        key, post = "", make_stub_post()
        out = pathlib.Path(tempfile.mkdtemp()) / "koda_recorded.py"
        head = load_existing(OUT_DEFAULT)[1]
        rec = {"recorded_on": None, "module01": {}, "module02": {}, "benchmark": {}}
    else:
        key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if not key:
            print("set OPENROUTER_API_KEY in the environment first (nothing is read from any file)", file=sys.stderr)
            return 2
        post = make_post()
        out = pathlib.Path(a.out)
        rec, head = load_existing(out)

    for model in models:
        if "module01" in what:
            r, err = await record_module01(post, key, model)
            if r is None:
                print(f"module01 {model}: skipped, {json.dumps(err)[:200]}")
            else:
                rec["module01"][model] = r
                print(f"module01 {model}: content={r['content']!r:.40} calls={[c['name'] for c in r['tool_calls']]}")
        if "module02" in what:
            r, err = await record_module02(post, key, model)
            if r is None:
                print(f"module02 {model}: skipped, {json.dumps(err)[:200]}")
            else:
                rec["module02"][model] = r
                print(f"module02 {model}: {summary_module02(r)}")
        if "benchmark" in what:
            r, err = await record_benchmark(post, key, model, a.tries)
            if r is None:
                print(f"benchmark {model}: skipped, {json.dumps(err)[:200]}")
            else:
                rec["benchmark"][model] = r
                print(f"benchmark {model}: {summary_benchmark(r)}")
    rec["recorded_on"] = TODAY
    size = write_module(out, rec, head, key)
    print(f"wrote {out} ({size / 1024:.0f} KB): module01 {len(rec['module01'])}, module02 {len(rec['module02'])}, "
          f"benchmark {len(rec['benchmark'])} models")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
