# The demo cycle explained: from attack to recovery

This explains everything built on top of the attack engine: the fake login
pages, the password-reuse flow, the blast radius, containment and recovery, and
how they fit together into one demo cycle. It's a companion to
`attack_engine_explained.md` (read that one first — it covers how emails get
delivered).

Files covered here:

| File | What it does |
|------|--------------|
| `pages.py` | The HTML for the demo web pages (sign-in, fake login, blocked, external) |
| `credentials.py` | The password-reuse event and the follow-up unusual sign-in |
| `blast_radius.py` | What a compromised account could reach in the org graph |
| `containment.py` | The simulated containment actions (quarantine, block, notify, …) |
| `recovery.py` | The recovery progress bars and checklist |
| `runtime.py` | The one shared set of objects, and `reset_demo()` |
| `router.py` | All the web addresses that tie it together |

---

## 1. The whole cycle in one picture

```
  ATTACK            the engine delivers the campaign emails on a timeline
     │
     ▼
  CLICK             Alice opens /r/{token}; the click is recorded
     │
     ▼
  PASSWORD          she types a password on the fake login page
     │                → is the domain on the approved list?
     │                   yes → nothing happens (safe)
     │                   no  → PASSWORD_REUSE event fires
     ▼
  SIGN-IN           a few seconds later: a simulated unusual sign-in
     │
     ▼
  BLAST RADIUS      the admin sees what Alice's account could reach
     │
     ▼
  CONTAINMENT       the admin approves "Contain campaign":
     │                quarantine, block, notify, protect accounts, investigate
     ▼
  RECOVERY          progress bars fill; a short checklist remains
     │
     ▼
  RESET             one call puts everything back for the next rehearsal
```

Each stage is one module. They never call each other directly — they talk
through the **event bus** (from `events.py`) and through the shared objects in
`runtime.py`. That keeps them independent, so the rest of the team can plug
their code into the same bus.

---

## 2. The approved-logins idea (the heart of detection)

The key insight of the whole project: **you don't need the employee to tell you
they were phished.** You can tell from *where* they typed their password.

The company has a short list of domains where signing in is normal, in
`data/approved_logins.json` — things like `login.lakeside-logistics.example`.
That is the `ApprovedLogins` list.

- Password typed on a domain **in** the list → expected, no alarm.
- Password typed on a domain **not** in the list → almost certainly a phishing
  site, so fire an alert.

