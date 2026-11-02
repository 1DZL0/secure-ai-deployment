# Module 09 outline: Monitoring, evaluation and governance

Working title: **Monitoring, evaluation and governance: prove what the agent did, and who answers for it**

Subtitle: You bounded the actions in Modules 02 to 04. This module makes that provable: a log that holds the literal call, a detector you write and then evade, the eval suite in CI, a stop you rehearse, and a one-page register with a name on every open risk.

Meta line: about 35 minutes · runs in your browser, no key needed · Koda is invented, nothing real is touched

Shape: Module 02's arc (see it first, predict, do, check, one sentence per part) at Module 01's pace (nothing longer than a screen, one interaction per section). No live model. Deterministic planner only, so the stage version is safe. Five parts, each with "You will do / You will have", a red or blue hat, one graded exercise, one documented case beside it, and "Part N in a sentence".

The one line to leave on the wall: **The fix is a permission, not a prompt; the proof is a log, a test and a name.**

---

## Opening

**See it first.** The Module 02 attack again (customer 42, three harmful calls), but this time the question is not "what happened" but "could you have proved it afterwards?" Two logs side by side from the same run: the thin log a typical deployment keeps (`read_file ok`, `query_db ok`, `remember ok`) and the full trace (literal arguments, the text that preceded each call and where it came from, the decision, the reason). Ask: which of these two could you hand to an auditor, a customer or a court?

