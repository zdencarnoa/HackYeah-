# Person A: detection engine, task guide

This guide explains every Person A task from `Noina radionica.md`: what it means, why it matters, how to build it, and when it counts as done.

## Your job in one paragraph

You are the first stage of the pipeline. A raw email comes in as an `.eml` file, either uploaded by an employee or delivered by D's simulated mailbox. You turn it into a structured `Message` and a list of `Signal`s. Each signal is one concrete, checkable fact ("the sender domain imitates microsoft.com"), written so a non-expert can understand it. You do **not** decide whether the email is phishing. B's risk fusion does that. You also own **link rewriting**, which is how the system finds out that someone clicked a link without anyone reporting it.

- Code: `backend/app/detection/`
- Branch: `detection`
- Tests: `backend/tests/detection/`

**Assumption: every email is an `.eml` file.** D stores the demo dataset as `.eml` files with full headers, and the employee's "Is this safe?" box accepts `.eml` uploads only. There is no pasted-text input.

## Where you fit

```
 .eml upload by an employee / .eml delivered by D's simulated mailbox
                 │
                 ▼
   ┌───────── A: detection ─────────┐
   │ parse        → Message         │
   │ checks       → Signal[]        │──► B: ML + risk fusion + LLM ──► Assessment ──► C, UI
   │ rewrite links→ /r/{token}      │
   └────────────────────────────────┘
                 │ employee clicks a rewritten link
                 ▼
   GET /r/{token} ──► Evidence(link_clicked) ──► C: incident escalates ──► admin UI (live, SSE)
                  └─► 302 redirect to the demo page (D's fake site)
```

Everything downstream depends on your output. If your signals are wrong, B's risk is wrong, C's incidents are wrong, and the UI shows wrong reasons.

## Rules you must never break

1. **Deterministic.** The same email always gives the same signals in the same order. No randomness and no LLM inside detection.
2. **Facts, not verdicts.** A signal says what you observed. Only B's fusion sets the risk level.
3. **Plain language.** The `evidence` text is shown to employees as-is. Jargon goes in `technical_detail`.
4. **Never execute anything.** Attachments are judged only by name, type and metadata.
5. **No live lookups.** No DNS, WHOIS, HTTP fetches or threat-intel APIs. The demo must work offline.
6. **Only redirect to `.example` / `.test`.** The click redirect must never send anyone to a real website.
7. **Announce `schemas.py` changes** to the whole team before merging. The UI mocks depend on them.

---

## Hour 0: what you need to agree with the team

These are the contracts you produce or consume. Get them settled in the first hour.

### Input format: `.eml` only

- **With D:** every demo email is stored as an `.eml` file with full headers: `From`, `To`, `Subject`, `Date`, `Message-ID` and `Authentication-Results`.
- **With the UI:** the "Is this safe?" box is an `.eml` upload, not a paste box.

The team plan still lists "pasted text" in your tasks and a "paste or upload box" in the UI tasks, so tell the team about this change.

### `Message` (you produce, everyone consumes)

`id, sender, display name, recipient, subject, body (text/html), urls[], attachments[] (name, mime), headers, received_at`

Suggestions to raise:

- **`urls[]` should hold objects, not plain strings**: `{url, anchor_text, found_in: "text" | "html"}`. The URL checks need the anchor text, because "the link shows X but goes to Y" is one of your strongest signals.
- **`headers` should allow repeated keys.** Headers such as `Received` and `Authentication-Results` can appear more than once. Use a list of `(name, value)` pairs or a `dict[str, list[str]]`.
- **`attachments[]` may need one extra field**, such as `encrypted: bool`. Checking whether a zip is password-protected needs the file bytes, which are only available while parsing.
- **`id`**: use a stable value, such as a hash of the `Message-ID` header plus the recipient, so scanning the same email twice does not create a duplicate.

### `Signal` (you and B produce, B consumes)

`id, category, severity (0–3), evidence (plain language), technical detail, source (rule / url / ml / intel)`

Agree on these points:

