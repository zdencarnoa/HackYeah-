# Step 3 explained: the attack engine

This explains the step 3 code (`events.py`, `engine.py`, `runtime.py`,
`router.py`, `dev_app.py`) in plain terms, function by function.

---

## 1. The big picture

In a real company, emails arrive through a mail server. We don't have one, so
the **attack engine pretends to be the mail server**. It reads the 33 demo
emails from `data/emails/` and "delivers" them one by one on a timeline, as
if they were arriving in real time.

When one email is delivered, five things happen:

```
   email from data/emails/
            │
            ▼
 1. remove the right answer   (the "scenario" field: phishing or not)
 2. make tracking links       (one /r/{token} link per person per URL)
 3. put it in the inboxes     (for every recipient)
 4. announce it               (an EMAIL_DELIVERED event on the event bus)
 5. hand it to ingestion      (C's code, which sends it to A and B for scoring)
```

Why each one matters:

1. **Remove the right answer.** Each email in our data says whether it is
   phishing. The detectors must never see that, or detection would be fake.
   The engine keeps the answer to itself.
2. **Tracking links.** Every link in an email is swapped for a link to our own
   server, like `http://localhost:8000/r/aB3xY9...`. When someone clicks it,
   we know who clicked which email, then send them on. Microsoft does the same
   thing in real life ("Safe Links").
3. **Inboxes.** The Employee Copilot UI shows each person their mail.
4. **Announce.** Other parts of the system, like the admin dashboard, react to
   events as they happen.
5. **Hand to ingestion.** Every email gets scored when it arrives, without
   waiting for the employee to report it. That's a core rule of the project.

---

## 2. Two kinds of time: real seconds and demo seconds

Every email has a `deliver_offset_s` value, for example
`"deliver_offset_s": 120`. That means "deliver this 120 seconds after
the demo starts".

All 33 emails together take 12 minutes (the last arrives at second 720), which is too long for a live
demo. So the engine has a **speed** setting:

| speed | 1 real second is | whole run takes | Alice's email arrives after |
|-------|------------------|-----------------|-----------------------------|
| 1     | 1 demo second    | 12 minutes      | 120 s                       |
| 10    | 10 demo seconds  | 72 seconds      | 12 s                        |
| 100   | 100 demo seconds | 7.2 seconds     | 1.2 s                       |

So there are two clocks:

- **Real seconds**: what your watch shows.
- **Demo seconds**: how far along the email timeline we are. Every email's
  `deliver_offset_s` is in demo seconds.

Formula: `demo seconds = real seconds × speed`.

### How the engine tracks demo time while you pause and resume

The engine never counts seconds one by one. It remembers two things:

- `_demo_seconds_banked`: demo time already finished in earlier runs (before a
  pause).
- `_run_started_at`: the real time the current run started, or `None` while
  paused.

The current demo time is then:

```
demo time = banked demo time + (real time now − run started at) × speed
```

Example at speed 10:

```
09:00:00  start          banked = 0     run_started_at = 09:00:00
09:00:05  (running)      demo time = 0 + 5 × 10 = 50
09:00:05  pause          banked = 50    run_started_at = None   (time frozen at 50)
09:03:00  (paused)       demo time = 50   (still 50, the 3 minutes don't count)
09:03:00  start again    banked = 50    run_started_at = 09:03:00
09:03:02  (running)      demo time = 50 + 2 × 10 = 70
```

"Banking" means: when you pause or change speed, the demo time so far is
saved into `_demo_seconds_banked` and the stopwatch restarts.

---

## 3. `events.py`: the event bus

An **event** is a record of "something happened": an email was delivered, a
link was clicked, and later a password was entered and so on. Each one is a
`SimEvent` (defined in `schemas.py`) with an id, a type, a time, optionally
an employee and a message, and some extra `data`.

The **event bus** is a noticeboard. Anyone can pin a notice (`publish`), and
anyone who signed up (`subscribe`) is told about every new notice.

### `utcnow()`
Returns the current time in UTC. It's the default clock.

### `EventBus.__init__(get_current_time=utcnow)`
Creates an empty bus:
- `self._subscribers`: the list of functions to call for each new event.
- `self.event_history`: every event ever published, oldest first.
- `self._get_current_time`: the clock used to timestamp events. Tests pass a
  fake clock here (see section 8).

### `subscribe(subscriber)`
Adds a function to the list. From then on, `subscriber(event)` is called for
every new event. It returns a function you can call to unsubscribe.

C will use this for live updates to the browser (SSE): they subscribe a small
function that puts each event into a queue, and their SSE endpoint reads from
that queue.

