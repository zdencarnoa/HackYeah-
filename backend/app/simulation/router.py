"""HTTP routes for the simulation: attack controls, inboxes and click tracking."""

from html import escape
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.schemas import AttackStatus, InboxMessage
from app.simulation.runtime import engine

router = APIRouter()


@router.post("/sim/attack/start", response_model=AttackStatus, tags=["simulation"])
async def start_attack(speed: float = Query(10.0, gt=0, le=1000)):
    engine.start(speed)
    return engine.status()


@router.post("/sim/attack/pause", response_model=AttackStatus, tags=["simulation"])
async def pause_attack():
    engine.pause()
    return engine.status()


@router.post("/sim/attack/step", response_model=AttackStatus, tags=["simulation"])
async def step_attack():
    engine.step()
    return engine.status()


@router.get("/sim/attack/status", response_model=AttackStatus, tags=["simulation"])
async def attack_status():
    return engine.status()


@router.get("/sim/inbox/{employee_id}", response_model=list[InboxMessage], tags=["simulation"])
async def inbox(employee_id: str):
    if employee_id not in engine.inbox_message_ids_by_employee:
        raise HTTPException(404, "unknown employee")
    return engine.inbox(employee_id)


@router.get("/r/{token}", tags=["simulation"])
async def follow_link(token: str):
    link = engine.record_click(token)
    if link is None:
        raise HTTPException(404, "unknown link")
    if engine.is_phishing(link.message_id):
        return RedirectResponse(f"/sim/landing/{token}", status_code=302)
    return RedirectResponse(f"/sim/external?url={quote(link.url, safe='')}", status_code=302)


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'><title>{escape(title)}</title></head>"
        f"<body style='font-family:sans-serif;max-width:40rem;margin:4rem auto;padding:0 1rem'>"
        f"<p><strong>SIMULATION</strong></p>{body}</body></html>"
    )


@router.get("/sim/external", response_class=HTMLResponse, include_in_schema=False)
async def external_site(url: str):
    return _page("Simulated external site",
                 f"<h1>Simulated external site</h1><p>In real life this link would open "
                 f"<code>{escape(url)}</code>. Nothing outside the demo was contacted.</p>")


@router.get("/sim/landing/{token}", response_class=HTMLResponse, include_in_schema=False)
async def phishing_landing(token: str):
    # Placeholder until step 4 adds the fake login page.
    link = engine.tracked_links_by_token.get(token)
    if link is None:
        raise HTTPException(404, "unknown link")
    return _page("Simulated phishing page",
                 f"<h1>Simulated phishing page</h1><p>This is where <code>{escape(link.url)}</code> "
                 f"would show a fake login form.</p>")