- **A fixed list of categories** (see the signal catalog below). B's hard floors depend on the names. Example: `credential_request` + `lookalike_domain` → at least HIGH.
- **What each severity means:**

  | Severity | Meaning | Example |
  | --- | --- | --- |
  | 0 | Context only, never alarming by itself | "The email contains a link" |
  | 1 | Weak, common in legitimate mail too | URL shortener, a login path in a link |
  | 2 | Moderate | Reply-To goes to a different domain |
  | 3 | Strong, rarely seen in legitimate mail | Lookalike domain, `invoice.pdf.exe` |

- **Your sources** are `rule` (headers, sender, content, attachments), `url` (link checks) and `intel` (blocklist). `ml` belongs to B.
- **How to report checks you could not run.** For example, an `.eml` without an `Authentication-Results` header means SPF, DKIM and DMARC cannot be checked. That is *not* a signal, but B must list it in `uncertainties[]`. The simplest approach is for `detect()` to return `signals` plus an `unchecked: list[str]` such as `["email authentication results missing"]`.

### Python functions B and D will import

Agree on the signatures and give B a stub right away, so they never wait on you:

```python
parse_eml(raw: bytes) -> Message
detect(message: Message) -> DetectionResult      # signals + unchecked
rewrite_links(message: Message, employee_id: str) -> Message
```

B's `/api/analyze` should call `detect()` directly as a Python import, not over HTTP.

### `Evidence` of kind `link_clicked` (you produce, C consumes)

`kind="link_clicked", employee_id, message_id, domain, source="automatic", timestamp`

Ask C for the intake function you will call, for example `record_evidence(evidence)`.

---

## Suggested code layout

Make every check a small **pure function** `check_x(message) -> list[Signal]`. Each one is then easy to test on its own, and a new rule never touches the others.

```
backend/app/detection/
  __init__.py       # exports parse_eml, detect, rewrite_links
  ingest.py         # task 1
  headers.py        # task 2
  sender.py         # task 3
  domains.py        # task 4: registrable domain, homoglyphs, lookalikes
  urls.py           # task 5
  content.py        # task 6
  attachments.py    # task 7
  intel.py          # task 8
  rewrite.py        # task 9: link rewriting + /r/{token}
  router.py         # task 10: FastAPI routes
  data/
    brands.json  freemail.json  shorteners.json  keywords.json  blocklist.json
```

```python
CHECKS = [header_checks, sender_checks, domain_checks, url_checks,
          content_checks, attachment_checks, intel_checks]

def detect(message: Message) -> DetectionResult:
    signals, unchecked = [], []
    for check in CHECKS:
        try:
            signals += check(message)
        except Exception:                      # one broken rule must never break the demo
            log.exception("check %s failed", check.__name__)
            unchecked.append(check.__name__)
    signals = dedupe(signals)                  # one signal per (category, rule)
    signals.sort(key=lambda s: (-s.severity, s.category))   # stable, deterministic order
    return DetectionResult(signals=signals, unchecked=unchecked)
```

Libraries: `fastapi`, `python-multipart` (needed for file uploads), `beautifulsoup4`, `rapidfuzz` (edit distance, optional) and `pytest`. Everything else is in the Python standard library.

---

## Task 1: Ingestion

> Parse `.eml` files into `Message`. Extract URLs from both the text and the HTML, and record anchor text beside each `href`.

**What it means.** An `.eml` file is a raw email: headers, then a body that may contain several parts (plain text, HTML, attachments) and may be encoded (base64, quoted-printable). You turn it into a clean `Message` object that every other check reads.

**How to build it.**

```python
from email import message_from_bytes, policy
from email.utils import parseaddr, parsedate_to_datetime

def parse_eml(raw: bytes) -> Message:
    msg = message_from_bytes(raw, policy=policy.default)   # policy.default decodes for you
    display_name, sender = parseaddr(str(msg.get("From", "")))
    text_part = msg.get_body(preferencelist=("plain",))
    html_part = msg.get_body(preferencelist=("html",))
    text = text_part.get_content() if text_part else ""
    html = html_part.get_content() if html_part else ""
    attachments = [{"name": p.get_filename(), "mime": p.get_content_type()}
                   for p in msg.iter_attachments()]
    headers = [(k, str(v)) for k, v in msg.items()]
    ...
```

URLs from the HTML, keeping the anchor text:

```python
from bs4 import BeautifulSoup

def links_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    return [{"url": a["href"], "anchor_text": a.get_text(" ", strip=True), "found_in": "html"}
            for a in soup.find_all("a", href=True)]
```

