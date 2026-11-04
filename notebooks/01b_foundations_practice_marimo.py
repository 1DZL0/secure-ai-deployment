import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium", css_file="../course/course.css", app_title="Foundations practice")


@app.cell
def _():
    import marimo as mo
    import koda_practice as kz
    from koda_lab import exercise_html, hero, recap_html, terms_html

    def fb_html(ok, head, body):
        return mo.Html(f'<div class="sad-fb" data-ok="{ok}"><b>{head}</b> &middot; {body}</div>')

    def predict_view(pick, correct, why, ran=True):
        # a prediction is locked in first; the explanation shows once the box below has run
        if pick is None:
            return mo.md("_Pick an answer before you run the box below._")
        if not ran:
            return fb_html("none", "Locked in", f"{pick}. Now run the box below and compare.")
        return fb_html("true" if pick == correct else "false",
                       "&#10003; you called it" if pick == correct else "&#10007; not quite", why)

    def hint_view(exs, family, fw=None):
        _items = {}
        for _ex in exs:
            _items[f"Stuck on {kz.ex_label(_ex)}? A hint"] = mo.md(kz.HINTS[_ex])
            _items[f"Show a working answer for {kz.ex_label(_ex)}"] = mo.md("```python\n" + kz.solution(_ex, family, fw) + "```")
        return mo.accordion(_items)

    def show_run(run, checks, passed):
        _n = len(kz.model_calls(run))
        return mo.vstack([
            mo.Html(kz.result_html(run, checks, passed)),
            mo.accordion({f"What went over the wire ({_n} call{'s' if _n != 1 else ''})": mo.Html(kz.wire_html(run.wire))}),
        ])

    return exercise_html, fb_html, hero, hint_view, kz, mo, predict_view, recap_html, show_run, terms_html


@app.cell
def _(mo):
    # each code box remembers which of its exercises have passed (and that it has run at all)
    get_p1, set_p1 = mo.state(frozenset())
    get_p2, set_p2 = mo.state(frozenset())
    get_p3, set_p3 = mo.state(frozenset())
    get_p4, set_p4 = mo.state(frozenset())
    get_p5, set_p5 = mo.state(frozenset())
    get_p6, set_p6 = mo.state(frozenset())
    get_step, set_step = mo.state(1)
    return get_p1, get_p2, get_p3, get_p4, get_p5, get_p6, get_step, set_p1, set_p2, set_p3, set_p4, set_p5, set_p6, set_step


@app.cell
def _(kz, mo):
    # one notebook, six practice pages: ?part=1 to ?part=6 picks the page (the course shell links each one)
    _q = mo.query_params()
    try:
        page = int(str(_q.get("part") or "1").strip())
    except ValueError:
        page = 1
    page = page if page in kz.PAGES else 1
    return (page,)


@app.cell
def _(hero, kz, mo, page, terms_html):
    _p = kz.PAGES[page]
    mo.vstack([
        mo.Html(hero(f"Foundations &middot; hands-on practice 1.{page} &middot; page {page} of 6", _p["title"], _p["blurb"],
                     meta=(f"about {_p['minutes']} minutes", "runs in your browser, nothing to install",
                           "practice model or your own key"))),
        mo.Html(terms_html(_p["terms"])),
        mo.Html(kz.teaser_html(page)),
    ])
    return


@app.cell
def _(mo, page):
    if page == 1:
        _intro = mo.md(
            """
            **First, choose where your code sends its requests.**

            - **Practice model.** A small script inside this page that answers by simple rules. No key, no cost, and not AI,
              but every box runs on it, so you can learn the plumbing first.
            - **OpenRouter, OpenAI or Anthropic.** A real model, on your own key. One run costs a fraction of a cent with the
              default model.
            - **Your key stays in this page.** It goes only to the provider you pick, nothing saves it, and it is gone when
              you close the tab.
            """
        )
    else:
        _intro = mo.md("**Choose where your code sends its requests.** The practice model needs no key. A real key is never "
                       "saved, so each practice page asks for it again.")
    _intro
    return


