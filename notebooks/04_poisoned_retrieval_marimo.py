import marimo

__generated_with = "0.25.1"
app = marimo.App(width="medium", css_file="../course/course.css")


@app.cell
def _():
    import marimo as mo
    import html
    import koda_retrieval as kr
    import koda_toolbox
    from koda_lab import contrast_html, divider, exercise_html, hat_html, hero, mono_panel, recap_html, results_table, terms_html
    return contrast_html, divider, exercise_html, hat_html, hero, html, koda_toolbox, kr, mo, mono_panel, recap_html, results_table, terms_html


@app.cell
def _(exercise_html, hat_html, html, kr, mo):
    # page helpers: feedback cards, team headings, exercise headers from the engine's EXERCISE_LIST, hints, grader verdicts
    esc = html.escape

    def fb_card(ok, why, head=None):
        # ok: True, False, or None for a neutral reveal
        _h = head or ("&#10003; correct" if ok else "&#10007; not quite")
        _k = "none" if ok is None else ("true" if ok else "false")
        return mo.Html(f'<div class="sad-fb" data-ok="{_k}"><b>{_h}</b> &middot; {why}</div>')

    def hat(side, title, note=""):
        return mo.Html(hat_html(side, title, note))

    def chip(text, strong=False):
        return f'<span class="sad-tag{" is-strong" if strong else ""}">{text}</span>'

    def ex(num):
        _e = next(e for e in kr.EXERCISE_LIST if e["num"] == num)
        return mo.Html(exercise_html(_e["num"], esc(_e["title"]), esc(_e["goal"]), minutes=_e["minutes"], passes=esc(_e["passes"]))
                       .replace("</p><h3>", f" &middot; {_e['n']} of {len(kr.EXERCISE_LIST)}</p><h3>", 1))

    def stuck(hint):
        return mo.accordion({"Stuck?": mo.md(hint)})

    def verdict(state, err, passed, failed):
        return {"missing": "**Write the function** (keep its name), then click out of the editor and the check runs.",
                "blank": "**Write the body**: it still returns the `...` placeholder. The check runs when you click out of the editor.",
                "raised": f"Your code raised `{err}`, fix it and the check re-runs.",
                "pass": "**PASS.** " + passed,
                "fail": "**Not yet.** " + failed}[state]

    def answer(code):
        return mo.accordion({"Show a working answer": mo.md("```python\n" + code + "\n```")})

    return answer, chip, esc, ex, fb_card, hat, stuck, verdict


@app.cell
def _(contrast_html, esc, hero, kr, mo, terms_html):
    _parts = ["How an answer is made", "Red team: get picked, then lie", "Three ways in", "Ingest: the parser reads more than the reviewer",
              "Chunk: a document cut apart", "Assemble: copies, conflicts and blockers", "Answer: check it against its source",
              "Blue team: bound it at three points", "The index outlives its sources", "Capstone and your own system"]
    mo.vstack([
        mo.Html(hero(
            "Secure AI Deployment &middot; Module 04",
            "Poisoned retrieval: when the knowledge is the attack",
            "A search-powered assistant answers from whatever its retriever picks, and an attacker can choose what gets picked. This module "
            "follows one document from its source to the answer, and out of the index again, and asks at each step what can go wrong.",
            meta=("about 60 minutes", "runs in your browser, no key needed", "nothing real is touched"),
        )),
        mo.Html(terms_html([(esc(_t), esc(_m)) for _t, _m in kr.TERMS])),
        mo.Html(contrast_html("04")),
        mo.md("**What you will do**\n\n" + "\n".join(f"- Part {_i}: {_p}." for _i, _p in enumerate(_parts, 1))),
    ])
    return


@app.cell
def _(divider, mo):
    mo.Html(divider(1, "How an answer is made", "You will do: finish the retriever, predict a password question's pick. "
                    "You will have: the pipeline, and where each Part of this module sits on it."))
    return


@app.cell
def _(kr, mo, results_table):
    _stages = [("sources", 3), ("ingest", 4), ("chunk", 5), ("index", 9), ("rank", 2), ("prompt", 6), ("answer", 7)]
    _chips = ' <span class="sad-dim">&#8594;</span> '.join(
        f'<span class="sad-tag is-strong">{_s} <span class="sad-dim">Part {_n}</span></span>' for _s, _n in _stages)
    _docs = [(d["id"], d["text"], None, f'{d["source"]}, {d["tier"]}') for d in kr.STORE]
    mo.vstack([
        mo.md("Search, paste the best matches into the prompt, answer. Nothing in that chain checks truth, and every link in it is a place "
              "where the answer can change without anyone touching the model."),
        mo.Html('<div class="sad-panel"><div class="sad-flow">' + _chips + '</div>'
                '<p class="sad-cap">Each stage has its own failure, and the Part that covers it. Part 8 bounds the whole chain.</p></div>'),
        mo.Html(results_table("the store: four handbook documents", _docs)),
    ])
    return


@app.cell
def _(ex, kr, mo, stuck):
    score_code = mo.ui.code_editor(theme="dark", value=kr.STARTERS["score"], language="python", debounce=True)
    mo.vstack([ex("4.1.1"), score_code,
               stuck("Turn each text into a set of words with `set(re.findall(r'[a-z]+', text.lower()))`, then count the words in both "
                     "sets: `len(a & b)`.")])
    return (score_code,)


@app.cell
def _(answer, kr, mo, results_table, score_code, verdict):
    _rows, _state, _err = kr.grade("score", score_code.value)
    mo.vstack([
        mo.Html(results_table(f"your score() on {len(kr.EXERCISE_CASES['score'])} pairs", _rows)) if _rows else mo.md(""),
        mo.md(verdict(_state, _err,
                      "That is the whole retriever in this lab: count shared words, highest first. Real systems compare meaning instead "
                      "of words (Part 2), and the rest of this module holds for both.",
                      "The rows marked ✗ are wrong. Lowercase both texts, keep letters only, and count each shared word once: a set does both.")),
        answer(kr.ANSWERS["score"]),
    ])
    return


@app.cell
def _(ex, kr, mo):
    p1_pick = mo.ui.radio(options=[d["id"] for d in kr.STORE], inline=True,
                          label="Which document ranks first for how do I reset my password?")
    mo.vstack([ex("4.1.2"), p1_pick])
    return (p1_pick,)


@app.cell
def _(fb_card, kr, mo, p1_pick, results_table):
    mo.stop(p1_pick.value is None, mo.md("_Guess first._"))
    _q = kr.QUESTIONS[0]
    _rows = [(d["id"], str(kr.score(_q, d["text"])), None, d["text"][:60] + "&hellip;") for d in kr.rank(_q, kr.STORE)]
    mo.vstack([
        fb_card(p1_pick.value == "hr-1", "hr-1 shares two words with the question (reset, password); the others share none. Two "
                "shared words decided the answer." if p1_pick.value == "hr-1" else
                f"{p1_pick.value} shares no word with the question. hr-1 shares two (reset, password), so it ranks first."),
        mo.Html(results_table(f"shared-word score for: {_q}", _rows)),
    ])
    return


@app.cell
def _(mo):
    mo.callout(mo.md("**Part 1 in a sentence.** An answer is the top-ranked text read aloud, and rank measures matching, not truth."),
               kind="success")
    return


@app.cell
def _(divider, mo):
    mo.Html(divider(2, "Red team: get picked, then lie", "You will do: watch a false procedure land, outrank the handbook, turn two "
                    "ranking knobs. You will have: ranking is relevance, not trust, whatever the ranker measures."))
    return


@app.cell
def _(esc, ex, hat, kr, mo):
    p2_pick = mo.ui.radio(options=[d["id"] for d in kr.POISONED], inline=True,
                          label="With web-9 in the store, which ranks first for the password question?")
    mo.vstack([
        ex("4.2.1"),
        hat("red", "One imported page"),
        mo.md("Koda imports a help site into the index. One page reads:"),
        mo.Html(f'<div class="sad-panel"><p class="sad-cap">web-9 &middot; web-import, untrusted</p><div class="sad-mono">{esc(kr.POISON["text"])}</div></div>'),
        p2_pick,
    ])
    return (p2_pick,)