URLs from the plain text: use a regex such as `(?:https?://|www\.)[^\s<>"')\]]+`, then strip trailing `.,;:!?` characters.

**Incomplete `.eml` files.** A valid `.eml` can still lack pieces: no HTML part, no `Date`, no `Authentication-Results`, no attachments. Fill in what you can, leave the rest empty, and report missing authentication results as unchecked. The `email` package accepts almost any bytes without complaint, so `parse_eml` must raise a `ValueError` itself when the file is clearly not an email (no `From` header and no body).

**Pitfalls**

- Skip or separate `mailto:` and `tel:` links, because they are not web links.
- Deduplicate URLs, since the same link often appears in both the text part and the HTML part.
- `received_at`: use `parsedate_to_datetime(msg["Date"])` and fall back to now if it is missing or broken.
- Bad charsets: wrap content decoding in `try` so one strange email cannot crash the scan.

**Done when** every demo `.eml` parses without errors, and the Microsoft email's link appears with its anchor text. Also try one `.eml` saved from Gmail or Outlook, because real exports are messier than synthetic ones. Use it only for local testing and don't commit it.

---

## Task 2: Header checks

> Read SPF, DKIM and DMARC from `Authentication-Results`, and spot Reply-To or Return-Path values that differ from From.

**What it means.**

- **SPF**: is the sending server allowed to send mail for this domain?
- **DKIM**: does the email carry a valid digital signature from the domain?
- **DMARC**: does the domain in the visible `From` pass SPF or DKIM, according to the domain's own policy? A DMARC `fail` is the strongest of the three.

The receiving mail server writes these results into a header like this:

```
Authentication-Results: mx.company.example; spf=fail smtp.mailfrom=micr0soft-verify.example;
    dkim=none; dmarc=fail header.from=micr0soft-verify.example
```

You only **read** this header. You never do the DNS checks yourself.

```python
import re
AUTH_RE = re.compile(r"\b(spf|dkim|dmarc)=(\w+)", re.I)

def read_auth_results(values: list[str]) -> dict[str, str]:
    results = {}
    for value in values:                       # every Authentication-Results header
        for mech, result in AUTH_RE.findall(value):
            results.setdefault(mech.lower(), result.lower())
    return results                             # {"spf": "fail", "dkim": "none", "dmarc": "fail"}
```

**Mismatches**

- **Reply-To** on a different registrable domain than `From`: replies go to someone else, a classic fraud trick. Severity 2.
- **Return-Path** on a different domain: weaker (severity 1), because legitimate mailing services such as newsletters use their own bounce domains.

"Registrable domain" means the part you actually buy: `login.company.example` → `company.example`. Write a small helper rather than using `tldextract`, which downloads data on first use and does not understand `.example`:

```python
MULTI_PART_SUFFIXES = {"co.uk", "com.pl", "org.pl", "net.pl", "com.au"}

def registrable(host: str) -> str:
    labels = host.lower().rstrip(".").split(".")
    if len(labels) >= 3 and ".".join(labels[-2:]) in MULTI_PART_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])
```

You will use this helper in tasks 3, 4, 5 and 8.

**Pitfalls**

- A missing header is **not** evidence. Report it as unchecked so B can list it as an uncertainty.
- The demo emails are synthetic, so ask D to include an `Authentication-Results` header in every `.eml`: `fail`/`none` for attacks, `pass` for legitimate mail.

---

## Task 3: Sender checks

> Display name claims a brand while the domain does not match it; free-mail sender claiming to be a company.

**Brand impersonation** (one of the five demo-critical indicators). The email *says* it is Microsoft but does not *come from* Microsoft. Keep a brand list in `data/brands.json`:

```json
[
  {"key": "microsoft", "name": "Microsoft",
   "keywords": ["microsoft", "office 365", "outlook", "onedrive", "teams"],
   "domains": ["microsoft.com", "office.com", "outlook.com", "live.com"]},
  {"key": "company", "name": "our company",
   "keywords": ["company it", "it helpdesk"],
   "domains": ["company.example"]}
]
```

Also add Google, a bank and a courier. Listing real legitimate domains here is fine, because you never contact them.