@app.cell
def _(kz, mo):
    provider = mo.ui.radio(options={_v["label"]: _k for _k, _v in kz.PROVIDER_INFO.items()},
                           value=kz.PROVIDER_INFO[kz.PRACTICE]["label"], label="Send requests to")
    api_key = mo.ui.text(kind="password", label="API key (not needed for the practice model)", full_width=True)
    mo.callout(mo.vstack([provider, api_key], gap=0.8), kind="neutral")
    return api_key, provider


@app.cell
def _(kz, mo, provider):
    _info = kz.PROVIDER_INFO[provider.value]
    family = _info["family"]
    model_pick = mo.ui.radio(options=_info["models"], value=_info["default"], label="Model", inline=True)
    model_pick if provider.value != kz.PRACTICE else mo.md("")
    return family, model_pick


@app.cell
def _(api_key, kz, mo, model_pick, provider):
    env = kz.make_env(provider.value, api_key.value, model_pick.value)
    _problem = kz.env_problem(env)
    mo.vstack([
        mo.md(f"The code box below can use three names from this panel: `API_KEY`, `MODEL` (now `{env['model']}`) and "
              f"`BASE_URL` (now `{env['base_url']}`). The page loads its libraries in the background; a ✓ line appears "
              "below when they are ready."),
        mo.callout(mo.md(_problem), kind="warn") if _problem else mo.md(""),
    ])
    return (env,)


@app.cell
def _(core, mo):
    mo.Html(f'<p class="sad-cap">&#10003; Libraries loaded in this page: openai and anthropic ({core:.0f} s).</p>')
    return


@app.cell
def _(mo):
    def _reset():
        return mo.ui.button(value=0, on_click=lambda v: v + 1, label="↺  Reset the code")
    reset1, reset2, reset3, reset4, reset5, reset6 = (_reset() for _ in range(6))
    return reset1, reset2, reset3, reset4, reset5, reset6


# ------------------------------------------------------------------------------------------------------------------
# 1.1 Call a model
# ------------------------------------------------------------------------------------------------------------------
@app.cell
def _(kz, mo, page):
    mo.stop(page != 1)
    mo.vstack([
        mo.md(
            """
            ### Messages in, one message out

            Every AI product, from ChatGPT to an agent, is built on one move. Your code sends a **list of messages**, and
            the model sends back **one new message**. That is all a model call is.

            - **system**: standing instructions, written by the developer
            - **user**: what the person typed
            - **assistant**: what the model said earlier
            - the reply is one more assistant message, and your code decides what to do with it
            """
        ),
        mo.Html(kz.call_svg()),
    ])
    return


@app.cell
def _(mo, page):
    mo.stop(page != 1)
    predict1 = mo.ui.radio(options=["The style and role of the answer", "Nothing, the model ignores it", "The model forgets the question"],
                           label="Predict: you change only the system message and run again. What changes?")
    predict1
    return (predict1,)


@app.cell
def _(get_p1, predict1, predict_view):
    predict_view(predict1.value, "The style and role of the answer",
                 "The system message is just the first entry in the list the model reads, so changing it changes how the model "
                 "behaves. Foundations Part 3 shows why that matters for security.", ran=bool(get_p1()))
    return


@app.cell
def _(exercise_html, mo, page):
    mo.stop(page != 1)
    mo.Html(
        exercise_html("1.1.1", "Send your first call", "Press Run. The code builds a list of two messages, sends it, and prints the reply.",
                      minutes=2, passes="a reply comes back.")
        + exercise_html("1.1.2", "Change who it is",
                        "Edit the system message so the model plays someone else, for example a tired lifeguard or a strict "
                        "teacher, then run again.", minutes=3, passes="the system message is your own and a reply comes back."))
    return


@app.cell
def _(family, hint_view, kz, mo, page, reset1):
    mo.stop(page != 1)
    code1 = mo.ui.code_editor(value=kz.starter(1, family), language="python", theme="dark", min_height=160, debounce=True)
    run1 = mo.ui.run_button(label="▶  Run")
    mo.vstack([code1, mo.hstack([run1, reset1], justify="start", gap=0.6), hint_view(["1.2"], family)])
    return code1, run1