@app.cell
def _(esc, fb_card, kr, mo, mono_panel, p2_pick, results_table):
    mo.stop(p2_pick.value is None, mo.md("_Guess first._"))
    _q = kr.QUESTIONS[0]
    _before = [(d["id"], str(kr.score(_q, d["text"])), None, "") for d in kr.rank(_q, kr.STORE)]
    _after = [(d["id"], str(kr.score(_q, d["text"])), d["id"] != "web-9" if d["id"] in ("web-9", "hr-1") else None,
               "the poison" if d["id"] == "web-9" else "") for d in kr.rank(_q, kr.POISONED)]
    _r = kr.ask(_q, kr.POISONED)
    _ans = esc(_r["answer"]).replace(esc(kr.FALSE_SIGN), f'<span class="sad-hl">{esc(kr.FALSE_SIGN)}</span>')
    mo.vstack([
        fb_card(p2_pick.value == "web-9", "web-9 repeats the question word for word, so it shares six words where hr-1 shares two."
                if p2_pick.value == "web-9" else "web-9 repeats the question word for word: six shared words to hr-1's two. The poison ranks first."),
        mo.Html('<div class="sad-pair">' + results_table("before the import", _before) + results_table("after the import", _after) + "</div>"),
        mo.Html(mono_panel("what the user is told", f'<span class="sad-dim">user:</span> {esc(_q)}\n<span class="sad-dim">assistant:</span> {_ans}',
                           "No tool was called and no permission refused anything: Module 02's switchboard would not have fired.",
                           "a false procedure, answered with full confidence", "bad")),
    ])
    return


@app.cell
def _(ex, mo):
    my_doc = mo.ui.text_area(placeholder="Outrank the handbook for all three questions", rows=4, full_width=True,
                             label="Write a document; it is ranked against the four honest ones.")
    mo.vstack([ex("4.2.2"), my_doc])
    return (my_doc,)


@app.cell
def _(kr, mo, my_doc, results_table):
    mo.stop(not my_doc.value.strip(), mo.md("_Type a document; it is scored when you click out._"))
    _mine = {"id": "yours", "text": my_doc.value}
    _rows, _firsts = [], 0
    for _q in kr.QUESTIONS:
        _ranked = kr.rank(_q, kr.STORE + [_mine])
        _pos = [d["id"] for d in _ranked].index("yours") + 1
        _won = _pos == 1 and kr.score(_q, _mine["text"]) > 0
        _firsts += _won
        _rows.append((_q, f"rank {_pos} of 5, score {kr.score(_q, _mine['text'])}", _won,
                      f"beats {_ranked[1]['id']}" if _pos == 1 else f"{_ranked[0]['id']} wins with {kr.score(_q, _ranked[0]['text'])}"))
    mo.vstack([
        mo.Html(results_table("your document against the handbook", _rows)),
        mo.md(f"**Your document ranks first for {_firsts} of 3 questions.** " + (
            "You needed no account and no secret, only the words people type." if _firsts == 3 else
            "Repeat the words of the question you are losing, and it will.")),
    ])
    return


@app.cell
def _(esc, ex, kr, mo):
    knob_pick = mo.ui.radio(options=["the freshness boost", "the reranker", "either one", "neither"], inline=True,
                            label="Which knob puts web-12 first?")
    knob_fresh = mo.ui.switch(label="Newest first")
    knob_rerank = mo.ui.switch(label="Reranker")
    mo.vstack([
        ex("4.2.3"),
        mo.md("Word overlap is one ranking signal, and real systems stack more on top. A **freshness boost** ranks recent documents higher, "
              "because policies change. A **reranker** is a second model that re-reads the matches and orders them by how relevant and "
              "reliable they look (here, a stand-in that rewards what a page says about itself). Here is a page that barely matches the password question: it shares one word, where hr-1 shares two."),
        mo.Html(f'<div class="sad-panel"><p class="sad-cap">web-12 &middot; web-import, untrusted, posted {kr.FRESH["posted"]}</p>'
                f'<div class="sad-mono">{esc(kr.FRESH["text"])}</div></div>'),
        knob_pick,
        mo.hstack([knob_fresh, knob_rerank], justify="start", gap=0.5, wrap=True),
    ])
    return knob_fresh, knob_pick, knob_rerank


@app.cell
def _(fb_card, knob_fresh, knob_pick, knob_rerank, kr, mo, results_table):
    _q = kr.QUESTIONS[0]
    _ranked = kr.rank_with(_q, kr.STORE + [kr.FRESH], newest_first=knob_fresh.value, reranker=knob_rerank.value)
    _rows = [(d["id"], f'{d["source"]}, posted {d["posted"]}', (d["id"] == "hr-1") if i == 0 else None,
              f'shares {kr.score(_q, d["text"])} word{"s" if kr.score(_q, d["text"]) != 1 else ""}') for i, d in enumerate(_ranked)]
    _first = _ranked[0]["id"]
    _on = [n for n, v in (("the freshness boost", knob_fresh.value), ("the reranker", knob_rerank.value)) if v]
    _out = [mo.Html(results_table("the ranking for the password question, with " + (" and ".join(_on) or "no knob"), _rows)),
            mo.md(f"**{_first} ranks first.** " + (
                "The freshness boost asks when, not who: web-12 was posted this week, so it leads, and an attacker can always post last."
                if knob_fresh.value and not knob_rerank.value else
                "The reranker read web-12 calling itself official and verified, and believed it. A model that ranks text can be talked "
                "into its ranking by the text it is ranking." if knob_rerank.value and not knob_fresh.value else
                "Both knobs push the same way." if knob_fresh.value and knob_rerank.value else
                "With word overlap alone, the handbook still leads."))]
    if knob_pick.value:
        _out.insert(0, fb_card(knob_pick.value == "either one",
                               "either one. Each knob measures something an attacker controls: the date they post and the words they use "
                               "about themselves. Turn them on one at a time to see it." if knob_pick.value == "either one" else
                               "turn the switches one at a time: each knob alone puts web-12 first, because each measures something the "
                               "attacker controls, the date and the self-description."))
    mo.vstack(_out)
    return


@app.cell
def _(mo):
    _text = (
        "**Meaning instead of words.** Most production retrievers compare *embeddings*, lists of numbers that place texts with similar "
        "meaning close together, so a document can be picked without sharing a single word with the question. That raises the stakes "
        "rather than lowering them: a passage can be tuned to sit near many phrasings at once. The PoisonedRAG authors (Zou, Geng, Wang "
        'and Jia, <a href="https://arxiv.org/abs/2402.07867" target="_blank" rel="noopener">arXiv 2402.07867</a>, USENIX Security 2025) '
        "describe what a poisoned text needs: a <i>retrieval condition</i> (&ldquo;a malicious text can be retrieved for a target question&rdquo;) and a <i>generation condition</i> (it &ldquo;can mislead an LLM to generate a target answer&rdquo;). Word overlap, embeddings and both knobs above only decide the first. OWASP&rsquo;s 2026 entry on vector and embedding weaknesses (<a href='https://github.com/GenAI-Security-Project/GenAI-LLM-Top10/blob/main/2026/final/LLM09_VectorAndEmbeddingWeaknesses.md' target='_blank' rel='noopener'>LLM09:2026</a>) uses the same two-part test.\n\n"
        "**Measured on real search.** Nestaas, Debenedetti and Tram&egrave;r (ETH Zurich, <a href='https://arxiv.org/abs/2406.18382' target='_blank' rel='noopener'>ICLR 2025</a>) wrote web pages that steer LLM search engines, which they call &ldquo;Preference Manipulation Attacks&rdquo;, and showed them on Bing and Perplexity: their target camera became 2.5 times more likely to be recommended by Bing. They disclosed in March 2024, and Microsoft acknowledged the issues. Pfrommer and colleagues (UC Berkeley, <a href='https://arxiv.org/abs/2406.03589' target='_blank' rel='noopener'>EMNLP 2024</a>) did the same to the ranking a model writes in its own answer: adversarial text on a product&rsquo;s page closed, on average, 82.94 percent of the gap to the top spot for GPT-4 Turbo. This lab&rsquo;s reranker is a stand-in; theirs were the real thing."
    )
    mo.md(_text)
    return