### `publish(event_type, employee_id=..., message_id=..., data=...)`
1. Builds a `SimEvent` with a random id and the current time.
2. Adds it to `event_history`.
3. Calls every subscriber with it. If one subscriber crashes, the error is
   logged and the others still get the event.
4. Returns the event.

### `clear_history()`
Empties `event_history`. The demo reset (step 8) will use it.

---

## 4. `engine.py`: the attack engine

### Module-level things

- `logger`: used to write messages to the server log.
- `PUBLIC_BASE_URL`: the start of every tracking link. It defaults to
  `http://localhost:8000` and can be changed with the environment variable
  `SIM_PUBLIC_BASE_URL` if the backend runs somewhere else during the demo.
- `DeliveryHook`: a type meaning "a function that takes a `DeliveredEmail`
  and returns nothing". That is the shape of C's ingestion function.
- `log_delivery(delivered_email)`: the default hook. It just writes "delivered
  leg-01 to 1 recipients" to the log. C replaces it with their real function.

### `AttackEngine.__init__(...)`

Parameters:

| parameter          | what it is                                    | default                  |
|--------------------|-----------------------------------------------|--------------------------|
| `event_bus`        | where to announce deliveries and clicks       | (required)               |
| `emails`           | which emails to deliver                       | all 33 from `data/`      |
| `organization`     | the fake company (employees, domain)          | from `data/org.json`     |
| `on_deliver`       | function called with each delivered email     | `log_delivery`           |
| `get_current_time` | the clock                                     | `utcnow` (the real time) |
| `public_base_url`  | start of tracking links                       | `PUBLIC_BASE_URL`        |

What it sets up:
- `_emails_in_delivery_order`: the emails sorted by `deliver_offset_s`.
- `_ground_truth_by_message_id`: the "right answer" for each email id. It is
  kept here so it never has to travel with the email.
- `_employee_id_by_address`: a lookup from `alice.johnson@...` to `e01`.
- `_delivery_loop_task`: the background task (see `_delivery_loop`), `None`
  when nothing is running.
- Then it calls `reset()` to set everything else to "nothing delivered yet".

### Timeline functions

#### `reset()`
Puts the engine back to before the first email:
- stops the background task
- `_next_email_index = 0`: the position in `_emails_in_delivery_order` of
  the next email to deliver. This number is also how many emails have been
  delivered so far.
- demo time back to 0, paused, speed 1
- empties the three stores:
  - `delivered_emails_by_id`: `"cmp-01"` → the `DeliveredEmail`
  - `inbox_message_ids_by_employee`: `"e01"` → `["leg-02", "cmp-01", ...]`
  - `tracked_links_by_token`: `"aB3xY9..."` → the `TrackedLink`

It doesn't clear the event bus; the full demo reset in step 8 will do that.

#### `is_running` (property)
`True` while the timeline is moving, meaning `_run_started_at` is set.

#### `is_finished` (property)
`True` once all emails have been delivered.

#### `demo_seconds_elapsed()`
Returns the current demo time using the formula from section 2. While paused
it simply returns `_demo_seconds_banked`.

#### `status()`
Returns an `AttackStatus` summary for the UI and the `/sim/attack/status`
endpoint, for example:

```json
{
  "running": true,
  "speed": 10.0,
  "demo_seconds_elapsed": 241.2,
  "delivered_count": 13,
  "total_count": 33,
  "next_message_id": "cmp-11",
  "next_delivery_at_seconds": 245
}
```

#### `start(speed=1.0)`
Starts or resumes the timeline.
1. Refuses a speed of 0 or less.
2. Does nothing if everything was already delivered.
3. Banks the demo time so far (in case it's already running and you're only
   changing the speed).
4. Saves the new speed and the start time.
5. (Re)starts the background delivery loop.

#### `pause()`
Banks the demo time, which freezes the timeline, and stops the background
loop. `start()` resumes from the same point.

#### `step()`
"Deliver the next email right now." This is the presenter's safety button:
on stage you don't have to wait for a timer. It jumps the timeline to the
next email's `deliver_offset_s`, so the later emails keep their spacing.

#### `jump_to_demo_second(target_demo_second)`
Moves the timeline forward to `target_demo_second` and delivers everything that
is now due.
- Only forward: jumping back in time is ignored.
- If the timeline is running, the stopwatch restarts from the new point and
  the background loop is restarted, so it doesn't keep sleeping on an old,
  now-wrong wait time.