@app.cell
async def _(code1, env, get_p1, kz, mo, run1, set_p1, show_run):
    mo.stop(not run1.value, mo.md("_Press **Run** to send this code._"))
    mo.stop(bool(kz.env_problem(env)), mo.callout(mo.md(kz.env_problem(env) or ""), kind="warn"))
    _run = await kz.run_code(code1.value, env)
    _checks, _tokens = kz.grade(1, _run, env, passed=get_p1())
    _passed = get_p1() | _tokens
    set_p1(_passed)
    show_run(_run, _checks, _passed)
    return


@app.cell
def _(mo, page):
    mo.stop(page != 1)
    mo.callout(mo.md("**1.1 in a sentence.** A model call is a list of messages in and one message out, and the system "
                     "message is simply the first entry in that list."), kind="success")
    return


# ------------------------------------------------------------------------------------------------------------------
# 1.2 Memory is the list you send
# ------------------------------------------------------------------------------------------------------------------
@app.cell
def _(kz, mo, page):
    mo.stop(page != 2)
    mo.vstack([
        mo.md(
            """
            ### The model keeps nothing between calls

            It only seems to remember because your code sends **the whole conversation every time**. Delete a message and
            the model has never seen it. Add one and the model believes it.

            - each call stands alone: nothing about your chat is kept on the model's side
            - your code owns the list, so it can drop, edit or invent turns
            - whoever controls the list controls what the model believes, which is where Module 02 starts
            """
        ),
        mo.Html(kz.memory_svg()),
    ])
    return


@app.cell
def _(mo, page):
    mo.stop(page != 2)
    predict2 = mo.ui.radio(options=["Yes, it remembers from the last run", "No, the name is no longer in the list it receives",
                                    "Only if it is a large model"],
                           label="Predict: you delete Ana's introduction and run. Will the model still know her name?")
    predict2
    return (predict2,)


@app.cell
def _(get_p2, predict2, predict_view):
    predict_view(predict2.value, "No, the name is no longer in the list it receives",
                 "The model reads only the list that arrives with this call. Ana's name was never in it, so to the model it was "
                 "never said, however large the model is.", ran=bool(get_p2()))
    return


@app.cell
def _(exercise_html, mo, page):
    mo.stop(page != 2)
    mo.Html(
        exercise_html("1.2.1", "Make it forget",
                      "Run the code once as it is: the model knows Ana's name and town. Then delete the first two messages, keep "
                      "the question, and run again.", minutes=3, passes="the name Ana is not in what you send, and a reply comes back.")
        + exercise_html("1.2.2", "Put words in its mouth",
                        "Change the assistant message into something the model never said, such as a promise of free coffee for "
                        "life, and ask about it. Run.", minutes=3, passes="an assistant message you wrote goes out, and a reply comes back."))
    return


@app.cell
def _(family, hint_view, kz, mo, page, reset2):
    mo.stop(page != 2)
    code2 = mo.ui.code_editor(value=kz.starter(2, family), language="python", theme="dark", min_height=160, debounce=True)
    run2 = mo.ui.run_button(label="▶  Run")
    mo.vstack([code2, mo.hstack([run2, reset2], justify="start", gap=0.6), hint_view(["2.1", "2.2"], family)])
    return code2, run2


@app.cell
async def _(code2, env, get_p2, kz, mo, run2, set_p2, show_run):
    mo.stop(not run2.value, mo.md("_Press **Run** to send this code._"))
    mo.stop(bool(kz.env_problem(env)), mo.callout(mo.md(kz.env_problem(env) or ""), kind="warn"))
    _run = await kz.run_code(code2.value, env)
    _checks, _tokens = kz.grade(2, _run, env, passed=get_p2())
    _passed = get_p2() | _tokens
    set_p2(_passed)
    show_run(_run, _checks, _passed)
    return


@app.cell
def _(mo, page):
    mo.stop(page != 2)
    mo.callout(mo.md("**1.2 in a sentence.** The model's memory is the message list your code sends, so anyone who can edit "
                     "that list can change what the model believes."), kind="success")
    return