@app.cell
def _(mo):
    mo.callout(mo.md("**Part 2 in a sentence.** Ranking measures relevance, recency or self-description, never trust, and an attacker controls "
                     "all three."), kind="success")
    return


@app.cell
def _(divider, mo):
    mo.Html(divider(3, "Three ways in", "You will do: pick which sources a stranger can write to. You will have: three doors, one control each."))
    return


@app.cell
def _(ex, mo):
    _ways = ["an outside feed imported into the index (web crawl, vendor docs, a partner's PDF, live web search)",
             "a place any user can write that the index reads (support tickets, a shared wiki, inbound email, calendar invites)",
             "a shared index with no access filter (another tenant's or another person's documents come back)"]
    p3_pick = mo.Html('<div class="sad-title">Which of these can an outsider write to without an account?</div>'
                      '<div class="sad-stack">' + "".join(f"{{w{_i}}}" for _i in range(3)) + "</div>").batch(
        **{f"w{_i}": mo.ui.checkbox(label=_w) for _i, _w in enumerate(_ways)})
    mo.vstack([ex("4.3.1"), p3_pick])
    return (p3_pick,)


@app.cell
def _(fb_card, mo, p3_pick):
    mo.stop(not any(p3_pick.value.values()), mo.md("_Tick your picks first._"))
    _on = tuple(p3_pick.value[f"w{_i}"] for _i in range(3))
    _col = lambda h, how, see, ctl: (f'<div><h4>{h}</h4><ul><li><b>How it gets in:</b> {how}</li><li><b>What you see:</b> {see}</li>'
                                     f'<li><b>The one control:</b> {ctl}</li></ul></div>')
    mo.vstack([
        fb_card(_on == (True, True, False), "the first two. The third needs no writer at all: another tenant's document comes back because "
                "nothing filtered it, with nobody attacking." if _on == (True, True, False) else
                ("the shared index needs no writer: the leak happens with nobody attacking, so it is not an outsider's door." if _on[2] else
                 "both of the first two are open to a stranger: a crawl fetches any page, and anyone can file a ticket or send an email.")),
        mo.Html('<div class="sad-cols">'
                + _col("1. An outside feed", "the import job fetches it, or the agent searches the web.", "a confident answer that quotes the web.",
                       "a provenance tier at ingestion: the feed never answers a policy question.")
                + _col("2. A user-writable source", "a stranger files a ticket; the index reads tickets.",
                       "a ticket's wording comes back as the answer.", "tier user-written sources as untrusted; same gate.")
                + _col("3. A shared index", "a missing filter, not a document.", "another customer's terms in your answer.",
                       "authorization at retrieval, from the user's credential.") + "</div>"),
    ])
    return


@app.cell
def _(mo):
    mo.callout(mo.md("**Part 3 in a sentence.** Two doors open to a stranger who writes, the third opens with no writer, and each has one control."),
               kind="success")
    return


@app.cell
def _(divider, mo):
    mo.Html(divider(4, "Ingest: the parser reads more than the reviewer", "You will do: tick what an importer indexes from a partner's PDF, then "
                    "write the check that finds what nobody approved. You will have: index what was reviewed."))
    return


@app.cell
def _(esc, ex, kr, mo):
    _layers = kr.VENDOR_PDF["layers"]
    layer_pick = mo.Html('<div class="sad-title">Which layers of vendor-3 does this importer put in the index?</div>'
                         '<div class="sad-stack">' + "".join(f"{{l{_i}}}" for _i in range(len(_layers))) + "</div>").batch(
        **{f"l{_i}": mo.ui.checkbox(label=_l["name"]) for _i, _l in enumerate(_layers)})
    mo.vstack([
        mo.md("A partner sends a setup guide as a PDF. Someone at Koda opens it, reads it, and approves it for the index. What they approved is "
              "the page as it renders. What the index holds is whatever the *parser* pulls out of the file, and a file has more layers than a "
              "screen shows: text coloured to match the background, text placed outside the visible page, the document&rsquo;s properties, "
              "comments. This lab&rsquo;s importer reads every text layer it can find, coloured or not, on the page or not, and the subject "
              "field, and skips margin comments. Yours has its own list; the first job is finding out what it is."),
        mo.Html(f'<div class="sad-panel"><p class="sad-cap">{esc(kr.VENDOR_PDF["id"])} &middot; {esc(kr.VENDOR_PDF["source"])}, '
                f'as the reviewer saw it</p><div class="sad-mono">{esc(kr.seen_by_reviewer(kr.VENDOR_PDF))}</div></div>'),
        ex("4.4.1"),
        layer_pick,
    ])
    return (layer_pick,)


@app.cell
def _(esc, fb_card, kr, layer_pick, mo, mono_panel):
    mo.stop(not any(layer_pick.value.values()), mo.md("_Tick your picks first._"))
    _layers = kr.VENDOR_PDF["layers"]
    _mine = [layer_pick.value[f"l{_i}"] for _i in range(len(_layers))]
    _right = [l["indexed"] for l in _layers]
    _wrong = [l["name"] for l, m, r in zip(_layers, _mine, _right) if m != r]
    _hidden = kr.reference_unseen(kr.seen_by_reviewer(kr.VENDOR_PDF), kr.extracted(kr.VENDOR_PDF))
    _idx = esc(kr.extracted(kr.VENDOR_PDF))
    for _h in _hidden:
        _idx = _idx.replace(esc(_h), f'<span class="sad-hl">{esc(_h)}</span>')
    mo.vstack([
        fb_card(not _wrong, "four of the five: the body, the white text, the text off the page and the subject field. Only the margin comment "
                "stays out, and it was the one harmless layer." if not _wrong else
                "look again at: " + ", ".join(_wrong) + ". This importer reads every text layer, whatever its colour or position, and the "
                "subject field; it skips margin comments."),
        mo.Html(mono_panel("what the index holds for vendor-3", _idx,
                           "The highlighted sentences were never on the reviewer&rsquo;s screen. Each one is about passwords, and none is an order "
                           "to the assistant: they are false facts, waiting for a password question.",
                           "three sentences nobody approved", "bad")),
    ])
    return


@app.cell
def _(ex, kr, mo, stuck):
    unseen_code = mo.ui.code_editor(theme="dark", value=kr.STARTERS["unseen"], language="python", debounce=True)
    mo.vstack([
        ex("4.4.2"),
        mo.md("The control is to index only what was reviewed, and the check behind it is a comparison: the text the reviewer saw against the "
              "text the parser extracted. Anything extracted and never seen goes to a person before the document is indexed."),
        unseen_code,
        stuck("Normalise each sentence with `' '.join(s.lower().split())`, put the reviewer&rsquo;s normalised sentences in a set, and keep "
              "each extracted sentence whose normalised form is not in it. Compare whole sentences: a word or substring check misses a "
              "hidden sentence made of words that are on screen."),
    ])
    return (unseen_code,)


