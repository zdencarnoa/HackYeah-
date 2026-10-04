"""Tasks 9 and 10: detection's HTTP routes.

`signals_router` has only POST /api/analyze/signals. `router` has that plus the
standalone /r/{token} and /demo placeholder. In the live app the simulation owns
/r/{token} (it serves the fake sign-in page and records clicks), so C mounts only:

    from app.detection.router import signals_router
    app.include_router(signals_router)

Mounting `router` as well would register /r/{token} twice.
"""

from html import escape

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from app.detection.engine import detect
from app.detection.ingest import parse_eml
from app.detection.rewrite import DEMO_TLDS, demo_target, follow
from app.schemas import SignalsResponse

signals_router = APIRouter()
link_router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font-family:system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem;line-height:1.5">
<h1 style="font-size:1.4rem">{title}</h1>{body}</body></html>"""

UNKNOWN_LINK_PAGE = PAGE.format(
    title="This link is not available",
    body="<p>Security Copilot does not know this link. It may be from before the demo was reset.</p>")

BLOCKED_PAGE = PAGE.format(
    title="Link blocked by Security Copilot",
    body="<p>This link leads to <strong>{domain}</strong>, which is outside the demo, "
         "so it was not opened. Your click was recorded.</p>")

PLACEHOLDER_PAGE = PAGE.format(
    title="SIMULATION: {host}",
    body="<p>This page stands in for <strong>{host}</strong>{path} in the demo. "
         "The simulated sign-in page will appear here.</p>"
         "<p>Nothing on this page is real, and nothing is sent anywhere.</p>")


@signals_router.post("/api/analyze/signals", response_model=SignalsResponse)
async def analyze_signals(file: UploadFile = File(...)) -> SignalsResponse:
    """An uploaded .eml, parsed, with its signals."""
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="This file is too large for an email (the limit is 10 MB).")
    try:
        message = parse_eml(raw)
    except ValueError as exc:  # parse_eml raises this for files that are not email
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result = detect(message)
    return SignalsResponse(message=message, signals=result.signals, unchecked=result.unchecked)


@link_router.get("/r/{token}")
def follow_link(token: str):
    """A click on a rewritten link: recorded first, then sent on to a demo page only."""
    record = follow(token)
    if record is None:
        return HTMLResponse(UNKNOWN_LINK_PAGE, status_code=404)
    target = demo_target(record)
    if target is None:  # safety net: never forward anyone to a real website
        return HTMLResponse(BLOCKED_PAGE.replace("{domain}", escape(record.domain or "an unknown address")))
    return RedirectResponse(target, status_code=302)


@link_router.get("/demo/{host}/{path:path}", response_class=HTMLResponse)
def demo_placeholder(host: str, path: str = ""):
    """Stands in for D's fake site until DEMO_SITE_URL points there."""
    if not host.endswith(DEMO_TLDS):
        raise HTTPException(status_code=404)
    return PLACEHOLDER_PAGE.replace("{host}", escape(host)).replace("{path}", escape("/" + path if path else ""))


router = APIRouter()
router.include_router(signals_router)
router.include_router(link_router)