# ------------------------------------------------------------------------------------------------------------------
# 1.3 Describe a tool
# ------------------------------------------------------------------------------------------------------------------
@app.cell
def _(family, kz, mo, page):
    mo.stop(page != 3)
    mo.vstack([
        mo.md(
            """
            ### The model only ever sees the description

            Foundations showed that a tool call is a request: the model asks, your code acts. The model can only ask for a
            tool you have **described** to it. The description is a few lines of JSON sent along with the messages, and it
            is all the model knows about your function.

            - the **name** is what the model will ask for
            - the **description** is how it decides when to ask
            - the **parameters** are the inputs it must fill in, taken from the conversation
            """
        ),
        mo.Html(kz.tool_anatomy_html(family)),
    ])
    return


@app.cell
def _(mo, page):
    mo.stop(page != 3)
    predict3 = mo.ui.radio(options=["It still asks for it, because the function is the same",
                                    "It may stop asking for it: it no longer knows what the tool is for",
                                    "The provider rejects the request"],
                           label="Predict: you rename get_weather to tool_1 and delete its description. What does the model do?")
    predict3
    return (predict3,)


@app.cell
def _(get_p3, predict3, predict_view):
    predict_view(predict3.value, "It may stop asking for it: it no longer knows what the tool is for",
                 "The model never sees your Python function, only the description. Take away the name and the sentence and it "
                 "has nothing to decide with. Try it in the box. That is also why a tool description is part of the attack "
                 "surface in Module 03.", ran=bool(get_p3()))
    return


@app.cell
def _(exercise_html, mo, page):
    mo.stop(page != 3)
    mo.Html(
        exercise_html("1.3.1", "Read the request",
                      "Run the code. Which tool did the model ask for, which inputs did it fill in, and where in the question did "
                      "it find them?", minutes=2, passes="the reply carries a tool request.")
        + exercise_html("1.3.2", "Describe your own tool",
                        "Replace the weather tool with one of your own, for example an exchange rate or train times, and change "
                        "the question so it needs your tool. Run.", minutes=5, passes="the model asks for a tool that is not get_weather."))
    return


@app.cell
def _(family, hint_view, kz, mo, page, reset3):
    mo.stop(page != 3)
    code3 = mo.ui.code_editor(value=kz.starter(3, family), language="python", theme="dark", min_height=200, debounce=True)
    run3 = mo.ui.run_button(label="▶  Run")
    mo.vstack([code3, mo.hstack([run3, reset3], justify="start", gap=0.6), hint_view(["3.2"], family)])
    return code3, run3


@app.cell
async def _(code3, env, get_p3, kz, mo, run3, set_p3, show_run):
    mo.stop(not run3.value, mo.md("_Press **Run** to send this code._"))
    mo.stop(bool(kz.env_problem(env)), mo.callout(mo.md(kz.env_problem(env) or ""), kind="warn"))
    _run = await kz.run_code(code3.value, env)
    _checks, _tokens = kz.grade(3, _run, env, passed=get_p3())
    _passed = get_p3() | _tokens
    set_p3(_passed)
    show_run(_run, _checks, _passed)
    return


@app.cell
def _(mo, page):
    mo.stop(page != 3)
    mo.callout(mo.md("**1.3 in a sentence.** A tool is a name, a sentence and a list of inputs; the model decides when to ask "
                     "for it from those words alone."), kind="success")
    return


# ------------------------------------------------------------------------------------------------------------------
# 1.4 Write the loop
# ------------------------------------------------------------------------------------------------------------------
@app.cell
def _(mo, page):
    mo.stop(page != 4)
    mo.md(
        """
        ### From the picture to the code

        Foundations Part 2 drew the loop as five numbered arrows and ran a pretend one. Here is the real code. Step through it:
        the lit lines are the step, and each step names its arrow in that picture.
        """
    )
    return


@app.cell
def _(mo, page, set_step):
    mo.stop(page != 4)
    step_back = mo.ui.button(label="◀  Back", on_change=lambda _: set_step(lambda s: max(1, s - 1)))
    step_next = mo.ui.button(label="Next step  ▶", on_change=lambda _: set_step(lambda s: s % 5 + 1))
    return step_back, step_next