@app.cell
def _(answer, kr, mo, results_table, unseen_code, verdict):
    _rows, _state, _err = kr.grade("unseen", unseen_code.value)
    mo.vstack([
        mo.Html(results_table(f"your unseen() on {len(kr.EXERCISE_CASES['unseen'])} documents", _rows)) if _rows else mo.md(""),
        mo.md(verdict(_state, _err,
                      "Run at ingestion, this holds vendor-3 for a person with three sentences to look at, instead of indexing them unseen. "
                      "Two limits to keep in mind: it compares against what your viewer renders, so render the way your reviewers see it; "
                      "and text inside images needs an OCR pass on both sides of the comparison.",
                      "The rows marked ✗ are wrong. Compare whole sentences after lowercasing and collapsing spaces, return the extracted "
                      "sentences that are not in the reviewer&rsquo;s text, and ignore sentences only the reviewer saw.")),
        answer(kr.ANSWERS["unseen"]),
    ])
    return


@app.cell
def _(mo):
    _text = ("**Documented.** OWASP&rsquo;s 2025 list opened its vector and embedding entry with this case (<a href='https://genai.owasp.org/llmrisk/llm082025-vector-and-embedding-weaknesses/' target='_blank' rel='noopener'>LLM08:2025</a>, scenario 1): a resume with &ldquo;hidden text, such as white text on a white background&rdquo;, sent to a screening system that uses retrieval. In July 2025 <a href='https://asia.nikkei.com/business/technology/artificial-intelligence/positive-review-only-researchers-hide-ai-prompts-in-papers' target='_blank' rel='noopener'>Nikkei Asia</a> found prompts aimed at AI reviewers hidden in 17 arXiv preprints from 14 institutions in eight countries, &ldquo;concealed from human readers using tricks such as white text or extremely small font sizes&rdquo;. The 2026 edition asks for hidden text such as &ldquo;white-on-white text&rdquo; to be stripped at extraction.")
    mo.md(_text)
    return


@app.cell
def _(mo):
    mo.callout(mo.md("**Part 4 in a sentence.** The index holds what the parser extracted, not what the reviewer approved, so compare the two "
                     "and index only what someone saw."), kind="success")
    return


@app.cell
def _(divider, mo):
    mo.Html(divider(5, "Chunk: a document cut apart", "You will do: chunk a withdrawn procedure two ways and see which keeps its warning. "
                    "You will have: a chunk must carry what it belongs to."))
    return


@app.cell
def _(esc, ex, kr, mo):
    chunk_pick = mo.ui.radio(options=["the procedure, with its warning", "the procedure, without its warning", "the Settings answer from hr-1"],
                             inline=False, label="With one-sentence chunks, what is the user told?")
    chunk_size = mo.ui.radio(options={"One sentence": "1", "The whole page": "page"}, value="One sentence", inline=True, label="Chunk size:")
    chunk_carry = mo.ui.switch(label="Carry title and status")
    mo.vstack([
        mo.md("An index does not store documents, it stores **chunks**: pieces small enough to rank and to fit many into one prompt. The cut "
              "is made by a rule (so many sentences, so many tokens), and the rule does not know which sentence another one depends on. "
              "Here is a handbook page, withdrawn last month but still in the index, and a question that matches it:"),
        mo.Html(f'<div class="sad-panel"><p class="sad-cap">{esc(kr.PHONE_PAGE["id"])} &middot; {esc(kr.PHONE_PAGE["title"])}, '
                f'{esc(kr.PHONE_PAGE["status"])}</p><div class="sad-mono">{esc(kr.PHONE_PAGE["text"])}</div></div>'
                f'<p class="sad-cap">The question: {esc(kr.PHONE_Q)}</p>'),
        ex("4.5.1"),
        chunk_pick,
        mo.hstack([chunk_size, chunk_carry], justify="start", gap=1, wrap=True),
    ])
    return chunk_carry, chunk_pick, chunk_size


@app.cell
def _(chunk_carry, chunk_pick, chunk_size, esc, fb_card, kr, mo, mono_panel):
    _size = 1 if chunk_size.value == "1" else None
    _r = kr.chunk_answer(_size, chunk_carry.value)
    _ans = _r["answer"]
    _warned = "withdrawn" in _ans
    _chunks = kr.chunks_of(kr.PHONE_PAGE, _size, chunk_carry.value)
    _body = ("".join(f'<span class="sad-dim">{esc(c["id"])}:</span> {esc(c["text"])}\n' for c in _chunks)
             + f'\n<span class="sad-dim">retrieved:</span> {esc(_r["top"]["id"])}\n<span class="sad-dim">assistant:</span> {esc(_ans)}')
    _out = [mo.Html(mono_panel("the chunks, and what the user is told", _body, "",
                               "the answer carries the warning" if _warned else
                               "a withdrawn procedure, answered as current", "good" if _warned else "bad"))]
    if chunk_pick.value:
        _out.insert(0, fb_card(chunk_pick.value == "the procedure, without its warning",
                               "without its warning. The warning is one sentence and the procedure another; the question matches the "
                               "procedure&rsquo;s words, so that chunk ranks first and arrives alone." if chunk_pick.value.startswith("the procedure, without")
                               else "the question shares four words with the procedure&rsquo;s sentence and none with the warning&rsquo;s, so "
                                    "with one-sentence chunks the procedure arrives alone, without its warning. It also beats hr-1, which "
                                    "shares two."))
    mo.vstack(_out)
    return


@app.cell
def _(mo):
    _text = (
        "**The control: a chunk carries what it belongs to.** Bigger chunks keep the warning here, but they blur the ranking everywhere else, "
        "so the usual fix is to keep chunks small and put the document&rsquo;s title, section and status at the front of each one. Then "
        "whichever chunk ranks first says *withdrawn*, and a rule can refuse to answer from a withdrawn page at all. Anthropic measured this fix (<a href='https://www.anthropic.com/research/contextual-retrieval' target='_blank' rel='noopener'>Contextual Retrieval</a>, Sep 2024), noting that the usual pipelines &ldquo;often destroy context&rdquo; when they cut documents: adding a short, chunk-specific context to the front of each chunk before indexing cut the share of searches whose right chunk missed the top 20 by 35 percent, by 49 percent with a keyword index built the same way, and by 67 percent with a reranker on top (from 5.7 to 1.9 percent), in their tests.\n\n"
        "No attacker was needed for this one, but an attacker can use the same cut: put a claim far enough from its disclaimer and the "
        "chunker separates them for you."
    )
    mo.md(_text)
    return


@app.cell
def _(mo):
    mo.callout(mo.md("**Part 5 in a sentence.** A chunk is read on its own, so it has to carry its title and status, or a warning stays behind "
                     "in the chunk nobody retrieved."), kind="success")
    return


@app.cell
def _(divider, mo):
    mo.Html(divider(6, "Assemble: copies, conflicts and blockers", "You will do: plant copies of a false page until the assistant believes it, "
                    "then plant one page that silences three questions. You will have: show the conflict, gate the tier, watch refusals."))
    return


@app.cell
def _(ex, mo):
    copies_pick = mo.ui.radio(options=["1", "2", "3", "it never flips"], inline=True, label="How many copies of the false page flip the answer?")
    copies_n = mo.ui.radio(options={"none": "0", "one": "1", "two": "2", "three": "3"}, value="none", inline=True, label="Copies planted:")
    conflict_sw = mo.ui.switch(label="Show the conflict")
    mo.vstack([
        mo.md("So far the assistant read one chunk aloud. Real assistants put the top few chunks into the prompt together, here the top four, "
              "and the model writes one answer from all of them. When the chunks disagree, the model has to pick. This lab&rsquo;s stand-in "
              "goes with the side most chunks take, and on a tie with the side of the higher-ranked chunk. It is a stand-in, and it copies what was measured: Xie and colleagues (<a href='https://arxiv.org/abs/2305.13300' target='_blank' rel='noopener'>ICLR 2024</a>) found that models &ldquo;can be highly receptive to external evidence even when that conflicts with their parametric memory, given that the external evidence is coherent and convincing&rdquo;, and that they &ldquo;generally provide answers backed by the majority of evidence&rdquo;.\n\n"
              "The handbook now has two pages on passwords, hr-1 and it-3, and both say Settings."),
        ex("4.6.1"),
        copies_pick,
        mo.hstack([copies_n, conflict_sw], justify="start", gap=1, wrap=True),
    ])
    return conflict_sw, copies_n, copies_pick