- `step()` uses it, and so do the tests (`jump_to_demo_second(130)` = "what
  has arrived by second 130?").

#### `deliver_due_emails()`
Delivers, in order, every email whose `deliver_offset_s` is at or before
the current demo time, and returns the list of those just delivered. It
stops at the first email that isn't due yet. Because the list is sorted,
nothing after that one can be due either.

#### `_delivery_loop()` (the background task)
This is what makes delivery automatic while running:

```
repeat:
    deliver everything that is due
    if all emails are delivered: stop
    wait = (next email's demo second − current demo second) ÷ speed
    sleep for that many real seconds
when finished: freeze the timeline
```

It's an `async` function running as an **asyncio task**: a job that runs in
the background inside the FastAPI server, without blocking web requests.
`await asyncio.sleep(...)` lets the server handle requests while it waits.

#### `_stop_clock_and_bank_time()`
Saves the current demo time into `_demo_seconds_banked` and sets
`_run_started_at = None`. Used by pause, by start (before changing speed)
and when the loop finishes.

#### `_restart_delivery_loop()`
Stops the old background task (if any) and starts a fresh one.

#### `_stop_delivery_loop()`
Cancels the background task if it is still running.

### Delivery functions

#### `_expand_recipients(addresses)`
Turns email addresses into employee ids:
- `alice.johnson@lakeside-logistics.example` → `e01`
- `all@lakeside-logistics.example` → every employee (`e01` … `e24`)
- unknown addresses are skipped
- duplicates are removed, and the order is kept

#### `_deliver(sim_email)`
The core of the engine. For one email:
1. Works out the recipients with `_expand_recipients(to + cc)`.
2. For **each recipient** and **each URL** in the email, creates a
   `TrackedLink` with a random, unguessable `token` (from
   `secrets.token_urlsafe`). It remembers who it belongs to, which email, and
   the original URL, and stores it in `tracked_links_by_token`.
   An email with 1 link sent to `all@` (24 people) gets 24 tokens.
3. Adds the email id to each recipient's inbox.
4. Builds the `DeliveredEmail`. It copies every field **except** `scenario`
   (the right answer) and `deliver_offset_s`, and adds `delivered_at`,
   `recipient_ids` and `links`.
5. Saves it in `delivered_emails_by_id`.
6. Publishes an `EMAIL_DELIVERED` event.
7. Calls `on_deliver(delivered_email)`. This is C's ingestion. If it crashes,
   the error is logged and delivery carries on: a bug in scoring must not stop
   the demo.

Note: the `DeliveredEmail` keeps the **original** body and URLs. The
detectors need the real destination (`login.micr0soft-example.test`) to judge
it. The tracking links are only for what the employee sees.

### Inbox and click functions

#### `tracking_url(token)`
Builds the full link, e.g. `http://localhost:8000/r/aB3xY9...`.

#### `inbox(employee_id)`
Returns the employee's emails, newest first, as `InboxMessage`s. For each
email it:
1. Picks out only **this employee's** tracking links.
2. Replaces every original URL in the body with this employee's tracking URL.
   It replaces the longest URLs first, so if one URL is the start of
   another, the shorter one can't break the longer one.

That means Alice's copy and Carol's copy of the same campaign email have
different links in the text, so a click tells us exactly who clicked.

#### `record_click(token)`
Called when someone opens `/r/{token}`:
- Unknown token → returns `None` (the router then answers 404).
- Known token → publishes a `LINK_CLICKED` event with who clicked, which
  email, the original URL and its domain, then returns the `TrackedLink`.

#### `is_phishing(message_id)`
Looks up the right answer. Only the **simulation** uses it, to decide where a
clicked link leads (fake login page or harmless page). Detection never calls it.

---

## 5. `runtime.py`: the shared instances

Creates exactly one `event_bus` and one `engine` for the whole running app.
Everyone imports these same two objects:

```python
from app.simulation.runtime import engine, event_bus

engine.on_deliver = c_ingest_function          # C connects ingestion
event_bus.subscribe(c_sse_function)            # C connects live updates
```

---

## 6. `router.py`: the web endpoints

A FastAPI `APIRouter` is a group of URLs that the main app mounts. Each
function below answers one URL.

| method + URL                    | function            | what it does                                                        |
|---------------------------------|---------------------|---------------------------------------------------------------------|
| `POST /sim/attack/start?speed=10` | `start_attack`    | `engine.start(speed)`; speed must be > 0 and ≤ 1000; returns status |
| `POST /sim/attack/pause`        | `pause_attack`      | `engine.pause()`; returns status                                    |
| `POST /sim/attack/step`         | `step_attack`       | `engine.step()`; returns status                                     |
| `GET /sim/attack/status`        | `attack_status`     | returns status                                                      |
| `GET /sim/inbox/{employee_id}`  | `inbox`             | the employee's inbox; 404 if the employee doesn't exist             |
| `GET /r/{token}`                | `follow_link`       | records the click, then redirects (see below); 404 for a bad token  |
| `GET /sim/external?url=...`     | `external_site`     | harmless "you would now be at …" page                               |
| `GET /sim/landing/{token}`      | `phishing_landing`  | placeholder; step 4 replaces it with the fake login page            |

### Where a click leads (`follow_link`)

```
GET /r/{token}
   │
   ├─ unknown token ───────────► 404
   │
   ├─ email is phishing ───────► 302 redirect to /sim/landing/{token}
   │                             (step 4: the fake login page)
   │
   └─ email is legitimate ─────► 302 redirect to /sim/external?url=...
                                 (says where you'd be; opens nothing real)
```

A **302 redirect** is the server telling the browser "go to this other address
instead". The browser follows it automatically.

### `_page(title, body)`
A small helper that wraps text in a basic HTML page with a "SIMULATION" label
on top. Every value shown on the page passes through `escape(...)`, so text from
a URL can't inject HTML into the page.

---

## 7. `dev_app.py`: running it yourself

C will own the main FastAPI app. Until it exists, `dev_app.py` is a tiny app
that contains only our router, so you can try things out.

From `backend/`:

```
..\.venv\Scripts\python -m uvicorn app.simulation.dev_app:app --reload
```

Then open **http://localhost:8000/docs**. FastAPI generates a page where you
can press buttons to call each endpoint:

1. `POST /sim/attack/step` a few times (or `start` with speed 10)
2. `GET /sim/attack/status`: watch `delivered_count` go up
3. `GET /sim/inbox/e01`: Alice's inbox. Copy a link from `body_text`
   into a new browser tab to "click" it.

`--reload` restarts the server whenever you save a file.

---

## 8. Tests (`tests/test_engine.py`)

### The fake clock

Testing a 12-minute timeline by really waiting would be terrible. So the
engine never asks the computer for the time directly. It calls
`get_current_time()`, which the tests replace with a `FakeClock`:

```python
clock = FakeClock()          # starts at 2026-10-03 09:00
engine = AttackEngine(event_bus, get_current_time=clock)
engine.start(speed=10)
clock.advance(12)            # pretend 12 real seconds passed, instantly
engine.demo_seconds_elapsed()   # → 120
```

The idea of passing the clock in instead of hard-coding it is called
**dependency injection**.

### What each test checks

| test | checks that… |
|---|---|
| `test_delivers_only_what_is_due` | jumping to second 130 delivers exactly the emails due by 130 |
| `test_ground_truth_never_leaves_the_engine` | ingestion receives all 33 emails and none contains `scenario` |
| `test_all_company_mail_expands_to_every_employee` | `all@` mail reaches all 24 inboxes |
| `test_inbox_links_are_rewritten_per_recipient` | Alice's body shows her tracking link, not the original URL |
| `test_each_recipient_gets_their_own_token` | 24 recipients → 24 different tokens |
| `test_click_records_event_and_unknown_token_is_ignored` | a click creates a `LINK_CLICKED` event for Alice; a bad token gives `None` |
| `test_failing_ingestion_hook_does_not_stop_delivery` | a crashing ingestion function doesn't stop delivery |
| `test_step_delivers_next_message_and_moves_timeline` | step delivers one email and moves demo time to it |
| `test_reset_clears_deliveries` | reset empties inboxes, links and the counter |
| `test_running_timeline_uses_speed` | speed 10 × 12 s = 120 demo s; pausing freezes time |
| `test_full_run_finishes_with_real_clock` | with the real clock at speed 1000, all 33 arrive and it stops by itself |
| `test_http_flow` | the real endpoints: step, inbox, click → correct redirects, 404s |

Run them from `backend/`:

```
..\.venv\Scripts\python -m pytest -q                     # all tests
..\.venv\Scripts\python -m pytest -q tests/test_engine.py # only these
```

---

## 9. Glossary

- **token**: a random string that stands in for something else. Here it
  stands for "this link, in this email, for this person".
- **event bus**: a noticeboard where code posts events and other code
  listens.
- **hook / callback**: a function you hand to someone else's code so it can
  call you back (`on_deliver`).
- **asyncio task**: a background job inside the server that can wait without
  blocking anything else.
- **ground truth**: the known right answer (phishing or legitimate), used only
  to check the demo, never for detection.
- **SSE (Server-Sent Events)**: the way C will push events live to the
  browser.
- **dependency injection**: passing in things like the clock instead of
  hard-coding them, so tests can swap them out.