**Three things make a deployment answerable** (numbered list, like 02's "four things"):
1. **The literal call is in the log.** Not the model's summary of it. Arguments, result, the principal whose authority it used, and what text arrived just before.
2. **The proof lives outside the model.** A test that runs on every change and asserts on the trace, never on the reply.
3. **Someone's name is on what is still open.** A residual-risk line with an owner, dated, and a stop that was rehearsed.

**In this module** (parts list):
- Part 1. **What a log must hold.** Rebuild the trace from the thin log and fail; learn the eight fields.
- Part 2. **Write the detector, then evade it.** A `suspicious()` over trace steps, graded; then beat your own rule.
- Part 3. **Make it a test.** The repo's real CI eval suite; add a vector, watch it fail, then pass.
- Part 4. **The stop that wasn't tested.** Three documented incidents, timed; set a stop rule and watch where the run halts.
- Part 5. **The register.** Your tools, their controls, their tests and the name on each open risk, on one page.

**You leave with:** a one-page risk register for your own agent, a detector and a CI test you wrote, and a stop drill you can run quarterly. It builds on the tool register from Module 03 and the residual-risk line from Module 02.

**Where this module stops.** It is not a SIEM product tour and not legal advice. The EU AI Act section is one dated accordion, with a "checked on" line, because it will change; the controls here are the ones that satisfy any of the frameworks named. Modules 05 to 08 own the specific channels (answer path, code, memory, peers); this module owns the evidence.

---

## Part 1. What a log must hold (blue team)

You will do: reconstruct an attack from a thin log, fail, then pick the fields that would have made it possible.
You will have: the eight fields of a tool-call record, and the rule that refusal reasons go to the log, never back to the model.

- **Predict first** (radio): "From the thin log alone, which of the three harmful calls can you prove happened?" Answer: none; you can prove tools ran, not what they did.
- **Exercise** (checkbox batch, graded): tick the fields a tool-call record needs. Eight right answers: run id, timestamp, principal (whose authority), tool, literal arguments, result (size and hash, not the payload), provenance of the text that preceded the call (which document, which field, trusted or not), decision and reason. Four distractors: the model's explanation, the full system prompt per call, the reply text, a risk score.
- **Why the reason stays out of the reply:** Module 02's rule shown as a log line. A precise denial in the log is evidence; the same denial sent to the model is an oracle.
- **Documented cases beside it:** Hugging Face recovered "about 17,600 actions" from logs and could say which five datasets were touched (case 29); Asana could only offer "logs on request" and a form (case 6).
- **Part 1 in a sentence.** If the literal call is not in the log, you can prove what the agent said, not what it did.

Reuses: `koda_lab.run_agent`, `console_html` (add a "log view" renderer that prints the same steps as records), Module 03's checkbox-batch form.

## Part 2. Write the detector, then evade it (blue team, then red team)

You will do: write `suspicious(step, ctx)` over a list of trace steps; then reword the attack until your detector misses it.
You will have: a working detector, the difference between time to alert and time to stop, and the reason a detector is filed under detect, not bound.

- **Exercise** (code editor, graded like Module 02's `allowed()`): steps carry `tool`, `args`, `result`, `blocked`, `provenance`, `t`. Cases: an outbound URL carrying a value the agent just loaded (taint); the fourth email inside a minute (burst); a durable write after untrusted text arrived; a destructive verb in a session that was supposed to be read-only; two benign rows that must pass (a lookup, a reply to the customer's own address).
- **Red team: beat your own detector.** Base64 the email, split it over two fetches, rename the note. Your rule slips. Same lesson as the keyword filter in 02: a detector buys time and evidence, not safety.
- **Two clocks:** time to alert and time to stop. Show case 30's numbers: alert at 12 minutes, acknowledged at 15, run killed at 2 hours 44, because the automated stop did not fire and nobody was sure they were allowed to pull it by hand.
- **Part 2 in a sentence.** A detector tells you something happened; only a tested stop makes it stop.

Reuses: `koda_toolbox.grade_function` and `call_guarded`, `koda_lab.step_is_win` for the oracle, Module 02's `AMBER` highlight for the planted text.

## Part 3. Make it a test (blue team)

You will do: read the repo's real eval suite and its CI job, add one vector, watch it fail, add the control, watch it pass.
You will have: the shape of an injection eval (plant, run, assert on the trace), and the two numbers to report (attack success and task success).

- **Show the real thing:** `test_lab.py` (the `VECTORS` list: each is a planted note, a target tool and an expected refusal) and `.github/workflows/ci.yml` (it runs on every push with no model and no key). This is what "the policy layer is tested" means on this course.
- **Exercise** (editor, graded): add a vector for a new note. The page runs the policy layer in the browser against the unsafe and the hardened profile. Red first (unsafe lets it through), then green once the matching control is on. The grader requires both: the test must fail on unsafe and pass on hardened, or it is not testing anything.
- **Predict first** (radio): "A classifier vendor shows 99 percent on its own test set. Which test matters?" Answer: an adaptive attacker with many attempts (The Attacker Moves Second; OWASP 2026 control 11).
- **The cost column:** report utility beside security, the AgentDojo habit from Module 02 Part 7. A boundary that breaks the real task gets removed by the first person it blocks.
- **Part 3 in a sentence.** An eval that asserts on the trace, in CI, is the only control that catches the regression nobody noticed.

Reuses: `koda_lab.dispatch`, `replay`, `PROFILES`; the `VECTORS` structure from `test_lab.py` (the browser version imports the same list).

## Part 4. The stop that wasn't tested (case replay, then blue team)

You will do: time three documented incidents, name the missing control, then set a stop rule on the Koda stream and watch where the run halts.
You will have: a stop drill, and the habit of measuring time to stop.

- **Three cases, one question each** (radio with feedback, Module 01's "spot the risk" format):
  - Case 30, the DNS route out of a "closed" sandbox: first signal at 12 minutes, stop at 2 hours 44. What should have stopped it at minute 15? (An automated stop that had been tested, and a written rule that anyone on call may pull it.)
  - Case 19, `terraform destroy` on production: no adversary, no alert, restore took 24 hours from backups outside Terraform. What was the control? (Deletion protection and a daily restore test; the agent without apply or destroy rights.)
  - Case 18, the 13-hour Kiro outage: the agent "decided to delete and recreate the environment" under broader permissions than expected. What was the control? (A task-scoped role, second-person approval of the literal destructive plan, change windows.)
- **Exercise: set the stop rule.** The Module 03 approval stream with a stop panel: choose a rule (stop after the first refused egress; stop after N refused calls; stop when a write follows untrusted text) and the stream shows where the run halts and what still got through before it did. The point lands by itself: a rule that fires on the second bad call still let the first one through, so the stop is a backstop under the boundary, not instead of it.
- **Rehearse it:** a three-line stop drill to copy (who may stop, how, how you know it worked), scheduled like a fire drill.
- **Part 4 in a sentence.** Measure time to stop, not time to alert, and rehearse the stop before the day you need it.

Reuses: Module 03's approval-stream renderer and `needs_approval` plumbing; case cards from `cases.json` rendered with Module 03's card function.

## Part 5. The register (blue team)

You will do: lay your tool register onto the frameworks, fill the one-page risk register, and put a name on every open row.
You will have: the deliverable a company would want from this training, and the vocabulary an auditor will use.

- **The frameworks in one table, mapped to what you already built** (no new theory): NIST AI RMF's four functions (Govern, Map, Measure, Manage) as columns; the rows are this course's controls (tool diet, scoped credential, object check, argument check, approval gate, egress allowlist, gated memory, the eval in CI, the log, the stop drill). OWASP's 2026 LLM01 controls c1 to c11 and the Agentic Top 10 ids appear as the second vocabulary, pointing back to the parts that built them.
- **The EU AI Act, one dated accordion.** What it is (Regulation 2024/1689, applicable from 2 August 2026 with staged exceptions), the two questions a company building agents has to answer (which risk class, and provider or deployer), and the duties that map onto this module (logging, documentation, human oversight, incident reporting). Checked-on date in the first line, like the case library. No legal advice; a pointer to the Commission's page.
- **Exercise: fill the register** (an `Html.batch` form, prefilled with Koda's tools as the worked example, then blank rows for the learner's own). Columns: tool · action type · control · where it is enforced · the test that proves it · residual risk · owner · review date. The page renders it as a printable page; that is the thing they leave with.
- **Predict first** (radio): "Who signs the residual-risk line?" Answer: someone who can accept the risk for the business, not the engineer who found it.
- **Part 5 in a sentence.** Governance is the register plus the names on it: every unbounded action has an owner who accepted it in writing, with a date.

Reuses: the tool-register table from Module 03 Part 9, the c1 to c11 table from Module 02 Part 5, the residual-risk step from Module 02 Part 7.

---

## Closing

**You now have the evidence.** Modules 02 to 04 bounded the actions; this module made the bounds provable. Then the one line. Then "Next": the course map, which modules are still coming, and the take-home pack.

**Take it to your own agent** (short, since 02 and 03 already carry the long versions): fill the register for your own tools; put one eval in CI this week; add the eight log fields to your tool wrapper; schedule the stop drill; name the owner and the review date.

## Checkpoint questions for the course shell (draft)

1. From a log that records only tool names and "ok", what can you prove about an incident? (That tools ran, not what they did; the literal arguments and the preceding text are the evidence.)
2. Your detector flags an outbound URL that carries a customer email. An attacker base64-encodes the email. What have you learned about the detector? (It is a reducer; it buys evidence and time, and the boundary still has to sit on the action.)
3. A new test passes on both the unsafe and the hardened profile. What is wrong? (It is not testing the control; a real eval fails without the control and passes with it.)
4. In the DNS incident the alert fired at 12 minutes and the run stopped at 2 hours 44. Which number does governance care about, and what cut it? (Time to stop; a tested automated stop and a standing rule that on-call staff may pull it.)
5. Who signs the residual-risk line for an action nothing bounds yet? (Someone able to accept the risk for the business, dated and reviewed, not the engineer.)

## Build notes

- New code: a log-record renderer over `koda_lab` steps; the `suspicious()` exercise with its case list and oracle; a browser-side runner for `VECTORS` against `PROFILES`; a stop-rule option on the Module 03 stream; the register form and its printable render. Everything else is reuse.
- Length target: 35 minutes, about 35 cells. Keep every part on one screen before its exercise.
- Facts to date-stamp in the text: ATLAS version, OWASP editions, AI Act applicability. Put them in one place so the next fact-check is one edit.
- Shell: add the quiz, set `minutes: 35`, flip `coming` off, and the Module 01 map's row 09 from "coming" to live.
