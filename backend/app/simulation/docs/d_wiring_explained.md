# D wiring explained: connecting the simulation to the live backend

The attack engine, blast radius, containment and recovery already work on their
own (see `attack_engine_explained.md` and `demo_cycle_explained.md`). The D-wiring
tasks connect them to the other areas so the demo runs end to end against the live
backend instead of in isolation:

| Task | What it connects | Status |
|------|------------------|--------|
| D1 | delivery → scoring (A + B) → incidents/campaigns (C) | done |
| D2 | the fake login → C's password-reuse endpoint | todo |
| D3 | one reset for the whole demo, D's state + C's database | todo |
| D4 | "Contain campaign" → C's incident record | todo |
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