The rule:

- If the display name contains a brand keyword and the sender's registrable domain is not in that brand's `domains`, emit `brand_impersonation` (severity 3).
- As a second rule, for emails whose display name is neutral (such as "Account Team"): if the subject or body names a brand and the links go to a domain outside that brand's list, emit `brand_impersonation` (severity 2).

**Free-mail pretending to be a company.** The sender domain is in a free-mail list (`gmail.com`, `outlook.com`, `yahoo.com`, `wp.pl`, `onet.pl`, `o2.pl`, `interia.pl`), but the display name or signature claims a company role or name ("CEO", "Finance Department", "Company IT"). This is typical CEO fraud. Severity 2.

**Evidence examples**

- "The sender calls itself 'Microsoft Security', but the email comes from micr0soft-verify.example, which is not a Microsoft address."
- "The sender says they are our CFO but writes from a personal Gmail address."

---

## Task 4: Lookalike domains

> Compare against a brand list using homoglyph normalization (0→o, rn→m) and edit distance.

**What it means.** Attackers register domains that look like a real brand at a glance: `micr0soft` (digit zero), `rnicrosoft` ("rn" looks like "m"), `microsfot` (swapped letters), or Cyrillic letters that look identical to Latin ones. Homoglyphs are characters that look alike. Edit distance is how many single-letter changes turn one word into another.

**How to build it.**

```python
HOMOGLYPHS = {"0": "o", "1": "l", "3": "e", "5": "s", "@": "a",
              "а": "a", "е": "e", "о": "o", "р": "p", "с": "c"}   # last five are Cyrillic
MULTI = {"rn": "m", "vv": "w", "cl": "d"}

def normalize(label: str) -> str:
    label = label.lower()
    for fake, real in MULTI.items():
        label = label.replace(fake, real)
    return "".join(HOMOGLYPHS.get(ch, ch) for ch in label)

def find_lookalike(host: str, brands) -> Brand | None:
    reg = registrable(host)                          # "micr0soft-verify.example"
    if any(reg in b.domains for b in brands):        # the real domain is never a lookalike
        return None
    label = reg.split(".")[0]                        # "micr0soft-verify"
    for token in [label, *label.split("-")]:         # also check "micr0soft" and "verify"
        norm = normalize(token)
        for brand in brands:
            key = normalize(brand.key)               # normalize both sides the same way
            if norm == key or (len(key) >= 5 and levenshtein(norm, key) <= 1):
                return brand
    return None
```

`levenshtein` can come from `rapidfuzz.distance.Levenshtein.distance` or a 15-line function. The edit distance also catches cases the map misses, such as `m1crosoft`.

**Punycode.** International domains are encoded as `xn--…`. Decode them before comparing: `label.encode("ascii").decode("idna")`, wrapped in `try`. A Cyrillic "microsoft" then normalizes to the Latin one.

**Where to run it**

- On the **sender domain** → `lookalike_domain` (severity 3). This is a demo-critical indicator.
- On **every link host** → `suspicious_url` (severity 3), with evidence such as "The link leads to micr0soft-verify.example, an imitation of microsoft.com." This makes the suspicious-URL indicator fire reliably.

**Good evidence names the trick:** "micr0soft-verify.example imitates microsoft.com: the letter 'o' was replaced by the digit '0'." Record which substitution matched, so you can write this sentence.

**Pitfalls**

- Never flag the real domain or its subdomains (`login.company.example`, `account.microsoft.com`).
- Short brand keys such as `dhl` should only match exactly after normalization. Edit distance on 3-letter words produces false alarms.
- Include your own organization (`company`) so `c0mpany.example` is caught.

---

## Task 5: URL checks

> Link text shows one domain but the link goes to another; IP-literal hosts; URL shorteners; deep subdomains; punycode; login-page path keywords.

Use `urllib.parse.urlsplit(url).hostname`. It lowercases the host and strips the port and any `user@` part. All of these rules use the category `suspicious_url` and differ only in the rule name in `technical_detail`.