@app.cell
def _(conflict_sw, copies_n, copies_pick, esc, fb_card, kr, mo, mono_panel):
    _n = int(copies_n.value)
    _r = kr.assembled(kr.QUESTIONS[0], kr.copies_store(_n), show_conflict=conflict_sw.value)
    _hits = "\n".join(f'<span class="sad-dim">{i + 1}.</span> {esc(d["id"])} ({esc(d["source"])}, {esc(d["tier"])}): says '
                      f'{esc(kr.CLAIM_TEXT.get(d.get("claim"), "nothing on this"))}' for i, d in enumerate(_r["hits"]))
    _kind = {"email": "bad", "conflict": "warn"}.get(_r["claim"], "good")
    _verdict = {"email": "the false procedure won", "conflict": "the user sees both sides and where each came from"}.get(
        _r["claim"], "the handbook answers")
    _out = [mo.Html(mono_panel(f"the top four chunks, with {copies_n.value} cop{'y' if _n == 1 else 'ies'} planted",
                               _hits + f'\n\n<span class="sad-dim">assistant:</span> {esc(_r["answer"])}', "", _verdict, _kind))]
    if copies_pick.value:
        _out.insert(0, fb_card(copies_pick.value == "2",
                               "two. One copy loses two to one. Two copies tie with the two handbook pages, and the copies rank higher "
                               "because they repeat the question, so the tie goes their way. Three win outright." if copies_pick.value == "2"
                               else "step through the copies: one loses to the two handbook pages, two tie and win on rank, because the "
                                    "copies repeat the question."))
    mo.vstack(_out)
    return


@app.cell
def _(mo):
    _text = ("This is why the PoisonedRAG authors planted five texts per question and not one: five copies can fill a top five, and then there "
          "is no other side left in the prompt, and their success fell once the retriever returned more than five. **Showing the conflict** is a reducer: the user sees two answers and where each came from, "
          "and can check before acting. The **tier gate** from Part 8 is the bound: the copies never reach the prompt, however many there are.")
    mo.md(_text)
    return


@app.cell
def _(ex, mo):
    blocker_sw = mo.ui.switch(label="Plant web-20")
    blocker_gate = mo.ui.switch(label="Trusted sources only")
    mo.vstack([
        ex("4.6.2"),
        mo.md("The harm does not have to be a wrong answer. A **blocker** document is written to be retrieved for many questions and to make "
              "the assistant decline them, and the second switch is the tier gate. web-20 gives no order: it states, falsely, that three topics are closed, and the model&rsquo;s own "
              "caution does the rest. Shafran, Schuster and Shmatikov showed it with one document and nothing but query access (<a href='https://arxiv.org/abs/2406.05870' target='_blank' rel='noopener'>USENIX Security 2025</a>): a single blocker jammed 28 to 73 percent of target queries on six open models, and 0 to 13 percent when moved unchanged to frontier models. This lab&rsquo;s stand-in refuses every time; real models refuse some of the time, and the authors found that &ldquo;higher safety scores are correlated with higher vulnerability to jamming&rdquo;."),
        mo.hstack([blocker_sw, blocker_gate], justify="start", gap=0.5, wrap=True),
    ])
    return blocker_gate, blocker_sw


@app.cell
def _(blocker_gate, blocker_sw, esc, fb_card, kr, mo, results_table):
    _store = kr.STORE + ([kr.BLOCKER] if blocker_sw.value else [])
    _rows, _refused = [], 0
    for _q in kr.QUESTIONS:
        _r = kr.assembled(_q, _store, trusted_only=blocker_gate.value)
        _no = _r["answer"] == kr.REFUSAL
        _refused += _no
        _rows.append((esc(_q), esc(_r["answer"][:70]) + ("&hellip;" if len(_r["answer"]) > 70 else ""), not _no))
    if not blocker_sw.value:
        _fb = fb_card(None, "all three answered. Plant web-20 and watch.", head="&#9675; nothing planted yet")
    elif _refused:
        _fb = fb_card(False, f"{_refused} of 3 questions refused by one document. Nothing false was said, so nothing looks wrong in a "
                             "single conversation: the sign is a refusal rate that jumps for questions that used to be answered.",
                      head="&#10007; one page, three refusals")
    else:
        _fb = fb_card(True, "all three answered again: web-20 is still in the store and never reaches the prompt. Keep a refusal-rate "
                            "alert per question as well, for the blocker that arrives through a source you trust.")
    mo.vstack([mo.Html(results_table("the three questions", _rows)), _fb])
    return


@app.cell
def _(mo):
    mo.callout(mo.md("**Part 6 in a sentence.** When chunks disagree the model picks, copies and blockers decide what it picks, and only the "
                     "tier gate keeps them out of the prompt."), kind="success")
    return


@app.cell
def _(divider, mo):
    mo.Html(divider(7, "Answer: check it against its source", "You will do: write the check that an answer says what its cited chunk says. "
                    "You will have: a citation shows where an answer came from, and a check shows it is true to it."))
    return


@app.cell
def _(esc, kr, mo, results_table):
    _rows = [(esc(a[:58]) + ("&hellip;" if len(a) > 58 else ""), "supported" if ok else "not supported", ok,
              "word for word" if i == 0 else ("a number the chunk never gave" if i == 1 else "an address the chunk never gave"))
             for i, (a, c, ok) in enumerate(kr.GROUNDING_SAMPLES)]
    mo.vstack([
        mo.md("Part 8 adds a citation to every answer, and it helps: the reader can open the source. It does not tell the reader whether the "
              "answer says what the source says. The model can cite the right chunk and still change a number, or add an address the chunk "
              "never gave. Three answers, all citing acme-1:"),
        mo.Html(f'<div class="sad-panel"><p class="sad-cap">acme-1, the cited chunk</p><div class="sad-mono">{esc(kr.TENANT_CHUNK)}</div></div>'),
        mo.Html(results_table("three answers that cite it", _rows)),
    ])
    return


@app.cell
def _(ex, kr, mo, stuck):
    supported_code = mo.ui.code_editor(theme="dark", value=kr.STARTERS["supported"], language="python", debounce=True)
    mo.vstack([
        ex("4.7.1"),
        supported_code,
        stuck("Return False first if either text is empty after `.strip()`. Then compare sets: `facts(answer) <= facts(chunk)` is True only "
              "when every fact in the answer is in the chunk. Last, `len(words(answer) & words(chunk)) * 2 >= len(words(answer))`. Compare "
              "the sets, not the strings: `'30' in '0100 200 300'` is True."),
    ])
    return (supported_code,)


@app.cell
def _(answer, kr, mo, results_table, supported_code, verdict):
    _rows, _state, _err = kr.grade("supported", supported_code.value)
    mo.vstack([
        mo.Html(results_table(f"your supported() on {len(kr.EXERCISE_CASES['supported'])} answers", _rows)) if _rows else mo.md(""),
        mo.md(verdict(_state, _err,
                      "Run it before an answer is shown, or on a sample of logged answers every day. It is a reducer, and an honest one about "
                      "its limits: it catches a changed number or an invented address, and it cannot catch an answer that is faithful to a "
                      "chunk that was itself false. That is what the tier gate is for.",
                      "The rows marked ✗ are wrong. Empty answers and empty chunks are never supported; every fact in the answer must be in "
                      "the chunk&rsquo;s facts (compare sets, not substrings); and at least half the answer&rsquo;s words must be in the chunk.")),
        answer(kr.ANSWERS["supported"]),
    ])
    return


@app.cell
def _(mo):
    _text = ("The same idea at the other end of an agent&rsquo;s work is a claim of completion: <a href='../course/#/lesson/tools-agency' "
          "target='_top'>Module 03</a> (Part 7) checks the records before it believes an agent that says it is done.")
    mo.md(_text)
    return