@app.cell
def _(family, get_step, kz, mo, step_back, step_next):
    _s = get_step()
    mo.vstack([
        mo.Html(kz.code_walk_html(_s, family)),
        mo.md(f"**Step {_s}.** {kz.WALK[_s][0]}"),
        mo.hstack([step_back, step_next], justify="start", gap=0.6),
    ])
    return


@app.cell
def _(mo, page):
    mo.stop(page != 4)
    predict4 = mo.ui.radio(options=["The model answers anyway", "The provider refuses the next request",
                                    "The tool runs again by itself"],
                           label="Predict: the loop runs the tool but never adds the result to the list. What happens on the next call?")
    predict4
    return (predict4,)


@app.cell
def _(get_p4, predict4, predict_view):
    predict_view(predict4.value, "The provider refuses the next request",
                 "The list now holds a tool request with no result after it. The APIs refuse that with an error, because the "
                 "model would be answering without what it asked for. Run the box as it is and read the error.",
                 ran=bool(get_p4()))
    return


@app.cell
def _(exercise_html, mo, page):
    mo.stop(page != 4)
    mo.Html(
        exercise_html("1.4.1", "Finish the loop",
                      "Run it first and read the error: one line is missing, so the tool's result never goes back to the model. "
                      "Add it where the comment says TODO, then run.", minutes=5, passes="the model sees the tool's result and answers.")
        + exercise_html("1.4.2", "Give it a second tool",
                        "Add a get_time(city) tool: write the function, add it to functions, add its description to tools, "
                        "and ask a question that needs both tools.", minutes=6,
                        passes="one run calls two different tools and ends with an answer."))
    return


@app.cell
def _(family, hint_view, kz, mo, page, reset4):
    mo.stop(page != 4)
    code4 = mo.ui.code_editor(value=kz.starter(4, family), language="python", theme="dark", min_height=320, debounce=True)
    run4 = mo.ui.run_button(label="▶  Run")
    mo.vstack([code4, mo.hstack([run4, reset4], justify="start", gap=0.6), hint_view(["4.1", "4.2"], family)])
    return code4, run4


@app.cell
async def _(code4, env, get_p4, kz, mo, run4, set_p4, show_run):
    mo.stop(not run4.value, mo.md("_Press **Run** to send this code._"))
    mo.stop(bool(kz.env_problem(env)), mo.callout(mo.md(kz.env_problem(env) or ""), kind="warn"))
    _run = await kz.run_code(code4.value, env)
    _checks, _tokens = kz.grade(4, _run, env, passed=get_p4())
    _passed = get_p4() | _tokens
    set_p4(_passed)
    show_run(_run, _checks, _passed)
    return


@app.cell
def _(mo, page):
    mo.stop(page != 4)
    mo.callout(mo.md("**1.4 in a sentence.** The loop is a few lines of your own code: call, run what was asked for, append "
                     "the result, call again, and stop when the reply is text."), kind="success")
    return


# ------------------------------------------------------------------------------------------------------------------
# 1.5 Let it run code
# ------------------------------------------------------------------------------------------------------------------
@app.cell
def _(kz, mo, page):
    mo.stop(page != 5)
    mo.vstack([
        mo.md(
            """
            ### A tool that runs what the model writes

            The most powerful tool you can give an agent is one that runs code it writes itself. It can calculate, convert and
            analyse. It can also do anything code can do. So the code passes through a function you control **before** it runs.

            - `run_python` is an ordinary tool: the model sends code as the input
            - `approve(code)` is your rule: it reads the code first and says yes or no, outside the model
            - here the code runs inside this browser tab, which cannot reach your files; on a laptop it could reach everything you can
            """
        ),
        mo.Html(kz.gate_svg()),
    ])
    return


@app.cell
def _(exercise_html, mo, page):
    mo.stop(page != 5)
    mo.Html(
        exercise_html("1.5.1", "Let it calculate",
                      "Run it. The model writes Python to answer a maths question, approve() lets it through, and the result "
                      "goes back. Read the code it wrote in the printout.", minutes=3, passes="the agent runs code it wrote and answers.")
        + exercise_html("1.5.2", "Write the rule",
                        "Change approve(code) so it blocks code that touches files or the system, and still allows plain maths "
                        "and the maths library. Then try the question \"What files are in this folder?\" and watch it get blocked.",
                        minutes=6, passes="your rule gets all six test snippets right: two allowed, four blocked."))
    return