| Rule | What to detect | Severity | Evidence example |
| --- | --- | --- | --- |
| Text/link mismatch | The anchor text contains a domain, and its registrable domain differs from the real link's. "Click here" is not a mismatch | 3 | "The link shows account.microsoft.com but actually leads to micr0soft-verify.example." |
| Lookalike host | Task 4 on the link host | 3 | "The link leads to micr0soft-verify.example, an imitation of microsoft.com." |
| IP-literal host | `ipaddress.ip_address(host)` succeeds | 2 | "The link goes to a bare number address (192.0.2.10) instead of a named website." |
| Brand in subdomain | A brand's domain appears in the subdomain while the registrable domain is something else: `microsoft.com.account-check.example` | 2 | "The address starts with 'microsoft.com', but the real website is account-check.example." |
| Deep subdomain | Five or more labels in the host | 1 | "The web address is unusually long and nested, which can hide the real site." |
| Punycode | A label starts with `xn--` (show the decoded version) | 2 | "The web address uses characters from another alphabet that look like normal letters." |
| `@` in URL | `https://microsoft.com@evil.example`: the browser ignores everything before the `@` | 3 | "The link looks like microsoft.com but really goes to evil.example." |
| URL shortener | Host is in `shorteners.json` (`bit.ly`, `tinyurl.com`, `t.co`, `is.gd`, `ow.ly`, `cutt.ly`, …). Never expand it, since that would be a live lookup | 1 | "The link uses a shortening service, which hides where it really goes." |
| Login path | Path contains `login`, `signin`, `verify`, `account`, `password`, `secure`, `update` | 1 | "The link leads to a sign-in page." |

**Pitfalls**

- Compare **registrable** domains, so `www.microsoft.com` vs `microsoft.com` is not a mismatch.
- Weak rules (shortener, login path) are common in legitimate mail. Keep them at severity 1 and let B's fusion combine them.
- Run the URL checks on the **original** URLs, never on rewritten `/r/{token}` links (see task 9).

---

## Task 6: Content rules

> Urgency or threat wording, credential requests, payment or IBAN changes, gift cards, MFA-code requests.

**What it means.** These are keyword and regex rules on the subject plus the body text. For HTML, take the visible text with `BeautifulSoup(html, "html.parser").get_text(" ")`. Keep the phrase lists in `data/keywords.json`, so you can extend them without touching code.

| Category | Example phrases | Suggested severity |
| --- | --- | --- |
| `urgency` | "urgent", "immediately", "within 24 hours", "will be suspended", "final notice", "legal action", "unusual activity" | 2 |
| `credential_request` | "verify your account", "confirm your password", "sign in to keep", "update your credentials", "re-enter your login" | 2 |
| `payment_change` | "new bank details", "updated IBAN", "changed our account", "do not use the old account". Also regex for an IBAN: `\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b` | 3 |
| `gift_card` | "gift card", "Google Play card", "Apple card", "Amazon voucher", "scratch off the code" | 3 |
| `mfa_code_request` | "send me the code", "verification code you received", "6-digit code", "read me the code" | 3 |

These severities are suggestions. Agree on them with B, who owns the final weighting.

**Quote the actual sentence.** It is the most convincing evidence for a non-expert:

> The email pushes you to act fast: "Your account will be suspended within 24 hours."

Find the sentence that contains the match and trim it to about 120 characters.

**Pitfalls**

- **One signal per category**, not one per match. Five urgent words are still one urgency signal.
- `payment_change` must mean a *change* of bank details, not any payment. A legitimate invoice says "please pay by Friday" and must not trigger it.
- **Prompt-injection safety.** Your quotes travel into B's LLM. Keep each quote short (one sentence, at most 120 characters) and never copy whole paragraphs into evidence. Otherwise an attacker could hide "ignore your instructions…" in the body and it would reach the LLM through your evidence.
- Polish phrases are a later add-on (shared with B). Keep the keyword file structured so adding a `"pl"` list is easy.

---

## Task 7: Attachment rules

> Risky extensions, double extensions, macro Office files, password-protected archives. Static metadata only, never execute anything.