@app.cell
def _(mo):
    mo.callout(mo.md("**Part 7 in a sentence.** A citation says where an answer came from; a check against the cited chunk says whether the "
                     "answer is true to it, and neither says the chunk is true."), kind="success")
    return


@app.cell
def _(divider, mo):
    mo.Html(divider(8, "Blue team: bound it at three points", "You will do: predict the fixing switch, turn on three controls. "
                    "You will have: the action to control table for the whole pipeline."))
    return


@app.cell
def _(ex, hat, mo):
    p8_pick = mo.ui.radio(options=["provenance tiers at ingestion", "authorization at retrieval", "citations at the answer"], inline=True,
                          label="Which single control takes the false procedure out of the password answer?")
    mo.vstack([ex("4.8.1"), hat("blue", "The switchboard"), p8_pick])
    return (p8_pick,)


@app.cell
def _(fb_card, mo, p8_pick):
    mo.stop(p8_pick.value is None, mo.md("_Guess first._"))
    fb_card(p8_pick.value == "provenance tiers at ingestion",
            "only the trusted tier may answer a how-to question, so web-9 is still retrieved and never reaches the prompt." if p8_pick.value.startswith("provenance")
            else ("authorization filters by who may see a document; web-9 is in Koda's own index, so it passes." if p8_pick.value.startswith("authorization")
                  else "a citation shows the reader where the answer came from; the false procedure is still in it. The tier gate removes it."))
    return


@app.cell
def _(ex, mo):
    sw_tier = mo.ui.switch(label="provenance tiers at ingestion")
    sw_auth = mo.ui.switch(label="authorization at retrieval")
    sw_cite = mo.ui.switch(label="citations at the answer")
    mo.vstack([
        ex("4.8.2"),
        mo.md("The store now also holds `acme-1`, another customer's terms. Turn controls on; watch both questions."),
        mo.hstack([sw_tier, sw_auth, sw_cite], justify="start", gap=0.5, wrap=True),
    ])
    return sw_auth, sw_cite, sw_tier


@app.cell
def _(esc, kr, mo, mono_panel, sw_auth, sw_cite, sw_tier):
    _policy = {"answer_from": {"handbook"} if sw_tier.value else None, "filter_by_user": sw_auth.value, "cite": sw_cite.value}

    def _panel(q, bad_if, bad_text, good_text):
        _r = kr.ask(q, kr.SHARED, _policy)
        _bad = bad_if(_r)
        _ans = esc(_r["answer"])
        if sw_cite.value and "untrusted" in _r["answer"]:
            _ans = _ans.replace("web-import, untrusted", '<span class="sad-hl">web-import, untrusted</span>')
        _ret = ", ".join(d["id"] for d in _r["retrieved"]) or "nothing"
        _rea = ", ".join(d["id"] for d in _r["reaches"]) or "nothing"
        return mono_panel(f"user: {esc(q)}", f'<span class="sad-dim">retrieved:</span> {_ret}\n<span class="sad-dim">reached the prompt:</span> {_rea}\n'
                          f'<span class="sad-dim">assistant:</span> {_ans}', "",
                          bad_text if _bad else good_text, "bad" if _bad else "good")

    _p1 = _panel(kr.QUESTIONS[0], lambda r: kr.FALSE_SIGN in r["answer"],
                 "the false procedure is answered" + (", and now the reader can see it came from web-import, untrusted" if sw_cite.value else ""),
                 "the handbook answers; web-9 was retrieved and never reached the prompt")
    _p2 = _panel(kr.Q_TENANT, lambda r: any(d["id"] == "acme-1" for d in r["retrieved"]),
                 "Acme's terms came back for a Koda user", "the other tenant's document never came back")
    mo.vstack([
        mo.Html(_p1), mo.Html(_p2),
        mo.md("Detect: a canary document that must never be answered; the day a logged answer carries it, the gate has failed."),
    ])
    return


@app.cell
def _(mo):
    _rows = [("a wrong fact answered as policy", "provenance tier at ingestion", "only the trusted tier may answer a how-to question", "bound"),
             ("text nobody approved gets indexed", "compare extracted with reviewed text (Part 4)", "at ingestion, before indexing", "bound"),
             ("a chunk loses its warning", "carry title and status into every chunk (Part 5)", "at chunking", "reduce"),
             ("the attacker ranks first, or fills the top k", "trust-weighted ranking, show the conflict (Parts 2, 6)", "ranking and assembly; the gate still decides", "reduce"),
             ("a blocker silences questions", "the tier gate, and a refusal-rate alert (Part 6)", "before the prompt, and in monitoring", "bound, then detect"),
             ("the answer changes what the source said", "check the answer against its chunk (Part 7)", "after generation, before showing", "reduce"),
             ("another tenant's document returned", "authorization at retrieval", "the filter reads the user's credential, before the model reads anything", "bound"),
             ("a stale document still answers", "live access check, cache purge, delete by source (Part 9)", "at query time, and in every copy", "bound"),
             ("the document gives an order", '<a href="../course/#/lesson/prompt-injection" target="_top">Module 02</a>: a permission on the action',
              "the same bug through a new door", "bound")]
    _body = "".join(f"<tr><td>{a}</td><td>{c}</td><td data-k='muted'>{w}</td><td data-k='muted'>{k}</td></tr>" for a, c, w, k in _rows)
    _col = lambda h, items: f"<div><h4>{h}</h4><ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul></div>"
    mo.vstack([
        mo.md("**The action to control table**, yours to keep:"),
        mo.Html('<div class="sad-tablebox"><table class="sad-table"><tr><th>what goes wrong</th><th>the control</th><th>where it sits</th><th>kind</th></tr>'
                + _body + "</table></div>"),
        mo.Html('<div class="sad-cols">'
                + _col("Reduce the odds", ["trust-weighted ranking", "context carried into chunks", "show conflicts", "check answers against chunks"])
                + _col("Bound the impact", ["tiers at ingestion", "index only reviewed text", "authorization at retrieval, checked live", "secrets never in the index"])
                + _col("Detect and respond", ["log what was retrieved per answer", "canary documents", "refusal-rate alerts", "re-ingest from a known snapshot"])
                + "</div>"),
    ])
    return


@app.cell
def _(mo):
    mo.callout(mo.md("**Part 8 in a sentence.** The poison stays in the store: a tier keeps it out of the prompt, a filter keeps other "
                     "tenants out, a citation lets the reader check."), kind="success")
    return


@app.cell
def _(divider, mo):
    mo.Html(divider(9, "The index outlives its sources", "You will do: stop three stale answers with the fewest controls, stop a saved reply "
                    "laundering a false page, and watch an agent pick its own search. You will have: the index is a copy, and copies need a lifecycle."))
    return


@app.cell
def _(ex, kr, mo):
    life_pick = mo.ui.radio(options=["the live check alone", "the live check and the cache purge", "deletion and the cache purge", "all three"],
                            inline=False, label="Which is the smallest set of controls that stops all three stale answers?")
    life_live = mo.ui.switch(label="Live access check")
    life_delete = mo.ui.switch(label="Delete by source id")
    life_purge = mo.ui.switch(label="Purge stale answers")
    mo.vstack([
        mo.md("An index is a copy of its sources, made at one moment. The sources keep changing: permissions narrow, documents are deleted, "
              "and the answers built on them get cached. Three things happened at Koda this month, and three controls are on offer: "
              "**live access check** (at query time, ask the source whether this user may read the document), **delete by source id** "
              "(remove every chunk of a deleted source, from the index and its backups) and **purge stale answers** (drop cached "
              "answers that cite a removed source)."),
        ex("4.9.1"),
        life_pick,
        mo.vstack([life_live, life_delete, life_purge], gap=0.25),
    ])
    return life_delete, life_live, life_pick, life_purge