@app.cell
def _(family, hint_view, kz, mo, page, reset5):
    mo.stop(page != 5)
    code5 = mo.ui.code_editor(value=kz.starter(5, family), language="python", theme="dark", min_height=320, debounce=True)
    run5 = mo.ui.run_button(label="▶  Run")
    mo.vstack([code5, mo.hstack([run5, reset5], justify="start", gap=0.6), hint_view(["5.2"], family)])
    return code5, run5


@app.cell
async def _(code5, env, get_p5, kz, mo, run5, set_p5, show_run):
    mo.stop(not run5.value, mo.md("_Press **Run** to send this code._"))
    mo.stop(bool(kz.env_problem(env)), mo.callout(mo.md(kz.env_problem(env) or ""), kind="warn"))
    _run = await kz.run_code(code5.value, env)
    _checks, _tokens = kz.grade(5, _run, env, passed=get_p5())
    _passed = get_p5() | _tokens
    set_p5(_passed)
    show_run(_run, _checks, _passed)
    return


@app.cell
def _(mo, page):
    mo.stop(page != 5)
    predict5 = mo.ui.radio(options=["Yes, os was the only way in", "No, code can reach the system in ways the rule did not list",
                                    "Yes, models never write harmful code"],
                           label="Think: your rule blocks code that contains \"import os\". Is the agent now safe?")
    predict5
    return (predict5,)


@app.cell
def _(predict5, predict_view):
    predict_view(predict5.value, "No, code can reach the system in ways the rule did not list",
                 "A blocklist catches the wordings you thought of; an attacker writes one you did not, such as "
                 "<code>__import__</code> or <code>getattr</code> tricks. A rule is a start. Real protection runs the code "
                 "somewhere it cannot do harm, which is Module 06.")
    return


@app.cell
def _(mo, page):
    mo.stop(page != 5)
    mo.callout(mo.md("**1.5 in a sentence.** Running code makes an agent powerful and dangerous for the same reason, so every "
                     "run passes a rule you control, and a rule alone is only a start."), kind="success")
    return


# ------------------------------------------------------------------------------------------------------------------
# 1.6 Frameworks, and your own machine
# ------------------------------------------------------------------------------------------------------------------
@app.cell
def _(kz, mo, page):
    mo.stop(page != 6)
    mo.vstack([
        mo.md(
            """
            ### Find your loop inside a framework

            Foundations said a framework runs the loop for you, and that the seam, where a tool request becomes an action,
            moves inside it. Here you run three frameworks and find that seam in each. Under the new names, every one of them
            does what you wrote in 1.4.
            """
        ),
        mo.Html(kz.framework_table_html()),
        mo.md("The first run loads the frameworks into the page, about 30 seconds, once. With an Anthropic key the OpenAI "
              "Agents SDK is not offered, because it speaks the OpenAI request format."),
    ])
    return


@app.cell
def _(family, kz, mo, page):
    mo.stop(page != 6)
    fw_pick = mo.ui.radio(options=kz.FRAMEWORKS_FOR[family], value=kz.FRAMEWORKS_FOR[family][0], label="Framework", inline=True)
    fw_pick
    return (fw_pick,)


@app.cell
def _(exercise_html, mo, page):
    mo.stop(page != 6)
    mo.Html(
        exercise_html("1.6.1", "Same agent, two frameworks",
                      "Pick a framework and press Run. Then pick another and run that. In each, find the model call, the tool, the "
                      "line that runs the loop, and the seam.", minutes=5, passes="two different frameworks each run the tool and answer.")
        + exercise_html("1.6.2", "Add a tool in a framework",
                        "In any framework, add a get_time(city) tool and ask a question that needs both tools.",
                        minutes=5, passes="one framework run calls two different tools."))
    return


@app.cell
def _(family, fw_pick, hint_view, kz, mo, reset6):
    code6 = mo.ui.code_editor(value=kz.starter(6, family, fw_pick.value), language="python", theme="dark", min_height=300, debounce=True)
    run6 = mo.ui.run_button(label="▶  Run")
    mo.vstack([code6, mo.hstack([run6, reset6], justify="start", gap=0.6), hint_view(["6.2"], family, fw_pick.value)])
    return code6, run6