| Rule | What to detect | Severity |
| --- | --- | --- |
| Risky extension | `.exe .scr .js .vbs .bat .cmd .ps1 .hta .iso .img .lnk .jar .msi .wsf .com` | 3 |
| Double extension | A document extension followed by a risky one: `invoice.pdf.exe`, including tricks with many spaces (`invoice.pdf      .exe`) or the right-to-left override character `U+202E` | 3 |
| Macro Office file | `.docm .xlsm .pptm .xlam`, and old `.doc` / `.xls`, which can also hold macros | 2 |
| Password-protected archive | A zip whose entries have the encryption flag: `any(i.flag_bits & 0x1 for i in zipfile.ZipFile(io.BytesIO(data)).infolist())`. For `.7z` / `.rar`, or any archive plus a password in the body ("password: 1234") | 2 |
| Type mismatch (optional) | The name says `.pdf`, but the MIME type says a program (`application/x-msdownload`) | 3 |

**Evidence examples**

- "'invoice.pdf.exe' pretends to be a PDF but is actually a program. Opening it would run it."
- "The attachment is a password-protected archive, a common way to hide malware from scanners."

**Pitfalls**

- The zip check needs the bytes, so do it during parsing (task 1) and store the result, for example `encrypted: true` on the attachment.
- Never write attachments to disk, open them in Office, or unpack them. Reading the zip's table of contents in memory is enough.

---

## Task 8: Offline threat indicators

> A local blocklist JSON. No live lookups of demo domains.

**What it means.** A small file of "known bad" things, loaded once at startup:

```json
{
  "updated": "2026-10-03",
  "note": "Demo snapshot. Offline only.",
  "domains": ["invoice-portal-pay.test"],
  "urls": [],
  "senders": [],
  "ips": ["192.0.2.66"]
}
```

Match the sender domain, the link hosts (by registrable domain), the full URLs and the IPs. A match emits `known_bad` with source `intel`, severity 3: "micr0soft-verify.example is on our list of known phishing sites."

**Recommendation:** keep the **Microsoft attacker domain out of the blocklist**. The demo is far stronger when the five indicators fire on a domain the system has never seen ("we caught it with no prior knowledge"). Use the blocklist for the invoice-fraud domain or something in the background.

**Why no live lookups.** `.example` and `.test` domains never resolve anyway, and any network call makes the demo fragile. Things you cannot know offline, such as domain age, are uncertainties for B, never signals.

The CERT Polska warning list is a later add-on: download it once as a snapshot into the same format.

---

## Task 9: Link rewriting

> On delivery, replace each URL with `/r/{token}`. The redirect records a `link_clicked` evidence item, then forwards to the original page (only `.example` / `.test` demo pages).

**What it means.** This is how "Alice clicked the link" is detected automatically (demo step 3). Real products such as Microsoft Safe Links work the same way.

