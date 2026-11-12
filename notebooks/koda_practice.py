"""Foundations practice (pages 1.1 to 1.6 under Module 1): everything the pages need besides their text.

- install_core / install_frameworks: load the SDKs into the browser (Pyodide) in an order micropip can resolve
- patch_http: make the SDKs' HTTP clients work from a web page, log every call (the "wire"), answer the practice model
- practice_reply: the practice model, a few rules returning OpenAI-format replies so every box runs with no key
- run_code: run a learner's code box (top-level await allowed), capturing what it prints, any error and the wire
- STARTERS / SOLUTIONS / grade: the code in each box, a working answer, and the checks behind every exercise
- *_svg / *_html: the pictures and panels

Browser findings this rests on (tested 4 Nov 2026, Pyodide 314, marimo 0.25.1): the SDKs reach the providers through the
browser's fetch; micropip never backtracks, so shared packages are pinned before the frameworks; ormsgpack has no browser
build, so LangGraph's checkpoint package gets a msgpack stand-in; langchain-openai must not open raw TCP sockets; and
OpenRouter's CORS list rejects the SDKs' x-stainless-* telemetry headers, so those are stripped from a copy of each request.

Run this file directly for a self-check (no browser, no key, no network).
"""
import ast
import contextlib
import html
import importlib
import inspect
import io
import json
import os
import re
import sys
import time
import traceback

from koda_lab import PROVIDERS, has_key, key_mismatch

IN_BROWSER = sys.platform == "emscripten"
PRACTICE = "Practice model"
PRACTICE_HOST = "practice.local"

PROVIDER_INFO = {
    PRACTICE: {"family": "openai", "base_url": f"https://{PRACTICE_HOST}/v1", "models": ["practice-model"],
               "default": "practice-model", "label": "Practice model (no key, not AI)"},
    "OpenRouter": {"family": "openai", "base_url": "https://openrouter.ai/api/v1", "models": PROVIDERS["OpenRouter"]["models"],
                   "default": "openai/gpt-4o-mini", "label": PROVIDERS["OpenRouter"]["label"]},
    "OpenAI": {"family": "openai", "base_url": "https://api.openai.com/v1", "models": PROVIDERS["OpenAI"]["models"],
               "default": "gpt-4o-mini", "label": PROVIDERS["OpenAI"]["label"]},
    "Anthropic": {"family": "anthropic", "base_url": "https://api.anthropic.com", "models": PROVIDERS["Anthropic"]["models"],
                  "default": "claude-haiku-4-5", "label": PROVIDERS["Anthropic"]["label"]},
}


def make_env(provider, raw_key, model):
    """What a code box sees: API_KEY, MODEL and BASE_URL, plus the provider and its request format ("family")."""
    info = PROVIDER_INFO[provider]
    return {"provider": provider, "family": info["family"], "model": model or info["default"], "base_url": info["base_url"],
            "key": "practice-key" if provider == PRACTICE else (raw_key or "").strip(), "raw_key": raw_key or ""}


def env_problem(env):
    """Why a box cannot run yet (no key, or a key for another provider), or None."""
    if env["provider"] == PRACTICE:
        return None
    if not has_key(env["raw_key"]):
        return f"Paste your {env['provider']} key in the panel at the top, or pick the practice model there."
    return key_mismatch(env["provider"], env["raw_key"])


# ----------------------------------------------------------------------------------------------------------------------
# Installing the libraries in the browser
# ----------------------------------------------------------------------------------------------------------------------
CORE = ["openai==3.45.0", "anthropic==2.4.0"]
PINS = ["uuid-utils==0.19.0", "urllib3>=2.8", "certifi>=2026.10.19", "websockets<17", "cryptography"]
FRAMEWORKS = ["openai-agents==0.24.0", "langchain-openai==1.7.3", "langchain-anthropic==1.7.9"]
CHECKPOINT = "langgraph-checkpoint==4.3.1"
GRAPH = ["langgraph==1.2.19", "langchain==1.4.8"]
_STATE = {"core": False, "frameworks": False}


async def install_core():
    """The two provider SDKs. Returns the seconds it took (0 outside the browser, where they are already installed)."""
    t0 = time.time()
    if IN_BROWSER and not _STATE["core"]:
        import micropip
        await micropip.install(CORE)
    _STATE["core"] = True
    patch_http()
    return time.time() - t0


async def install_frameworks():
    """The OpenAI Agents SDK, LangChain and LangGraph, once per page. Returns the seconds it took."""
    if _STATE["frameworks"]:
        return 0.0
    t0 = time.time()
    if IN_BROWSER:
        import micropip
        await micropip.install(PINS)                      # micropip takes the first version that fits and never backtracks
        await micropip.install(FRAMEWORKS)
        await micropip.install("msgpack")
        await micropip.install(CHECKPOINT, deps=False)    # its ormsgpack dependency has no browser build
        _ormsgpack_standin()
        await micropip.install(GRAPH)
    _STATE["frameworks"] = True
    patch_http()                                          # LangChain brings the older httpx as well
    return time.time() - t0


def frameworks_ready():
    return _STATE["frameworks"]


def _ormsgpack_standin():
    """LangGraph imports ormsgpack for checkpoints; these pages never checkpoint, so msgpack stands in."""
    try:
        import ormsgpack  # noqa: F401
        return
    except ImportError:
        pass
    import types
    import msgpack
    mod = types.ModuleType("ormsgpack")

    class MsgpackEncodeError(TypeError):
        pass

    class MsgpackDecodeError(ValueError):
        pass

    def packb(obj, default=None, option=None):
        return msgpack.packb(obj, default=default, use_bin_type=True)

    def unpackb(data, ext_hook=None, option=None):
        return msgpack.unpackb(data, ext_hook=ext_hook or msgpack.ExtType, raw=False, strict_map_key=False)

    def _missing(name):
        if name.startswith("OPT_"):
            return 0
        raise AttributeError(name)

    mod.packb, mod.unpackb, mod.Ext = packb, unpackb, msgpack.ExtType
    mod.MsgpackEncodeError, mod.MsgpackDecodeError, mod.__getattr__ = MsgpackEncodeError, MsgpackDecodeError, _missing
    sys.modules["ormsgpack"] = mod


# ----------------------------------------------------------------------------------------------------------------------
# The HTTP patch: browser-safe headers, the wire log, and the practice model answered locally
# ----------------------------------------------------------------------------------------------------------------------
WIRE = []          # one entry per HTTP call made during the current run_code
MODEL_PATHS = ("/chat/completions", "/messages", "/responses")


def _json_or_none(raw):
    try:
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _body_of(resp):
    try:
        return resp.json()
    except Exception:
        try:
            return resp.text[:4000]
        except Exception:
            return None


def _clean(hx, request):
    """A copy of the request for the network: no x-stainless-* telemetry headers (OpenRouter's CORS list rejects some),
    and Anthropic's opt-in header for calls made from a web page."""
    hdrs = [(k, v) for k, v in request.headers.multi_items() if not k.lower().startswith("x-stainless-")]
    if request.url.host == "api.anthropic.com" and not any(k.lower() == "anthropic-dangerous-direct-browser-access" for k, _ in hdrs):
        hdrs.append(("anthropic-dangerous-direct-browser-access", "true"))
    return hx.Request(request.method, request.url, headers=hdrs, content=request.content, extensions=request.extensions)


def _entry(request):
    return {"host": request.url.host, "path": request.url.path, "method": request.method, "req": _json_or_none(request.content)}


def _wrap_sync(hx, orig):
    def send(self, request, **kw):
        request.read()
        entry = _entry(request)
        if request.url.host == PRACTICE_HOST:
            status, payload = practice_reply(entry["req"] or {})
            resp = hx.Response(status, json=payload, request=request)
        else:
            resp = orig(self, _clean(hx, request), **kw)
            resp.read()
            resp.request = request          # the SDK reads its own markers back off the original request
        entry.update(status=resp.status_code, resp=_body_of(resp))
        WIRE.append(entry)
        return resp
    send._kz = True
    return send


def _wrap_async(hx, orig):
    async def send(self, request, **kw):
        await request.aread()
        entry = _entry(request)
        if request.url.host == PRACTICE_HOST:
            status, payload = practice_reply(entry["req"] or {})
            resp = hx.Response(status, json=payload, request=request)
        else:
            resp = await orig(self, _clean(hx, request), **kw)
            await resp.aread()
            resp.request = request
        entry.update(status=resp.status_code, resp=_body_of(resp))
        WIRE.append(entry)
        return resp
    send._kz = True
    return send


def patch_http():
    """Wrap Client.send and AsyncClient.send of httpx2 (the SDKs) and httpx (LangChain's extras). Safe to call again."""
    os.environ["LANGCHAIN_OPENAI_TCP_KEEPALIVE"] = "0"     # otherwise langchain-openai builds a raw-socket transport
    patched = []
    for lib in ("httpx2", "httpx"):
        try:
            hx = importlib.import_module(lib)
        except ImportError:
            continue
        if not getattr(hx.Client.send, "_kz", False):
            hx.Client.send = _wrap_sync(hx, hx.Client.send)
        if not getattr(hx.AsyncClient.send, "_kz", False):
            hx.AsyncClient.send = _wrap_async(hx, hx.AsyncClient.send)
        patched.append(lib)
    return patched


