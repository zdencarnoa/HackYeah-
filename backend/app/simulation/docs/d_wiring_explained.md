# D wiring explained: connecting the simulation to the live backend

The attack engine, blast radius, containment and recovery already work on their
own (see `attack_engine_explained.md` and `demo_cycle_explained.md`). The D-wiring
tasks connect them to the other areas so the demo runs end to end against the live
backend instead of in isolation:

| Task | What it connects | Status |
|------|------------------|--------|
| D1 | delivery → scoring (A + B) → incidents/campaigns (C) | done |
| D2 | the fake login → C's password-reuse handler | done |
| D3 | one reset for the whole demo, D's state + C's database | done |
| D4 | "Contain campaign" → C's incident record | done |
| D5 | the simulation routes mounted on the live app | todo |

This file grows one section per task.

---

## D1 — Score every delivered email on arrival

**The goal.** A core rule of the project: detection must not depend on the
employee. The moment an email is delivered, it is scored, and campaigns and
incidents start forming — before anyone clicks anything. D1 is the glue that makes
that happen.

**The chain.** When the engine delivers an email it calls `on_deliver`. D1 points
that hook at a pipeline that runs three steps:

```
DeliveredEmail
     │
     ▼
1. message_from_sim(sim)      A: render the email to a Message and parse it,
     │                           exactly like an uploaded .eml
     ▼
2. detect(message) + fuse()   A's rules + B's fusion → a risk level
     │                           (LOW / MEDIUM / HIGH / CRITICAL)
     ▼
3. ingest_message(db, msg)    C: store the message, file "email_scored" evidence,
                                 and run campaign correlation
```

### The files

**`org_seed.py` — put D's company in C's database.**
C's `db/seed.py` ships a placeholder org and says in a comment that D's real org
replaces it. `seed_org(db)` loads the 24 employees from `data/org.json` into C's
`employees` table, so ingestion can find every demo recipient by id or email. This
is also what the demo reset re-seeds (D3).

**`pipeline.py` — the delivery glue.**
`DeliveryPipeline` is a callable used as `engine.on_deliver`:

- `score(delivered)` — looks up the original `SimEmail` (the engine now keeps
  `sim_email_by_id`), renders it to a `Message` with A's `message_from_sim`, runs
  A's `detect()` and B's `fuse()`, and returns just the risk level.
- `__call__(delivered)` — scores the email, builds a `MessageIn` carrying that
  risk, opens a database session and calls C's `ingest_message()`.

`attach(engine, session_factory, use_ml=False)` wires the pipeline onto the engine
and returns it.

**`engine.py` — one small addition.**
`sim_email_by_id` now maps each delivered message id back to its original
`SimEmail`, so the pipeline can render it. The email's ground truth is still never
read outside the engine.

### Two deliberate choices

**Scoring stops at the risk level; it does not call the LLM.** B's full `analyze()`
also writes a plain-language explanation through the LLM, which adds several
seconds per email while it reaches a model. On delivery we only need the risk to
store the message and file evidence. The full explanation — the reasons a person
reads — is produced on demand when the employee opens "Is this safe?" (B's
`/api/analyze`). So delivery scoring uses the fast `detect` + `fuse` path, and
scoring all 39 demo emails takes about two seconds.

**ML is off by default here.** `attach(..., use_ml=False)` scores with the
deterministic rules only. The rules already carry the demo: the Microsoft campaign
fires five indicators and fusion rates it HIGH with no model installed. Passing
`use_ml=True` adds B's classifier as one more signal when the weights are present.
(The ML score can never set HIGH on its own — fusion caps it.)

**One row per message.** C's message store keys on the message id with a single
recipient. Demo campaign emails go to one person each, so this is exact for them.
Company-wide (`all@`) mail is LOW risk and does not drive incidents, so the
pipeline attributes it to the first recipient and moves on.

### What correlation does with the scored messages

C's `correlate()` groups messages that score suspicious and share a sender
pattern, URL, similar wording and a close delivery time. Because the 14 Microsoft
emails all score HIGH and share those traits, they cluster into one campaign on
their own — that is the demo's "campaign discovery", driven by content, not by any
label from D's dataset.

### How it is wired into the running app

The pipeline is not attached by default, so the simulation's own unit tests stay
free of the database. The live app attaches it at startup with the real session
factory:

```python
from app.simulation import pipeline
from app.simulation.runtime import engine
from app.db.session import SessionLocal

pipeline.attach(engine, SessionLocal)   # now every delivery is scored and ingested
```

(That call belongs in app assembly, alongside mounting the routers — tasks C2/D5.)

### Tests (`tests/test_pipeline.py`)

An in-memory database, seeded with D's org, with the pipeline attached:

| test | checks that… |
|------|--------------|
| `test_delivered_campaign_email_is_scored_high` | Alice's `cmp-01` lands in the DB scored HIGH or above |
| `test_email_scored_evidence_is_filed_automatically` | one `email_scored` evidence item, tagged `automatic`, not reported |
| `test_campaign_correlates_from_scored_messages` | the scored campaign messages cluster into one campaign |
| `test_legitimate_mail_scores_low` | a normal supplier invoice scores LOW/MEDIUM |

---

## D2 — Turn a typed password into an incident

**The goal.** In the demo Alice types her password on the fake Microsoft page.
The admin should see a CRITICAL incident within seconds — before Alice reports
anything. D2 connects the fake login to C's incident system.

**The flow.**

```
Alice submits the fake login form
     │
     ▼
CredentialSimulator           domain is not on the approved list →
  fires a PASSWORD_REUSE        a Chrome-style event is produced
     │
     ▼
handle_password_reuse (C)     files "password_reuse" evidence →
     │                          opens a CRITICAL incident
     ▼
(a few seconds later)
unusual sign-in               filed as "unusual_signin" evidence,
                                added to the incident timeline
```

**What was wired (`pipeline.attach_credentials`).** One function sets two hooks on
the credential simulator:

- **Password reuse.** The simulator's event is wrapped in the same Pub/Sub shape
  C's HTTP endpoint expects and handed straight to C's `handle_password_reuse`.
  In-process, this is the exact function the endpoint calls; in production a real
  Chrome feed would POST it over the network.
- **Unusual sign-in.** The follow-up sign-in event is filed as `unusual_signin`
  evidence, so it lands on the same incident's timeline.

**One shared list made real.** C's code had a placeholder for the approved
sign-in domains. It now reads D's real list from `data/approved_logins.json`, so
a password on `login.lakeside-logistics.example` is safe and one on
`micr0soft-verify.example` is an alarm. Both the simulator and C check this, so
the "no false alarms" step holds on both sides.

**Why nothing leaks.** The password itself is never sent — the fake page submits
only a flag that a password was typed, and the event carries a label, not the
secret.

**Tests (`tests/test_credentials_bridge.py`).**

| test | checks that… |
|------|--------------|
| `test_password_on_phishing_page_opens_an_incident` | a phishing-page password files `password_reuse` evidence and opens a CRITICAL incident, tagged automatic |
| `test_follow_up_unusual_sign_in_joins_the_timeline` | the later sign-in is filed as `unusual_signin` evidence |
| `test_password_on_approved_domain_is_silent` | a password on the real sign-in page fires nothing |

---

## D3 — One reset for the whole demo

**The goal.** Between rehearsals, one call should put everything back to the start:
no delivered mail, no incidents, a clean slate — but with the company still in
place so the next run works.

**What it does (`pipeline.reset_all`).** One function, in order:

1. `reset_demo()` — clears D's in-memory state (engine, credentials, containment,
   recovery) and sends a `DEMO_RESET` event so the UI clears too.
2. `reset_db()` — drops and recreates C's tables (messages, incidents, evidence,
   campaigns).
3. `seed_org()` — re-seeds the 24 employees, so ingestion can find recipients again.

**Why `reset_demo()` stays DB-free.** `reset_demo()` resets only D's side and has
no database import, so the simulation keeps running on its own in the standalone
dev app and in unit tests. `reset_all()` is the demo-wide reset that also touches
C's database. The `POST /api/sim/reset` endpoint calls `reset_all` when a database
is configured (the live app) and falls back to `reset_demo` when there isn't one
(the dev app).

**Test (`tests/test_reset_all.py`).** Builds up both sides — delivered mail in the
engine, and a message, incident and evidence in the database — then calls
`reset_all` and checks everything is cleared while the 24-employee org is back.

---

## D4 — Link "Contain campaign" to the incident

**The goal.** When the admin approves "Contain campaign", D's simulation already
quarantines, blocks and notifies. The admin's incident should also show that it
has been dealt with, rather than staying open while the containment lives only in
the simulation's state.

**What was wired.** `ContainmentService` gained an `on_contained` hook, called
after any containment is applied. `pipeline.attach_containment` points it at C's
database: `mark_incidents_contained` finds the open incident(s) the containment
touched — by the campaign of the contained messages, or by the affected employees'
evidence — sets their status to `contained`, and publishes a `containment.done`
event so the admin dashboard updates live.

**Small shared-schema addition.** C's incident row always had a `status` column,
but the `Incident` contract didn't expose it. It now carries `status` (default
`"open"`), set from the row, so the UI can show "Contained". This is the only
change to the shared schema, and incidents are built in just one place
(`to_incident`), so nothing else is affected.

**Approval still required.** Nothing here weakens the rule that containment needs
an admin: `apply()` still refuses a non-admin before anything runs, and the hook
only fires after a successful, approved containment.

**Test (`tests/test_containment_incident.py`).** Runs the whole chain — deliver
and score (D1), a password on the phishing page opens a CRITICAL incident (D2),
then "Contain campaign" flips that incident to `contained`. A second test confirms
a non-admin is still refused.