**Rewriting (called by D's mailbox on delivery)**

1. For every URL in the delivered copy, create a token with `secrets.token_urlsafe(16)`.
2. Store `token → {original_url, domain, message_id, employee_id}`. Use **one token per recipient**, so a click tells you *who* clicked.
3. In the HTML, replace only the `href` values (parse with BeautifulSoup, change `a["href"]`). Do not do a blind text replace. Keep the visible anchor text. In the plain text part, replace the URLs.
4. The new link is `{BASE_URL}/r/{token}`, where `BASE_URL` is the backend address from settings (for example `http://localhost:8000`).

**The redirect endpoint**

```python
@router.get("/r/{token}")
def follow_link(token: str):
    link = link_store.get(token)
    if link is None:
        raise HTTPException(status_code=404)
    record_evidence(Evidence(kind="link_clicked", employee_id=link.employee_id,
                             message_id=link.message_id, domain=link.domain,
                             source="automatic", timestamp=utcnow()))   # C's intake
    if not link.domain.endswith((".example", ".test")):
        return HTMLResponse(BLOCKED_PAGE)        # safety net: never forward to a real site
    return RedirectResponse(link.original_url, status_code=302)
```

**Things to settle with others**

- **Order of operations with D.** Analysis must see the **original** URLs. Run `detect()` / B's `/api/analyze` on the original message, then rewrite the copy that is shown in the inbox. If you analyze the rewritten copy, every link looks like `localhost/r/…` and your URL checks find nothing.
- **Where tokens are stored, with C.** A `link_tokens` table in C's database is best, so tokens survive a backend restart mid-demo. An in-memory dict is fine for early checkpoints. D's `/api/sim/reset` must clear the tokens too.
- **How a browser opens `micr0soft-verify.example`, with D and UI.** `.example` domains do not resolve in DNS, so "forward to the original page" needs either hosts-file entries (`127.0.0.1 micr0soft-verify.example`, `127.0.0.1 login.company.example`) or a mapping from demo domain to a local route. Decide this early, because it changes your redirect target.
- **Speed.** The click must reach C immediately, so the admin sees "Possible exposure: Alice" live. Record the evidence before redirecting, not in a background job that might lag.

---

## Task 10: API endpoint and tests

> `POST /api/analyze/signals` and a pytest suite over the demo dataset.

**Endpoint.** Accept an `.eml` upload and return the parsed message plus the signals.

```python
@router.post("/api/analyze/signals")
async def analyze_signals(file: UploadFile = File(...)) -> SignalsResponse:
    try:
        message = parse_eml(await file.read())
    except ValueError as exc:                  # parse_eml raises this for non-email files
        raise HTTPException(status_code=422, detail=str(exc))
    result = detect(message)
    return SignalsResponse(message=message, signals=result.signals, unchecked=result.unchecked)
```

This endpoint is mostly for debugging and for the UI's "Advanced details". The main path is B's `/api/analyze`, which imports `detect()` directly.

**Tests.** These protect the demo. Adjust the paths to D's dataset layout.

```python
from pathlib import Path
import pytest
from app.detection import parse_eml, detect

DEMO = Path(__file__).parents[3] / "data" / "demo"
MICROSOFT = sorted((DEMO / "microsoft").glob("*.eml"))
LEGIT = sorted((DEMO / "legit").glob("*.eml"))
FIVE = {"lookalike_domain", "urgency", "credential_request",
        "suspicious_url", "brand_impersonation"}

def test_dataset_is_present():                 # an empty glob would silently skip everything
    assert len(MICROSOFT) == 14 and LEGIT

@pytest.mark.parametrize("path", MICROSOFT, ids=lambda p: p.name)
def test_microsoft_variant_fires_all_five(path):
    signals = detect(parse_eml(path.read_bytes())).signals
    assert FIVE <= {s.category for s in signals}

@pytest.mark.parametrize("path", LEGIT, ids=lambda p: p.name)
def test_legit_email_has_no_strong_signal(path):
    signals = detect(parse_eml(path.read_bytes())).signals
    assert all(s.severity < 2 for s in signals), [s.evidence for s in signals]
```

Also add:

- **Unit tests per check**: `micr0soft` and `rnicrosoft` are caught, `microsoft.com` and `login.company.example` are not, `xn--` hosts decode, `invoice.pdf.exe` is caught and `report.pdf` is not.
- **Invoice-fraud emails** fire `payment_change`.
- **The ambiguous email** fires only weak signals (severity 1), so B can land on MEDIUM.
- **Link rewriting round trip**: rewrite → follow `/r/{token}` → one `link_clicked` evidence item and a 302 to the original URL. A non-demo domain gets the blocked page.
- **Determinism**: running `detect()` twice on the same email gives identical output.
- **Speed**: the whole detection should take well under 100 ms per email.

Run them with `pytest backend/tests/detection -q`.

---

## Demo-critical output: the five indicators on the Microsoft email

All five must fire on **all 14 variants**, every time.

| Indicator | Category | Produced by | What in the email triggers it |
| --- | --- | --- | --- |
| Lookalike domain | `lookalike_domain` | Task 4 on the sender | `security@micr0soft-verify.example`: digit 0 instead of the letter o |
| Urgency | `urgency` | Task 6 | "URGENT: Your account will be suspended" |
| Credential request | `credential_request` | Task 6 | "Verify your account / confirm your password" |
| Suspicious URL | `suspicious_url` | Tasks 5 and 4 on the link host | The link goes to `micr0soft-verify.example/login`, often behind text showing a Microsoft address |
| Brand impersonation | `brand_impersonation` | Task 3 | Display name "Microsoft Security" or Microsoft branding from a non-Microsoft domain |

How to make it reliable:

- **None of the five depend on authentication headers or the blocklist.** They come from the sender, subject, body and links, so they still fire on an `.eml` without an `Authentication-Results` header.
- **D writes the 14 variants.** Get them early and run the parametrized test after every change. When D adds new wording, either the variant still fires all five or you extend the keyword lists.
- The Microsoft email will probably produce **more than five** signals (DMARC fail, login path, …). That is fine. Agree with B and the UI whether the risk card shows the top five by severity and puts the rest under "Advanced details".

---

## How to write good evidence text

The UI shows your `evidence` text to employees, and B's LLM and template fallback build the explanation from it. Better evidence directly makes a better demo.

- One sentence, about 25 words at most.
- Name the concrete thing: the domain, the phrase, the file name.
- Say why it is risky, in everyday words.
- No jargon. "SPF", "homoglyph", "punycode" and "Levenshtein" go in `technical_detail`.

| Bad | Good |
| --- | --- |
| `href/anchor registrable domain mismatch` | The link shows account.microsoft.com but actually leads to micr0soft-verify.example. |
| `DMARC=fail` | The sending domain's own security check failed, so this email may not come from who it claims. |
| `double extension detected` | 'invoice.pdf.exe' pretends to be a PDF but is actually a program. |

---

## Suggested order of work, by checkpoint

| Checkpoint | What you deliver |
| --- | --- |
| **Hour 0** | `.eml` agreed as the only input format. Contracts agreed: `Message`, `Signal`, the category list, severity meanings, how unchecked items are reported, function signatures |
| **1. Contracts frozen** | A `detect()` stub that returns the five hard-coded signals for any email containing `micr0soft`, so B and the UI can start. Endpoint skeleton. A first Microsoft `.eml` drafted with D |
| **2. Thin vertical slice** *(your most important gate)* | Real ingestion plus the checks behind the five indicators: tasks 1, 3, 4, 5 and the urgency/credential rules from task 6. The parametrized Microsoft test passes |
| **3. Incident loop** | Link rewriting and `/r/{token}` sending `link_clicked` to C (needed for demo step 3) |
| **4. Organization view** | The remaining rules: headers (task 2), payment/gift-card/MFA (task 6), attachments (task 7), blocklist (task 8). Invoice-fraud and ambiguous emails behave as expected |
| **5. Full demo path** | Tests pass over the whole dataset. No false alarms on legitimate emails. Feature freeze |
| **6. Hardening** | Every check wrapped so one failure cannot break the demo. Rehearse. Help others |

Add-ons for you after checkpoint 6: Polish-language phishing rules (with B), the CERT Polska warning-list snapshot, and attachment static analysis with `oletools` (macro detection, still never executing anything).

---

## Who you depend on, and who depends on you

| Person | You need from them | They need from you |
| --- | --- | --- |
| **B** | Agreement on categories, severities and the unchecked format | `detect()` early (a stub at checkpoint 1), stable categories, short evidence quotes |
| **C** | `record_evidence()` and a `link_tokens` table | `link_clicked` evidence the moment a link is clicked |
| **D** | Demo `.eml` files with `Authentication-Results` headers, the delivery call order, the plan for opening `.example` pages | `rewrite_links()`, and URL checks that run on original links |
| **UI (Claude)** | An `.eml` upload box instead of a paste box | Plain-language `evidence` for the risk card, `technical_detail` for "Advanced details" |

---

## Definition of done (your checklist from the plan)

- [ ] Ingestion: `.eml` → `Message`, URLs from text and HTML with anchor text
- [ ] Header checks: SPF, DKIM, DMARC, Reply-To and Return-Path mismatches
- [ ] Sender checks: brand display name on the wrong domain, free-mail claiming a company role
- [ ] Lookalike domains: homoglyph normalization + edit distance, on the sender and on link hosts
- [ ] URL checks: text/link mismatch, IP host, shortener, deep or brand subdomain, punycode, `@` trick, login path
- [ ] Content rules: urgency, credential request, payment/IBAN change, gift card, MFA code
- [ ] Attachment rules: risky and double extensions, macro files, encrypted archives, never executed
- [ ] Offline blocklist JSON, with no network calls anywhere in detection
- [ ] Link rewriting + `/r/{token}` → `link_clicked` evidence → redirect to `.example` / `.test` only
- [ ] `POST /api/analyze/signals` + a pytest suite over the demo dataset
- [ ] **All five indicators fire on all 14 Microsoft variants, and legitimate emails have no strong signals**