@app.cell
def _(esc, fb_card, kr, life_delete, life_live, life_pick, life_purge, mo, status_text):
    _rows, _open = "", 0
    for _e in kr.LIFE_EVENTS:
        _still, _why = kr.lifecycle(_e["id"], live=life_live.value, delete=life_delete.value, purge=life_purge.value)
        _open += _still
        _rows += (f'<div class="sad-row"><div class="sad-grow"><div class="sad-title">{esc(_e["label"])}</div>'
                  f'<div class="sad-sub2">asked: {esc(_e["question"])}</div></div>'
                  f'<div class="sad-grow">{status_text(_still)} <span class="sad-sub2">{esc(_why)}</span></div></div>')
    _out = [mo.Html(f'<div class="sad-panel"><p class="sad-cap">Three stale answers</p>{_rows}</div>')]
    if life_pick.value:
        _out.insert(0, fb_card(life_pick.value == "the live check and the cache purge",
                               "the live check and the cache purge. Checking access against the source at query time catches both the "
                               "narrowed permission and the deleted document, because a deleted source allows nothing. The cache answers "
                               "before retrieval runs, so only clearing it helps there." if life_pick.value.startswith("the live check and")
                               else "turn the switches on one at a time and read which rows each one closes: one control covers two rows, "
                                    "and one row has a single control."))
    if not _open:
        _out.append(mo.md("All three stopped. Deletion by source id still earns its place: a live check only protects the paths that ask "
                          "it, and backups, exports and anything trained on the text never ask. An embedding left in a backup is not "
                          "anonymised either: Vec2Text rebuilt 92% of short (32-token) passages word for word from one open embedding model "
                          "(2023). The cache is documented: on Copilot for Microsoft 365, in the researchers&rsquo; own SharePoint set-up, the ConfusedPilot study (<a href='https://arxiv.org/abs/2408.04870' target='_blank' rel='noopener'>arXiv 2408.04870</a>, 2024) found that &ldquo;a deleted document is still presented in the cache until the next time it is indexed&rdquo;. Microsoft&rsquo;s own page puts the permission side plainly: Copilot &ldquo;only surfaces organizational data to which individual users have at least view permissions&rdquo; (<a href='https://learn.microsoft.com/en-us/copilot/plan/microsoft-365-copilot-privacy' target='_blank' rel='noopener'>Microsoft Learn</a>), so the permissions in the source are the control. OWASP&rsquo;s LLM09:2026: &ldquo;Delete embeddings within a bounded time when the source document is deleted, and verify with reconciliation audits.&rdquo;"))
    mo.vstack(_out)
    return


@app.cell
def _(status_chip):
    def status_text(still):
        return status_chip("&#10007; still answers", "bad") if still else status_chip("&#10003; stopped", "good")
    return (status_text,)


@app.cell
def _():
    def status_chip(text, kind):
        return f'<span class="sad-st" data-k="{kind}">{text}</span>'
    return (status_chip,)


@app.cell
def _(esc, ex, kr, mo):
    wb_sw = mo.ui.switch(label="Replies keep the lowest tier")
    mo.vstack([
        ex("4.9.2"),
        mo.md("Assistants write as well as read, and what they write can be indexed. Last month the assistant answered a ticket from web-9, "
              "before anyone gated web-9, and the reply was saved to *resolved tickets*, a source the index reads and treats as trusted, "
              "because staff close those tickets. The tier gate is on. The switch makes a saved reply keep the lowest tier of what it quoted."),
        mo.Html(f'<div class="sad-panel"><p class="sad-cap">{esc(kr.REPLY["id"])} &middot; {esc(kr.REPLY["source"])}, quoted '
                f'{esc(", ".join(kr.REPLY["quoted"]))}</p><div class="sad-mono">{esc(kr.REPLY["text"])}</div></div>'),
        wb_sw,
    ])
    return (wb_sw,)


@app.cell
def _(esc, kr, mo, mono_panel, wb_sw):
    _r = kr.write_back(wb_sw.value)
    _bad = _r["claim"] == "email"
    _hits = ", ".join(f'{d["id"]} ({d["tier"]})' for d in _r["hits"])
    mo.vstack([
        mo.Html(mono_panel("the next person asks how to reset their password", f'<span class="sad-dim">reached the prompt:</span> {esc(_hits)}\n'
                           f'<span class="sad-dim">assistant:</span> {esc(_r["answer"])}', "",
                           "web-9&rsquo;s procedure, now wearing a trusted label" if _bad else "the handbook answers",
                           "bad" if _bad else "good")),
        mo.md("The reply laundered web-9: the gate checks the tier of the chunk, and the reply&rsquo;s tier said trusted. The rule is that "
              "provenance travels: anything the assistant writes keeps the lowest tier of what it read. The same loop let a worm travel between email assistants in Morris II (Cohen, Bitton and Nassi, <a href='https://arxiv.org/abs/2403.02817' target='_blank' rel='noopener'>arXiv 2403.02817</a>, 2024), built on the authors&rsquo; own email client: to spread, the planted text had to &ldquo;(1) be stored in the RAG&rsquo;s database of the recipient (the new host), (2) be retrieved by the RAG when responding to new messages&rdquo;. Each reply carried it to the next inbox."),
    ])
    return


@app.cell
def _(mo):
    agent_sw = mo.ui.switch(label="Searches inherit the tier")
    mo.vstack([
        mo.md("**An agent that picks its own searches.** In agentic retrieval the model writes its next query from what it just read. A "
              "poisoned chunk does not have to carry the false answer; it only has to choose the next search. The switch makes a search "
              "planned from an untrusted chunk untrusted too."),
        agent_sw,
    ])
    return (agent_sw,)


@app.cell
def _(agent_sw, esc, kr, mo, mono_panel):
    _steps = kr.agent_trace(agent_sw.value)
    _lines = []
    for _i, (_q, _id, _may) in enumerate(_steps, 1):
        _lines.append(f'<span class="sad-dim">search {_i}:</span> {esc(_q)}\n<span class="sad-dim">  picked:</span> {esc(_id)}, '
                      + ("may answer" if _may else "may not answer a policy question"))
    _bad = _steps[1][2]
    mo.vstack([
        mo.Html(mono_panel("two searches", "\n".join(_lines), "",
                           "the second search reached the attacker&rsquo;s page, and it may answer" if _bad else
                           "the second search inherited web-14&rsquo;s tier, so its page cannot answer", "bad" if _bad else "good")),
        mo.md("AgentPoison (Chen and colleagues, <a href='https://arxiv.org/abs/2407.12784' target='_blank' rel='noopener'>NeurIPS 2024</a>) measured this on real agent designs: a few trigger-optimised entries, under 0.1 percent of an agent&rsquo;s memory or knowledge base, were retrieved 82 percent of the time and led to the harmful action 63 percent of the time end to end, while normal tasks changed by at most 1 percent. The control is the one from write-back: provenance travels, here from a chunk to the search it inspired."),
    ])
    return


@app.cell
def _(mo):
    mo.callout(mo.md("**Part 9 in a sentence.** The index is a copy: check access against the live source, clear what was cached, delete by "
                     "source id everywhere, and let provenance travel with anything the assistant writes or searches."), kind="success")
    return


@app.cell
def _(divider, mo):
    mo.Html(divider(10, "Capstone and your own system", "You will do: write a policy that passes four checks. You will have: a checklist "
                    "for your index and three documented cases."))
    return


@app.cell
def _(ex, mo):
    capstone_code = mo.ui.code_editor(theme="dark", language="python", debounce=True,
                                      value=("my_policy = {\n"
                                             "    \"answer_from\": None,       # a set of sources that may answer, for example {\"handbook\"}\n"
                                             "    \"filter_by_user\": False,   # drop documents the user may not see, before ranking\n"
                                             "    \"cite\": False,             # show source and tier on every answer\n"
                                             "}"))
    mo.vstack([ex("4.10.1"), mo.md("Write `my_policy` so all four checks pass; the poison stays in the store."), capstone_code])
    return (capstone_code,)


