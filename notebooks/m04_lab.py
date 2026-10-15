"""Module 04 lab kit: the graders and the demo knowledge base.
Imported at the top of the notebook so the lesson cells stay clean.
Nothing here needs editing, and nothing here needs a key. it is all inert demo data."""


def check(ok, got_it, hint):
    print(("[PASS]   " + got_it) if ok else ("[NOT YET]   " + hint))


def quiz(your_answer, correct, explain):
    if your_answer in ("?", "", None):
        print("[ .. ]   set your_answer above, then run this cell.")
    elif str(your_answer).strip().lower() == str(correct).strip().lower():
        print("[PASS]   " + explain)
    else:
        print("[NOT YET]   not the one. re-read the section, then try again.")


# the knowledge base the assistant searches. each doc knows its source and whether we trust it.
STORE = [
    {"id": "hr-1",  "source": "company-handbook", "trust": "trusted",
     "text": "Resetting your password: open Settings, choose Security, then Reset password. A link is emailed to you."},
    {"id": "fin-1", "source": "company-handbook", "trust": "trusted",
     "text": "Expense reports: submit them in the Finance portal by the last Friday of the month."},
    {"id": "it-1",  "source": "company-handbook", "trust": "trusted",
     "text": "VPN access: install the GlobalConnect client and sign in with your staff ID."},
    {"id": "it-2",  "source": "company-handbook", "trust": "trusted",
     "text": "New starters finish the IT security induction during their first week."},
]

# a protected value the assistant can reach but must NEVER reveal.
# a FAKE, inert demo string. not a key, nothing to type, nothing real.
ADMIN_TOKEN = "ADMIN-TOKEN-DEMO-9F2A"