# ----------------------------------------------------------------------------------------------------------------------
# The practice model: rules, not AI. OpenAI chat-completions format in and out.
# ----------------------------------------------------------------------------------------------------------------------
_SYN = {
    "weather": {"weather", "umbrella", "rain", "raining", "sunny", "temperature", "forecast", "cold", "hot", "jacket", "coat", "wear"},
    "time": {"time", "clock", "hour", "late", "early"},
    "python": {"calculate", "compute", "sum", "squares", "square", "multiply", "divide", "maths", "math", "python", "code",
               "files", "file", "folder", "directory", "run"},
    "code": {"calculate", "compute", "sum", "squares", "python", "code", "files", "folder", "run"},
    "exchange": {"exchange", "rate", "euro", "euros", "dollar", "dollars", "pound", "pounds", "currency", "convert", "eur", "usd", "gbp"},
    "rate": {"exchange", "rate", "currency", "convert"},
    "train": {"train", "trains", "timetable", "departure", "departures", "station", "travel"},
    "stock": {"stock", "share", "shares", "price", "market"},
    "price": {"price", "cost", "costs", "expensive", "cheap"},
    "news": {"news", "headline", "headlines", "latest"},
    "translate": {"translate", "translation", "french", "spanish", "german", "greek", "italian"},
    "search": {"search", "find", "look", "who", "latest"},
    "email": {"email", "mail", "send", "inbox"},
    "calendar": {"calendar", "meeting", "meetings", "schedule", "appointment", "diary"},
    "joke": {"joke", "funny", "laugh"},
}
_TOOL_STOP = {"get", "the", "for", "and", "with", "current", "from", "that", "this", "what", "your", "into", "return",
              "returns", "given", "city", "text", "tool", "use", "uses", "show", "value", "local"}
_CAP_STOP = {"I", "Should", "What", "Is", "Can", "Do", "Does", "How", "Please", "Use", "Tell", "The", "A", "An", "In", "And",
             "Hi", "Hello", "Python", "Who", "When", "Where", "Which", "Will", "Would", "Could", "My", "Give", "Find", "Look",
             "Show", "Get", "Today", "Now", "If", "Then", "Also", "Are", "Am", "It", "Its", "There", "Me", "We", "You", "Yes", "No"}