@app.cell
async def _(code6, env, fw_pick, get_p6, kz, mo, run6, set_p6, show_run):
    mo.stop(not run6.value, mo.md("_Press **Run** to send this code._"))
    mo.stop(bool(kz.env_problem(env)), mo.callout(mo.md(kz.env_problem(env) or ""), kind="warn"))
    if not kz.frameworks_ready():
        with mo.status.spinner(title="Loading LangChain, LangGraph and the OpenAI Agents SDK into the page (once, about 30 seconds)"):
            await kz.install_frameworks()
    _run = await kz.run_code(code6.value, env)
    _checks, _tokens = kz.grade(6, _run, env, fw=fw_pick.value, passed=get_p6())
    _passed = get_p6() | _tokens
    set_p6(_passed)
    show_run(_run, _checks, _passed)
    return


@app.cell
def _(kz, mo, page, provider):
    mo.stop(page != 6)
    _p = provider.value if provider.value != kz.PRACTICE else "OpenAI"
    _install, _var, _code = kz.laptop_parts(_p)
    _note = ("The practice model only exists inside this page, so these steps use OpenAI. Pick OpenRouter or Anthropic in the "
             "panel at the top to see their version.\n\n" if provider.value == kz.PRACTICE else "")
    mo.md(
        "### Take it home\n\n" + _note
        + "Everything you ran here works the same way on your computer. Two things change: you install the library once, and the "
          "key comes from an environment variable instead of the panel, so it never sits in your code.\n\n"
        + "1. Install Python 3.10 or newer, then the library:\n\n"
        + f"```\n{_install}\n```\n\n"
        + "2. Put your key in an environment variable, in the same terminal you will run from:\n\n"
        + f'```\nexport {_var}="paste-your-key-here"        # macOS and Linux\n$env:{_var}="paste-your-key-here"         # Windows PowerShell\n```\n\n'
        + "3. Save this as `agent.py`, run `python agent.py`, and ask it about the weather or the time somewhere:\n\n"
        + f"```python\n{_code}```"
    )
    return


@app.cell
def _(exercise_html, mo, page):
    mo.stop(page != 6)
    ran_it = mo.ui.checkbox(label="I ran agent.py on my machine and it printed an answer")
    mo.vstack([
        mo.Html(exercise_html("1.6.3", "Run it on your own machine", "Optional. Follow the three steps above, then tick the box.",
                              minutes=10, passes="you tick the box once your agent answers.")),
        ran_it,
        mo.callout(mo.md("**Never put a key in code you share or commit.** Read it from an environment variable, as above."),
                   kind="warn"),
    ])
    return (ran_it,)


@app.cell
def _(fb_html, ran_it):
    fb_html("true", "&#10003; Exercise 1.6.3", "Your agent runs on your own machine.") if ran_it.value else fb_html(
        "none", "Exercise 1.6.3", "Tick the box once your agent answers.")
    return


@app.cell
def _(mo, page, recap_html):
    mo.stop(page != 6)
    mo.vstack([
        mo.callout(mo.md("**1.6 in a sentence.** A framework is your 1.4 loop with names on it: find the model call, the tools, "
                         "the loop and the seam, and you can read any of them."), kind="success"),
        mo.Html(recap_html("What the six practice pages gave you", [
            "Call a model from code: a list of messages in, one message out.",
            "Control what it remembers, because its memory is the list you send.",
            "Describe a tool, and write the loop that turns its requests into actions.",
            "Put a rule in front of code execution, and say why a rule alone is not enough.",
            "Read the same agent in the OpenAI Agents SDK, LangChain and LangGraph, and run it on your own machine.",
        ], artefact="a working agent you wrote, ready for Module 02 to attack.")),
    ])
    return


@app.cell
def _(kz, mo, page):
    mo.Html(kz.nav_html(page))
    return


@app.cell
async def _(kz):
    # Load the provider SDKs into the page. This cell sits last so the page text renders before the download starts.
    core = await kz.install_core()
    return (core,)


if __name__ == "__main__":
    app.run()