Real Chrome Enterprise does exactly this (it's called `PASSWORD_REUSE_EVENT`).
We simulate it with the same shape.

---

## 3. `pages.py`: the web pages

These are deliberately plain pages, each with a permanent "SIMULATION" banner.
They are **not** meant to look like real brands — the convincing look is the
frontend's job. What lives here is only the behaviour.

**Safety, built into the HTML itself:** the password box has no `name`
attribute, so the browser never sends its contents. The form only sends a
hidden flag, `entered=1`, meaning "a password was typed". The password itself
never leaves the browser.

### The functions

- `company_sign_in_page(domain)` — the *real*, approved sign-in page. Signing
  in here is safe and fires nothing.
- `phishing_login_page(token, shown_domain)` — the attacker's page. It names the
  suspicious domain and posts back to `/r/{token}/submit`.
- `phishing_result_page(employee_name, event_fired)` — shown after submit. If a
  password was entered it explains that an alert already went to the admin; if
  not, it just says it was a simulation.
- `blocked_page()` — shown when someone clicks a link that containment has
  blocked.
- `external_site_page(url)` — a harmless "this is where the link would go" page
  for legitimate links. Nothing outside the demo is ever contacted.

`_shell(...)` and `_login_form(...)` are small helpers that build the HTML so
the pages share one look.

---

## 4. `credentials.py`: the password-reuse flow

This is the stage that turns "Alice typed a password" into the alerts the admin
sees.

### `CredentialSimulator.record_password_entry(employee_id, page_url, message_id)`

The core function. Step by step:

1. Takes the domain out of `page_url`.
2. If the domain is on the approved list → returns `None`, nothing happens.
3. Otherwise it builds a `PasswordReuseEvent`. Note what it contains: the
   employee, the URL, the domain and *which account's* password was reused —
   but **never the password itself**.
4. Publishes a `PASSWORD_REUSE` event on the bus (this is what the admin
   dashboard reacts to).
5. Calls `on_password_reuse(event)` — the hook C will replace with their real
   endpoint. A crash there is logged, not fatal.
6. Schedules the follow-up unusual sign-in.

### `emit_unusual_sign_in(employee_id)`

A few seconds after the password, the attacker "uses" it: this publishes an
`UNUSUAL_SIGN_IN` event from a new location (a reserved documentation IP). It
shows the attack progressing, not just the mistake.

### `_schedule_unusual_sign_in(...)`

Waits `unusual_sign_in_delay_seconds` (default 4) then emits the sign-in. If no
server is running (like in a plain test) it fires immediately, so tests don't
have to wait.

### `to_pubsub_push(event)`

Wraps an event the way Google Pub/Sub would deliver it (base64 inside a
`message` envelope). This is so C's endpoint can accept the *same* shape whether
the event is simulated or, one day, real.

---

## 5. `blast_radius.py`: what the account could reach

### `compute_blast_radius(organization, employee_id)`

Answers one question: *if this account is taken over, what's exposed?*

It walks the org graph (from `data/org.json`):

```
employee → identity provider → the services they can sign in to → the data in those services
                                                                 → colleagues (via the mailbox)
```

How it decides what's "at risk":

1. The identity provider and every service in the employee's `access` list are
   reachable.
2. Any data set *stored in* a reachable service is also reachable. (Alice can
   open the Finance ERP, so the supplier bank details behind it are exposed.)
3. If the mailbox is reachable, so are colleagues — an attacker can send
   convincing internal phishing from Alice's address.

It returns a `BlastRadius`: a list of `nodes` and `edges` (shaped for the
frontend's graph view), the list of affected service ids, and a plain-language
`explanation`. Every node has a `reason` string, so the UI can show *why* each
thing is or isn't at risk.

The important honesty point, baked into the wording: this shows what the account
*can* access, **not** what was actually accessed.

The helpers `_node_kind`, `_reason` and `_join` just format the pieces.

---

## 6. `containment.py`: the admin's response

### The one rule: admin approval

`ContainmentService.apply(request)` refuses any request whose `approved_by`
isn't an admin (raises `PermissionError`, which the API turns into 403). The
system *recommends*; the admin *approves*. Nothing contains itself.

### Everything is simulated

No action touches a real mailbox or account. Each one flips an in-memory flag
(a set of ids), returns a `ContainmentResult` with `simulated: true`, and is
written to an audit log. The UI shows the "✓ SIMULATION" label from that flag.

### The individual actions (`_run`)

| Action | What it records |
|--------|-----------------|
| `QUARANTINE_MESSAGES` | message ids removed from inboxes |
| `BLOCK_SENDER` / `BLOCK_DOMAIN` | senders/domains blocked (also stops *future* deliveries) |
| `NOTIFY_USERS` | which employees were warned |
| `REVOKE_SESSIONS` / `RESET_CREDENTIALS` / `DISABLE_ACCOUNT` | account-protection steps for named employees |
| `START_INVESTIGATION` | opens the investigation, flags affected accounts |

### The one-click bundle (`_contain_campaign`)

This is the demo's "Contain campaign" button. It runs a sensible sequence in
order: quarantine → block sender → block domain → notify recipients → (if
affected accounts are named) revoke sessions + reset credentials → start
investigation. That one call produces the list of "✓ 14 quarantined, sender
blocked, 7 notified…" lines.

### The queries other parts use

- `is_message_contained(message_id)` — quarantined, or from a blocked
  sender/domain. The inbox uses this to hide contained mail.
- `is_link_blocked(tracked_link)` — the `/r/{token}` route uses this to show the
  "blocked" page instead of the phishing page once containment has run.
- `is_account_disabled(employee_id)` — self-explanatory.

The `_delivered_message_ids`, `_senders_of`, `_recipients_of`, `_known_employee_ids`
and `_names` helpers validate inputs and translate ids to names.

---

## 7. `recovery.py`: are we back to safe?

### `RecoveryTracker.status()`

Turns the containment state into four progress bars (`RecoveryTrack`):

- **Account protection** — of the affected accounts, how many had both sessions
  revoked and credentials reset.
- **Message containment** — how many of the campaign's messages are now
  contained.
- **Affected users notified** — how many recipients were warned.
- **Investigation** — how much of the whole checklist is done.

### The checklist (`checklist()`)

Two kinds of items:

- **Automatic** items tick themselves from the containment state (e.g.
  "Campaign messages quarantined" is done once anything is quarantined).
- **Manual** items the admin ticks off by hand with `mark_done(item_id)`
  ("Review account activity", "Confirm password reset", "Complete incident
  report").

`remaining_actions` is just the unticked items, for the "remaining" list in the
UI.

---

## 8. `runtime.py`: the shared objects and reset

Creates exactly one of each, wired together:

```python
event_bus   = EventBus()
engine      = AttackEngine(event_bus)
credentials = CredentialSimulator(event_bus, …)
containment = ContainmentService(engine, event_bus)
recovery    = RecoveryTracker(containment)
```

The whole team imports these same objects. C connects their code to the bus:

```python
engine.on_deliver = c_ingest            # score every delivered email
credentials.on_password_reuse = c_handle_reuse
event_bus.subscribe(c_push_to_browser)  # live updates (SSE)
```

### `reset_demo()`

Puts everything back to the start — nothing delivered, nothing contained, no
events — and publishes a `DEMO_RESET` event so C and the UI clear their own
state too. This is the "rehearse again" button.

---

## 9. `router.py`: the addresses that tie it together

Two groups of routes.

### The web pages (served at the root, because employees "visit" them)

| Address | What happens |
|---------|--------------|
| `GET /r/{token}` | records the click; shows the **blocked** page if contained, the **phishing** page if it's a phishing link, else redirects to the harmless external page |
| `POST /r/{token}/submit` | the fake login was submitted; if a password was entered, fires the password-reuse flow; shows the result page |
| `GET/POST /sim/sign-in/company` | the safe company sign-in page (fires nothing) |
| `GET /sim/external` | the harmless "this is where it would go" page |

### The JSON API (under `/api`, matching the team's contracts)

| Address | What it does |
|---------|--------------|
| `POST /api/sim/attack/{scenario}?speed=` | launch a scenario (e.g. `microsoft`) |
| `POST /api/sim/attack/control/pause` · `/step` | presenter controls |
| `GET /api/sim/attack/status` | how far the attack has got |
| `GET /api/sim/inbox/{employee_id}` | an employee's inbox |
| `GET /api/blast-radius/{employee_id}` | the blast radius graph |
| `POST /api/sim/containment` | apply an action or the campaign bundle |
| `GET /api/sim/recovery` · `POST /api/sim/recovery/{item}/done` | recovery status, tick an item |
| `POST /api/sim/reset` | reset the whole demo |

---

## 10. Following the demo yourself

From `backend/`:

```
..\.venv\Scripts\python -m uvicorn app.simulation.dev_app:app --reload
```

Then at **http://localhost:8000/docs**:

1. `POST /api/sim/reset`
2. `POST /api/sim/attack/microsoft` with `speed=1000`
3. `GET /api/sim/inbox/e01` → copy Alice's `cmp-01` link token
4. open `http://localhost:8000/r/{token}` in a browser tab → the phishing page
5. type anything in the password box, submit → the "simulated phishing" result
6. `GET /api/blast-radius/e01` → what Alice's account could reach
7. `POST /api/sim/containment` with the campaign body (admin `e15`)
8. `GET /api/sim/recovery` → the bars are full, three manual items remain

---

## 11. What's still connected to the others

Three things wait on the rest of the team (see the team doc):

- **Scan on delivery** needs A's and B's analyze endpoint — the hand-off point
  (`engine.on_deliver`) is ready and waiting.
- **Schema names** in `schemas.py` (`SimEmail`, `BlastRadius`,
  `ContainmentResult`) don't yet match the doc's names (`Message`, `OrgGraph`,
  `ContainmentAction`).
- **Link rewriting** lives in the engine here; the team doc assigns it to A.

None of these block the demo running on its own today.