def _text(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for p in content:
            if isinstance(p, dict):
                out.append(_text(p.get("text") if "text" in p else p.get("content")))
            else:
                out.append(_text(p))
        return " ".join(o for o in out if o)
    if isinstance(content, dict):
        return _text(content.get("text") or content.get("content"))
    return str(content)


def _short(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _words(s):
    return set(re.findall(r"[a-z]+", (s or "").lower()))


def _tname(t):
    return (t.get("function") or t).get("name", "") if isinstance(t, dict) else ""


def _tdesc(t):
    return ((t.get("function") or t).get("description") or "") if isinstance(t, dict) else ""


def _tparams(t):
    f = (t.get("function") or t) if isinstance(t, dict) else {}
    return f.get("parameters") or f.get("input_schema") or {}


def _tool_words(t):
    base = {w for w in re.split(r"[_\W]+", _tname(t).lower()) if w} | {w for w in _words(_tdesc(t)) if len(w) > 3}
    extra = set()
    for k, syn in _SYN.items():
        if k in base:
            extra |= syn
    return (base | extra) - _TOOL_STOP


def _pick_tool(tools, question, called):
    q = _words(question)
    scored = [(len(_tool_words(t) & q), -i, t) for i, t in enumerate(tools) if _tname(t) and _tname(t) not in called]
    scored = [s for s in scored if s[0] > 0]
    return max(scored, key=lambda s: (s[0], s[1]))[2] if scored else None


def _practice_code(question):
    q = question.lower()
    if any(w in q for w in ("file", "folder", "directory")):
        return "import os\nprint(os.listdir('.'))"
    m = re.search(r"from (\d+) to (\d+)", q) or re.search(r"(\d+) to (\d+)", q)
    if m and "square" in q:
        return f"print(sum(n * n for n in range({m.group(1)}, {m.group(2)} + 1)))"
    if m and "sum" in q:
        return f"print(sum(range({m.group(1)}, {m.group(2)} + 1)))"
    for expr in re.findall(r"[\d\.\s\+\-\*/\(\)%]+", question):
        if re.search(r"\d", expr) and re.search(r"[\+\-\*/%]", expr):
            return f"print({expr.strip()})"
    return "print('The practice model only writes code for simple sums. Connect a real model for more.')"


def _guess_args(tool, question):
    props = _tparams(tool).get("properties") or {}
    caps = [w for w in re.findall(r"\b[A-Z][A-Za-z]+\b", question) if w not in _CAP_STOP]
    nums = re.findall(r"-?\d+(?:\.\d+)?", question)
    args, ci = {}, 0
    for name, spec in props.items():
        spec = spec or {}
        typ = spec.get("type", "string")
        if name.lower() in ("code", "source", "python", "script", "program"):
            args[name] = _practice_code(question)
        elif spec.get("enum"):
            args[name] = spec["enum"][0]
        elif typ in ("number", "integer"):
            v = float(nums.pop(0)) if nums else 1.0
            args[name] = int(v) if typ == "integer" else v
        elif typ == "boolean":
            args[name] = True
        elif caps:
            args[name] = caps[min(ci, len(caps) - 1)]
            ci += 1
        else:
            words = re.findall(r"[A-Za-z]+", question)
            args[name] = words[-1] if words else "something"
    return args


def _err(message):
    return {"error": {"message": message, "type": "invalid_request_error", "code": None}}


def _completion(body, text=None, tool=None, args=None, n=1):
    msg = {"role": "assistant", "content": text, "refusal": None}
    finish = "stop"
    if tool is not None:
        msg["content"] = None
        msg["tool_calls"] = [{"id": f"call_practice_{n}", "type": "function",
                              "function": {"name": _tname(tool), "arguments": json.dumps(args or {})}}]
        finish = "tool_calls"
    return {"id": f"practice-{n}", "object": "chat.completion", "created": int(time.time()),
            "model": body.get("model") or "practice-model",
            "choices": [{"index": 0, "message": msg, "finish_reason": finish, "logprobs": None}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
                      "prompt_tokens_details": {"cached_tokens": 0}, "completion_tokens_details": {"reasoning_tokens": 0}}}


PAIRING_ERROR = ("An assistant message with 'tool_calls' must be followed by tool messages responding to each "
                 "'tool_call_id'. (The practice model enforces the same rule as the real APIs.)")


def _no_tool_answer(msgs, system, question):
    q = question.lower()
    earlier = msgs[:-1]
    history = " ".join(_text(m.get("content")) for m in earlier if m.get("role") in ("user", "assistant"))
    said = [_text(m.get("content")) for m in earlier if m.get("role") == "assistant" and _text(m.get("content")).strip()]
    parts = []
    if "name" in q:
        m = re.search(r"\bmy name is ([A-Za-z]+)", history, re.I)
        parts.append(f"Your name is {m.group(1)}." if m else "I do not know your name: nothing in the messages I received says it.")
    if "live" in q:
        m = re.search(r"\bI live in ([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+)*)", history)
        parts.append(f"You live in {m.group(1)}." if m else "I do not know where you live: nothing in the messages I received says it.")
    if any(w in q for w in ("promise", "promised", "you said", "did you say", "agreed", "offer")):
        parts.append(f'Earlier in this conversation I said: "{_short(said[-1], 160)}" I have no other record, so I go by that.'
                     if said else "There is no earlier reply from me in the messages I received.")
    if parts:
        return "(practice model) " + " ".join(parts)
    lead = f'(practice model, following the system message "{_short(system, 80)}")' if system else "(practice model)"
    return (f'{lead} You asked: "{_short(question, 90)}". A real model would write a proper answer here. '
            "This is a script that shows the plumbing.")


def practice_reply(body):
    """(status, payload) for one chat-completions request to the practice model."""
    if not isinstance(body, dict):
        return 400, _err("The practice model expects a JSON body.")
    if body.get("stream"):
        return 400, _err("The practice model does not stream. Remove stream=True, or connect a real model.")
    msgs = [m for m in (body.get("messages") or []) if isinstance(m, dict)]
    tools = body.get("tools") or []
    for i, m in enumerate(msgs):                          # the rule the real APIs enforce
        if m.get("role") == "assistant" and m.get("tool_calls"):
            want = {c.get("id") for c in m["tool_calls"]}
            got, j = set(), i + 1
            while j < len(msgs) and msgs[j].get("role") == "tool":
                got.add(msgs[j].get("tool_call_id"))
                j += 1
            if not want <= got:
                return 400, _err(PAIRING_ERROR)
    system = " ".join(_text(m.get("content")) for m in msgs if m.get("role") in ("system", "developer")).strip()
    users = [i for i, m in enumerate(msgs) if m.get("role") == "user"]
    question = _text(msgs[users[-1]].get("content")) if users else ""
    after = msgs[users[-1] + 1:] if users else msgs
    total_calls = sum(len(m.get("tool_calls") or []) for m in msgs)
    names, called = {}, set()
    for m in after:
        for c in m.get("tool_calls") or []:
            names[c.get("id")] = (c.get("function") or {}).get("name")
            called.add(names[c.get("id")])
    results = [(names.get(m.get("tool_call_id"), "a tool"), _text(m.get("content"))) for m in after if m.get("role") == "tool"]
    if tools:
        pick = _pick_tool(tools, question, called)
        if pick is not None:
            return 200, _completion(body, tool=pick, args=_guess_args(pick, question), n=total_calls + 1)
    if results:
        text = ("(practice model) Put together from the tool results: "
                + "; ".join(f"{n} said: {_short(r, 160)}" for n, r in results) + ".")
    else:
        text = _no_tool_answer(msgs, system, question)
    return 200, _completion(body, text=text, n=total_calls + 1)


# ----------------------------------------------------------------------------------------------------------------------
# Running a code box
# ----------------------------------------------------------------------------------------------------------------------
class Run:
    """The outcome of one press of Run."""
    def __init__(self):
        self.ok, self.out, self.error, self.ns, self.wire, self.seconds = False, "", None, {}, [], 0.0


def _redact(s):
    return re.sub(r"sk-[A-Za-z0-9_\-]{6,}", "sk-[hidden]", str(s))


def _pairing_broken():
    """True when the newest request carries a tool request with no tool result after it (the bug in the 4.1 starter)."""
    if not WIRE:
        return False
    w = WIRE[-1]
    req = w.get("req") or {}
    msgs = [m for m in (req.get("messages") or []) if isinstance(m, dict)]
    if _fmt(w) == "anthropic":
        for i, m in enumerate(msgs):
            uses = [b.get("id") for b in (m.get("content") or []) if isinstance(b, dict) and b.get("type") == "tool_use"] \
                if m.get("role") == "assistant" and isinstance(m.get("content"), list) else []
            if uses:
                nxt = msgs[i + 1].get("content") if i + 1 < len(msgs) else None
                got = {b.get("tool_use_id") for b in (nxt or []) if isinstance(b, dict) and b.get("type") == "tool_result"} \
                    if isinstance(nxt, list) else set()
                if not set(uses) <= got:
                    return True
        return False
    for i, m in enumerate(msgs):
        if m.get("role") == "assistant" and m.get("tool_calls"):
            want = {c.get("id") for c in m["tool_calls"]}
            got, j = set(), i + 1
            while j < len(msgs) and msgs[j].get("role") == "tool":
                got.add(msgs[j].get("tool_call_id"))
                j += 1
            if not want <= got:
                return True
    return False


def friendly_error(e, env=None):
    """A plain-words title and hint for the errors beginners hit, plus the raw line for the curious."""
    name, msg = type(e).__name__, _redact(str(e))
    line = None
    for fr in traceback.extract_tb(e.__traceback__):
        if fr.filename == "<your code>":
            line = fr.lineno
    status = getattr(e, "status_code", None)
    where = f"Line {line}: " if line else ""
    prov = env["provider"] if env else "The provider"
    low = msg.lower()
    if status == 401:
        title, hint = f"{prov} rejected the key (401)", "Check that the provider in the panel matches your key, and that you pasted all of it."
    elif status == 402 or "insufficient credit" in low or "insufficient_quota" in low:
        title, hint = "The account has no credit", "Add credit with the provider, or pick the practice model."
    elif status == 403:
        title, hint = "This key has no access to that model (403)", "Pick another model in the panel."
    elif status == 404:
        title, hint = "Model not found (404)", "Pick another model in the panel."
    elif status == 429:
        title, hint = "Too many requests (429)", "Wait a minute, then run again."
    elif status == 400 and (_pairing_broken() or ("tool" in low and any(k in low for k in ("followed by", "tool_call_id", "tool_result", "tool_use")))):
        title = "The model asked for a tool, but never got the result (400)"
        hint = ("The next request carried the model's tool request with no tool result after it. "
                "Add the result to the messages: that is the line at the TODO.")
    elif status == 400:
        title, hint = "The provider refused the request (400)", _short(msg, 300)
    elif "ConnectionError" in name or "ConnectError" in name or "TimeoutError" in name:
        title = f"Could not reach {env['provider'] if env else 'the provider'}"
        hint = "Check your internet connection. Some school and office networks block AI providers."
    elif name == "NameError":
        title, hint = f"{where}a name is not defined", f"{msg}. Check the spelling, and that it is defined above the line that uses it."
    elif name in ("ModuleNotFoundError", "ImportError"):
        title, hint = f"{where}{msg}", "This page has openai, anthropic, LangChain, LangGraph and the OpenAI Agents SDK, nothing else."
    elif name == "KeyError" and line:
        title, hint = f"{where}KeyError {msg}", "A dictionary has no entry with that name. If it is a tool name, add it to functions."
    else:
        title, hint = f"{where}{name}", _short(msg, 300)
    return {"title": title, "detail": hint, "line": line, "raw": f"{name}: {_short(msg, 400)}"}


async def run_code(code, env):
    """Run a code box with API_KEY, MODEL and BASE_URL defined. Top-level await works (the Agents SDK needs it)."""
    WIRE.clear()
    run = Run()
    ns = {"__name__": "__main__", "API_KEY": env["key"], "MODEL": env["model"], "BASE_URL": env["base_url"]}
    buf = io.StringIO()
    t0 = time.time()
    try:
        compiled = compile(code, "<your code>", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
    except SyntaxError as e:
        run.error = {"title": f"Line {e.lineno}: this is not valid Python yet", "detail": f"{e.msg}. Check brackets, quotes and commas.",
                     "line": e.lineno, "raw": f"SyntaxError: {e.msg}"}
        return run
    try:
        with contextlib.redirect_stdout(buf):
            result = eval(compiled, ns)
            if inspect.iscoroutine(result):
                await result
        run.ok = True
    except (Exception, SystemExit) as e:
        run.error = friendly_error(e, env)
    run.out, run.ns, run.wire, run.seconds = buf.getvalue(), ns, list(WIRE), time.time() - t0
    return run


# ----------------------------------------------------------------------------------------------------------------------
# Reading the wire: what a call sent and what came back, in either request format
# ----------------------------------------------------------------------------------------------------------------------
def _fmt(w):
    return "anthropic" if (w.get("path") or "").endswith("/messages") else "openai"


def model_calls(run):
    return [w for w in run.wire if any((w.get("path") or "").endswith(p) for p in MODEL_PATHS)]


def ok_calls(run):
    return [w for w in model_calls(run) if w.get("status") == 200 and isinstance(w.get("resp"), dict)]


def sent_messages(w):
    """[(role, text)] carried by a request, system first; tool results appear as role "tool", requests as "tool request"."""
    req = w.get("req") or {}
    out = []
    if _fmt(w) == "anthropic":
        if req.get("system"):
            out.append(("system", _text(req["system"])))
        for m in req.get("messages") or []:
            c = m.get("content")
            if isinstance(c, list):
                for b in c:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "tool_result":
                        out.append(("tool", _text(b.get("content"))))
                    elif b.get("type") == "tool_use":
                        out.append(("tool request", f'{b.get("name")}({json.dumps(b.get("input"))})'))
                    elif b.get("type") == "text":
                        out.append((m.get("role"), b.get("text", "")))
            else:
                out.append((m.get("role"), _text(c)))
    else:
        for m in req.get("messages") or []:
            role = "system" if m.get("role") == "developer" else m.get("role")
            t = _text(m.get("content"))
            if t or role in ("tool", "user", "system"):
                out.append((role, t))
            for c in m.get("tool_calls") or []:
                f = c.get("function") or {}
                out.append(("tool request", f'{f.get("name")}({f.get("arguments")})'))
    return out


def offered_tools(w):
    return [_tname(t) for t in ((w.get("req") or {}).get("tools") or []) if _tname(t)]


def reply_of(w):
    """(text, [(tool name, arguments)]) of a successful reply."""
    r = w.get("resp")
    if not isinstance(r, dict):
        return "", []
    if _fmt(w) == "anthropic":
        blocks = [b for b in (r.get("content") or []) if isinstance(b, dict)]
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        calls = [(b.get("name"), json.dumps(b.get("input"))) for b in blocks if b.get("type") == "tool_use"]
        return text, calls
    msg = ((r.get("choices") or [{}])[0] or {}).get("message") or {}
    calls = [((c.get("function") or {}).get("name"), (c.get("function") or {}).get("arguments"))
             for c in (msg.get("tool_calls") or [])]
    return _text(msg.get("content")), calls


def _err_text(w):
    r = w.get("resp")
    if isinstance(r, dict):
        e = r.get("error")
        return _text(e.get("message") if isinstance(e, dict) else e) or json.dumps(r)[:300]
    return str(r or "")


def loop_facts(run):
    calls = model_calls(run)
    ok = [w for w in calls if w.get("status") == 200 and isinstance(w.get("resp"), dict)]
    tools = [n for w in ok for n, _ in reply_of(w)[1]]
    results = sum(1 for w in calls for r, _ in sent_messages(w) if r == "tool")
    last_text, last_calls = reply_of(ok[-1]) if ok else ("", [])
    done = len(ok) >= 2 and results >= 1 and bool(last_text.strip()) and not last_calls
    return {"calls": len(calls), "ok": len(ok), "tools": tools, "results": results, "answer": last_text, "done": done}


# ----------------------------------------------------------------------------------------------------------------------
# The exercises: starter code, a working answer, and the checks
# ----------------------------------------------------------------------------------------------------------------------
EXERCISES = {
    "1.1": "Send your first call", "1.2": "Change who it is",
    "2.1": "Make it forget", "2.2": "Put words in its mouth",
    "3.1": "Read the request", "3.2": "Describe your own tool",
    "4.1": "Finish the loop", "4.2": "Give it a second tool",
    "5.1": "Let it calculate", "5.2": "Write the rule",
    "6.1": "Same agent, two frameworks", "6.2": "Add a tool in a framework",
    "7.1": "Run it on your own machine",
}
def ex_label(ex):
    """Internal id "3.2" is shown as "1.3.2" (Foundations, practice page 3, exercise 2); "7.1" is page 6's third."""
    return "1.6.3" if ex == "7.1" else f"1.{ex}"


BOX_EXERCISES = {1: ("1.1", "1.2"), 2: ("2.1", "2.2"), 3: ("3.1", "3.2"), 4: ("4.1", "4.2"), 5: ("5.1", "5.2"), 6: ("6.1", "6.2")}
PAGES = {
    1: {"title": "Call a model", "minutes": 6,
        "blurb": "Send your first request to a model from code, read the reply, and change who the model pretends to be.",
        "do": "send a list of messages to a model and change the system message.",
        "have": "the shape of every model call.",
        "terms": [("API call", "your code sends a request, the model sends back one reply"),
                  ("message", "one turn: system, user or assistant"),
                  ("system message", "the developer's standing instructions, sent first")]},
    2: {"title": "Memory is the list you send", "minutes": 6,
        "blurb": "Make the model forget something, then make it remember something it never said.",
        "do": "delete one turn of a conversation, then invent one.",
        "have": "where a model's memory actually lives.",
        "terms": [("conversation history", "the earlier messages, sent again with every call"),
                  ("context", "everything the model reads on one call")]},
    3: {"title": "Describe a tool", "minutes": 8,
        "blurb": "Write the description that lets a model ask for a tool: its name, what it does, and the inputs it needs.",
        "do": "read a tool description, then write one of your own.",
        "have": "the JSON every tool-using agent is built from.",
        "terms": [("tool description", "a tool's name, purpose and inputs, sent as JSON"),
                  ("parameters", "the inputs the model has to fill in")]},
    4: {"title": "Write the loop", "minutes": 11,
        "blurb": "Walk through the code of a real agent loop, write its missing line, then give it a second tool.",
        "do": "finish a working agent loop in Python.",
        "have": "an agent you wrote, in about twenty lines.",
        "terms": [("tool result", "what your function returned, sent back as a message"),
                  ("stop condition", "a reply with no tool request ends the loop")]},
    5: {"title": "Let it run code", "minutes": 9,
        "blurb": "Give the agent a tool that runs Python it writes itself, then write the rule that decides what may run.",
        "do": "run model-written code, then put your own rule in front of it.",
        "have": "your first guardrail, and why it is not enough on its own.",
        "terms": [("code tool", "a tool whose input is code the model wrote"),
                  ("approval rule", "your function that says yes or no before code runs")]},
    6: {"title": "Frameworks, and your own machine", "minutes": 20,
        "blurb": "Run the same agent in the OpenAI Agents SDK, LangChain and LangGraph, then take it home and run it on your computer.",
        "do": "run one agent in different frameworks and find your loop in each.",
        "have": "the words to read any agent framework, and a script that runs on your machine.",
        "terms": [("framework", "a library that runs the loop for you"),
                  ("environment variable", "where a key lives on your machine, outside the code")]},
}


def teaser_html(page):
    p = PAGES[page]
    return (f'<section class="sad-part"><p><span class="sad-lbl">You will do:</span> {p["do"]}<br>'
            f'<span class="sad-lbl">You will have:</span> {p["have"]}</p></section>')


def nav_html(page):
    """Links to the next practice page (in the course shell), or on to Module 02 after the last one."""
    if page < 6:
        nxt = f'<a href="../course/#/practice/1.{page + 1}" target="_top"><b>Next: 1.{page + 1} {PAGES[page + 1]["title"]}</b></a>'
    else:
        nxt = '<a href="../course/#/lesson/prompt-injection" target="_top"><b>Next: Module 02, Prompt injection</b></a>'
    back = '<a href="../course/#/lesson/foundations" target="_top">Back to Foundations</a>'
    return f'<p class="sad-prose">{nxt} &middot; {back}</p>'


STARTER_SYSTEM = "You are a pirate. Answer in one short sentence."
STARTER_ASSISTANT = "Nice to meet you, Ana!"
FRAMEWORKS_FOR = {"openai": ["OpenAI Agents SDK", "LangChain", "LangGraph"], "anthropic": ["LangChain", "LangGraph"]}

_OA = "from openai import OpenAI\n\nclient = OpenAI(api_key=API_KEY, base_url=BASE_URL)\n"
_AN = "from anthropic import Anthropic\n\nclient = Anthropic(api_key=API_KEY)\n"

_WEATHER_FN = ('def get_weather(city):\n'
               '    return f"Light rain and 14 C in {city}"            # a pretend weather service\n')
_TIME_FN = ('def get_time(city):\n'
            '    return f"It is 10:30 in the morning in {city}"      # a pretend clock\n')
_OA_WEATHER = ('    {"type": "function", "function": {\n'
               '        "name": "get_weather",\n'
               '        "description": "Current weather for a city.",\n'
               '        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},\n'
               '    }},\n')
_OA_TIME = ('    {"type": "function", "function": {\n'
            '        "name": "get_time",\n'
            '        "description": "Current local time in a city.",\n'
            '        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},\n'
            '    }},\n')
_AN_WEATHER = ('    {\n'
               '        "name": "get_weather",\n'
               '        "description": "Current weather for a city.",\n'
               '        "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},\n'
               '    },\n')
_AN_TIME = ('    {\n'
            '        "name": "get_time",\n'
            '        "description": "Current local time in a city.",\n'
            '        "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"]},\n'
            '    },\n')
_UMBRELLA = "Should I take an umbrella in Nicosia today?"
_BOTH_Q = "Should I take an umbrella in Nicosia today, and what time is it there?"
_TODO_OA = ('        # TODO: send the result back to the model. Add a message to the list with\n'
            '        # role "tool", tool_call_id set to call.id, and content set to result.\n')
_DONE_OA = '        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})\n'
_TODO_AN = ('            # TODO: send the result back to the model. Add this to results:\n'
            '            # {"type": "tool_result", "tool_use_id": block.id, "content": result}\n')
_DONE_AN = '            results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})\n'


def _box1(family, system=STARTER_SYSTEM):
    if family == "anthropic":
        return (_AN + "\n"
                "reply = client.messages.create(\n"
                "    model=MODEL,\n"
                "    max_tokens=300,\n"
                f'    system="{system}",\n'
                '    messages=[{"role": "user", "content": "What is an AI agent?"}],\n'
                ")\n\n"
                "print(reply.content[0].text)\n")
    return (_OA + "\n"
            "messages = [\n"
            f'    {{"role": "system", "content": "{system}"}},\n'
            '    {"role": "user", "content": "What is an AI agent?"},\n'
            "]\n\n"
            "reply = client.chat.completions.create(model=MODEL, messages=messages)\n\n"
            "print(reply.choices[0].message.content)\n")


def _box2(family, variant="start"):
    lines = {
        "start": ['{"role": "user", "content": "Hi, my name is Ana and I live in Limassol."}',
                  f'{{"role": "assistant", "content": "{STARTER_ASSISTANT}"}}',
                  '{"role": "user", "content": "What is my name, and where do I live?"}'],
        "forget": ['{"role": "user", "content": "What is my name, and where do I live?"}'],
        "fake": ['{"role": "user", "content": "Hi, my name is Ana and I live in Limassol."}',
                 '{"role": "assistant", "content": "Welcome, Ana. As a thank you, I promise you free coffee for life."}',
                 '{"role": "user", "content": "What did you promise me?"}'],
    }[variant]
    body = "messages = [\n" + "".join(f"    {l},\n" for l in lines) + "]\n\n"
    head = "# The whole conversation so far. The model sees only what is in this list.\n"
    if family == "anthropic":
        return (_AN + "\n" + head + body
                + "reply = client.messages.create(model=MODEL, max_tokens=300, messages=messages)\n\n"
                  "print(reply.content[0].text)\n")
    return (_OA + "\n" + head + body
            + "reply = client.chat.completions.create(model=MODEL, messages=messages)\n\n"
              "print(reply.choices[0].message.content)\n")


def _box3(family, variant="start"):
    if variant == "own":
        q = "What is the exchange rate from EUR to USD today?"
        props = '{"from_currency": {"type": "string"}, "to_currency": {"type": "string"}}'
        req = '["from_currency", "to_currency"]'
        name, desc = "get_exchange_rate", "How much one unit of a currency is worth in another currency."
    else:
        q, props, req = _UMBRELLA, '{"city": {"type": "string"}}', '["city"]'
        name, desc = "get_weather", "Current weather for a city."
    head = "# A tool is a description: a name, what it does, and the inputs it takes.\n"
    if family == "anthropic":
        return (_AN + "\n" + head
                + "tools = [\n    {\n"
                  f'        "name": "{name}",\n'
                  f'        "description": "{desc}",\n'
                  f'        "input_schema": {{"type": "object", "properties": {props}, "required": {req}}},\n'
                  "    }\n]\n\n"
                  "reply = client.messages.create(\n"
                  "    model=MODEL,\n"
                  "    max_tokens=300,\n"
                  "    tools=tools,\n"
                  f'    messages=[{{"role": "user", "content": "{q}"}}],\n'
                  ")\n\n"
                  "for block in reply.content:\n"
                  '    if block.type == "text":\n'
                  '        print("Answer text:", block.text)\n'
                  '    if block.type == "tool_use":\n'
                  '        print("The model asks for:", block.name, block.input)\n')
    return (_OA + "\n" + head
            + "tools = [\n    {\n"
              '        "type": "function",\n'
              '        "function": {\n'
              f'            "name": "{name}",\n'
              f'            "description": "{desc}",\n'
              f'            "parameters": {{"type": "object", "properties": {props}, "required": {req}}},\n'
              "        },\n    }\n]\n\n"
              f'messages = [{{"role": "user", "content": "{q}"}}]\n\n'
              "reply = client.chat.completions.create(model=MODEL, messages=messages, tools=tools)\n\n"
              "message = reply.choices[0].message\n"
              'print("Answer text:", message.content)\n'
              "for call in message.tool_calls or []:\n"
              '    print("The model asks for:", call.function.name, call.function.arguments)\n')


def _box4(family, variant="start"):
    two = variant == "two"
    done = variant in ("done", "two")
    fns = _WEATHER_FN + ("\n" + _TIME_FN if two else "")
    table = ('functions = {"get_weather": get_weather, "get_time": get_time}   # tool name: the function that does it\n' if two
             else 'functions = {"get_weather": get_weather}   # tool name: the function that does it\n')
    q = _BOTH_Q if two else _UMBRELLA
    if family == "anthropic":
        tools = "tools = [\n" + _AN_WEATHER + (_AN_TIME if two else "") + "]\n"
        return (_AN + "\n" + fns + "\n" + table + "\n" + tools + "\n"
                f'messages = [{{"role": "user", "content": "{q}"}}]\n\n'
                "for step in range(5):                                   # the agent loop\n"
                "    reply = client.messages.create(model=MODEL, max_tokens=500, tools=tools, messages=messages)\n"
                '    if reply.stop_reason != "tool_use":                  # no tool request: this is the answer\n'
                '        print("Answer:", "".join(b.text for b in reply.content if b.type == "text"))\n'
                "        break\n"
                '    messages.append({"role": "assistant", "content": reply.content})   # keep its request in the list\n'
                "    results = []\n"
                "    for block in reply.content:\n"
                '        if block.type == "tool_use":\n'
                "            result = functions[block.name](**block.input)   # your code runs the tool\n"
                '            print(f"Step {step + 1}: {block.name}({block.input}) returned: {result}")\n'
                + (_DONE_AN if done else _TODO_AN)
                + '    messages.append({"role": "user", "content": results})\n')
    tools = "tools = [\n" + _OA_WEATHER + (_OA_TIME if two else "") + "]\n"
    return ("import json\n" + _OA + "\n" + fns + "\n" + table + "\n" + tools + "\n"
            f'messages = [{{"role": "user", "content": "{q}"}}]\n\n'
            "for step in range(5):                                   # the agent loop\n"
            "    reply = client.chat.completions.create(model=MODEL, messages=messages, tools=tools)\n"
            "    message = reply.choices[0].message\n"
            "    if not message.tool_calls:                          # no tool request: this is the answer\n"
            '        print("Answer:", message.content)\n'
            "        break\n"
            "    messages.append(message)                            # keep its request in the list\n"
            "    for call in message.tool_calls:\n"
            "        args = json.loads(call.function.arguments)\n"
            "        result = functions[call.function.name](**args)  # your code runs the tool\n"
            '        print(f"Step {step + 1}: {call.function.name}({args}) returned: {result}")\n'
            + (_DONE_OA if done else _TODO_OA))


_APPROVE_OPEN = ('def approve(code):\n'
                 '    """Your rule: return True to let this code run, False to block it."""\n'
                 '    return True                                         # for now, everything is allowed\n')
_APPROVE_RULE = ('def approve(code):\n'
                 '    """Your rule: return True to let this code run, False to block it."""\n'
                 '    blocked = ["import os", "open(", "subprocess", "__import__", "import sys", "shutil", "eval(", "exec("]\n'
                 '    return not any(word in code for word in blocked)\n')
_RUNNER = ('def run_python(code):\n'
           '    if not approve(code):\n'
           '        return "Blocked: the rule did not approve this code."\n'
           '    output = io.StringIO()\n'
           '    try:\n'
           '        with contextlib.redirect_stdout(output):\n'
           '            exec(code, {})                              # runs inside this browser tab\n'
           '    except Exception as error:\n'
           '        return f"Error: {error}"\n'
           '    return output.getvalue() or "The code ran but printed nothing. Use print() to show the result."\n')
_MATHS_Q = "What is the sum of the squares of the numbers from 1 to 100? Use Python."


def _box5(family, variant="start"):
    approve = _APPROVE_RULE if variant == "rule" else _APPROVE_OPEN
    desc = "Run Python code and return what it prints. Use print() to show results."
    if family == "anthropic":
        return ("import io, contextlib\n" + _AN + "\n" + approve + "\n" + _RUNNER + "\n"
                'functions = {"run_python": run_python}\n'
                "tools = [{\n"
                '    "name": "run_python",\n'
                f'    "description": "{desc}",\n'
                '    "input_schema": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},\n'
                "}]\n\n"
                f'messages = [{{"role": "user", "content": "{_MATHS_Q}"}}]\n\n'
                "for step in range(5):\n"
                "    reply = client.messages.create(model=MODEL, max_tokens=800, tools=tools, messages=messages)\n"
                '    if reply.stop_reason != "tool_use":\n'
                '        print("Answer:", "".join(b.text for b in reply.content if b.type == "text"))\n'
                "        break\n"
                '    messages.append({"role": "assistant", "content": reply.content})\n'
                "    results = []\n"
                "    for block in reply.content:\n"
                '        if block.type == "tool_use":\n'
                '            print(f"--- the model wrote this code (step {step + 1}) ---")\n'
                '            print(block.input["code"])\n'
                "            result = functions[block.name](**block.input)\n"
                '            print("--- result ---")\n'
                "            print(result)\n"
                '            results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})\n'
                '    messages.append({"role": "user", "content": results})\n')
    return ("import io, json, contextlib\n" + _OA + "\n" + approve + "\n" + _RUNNER + "\n"
            'functions = {"run_python": run_python}\n'
            'tools = [{"type": "function", "function": {\n'
            '    "name": "run_python",\n'
            f'    "description": "{desc}",\n'
            '    "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]},\n'
            "}}]\n\n"
            f'messages = [{{"role": "user", "content": "{_MATHS_Q}"}}]\n\n'
            "for step in range(5):\n"
            "    reply = client.chat.completions.create(model=MODEL, messages=messages, tools=tools)\n"
            "    message = reply.choices[0].message\n"
            "    if not message.tool_calls:\n"
            '        print("Answer:", message.content)\n'
            "        break\n"
            "    messages.append(message)\n"
            "    for call in message.tool_calls:\n"
            "        args = json.loads(call.function.arguments)\n"
            '        print(f"--- the model wrote this code (step {step + 1}) ---")\n'
            '        print(args["code"])\n'
            "        result = functions[call.function.name](**args)\n"
            '        print("--- result ---")\n'
            "        print(result)\n"
            '        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})\n')


def _box6(family, fw, variant="start"):
    two = variant == "two"
    q = _BOTH_Q if two else _UMBRELLA
    tool_defs = ('def get_weather(city: str) -> str:\n'
                 '    """Current weather for a city."""\n'
                 '    return f"Light rain and 14 C in {city}"\n'
                 + ('\n\ndef get_time(city: str) -> str:\n'
                    '    """Current local time in a city."""\n'
                    '    return f"It is 10:30 in the morning in {city}"\n' if two else ""))
    tool_list = "[get_weather, get_time]" if two else "[get_weather]"
    if family == "anthropic":
        chat_import, chat = "from langchain_anthropic import ChatAnthropic\n", "ChatAnthropic(model=MODEL, api_key=API_KEY)"
    else:
        chat_import, chat = "from langchain_openai import ChatOpenAI\n", "ChatOpenAI(model=MODEL, api_key=API_KEY, base_url=BASE_URL)"
    if fw == "OpenAI Agents SDK":
        deco = tool_defs.replace("def get_", "@function_tool\ndef get_")
        return ("from openai import AsyncOpenAI\n"
                "from agents import Agent, Runner, OpenAIChatCompletionsModel, function_tool, set_tracing_disabled\n\n"
                "set_tracing_disabled(True)        # otherwise the SDK uploads a trace of every run to OpenAI\n\n\n"
                + deco + "\n\n"
                "model = OpenAIChatCompletionsModel(model=MODEL, openai_client=AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL))\n\n"
                "agent = Agent(\n"
                '    name="Weather helper",\n'
                '    instructions="Use your tools, then answer in one sentence.",\n'
                f"    tools={tool_list},\n"
                "    model=model,\n"
                ")\n\n"
                f'result = await Runner.run(agent, "{q}")   # Runner.run is the loop\n'
                "print(result.final_output)\n")
    if fw == "LangChain":
        return ("from langchain.agents import create_agent\n" + chat_import + "\n\n" + tool_defs + "\n\n"
                f"model = {chat}\n\n"
                f'agent = create_agent(model=model, tools={tool_list}, system_prompt="Use your tools, then answer in one sentence.")\n\n'
                f'result = agent.invoke({{"messages": [{{"role": "user", "content": "{q}"}}]}})   # invoke runs the loop\n\n'
                'for message in result["messages"]:        # the message list the loop built\n'
                '    print(f"{message.type:>6}: {message.content or getattr(message, \'tool_calls\', \'\')}")\n')
    return (chat_import
            + "from langgraph.graph import StateGraph, MessagesState, START\n"
              "from langgraph.prebuilt import ToolNode, tools_condition\n\n\n" + tool_defs + "\n\n"
            + f"model = {chat}.bind_tools({tool_list})\n\n\n"
              "def call_model(state: MessagesState):\n"
              '    return {"messages": [model.invoke(state["messages"])]}\n\n\n'
              "graph = StateGraph(MessagesState)\n"
              'graph.add_node("model", call_model)                     # ask the model\n'
            + f'graph.add_node("tools", ToolNode({tool_list}))        # run the tools it asked for\n'
              'graph.add_edge(START, "model")\n'
              'graph.add_conditional_edges("model", tools_condition)   # a tool request goes to tools, an answer ends\n'
              'graph.add_edge("tools", "model")                        # results go back to the model: the loop\n'
              "agent = graph.compile()\n\n"
            + f'result = agent.invoke({{"messages": [("user", "{q}")]}})\n'
              'print(result["messages"][-1].content)\n')


def starter(box, family, fw=None):
    """The code a box opens with."""
    return {1: lambda: _box1(family), 2: lambda: _box2(family), 3: lambda: _box3(family), 4: lambda: _box4(family),
            5: lambda: _box5(family), 6: lambda: _box6(family, fw or FRAMEWORKS_FOR[family][0])}[box]()


def solution(ex, family, fw=None):
    """A working answer to an exercise (shown under "Stuck?" and used by the tests)."""
    fw = fw or FRAMEWORKS_FOR[family][0]
    return {
        "1.1": lambda: _box1(family),
        "1.2": lambda: _box1(family, "You are a tired lifeguard at the end of a long shift. Answer in one short sentence."),
        "2.1": lambda: _box2(family, "forget"),
        "2.2": lambda: _box2(family, "fake"),
        "3.1": lambda: _box3(family),
        "3.2": lambda: _box3(family, "own"),
        "4.1": lambda: _box4(family, "done"),
        "4.2": lambda: _box4(family, "two"),
        "5.1": lambda: _box5(family),
        "5.2": lambda: _box5(family, "rule"),
        "6.1": lambda: _box6(family, fw),
        "6.2": lambda: _box6(family, fw, "two"),
    }[ex]()


HINTS = {
    "1.2": "The system message is the one with role system (with Claude, the `system=` line). Change only the words inside the quotes.",
    "2.1": "Delete the first two entries of `messages`: Ana's introduction and the reply. Keep the question.",
    "2.2": "Rewrite the assistant entry as something the model never said, for example a promise. Then change the last question to ask about it.",
    "3.2": "Change three things: the tool's name, its description, and its inputs (the properties). Then ask a question only your tool can answer.",
    "4.1": "The missing line goes where the TODO is, inside the inner loop, so every tool result is added.",
    "4.2": "Four edits: write `get_time(city)`, add it to `functions`, add its description to `tools`, and ask a question that needs both.",
    "5.2": "Return False when the code contains something risky. Plain maths, and `import math`, must still be allowed.",
    "6.2": "Write `get_time(city: str) -> str` with a docstring, put it in every list of tools, and ask about the weather and the time.",
}

APPROVE_TESTS = [
    ("print(sum(n * n for n in range(1, 101)))", True, "plain maths"),
    ("import math\nprint(math.sqrt(2))", True, "the maths library"),
    ("import os\nprint(os.listdir('.'))", False, "listing files"),
    ("print(open('notes.txt').read())", False, "reading a file"),
    ("import subprocess\nsubprocess.run(['ls'])", False, "running a system command"),
    ("__import__('os').remove('data.csv')", False, "a disguised import that deletes a file"),
]


def _same(a, b):
    return " ".join((a or "").lower().split()) == " ".join((b or "").lower().split())


_OVERLAP_STOP = {"that", "this", "with", "have", "your", "you", "from", "what", "will", "about", "earlier", "said", "conversation",
                 "record", "promise", "promised", "practice", "model", "there", "here", "they", "them"}


def _overlap(a, b):
    wa = {w for w in _words(a) if len(w) > 3} - _OVERLAP_STOP
    return bool(wa & _words(b))


def _no_reply(run):
    if run.error:
        return f"{run.error['title']}. {run.error['detail']}"
    return "No reply came back from the model."


def grade(box, run, env, fw=None, passed=frozenset()):
    """[(exercise id, ok, message)] for the box's two exercises, plus tokens to remember (passed ids, frameworks done)."""
    practice = env["provider"] == PRACTICE
    ok = ok_calls(run)
    last = ok[-1] if ok else None
    text = reply_of(last)[0] if last else ""
    checks = []
    if box == 1:
        if not last:
            checks = [("1.1", False, _no_reply(run)), ("1.2", False, "Get 1.1.1 working first.")]
        else:
            checks.append(("1.1", bool(text.strip()), f'The model replied: "{_short(text, 160)}"' if text.strip()
                           else "A reply came back with no text in it."))
            sysmsg = next((t for r, t in sent_messages(last) if r == "system"), "")
            if not sysmsg.strip():
                checks.append(("1.2", False, "There is no system message in what you sent. Put one back, with a role of your own."))
            elif _same(sysmsg, STARTER_SYSTEM):
                checks.append(("1.2", False, "The system message is still the pirate one. Change its words and run again."))
            else:
                checks.append(("1.2", bool(text.strip()), f'Your system message went out: "{_short(sysmsg, 100)}". '
                                                          "Compare this reply with the pirate one."))
    elif box == 2:
        if not last:
            checks = [("2.1", False, _no_reply(run)), ("2.2", False, _no_reply(run))]
        else:
            sent = sent_messages(last)
            convo = [t for r, t in sent if r in ("user", "assistant")]
            if not any(re.search(r"\bana\b", t, re.I) for t in convo):
                checks.append(("2.1", True, f'The name Ana is not in what you sent, so the model never saw it. It replied: "{_short(text, 160)}"'))
            else:
                checks.append(("2.1", False, "Ana is still in what you sent. Delete the first two messages and run again."))
            mine = [t for r, t in sent if r == "assistant" and not _same(t, STARTER_ASSISTANT)]
            if mine:
                went = " It went along with it." if _overlap(mine[-1], text) else " Did it go along with it?"
                checks.append(("2.2", True, f'You sent an assistant turn the model never wrote: "{_short(mine[-1], 100)}". '
                                            f'It replied: "{_short(text, 160)}".{went}'))
            else:
                checks.append(("2.2", False, "No assistant message of your own went out yet. Change the words of the assistant "
                                             "message, then ask about them."))
    elif box == 3:
        calls = [(n, a) for w in ok for n, a in reply_of(w)[1]]
        if not last:
            checks = [("3.1", False, _no_reply(run)), ("3.2", False, _no_reply(run))]
        else:
            if calls:
                n, a = calls[-1]
                what = "wrote no answer text" if not text.strip() else f'also wrote "{_short(text, 80)}"'
                checks.append(("3.1", True, f"The model asked for {n}({_short(a, 80)}) and {what}. Nothing has run: "
                                            "your code has not called any function."))
            else:
                checks.append(("3.1", False, "The model answered in text without asking for the tool. Run again, or make the "
                                             "question need the tool."))
            mine = [(n, a) for n, a in calls if n != "get_weather"]
            offered = offered_tools(last)
            if mine:
                checks.append(("3.2", True, f"It asked for your tool: {mine[-1][0]}({_short(mine[-1][1], 80)})."))
            elif not [t for t in offered if t != "get_weather"]:
                checks.append(("3.2", False, "You still offer only get_weather. Rename the tool and describe your own."))
            else:
                tip = (" The practice model only matches words, so mention what your tool does in the question." if practice else "")
                checks.append(("3.2", False, f"Your tool {offered[0]} was offered, but the model did not ask for it. "
                                             f"Make the question need it.{tip}"))
    elif box in (4, 6):
        f = loop_facts(run)
        ids = BOX_EXERCISES[box]
        tools = ", ".join(dict.fromkeys(f["tools"])) or "no tool"
        if f["done"]:
            first = (f"{f['ok']} calls: the model asked for {tools}, got the result back, and answered: "
                     f'"{_short(f["answer"], 140)}"')
        elif run.error:
            first = f"{run.error['title']}. {run.error['detail']}"
        elif f["ok"] == 1 and f["tools"] and not f["results"]:
            first = "The model asked for a tool and your code ran it, but the result never went back, so the loop stopped."
        elif f["ok"] and not f["tools"]:
            first = "The model answered straight away without asking for a tool. Run again, or make the question need the tool."
        else:
            first = "The loop did not finish with an answer."
        if box == 4:
            checks.append(("4.1", f["done"], first))
        else:
            fws = {p[3:] for p in passed if p.startswith("fw:")} | ({fw} if f["done"] else set())
            more = "" if len(fws) >= 2 else " Now pick another framework and run it."
            checks.append(("6.1", f["done"] and len(fws) >= 2,
                           (f"{fw}: {first}" if f["done"] else first) + (f" Frameworks done: {', '.join(sorted(fws))}." if fws else "") + more))
        distinct = list(dict.fromkeys(f["tools"]))
        if f["done"] and len(distinct) >= 2:
            checks.append((ids[1], True, f"Two tools in one run: {', '.join(distinct)}."))
        elif f["done"]:
            checks.append((ids[1], False, f"Only {distinct[0] if distinct else 'one tool'} was called. Add get_time and ask a "
                                          "question that needs both tools."))
        else:
            checks.append((ids[1], False, "Get the loop to finish first."))
    elif box == 5:
        f = loop_facts(run)
        coded = [n for n in f["tools"] if "python" in (n or "") or "code" in (n or "")]
        if f["done"] and coded:
            checks.append(("5.1", True, f'The model wrote code, approve() let it run, and it answered: "{_short(f["answer"], 140)}"'))
        elif run.error:
            checks.append(("5.1", False, f"{run.error['title']}. {run.error['detail']}"))
        elif not coded:
            checks.append(("5.1", False, "The model answered without running any code. Run again, or ask for something to calculate."))
        else:
            checks.append(("5.1", False, "The code ran but the loop did not finish with an answer."))
        approve = run.ns.get("approve")
        if not callable(approve):
            checks.append(("5.2", False, "Keep a function named approve(code); the check calls it."))
        else:
            marks, wrong = [], 0
            for code, want, label in APPROVE_TESTS:
                try:
                    got = bool(approve(code))
                except Exception as e:
                    got = None
                    label = f"{label} (your rule raised {type(e).__name__})"
                good = got == want
                wrong += not good
                verb = ("allows" if want else "blocks") if good else ("should allow" if want else "should block")
                marks.append(f"{'&#10003;' if good else '&#10007;'} {verb} {label}")
            if wrong == 0:
                checks.append(("5.2", True, "Your rule passes all six snippets: " + " &middot; ".join(marks)))
            else:
                lead = "Right now approve() allows everything. " if all(approve(c) for c, _, _ in APPROVE_TESTS[2:]) else ""
                checks.append(("5.2", False, lead + " &middot; ".join(marks)))
    tokens = {ex for ex, good, _ in checks if good} | {"ran"}       # "ran" unlocks the prediction answers after any run
    if box == 6 and loop_facts(run)["done"] and fw:
        tokens.add(f"fw:{fw}")
    return checks, tokens


# ----------------------------------------------------------------------------------------------------------------------
# Panels and pictures (HTML strings; the page wraps them in mo.Html)
# ----------------------------------------------------------------------------------------------------------------------
def _e(s):
    return html.escape(str(s or ""))


def checks_html(checks, passed):
    rows = []
    for ex, good, msg in checks:
        earlier = (not good) and ex in passed
        mark = "&#10003;" if good or earlier else "&#9675;"
        note = "Passed on an earlier run. This run: " if earlier else ""
        rows.append(f'<li data-ok="{"true" if good or earlier else "false"}"><b>{mark} Exercise {ex_label(ex)} &middot; {EXERCISES[ex]}</b>'
                    f"<span>{note}{msg}</span></li>")
    allok = all(g or ex in passed for ex, g, _ in checks)
    return f'<div class="sad-fb sad-checks" data-ok="{"true" if allok else "false"}"><ul>{"".join(rows)}</ul></div>'


def result_html(run, checks, passed):
    parts = []
    if run.error:
        parts.append(f'<div class="sad-fb" data-ok="false"><b>{_e(run.error["title"])}</b> &middot; {_e(run.error["detail"])}'
                     f'<br><span class="sad-dim">{_e(run.error["raw"])}</span></div>')
    out = run.out.strip()
    body = _e(out[-6000:]) if out else '<span class="sad-dim">(nothing printed)</span>'
    parts.append(f'<div class="sad-mp"><div class="sad-mp-title">What your code printed &middot; {run.seconds:.1f} s</div>'
                 f'<div class="sad-mp-body">{body}</div></div>')
    parts.append(checks_html(checks, passed))
    return "".join(parts)


def wire_html(wire):
    calls = [w for w in wire if any((w.get("path") or "").endswith(p) for p in MODEL_PATHS)]
    if not calls:
        return '<p class="sad-cap">No call to a model went out in this run.</p>'
    blocks = []
    for i, w in enumerate(calls, 1):
        sent = "".join(f"<div><b>{_e(r)}</b> {_e(_short(t, 200))}</div>" for r, t in sent_messages(w))
        tools = offered_tools(w)
        if tools:
            sent += f"<div><b>tools offered</b> {_e(', '.join(tools))}</div>"
        if w.get("status") != 200:
            got = f"<div><b>error {w.get('status')}</b> {_e(_short(_err_text(w), 240))}</div>"
        else:
            text, calls_ = reply_of(w)
            got = (f"<div><b>text</b> {_e(_short(text, 240))}</div>" if text.strip() else "")
            got += "".join(f"<div><b>tool request</b> {_e(n)}({_e(_short(a, 120))})</div>" for n, a in calls_)
            got = got or "<div>(empty)</div>"
        raw = _e(json.dumps({"request": w.get("req"), "response": w.get("resp")}, indent=2)[:8000])
        blocks.append(f'<div class="sad-wire"><p class="sad-cap">Call {i} &middot; {_e(w.get("method"))} {_e(w.get("host"))}'
                      f'{_e(w.get("path"))} &middot; status {_e(w.get("status"))}</p>'
                      f'<div class="sad-wire-grid"><div><h4>You sent</h4>{sent or "(nothing)"}</div>'
                      f"<div><h4>It sent back</h4>{got}</div></div>"
                      f'<details><summary>Raw JSON</summary><pre class="sad-wire-raw">{raw}</pre></details></div>')
    return "".join(blocks)


_G, _B, _L = "#9ca3af", "#1d4ed8", "#d1d5db"


def _box(x, y, w, h, label, stroke=_G, weight=1.5, size=14):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#fafaf9" stroke="{stroke}" stroke-width="{weight}"/>'
            f'<text x="{x + w / 2}" y="{y + h / 2 + 5}" text-anchor="middle" fill="#1a1a1a" style="font:500 {size}px system-ui;">{label}</text>')


def _defs():
    return ('<defs>'
            f'<marker id="kzg" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{_G}"/></marker>'
            f'<marker id="kzb" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{_B}"/></marker>'
            f'<marker id="kzl" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{_L}"/></marker>'
            '</defs>')


def _label(x, y, t, color="#5f6368", weight=500, anchor="middle"):
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{color}" style="font:{weight} 14px system-ui;">{t}</text>'


def _fig(cap, svg, items=(), aria=""):
    lis = "".join(f"<li>{i}</li>" for i in items)
    return (f'<div class="sad-flowbox"><p class="sad-cap">{cap}</p>'
            f'<svg viewBox="0 0 360 {svg[0]}" width="100%" role="img" aria-label="{aria or cap}" '
            f'style="max-width:560px;display:block;margin:0 auto;">{_defs()}{svg[1]}</svg>'
            + (f'<ol class="sad-ul" style="font-size:15px;line-height:1.5;margin-top:4px;">{lis}</ol>' if lis else "") + "</div>")


def call_svg():
    s = (_box(1, 30, 110, 56, "your code") + _box(249, 30, 110, 56, "model")
         + f'<line x1="111" y1="46" x2="249" y2="46" stroke="{_B}" stroke-width="2.5" marker-end="url(#kzb)"/>' + _label(180, 36, "1", _B, 600)
         + f'<line x1="249" y1="72" x2="111" y2="72" stroke="{_G}" stroke-width="1.5" marker-end="url(#kzg)"/>' + _label(180, 92, "2", "#5f6368", 600))
    return _fig("one call", (110, s), ["your code sends the model's name and a list of messages: system, user, assistant",
                                       "the model sends back one new message, and that is all"])


def memory_svg():
    def bar(x, y, t, dim=False):
        return (f'<rect x="{x}" y="{y}" width="160" height="26" rx="4" fill="{"#f4f4f5" if dim else "#fafaf9"}" stroke="{_L if dim else _G}"/>'
                f'<text x="{x + 8}" y="{y + 18}" fill="{"#5f6368" if dim else "#1a1a1a"}" style="font:400 13px system-ui;">{t}</text>')
    s = (_label(90, 18, "call 1 sends", "#5f6368", 600) + bar(10, 28, "user: Hi, I am Ana")
         + _label(270, 18, "call 2 sends", "#5f6368", 600) + bar(190, 28, "user: Hi, I am Ana", True)
         + bar(190, 60, "assistant: Hi Ana!", True) + bar(190, 92, "user: What is my name?")
         + f'<line x1="172" y1="41" x2="188" y2="41" stroke="{_B}" stroke-width="2" marker-end="url(#kzb)"/>')
    return _fig("the same conversation, two calls", (126, s),
                ["call 1: one message goes out", "call 2: your code sends the whole list again, plus the new question",
                 "nothing is kept on the model's side: delete a line and it was never said"])


WALK = {
    1: ("Your code sends the messages and the tool descriptions. That is arrow 1 in the picture.",
        ("client.chat.completions.create(", "client.messages.create(")),
    2: ("The reply is either a tool request or the answer, and this line tells them apart. Arrow 2.",
        ("if not message.tool_calls", 'if reply.stop_reason != "tool_use"')),
    3: ("Your code runs the tool the model asked for. Arrow 3: the only step where anything happens.",
        ("result = functions[", "result = functions[")),
    4: ("The result goes back into the list and the loop calls the model again. Arrow 4. This line is missing: "
        "you write it in exercise 1.4.1.", ("# TODO", "# TODO")),
    5: ("With the result in hand, the model answers in text and the loop stops. Arrow 5.",
        ('print("Answer:"', 'print("Answer:"')),
}


def code_walk_html(step, family):
    """The 1.4 starter with the lines of one step lit."""
    marker = WALK[step][1][0 if family == "openai" else 1]
    lines = starter(4, family).rstrip("\n").splitlines()
    lit = {i for i, l in enumerate(lines) if marker in l}
    if step == 4:                                        # the TODO comment runs over two lines
        lit |= {i + 1 for i in lit if i + 1 < len(lines) and lines[i + 1].strip().startswith("#")}
    body = "\n".join(f'<span class="sad-hl">{_e(l)}</span>' if i in lit else f'<span class="sad-dim">{_e(l)}</span>'
                     for i, l in enumerate(lines))
    return (f'<div class="sad-mp"><div class="sad-mp-title">the loop you finish below &middot; step {step} of 5</div>'
            f'<div class="sad-mp-body">{body}</div></div>')


def tool_anatomy_html(family):
    """A tool description with each part labelled."""
    if family == "anthropic":
        rows = [('{', ''), ('    "name": "get_weather",', 'what the model calls it'),
                ('    "description": "Current weather for a city.",', 'how it decides when to ask'),
                ('    "input_schema": {', 'what it must fill in'),
                ('        "type": "object",', ''), ('        "properties": {"city": {"type": "string"}},', 'one input, a city name'),
                ('        "required": ["city"],', 'it cannot leave this out'), ('    },', ''), ('}', '')]
    else:
        rows = [('{"type": "function", "function": {', ''), ('    "name": "get_weather",', 'what the model calls it'),
                ('    "description": "Current weather for a city.",', 'how it decides when to ask'),
                ('    "parameters": {', 'what it must fill in'),
                ('        "type": "object",', ''), ('        "properties": {"city": {"type": "string"}},', 'one input, a city name'),
                ('        "required": ["city"],', 'it cannot leave this out'), ('    },', ''), ('}}', '')]
    width = max(len(c) for c, _ in rows) + 3
    body = "\n".join(_e(c) + (" " * (width - len(c)) + f'<span class="sad-dim"># {n}</span>' if n else "") for c, n in rows)
    return (f'<div class="sad-mp"><div class="sad-mp-title">a tool description, part by part</div>'
            f'<div class="sad-mp-body">{body}</div></div>')


def gate_svg():
    s = (_box(1, 40, 100, 44, "its code") + _box(128, 40, 104, 44, "approve()", _B, 2.5)
         + _box(262, 8, 96, 40, "run it") + _box(262, 76, 96, 40, "block it")
         + f'<line x1="101" y1="62" x2="126" y2="62" stroke="{_G}" stroke-width="1.5" marker-end="url(#kzg)"/>'
         + f'<path d="M232 54L260 30" fill="none" stroke="{_G}" stroke-width="1.5" marker-end="url(#kzg)"/>' + _label(238, 32, "yes")
         + f'<path d="M232 70L260 94" fill="none" stroke="{_G}" stroke-width="1.5" marker-end="url(#kzg)"/>' + _label(238, 104, "no"))
    return _fig("every piece of code passes your rule first", (124, s),
                ["the model writes code as the input to a run_python tool",
                 "approve(code) is a function you write: it reads the code and says yes or no",
                 "either way, the outcome goes back to the model as the tool's result"])


def framework_table_html():
    rows = [
        ("the model call", "the model you give the Agent", "ChatOpenAI or ChatAnthropic", "the model node"),
        ("a tool description", "@function_tool on a function", "a function with a docstring", "ToolNode"),
        ("the loop", "Runner.run", "create_agent, then invoke", "edges from model to tools and back"),
        ("the message list", "result.new_items", 'result["messages"]', "MessagesState"),
        ("the seam: where a request becomes an action", "the body of your @function_tool function",
         "your tool function, called inside the agent", "the ToolNode"),
    ]
    head = "<tr><th>What you built by hand</th><th>OpenAI Agents SDK</th><th>LangChain</th><th>LangGraph</th></tr>"
    body = "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in r) + "</tr>" for r in rows)
    return f'<div class="sad-tablebox"><table class="sad-table">{head}{body}</table></div>'


def laptop_parts(provider):
    """(install command, key variable, the agent.py file) for running the Part 4 agent on a laptop."""
    if provider == "Anthropic":
        var = "ANTHROPIC_API_KEY"
        code = _box4("anthropic", "two").replace(
            "from anthropic import Anthropic\n\nclient = Anthropic(api_key=API_KEY)\n",
            "import os\nfrom anthropic import Anthropic\n\nclient = Anthropic(api_key=os.environ[\"ANTHROPIC_API_KEY\"])\n"
            'MODEL = "claude-haiku-4-5"\n')
        return "pip install anthropic", var, code.replace(f'"content": "{_BOTH_Q}"', '"content": input("Ask the agent: ")')
    if provider == "OpenRouter":
        var, client = "OPENROUTER_API_KEY", ('client = OpenAI(base_url="https://openrouter.ai/api/v1", '
                                             'api_key=os.environ["OPENROUTER_API_KEY"])\nMODEL = "openai/gpt-4o-mini"\n')
    else:
        var, client = "OPENAI_API_KEY", 'client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])\nMODEL = "gpt-4o-mini"\n'
    code = _box4("openai", "two").replace("import json\nfrom openai import OpenAI\n\nclient = OpenAI(api_key=API_KEY, base_url=BASE_URL)\n",
                                          "import json, os\nfrom openai import OpenAI\n\n" + client)
    return "pip install openai", var, code.replace(f'"content": "{_BOTH_Q}"', '"content": input("Ask the agent: ")')


# ----------------------------------------------------------------------------------------------------------------------
# Self-check: python notebooks/koda_zero.py (no browser, no key, no network)
# ----------------------------------------------------------------------------------------------------------------------
def _selftest():
    # every starter and every working answer is valid Python with top-level await allowed
    for fam in ("openai", "anthropic"):
        for box in range(1, 7):
            for fw in (FRAMEWORKS_FOR[fam] if box == 6 else [None]):
                compile(starter(box, fam, fw), f"<starter {box} {fam} {fw}>", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
        for ex in BOX_EXERCISES.values():
            for e in ex:
                for fw in (FRAMEWORKS_FOR[fam] if e.startswith("6") else [None]):
                    compile(solution(e, fam, fw), f"<solution {e} {fam} {fw}>", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
        for prov in ("OpenAI", "OpenRouter", "Anthropic"):
            compile(laptop_parts(prov)[2], f"<laptop {prov}>", "exec")
    # the TODO line is missing from the 4.1 starter and present in the answer
    assert _DONE_OA not in starter(4, "openai") and _DONE_OA in solution("4.1", "openai")
    assert _DONE_AN not in starter(4, "anthropic") and _DONE_AN in solution("4.1", "anthropic")
    # the practice model: a tool request, then an answer from the result, and the pairing rule
    tool = [{"type": "function", "function": {"name": "get_weather", "description": "Current weather for a city.",
                                              "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}}}]
    st, r = practice_reply({"model": "m", "messages": [{"role": "user", "content": _UMBRELLA}], "tools": tool})
    call = r["choices"][0]["message"]["tool_calls"][0]
    assert st == 200 and call["function"]["name"] == "get_weather" and json.loads(call["function"]["arguments"]) == {"city": "Nicosia"}
    asked = {"role": "assistant", "content": None, "tool_calls": [call]}
    st, r = practice_reply({"messages": [{"role": "user", "content": _UMBRELLA}, asked], "tools": tool})
    assert st == 400 and "tool_call_id" in r["error"]["message"]
    st, r = practice_reply({"messages": [{"role": "user", "content": _UMBRELLA}, asked,
                                         {"role": "tool", "tool_call_id": call["id"], "content": "Light rain"}], "tools": tool})
    assert st == 200 and "Light rain" in r["choices"][0]["message"]["content"]
    # two tools are called one after the other
    both = tool + [{"type": "function", "function": {"name": "get_time", "description": "Current local time in a city.",
                                                     "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}}}]
    st, r = practice_reply({"messages": [{"role": "user", "content": _BOTH_Q}, asked,
                                         {"role": "tool", "tool_call_id": call["id"], "content": "Light rain"}], "tools": both})
    assert r["choices"][0]["message"]["tool_calls"][0]["function"]["name"] == "get_time"
    # memory: it knows what is in the list and nothing else
    convo = [{"role": "user", "content": "Hi, my name is Ana and I live in Limassol."}, {"role": "assistant", "content": STARTER_ASSISTANT},
             {"role": "user", "content": "What is my name, and where do I live?"}]
    assert "Ana" in practice_reply({"messages": convo})[1]["choices"][0]["message"]["content"]
    assert "do not know" in practice_reply({"messages": convo[2:]})[1]["choices"][0]["message"]["content"]
    fake = [{"role": "assistant", "content": "I promise you free coffee for life."}, {"role": "user", "content": "What did you promise me?"}]
    assert "coffee" in practice_reply({"messages": fake})[1]["choices"][0]["message"]["content"]
    # the code tool: maths becomes code
    assert "range(1, 100 + 1)" in _practice_code(_MATHS_Q)
    # the reference rule passes the approve tests, the open rule does not
    ns = {}
    exec(_APPROVE_RULE, ns)
    assert all(bool(ns["approve"](c)) == want for c, want, _ in APPROVE_TESTS)
    # graders on a hand-built wire: a finished two-tool loop passes 4.1 and 4.2
    def w(req, resp, status=200):
        return {"host": PRACTICE_HOST, "path": "/v1/chat/completions", "method": "POST", "req": req, "resp": resp, "status": status}
    run = Run()
    m1 = {"messages": [{"role": "user", "content": _BOTH_Q}], "tools": both}
    r1 = practice_reply(m1)[1]
    c1 = r1["choices"][0]["message"]
    m2 = {"messages": m1["messages"] + [c1, {"role": "tool", "tool_call_id": c1["tool_calls"][0]["id"], "content": "Light rain"}], "tools": both}
    r2 = practice_reply(m2)[1]
    c2 = r2["choices"][0]["message"]
    m3 = {"messages": m2["messages"] + [c2, {"role": "tool", "tool_call_id": c2["tool_calls"][0]["id"], "content": "10:30"}], "tools": both}
    r3 = practice_reply(m3)[1]
    run.wire = [w(m1, r1), w(m2, r2), w(m3, r3)]
    env = make_env(PRACTICE, "", None)
    checks, tokens = grade(4, run, env)
    assert [c[1] for c in checks] == [True, True], checks
    assert env_problem(make_env("OpenAI", "", "gpt-4o-mini")) and not env_problem(env)
    assert "sk-[hidden]" in _redact("Incorrect key sk-abcdefghijkl")
    # every step of the code walk lights at least one line, in both formats; labels map as shown on the pages
    for fam in ("openai", "anthropic"):
        for st in WALK:
            assert 'class="sad-hl"' in code_walk_html(st, fam), (fam, st)
        assert "how it decides when to ask" in tool_anatomy_html(fam)
    assert code_walk_html(4, "openai").count('class="sad-hl"') == 2
    assert [ex_label(e) for e in ("1.1", "3.2", "7.1")] == ["1.1.1", "1.3.2", "1.6.3"]
    assert all(set(PAGES[p]) >= {"title", "minutes", "blurb", "do", "have", "terms"} for p in range(1, 7))
    assert "practice/1.4" in nav_html(3) and "prompt-injection" in nav_html(6)
    print("koda_practice self-check: ok")


if __name__ == "__main__":
    _selftest()