@app.cell
def _(capstone_code, kr, mo, results_table):
    try:
        _ns = {}
        exec(capstone_code.value, _ns)
        _p = _ns.get("my_policy")
        if not isinstance(_p, dict) or not _p:
            raise ValueError("my_policy is empty: it needs answer_from, filter_by_user and cite")
        _r1 = kr.ask(kr.QUESTIONS[0], kr.SHARED, _p)
        _r2 = kr.ask(kr.Q_TENANT, kr.SHARED, _p)
        _checks = [("the false procedure is gone and the handbook answers", kr.FALSE_SIGN not in _r1["answer"] and "Settings" in _r1["answer"]),
                   ("the poison is still in the store", any(d["id"] == "web-9" for d in kr.SHARED)),
                   ("the other tenant's document is not returned", not any(d["id"] == "acme-1" for d in _r2["retrieved"])),
                   ("the citation is present", "[source:" in _r1["answer"])]
        _rows = [(c, "pass" if ok else "fail", ok) for c, ok in _checks]
        _n = sum(ok for _, ok in _checks)
        # the hint names the first failing check, not the count: each check has its own key
        _hints = {0: "Start with answer_from.", 2: "Which key decides who may see acme-1?", 3: "Which key makes the source visible?"}
        _first = next((_i for _i, (_, ok) in enumerate(_checks) if not ok), None)
        _msg = ("**PASS.** All four hold, and web-9 is still in the store: you bounded where knowledge may come from, not the text."
                if _n == 4 else f"**Not yet.** {_n} of 4 checks pass. " + _hints.get(_first, "One key left."))
        _out = mo.vstack([mo.Html(results_table("the grader", _rows)), mo.md(_msg + (f"\n\n*the answer:* {_r1['answer']}" if _n == 4 else ""))])
    except Exception as _e:
        _out = mo.md(f"**Not yet.** `{_e}`")
    _out
    return


@app.cell
def _(mo):
    _text = (
        "**Take it to your own system**\n\n"
        "- List the sources that feed each index, and mark which an outsider can write to.\n"
        "- Find out what your parser extracts from each file type, and compare it with what reviewers see before anything is indexed.\n"
        "- Check that every chunk carries its document&rsquo;s title, section and status.\n"
        "- Decide which tier answers what, and apply the gate before the prompt, not after.\n"
        "- Turn off ranking signals an outsider controls for anything that answers policy, or put the tier gate after them.\n"
        "- When retrieved chunks disagree, show the user both sides.\n"
        "- Alert on refusal rates per question, and plant a canary that must never be answered.\n"
        "- Spot-check that answers say what their cited chunk says.\n"
        "- Check access against the live source at query time, clear cached answers when a source goes, and delete by source id from "
        "the index, its backups and its exports.\n"
        "- Give anything the assistant writes the lowest tier of what it read, before it is indexed."
    )
    mo.md(_text)
    return


@app.cell
def _(chip, mo):
    def _case(date, kind, title, what, bound, links):
        _links = " &middot; ".join(f'<a href="{u}" target="_blank" rel="noopener">{l}</a>' for l, u in links)
        return ('<div class="sad-case">'
                f'<div class="sad-case-meta"><span>Documented case &middot; {date}</span>{chip(kind)}</div>'
                f'<div class="sad-case-title">{title}</div>'
                f'<div><b>What happened.</b> {what}</div>'
                f'<div class="sad-gap"><b>What would have bounded it.</b> {bound}</div>'
                f'<div class="sad-src sad-gap">Sources (open in a new tab): {_links}</div></div>')
    _cases = mo.Html(
        _case("Feb 2024, USENIX Security 2025", "Researcher demonstration", "PoisonedRAG: five texts in a database of millions",
              "Zou, Geng, Wang and Jia injected five malicious texts per target question into a knowledge database of millions of texts and "
              "report a 90 percent attack success rate: the assistant gave the attacker's chosen answer to the attacker's chosen question.",
              "Provenance at ingestion: a text nobody vouched for never answers. Five in millions is why ranking cannot be the trust signal.",
              [("arXiv 2402.07867", "https://arxiv.org/abs/2402.07867")])
        + _case("20 Aug 2024", "Disclosed vulnerability", "Slack AI: a public-channel message in a private answer",
                "A public channel with one member, its author, is a place anyone in the workspace can write to, and Slack AI's search reads it. "
                "When the victim asked Slack AI for an API key kept in a private channel, search pulled the stranger's public-channel message "
                "into the same context. The attacker's message was not cited as a source. Slack said public-channel search is intended behaviour.",
                "Door 2, a user-writable source the index reads: tier it as untrusted, and cite the source so a stranger's channel shows in the answer.",
                [("PromptArmor", "https://promptarmor.substack.com/p/data-exfiltration-from-slack-ai-via")])
        + _case("published 11 Jun 2025", "Disclosed vulnerability", "EchoLeak, Microsoft 365 Copilot, CVE-2025-32711",
                "One crafted email, retrieved by Copilot as context for the victim's question. The CVE record (CVSS 9.3) credits an unauthorized "
                "attacker: the writer needed no account. For this module: inbound email is a source a stranger can write to, and retrieval picked it.",
                "A provenance tier: an external email never answers an internal question.",
                [("CVE-2025-32711", "https://cveawg.mitre.org/api/cve/CVE-2025-32711")])
    )
    mo.vstack([mo.md("Three cases, read for one question only: who could write to what the search read."), _cases], gap=0.5)
    return


@app.cell
def _(mo):
    mo.accordion({"Where this module stops: poisoning the model itself": mo.md(
        "Everything here is **retrieval-time** poisoning: the bad text sits in a store you control, so tiers, filters and re-ingesting "
        "from a snapshot remove it. **Training-time** poisoning is different. The bad text went into the data a model learned from, and "
        "no control at retrieval can take it out: Anthropic, the UK AI Security Institute and the Alan Turing Institute found that about "
        '<a href="https://www.anthropic.com/research/small-samples-poison" target="_blank" rel="noopener">250 poisoned documents</a> '
        "planted a backdoor (a trigger word that made the model write gibberish) in models from 600 million to 13 billion parameters, "
        "whatever their size (Oct 2025). For a team building on "
        "hosted models the control is provenance: know where a model, an adapter or a fine-tuning set came from, and never fine-tune on "
        "data a stranger could write. The EU AI Act names data poisoning and model poisoning among the attacks a high-risk system must "
        'be built to resist (<a href="https://eur-lex.europa.eu/eli/reg/2024/1689/oj" target="_blank" rel="noopener">Article 15(5)</a>).')})
    return


@app.cell
def _(mo):
    _text = (
        "Standards: OWASP **LLM08:2025** (Vector &amp; Embedding Weaknesses, LLM09:2026), **LLM01** (Prompt Injection, the same number in 2025 "
        "and 2026), **ASI06** (Memory &amp; Context Poisoning)."
    )
    mo.md(_text)
    return


@app.cell
def _(mo, recap_html):
    mo.vstack([
        mo.Html(recap_html("You now have the method", [
            "Follow a document from its source to the answer, and ask at each step who could change it: the source, the parser, the chunker, "
            "the ranker, the prompt, the answer.",
            "Bound it where knowledge enters: a provenance tier at ingestion, authorization at retrieval, only reviewed text indexed.",
            "Treat the index as a copy with a lifecycle: live access checks, cache purges, deletion by source id, and provenance that "
            "travels with whatever the assistant writes.",
        ], "an action to control table for your own pipeline, and a checklist to run against your index.")),
        mo.md("Next: <a href=\"../course/#/lesson/data-leakage\" target=\"_top\">Module 05, data leakage and output handling</a>."),
    ])
    return


@app.cell
def _(mo):
    mo.callout(mo.md("**Part 10 in a sentence.** Bound where knowledge comes from, who may see it and how long it lives, and let the user see "
                     "where every answer came from."), kind="success")
    return


if __name__ == "__main__":
    app.run()
