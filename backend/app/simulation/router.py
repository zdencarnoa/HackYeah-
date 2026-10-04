"""HTTP routes for the simulation.

Two routers:
- `router`: the demo web pages and click tracking, served at the app root
  (`/r/{token}`, `/sim/...`), because employees "visit" these URLs.
- `api_router`: the JSON API under `/api`, matching the team's Hour-0 contracts
  (attack control, inbox, blast radius, containment, recovery, reset).
"""

from urllib.parse import urlparse

from fastapi import APIRouter, Body, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.schemas import (
    AttackStatus,
    BlastRadius,
    ContainmentRequest,
    ContainmentResult,
    InboxMessage,
    RecoveryStatus,
)
from app.simulation import pages
from app.simulation.blast_radius import compute_blast_radius
from app.simulation.runtime import containment, credentials, engine, recovery, reset_demo

router = APIRouter()
api_router = APIRouter(prefix="/api", tags=["simulation"])

COMPANY_SIGN_IN_DOMAIN = f"login.{engine.organization.domain}"


# --- demo web pages (served at the root) ------------------------------------


@router.get("/r/{token}", include_in_schema=False)
async def follow_link(token: str):
    tracked_link = engine.record_click(token)
    if tracked_link is None:
        raise HTTPException(404, "unknown link")
    if containment.is_link_blocked(tracked_link):
        return pages.blocked_page()
    if engine.is_phishing(tracked_link.message_id):
        shown_domain = urlparse(tracked_link.url).hostname or ""
        return pages.phishing_login_page(token, shown_domain)
    return RedirectResponse(f"/sim/external?url={tracked_link.url}", status_code=302)


@router.post("/r/{token}/submit", include_in_schema=False)
async def submit_phishing_login(token: str, entered: str = Form("")):
    """The fake login form was submitted. Fire the password-reuse flow if a password was typed."""
    tracked_link = engine.tracked_links_by_token.get(token)
    if tracked_link is None:
        raise HTTPException(404, "unknown link")
    employee = {e.id: e for e in engine.organization.employees}[tracked_link.employee_id]
    event = None
    if entered == "1":
        event = credentials.record_password_entry(
            employee.id, page_url=tracked_link.url, message_id=tracked_link.message_id
        )
    return pages.phishing_result_page(employee.name, event_fired=event is not None)


@router.get("/sim/sign-in/company", include_in_schema=False)
async def company_sign_in():
    return pages.company_sign_in_page(COMPANY_SIGN_IN_DOMAIN)


@router.post("/sim/sign-in/company", include_in_schema=False)
async def company_sign_in_submit(entered: str = Form(""), domain: str = Form("")):
    # Approved domain: entering a password here is expected and fires no alert.
    return pages.external_site_page(f"https://{domain or COMPANY_SIGN_IN_DOMAIN}/")


@router.get("/sim/external", response_class=HTMLResponse, include_in_schema=False)
async def external_site(url: str):
    return pages.external_site_page(url)


# --- JSON API (under /api) --------------------------------------------------


@api_router.post("/sim/attack/{scenario}", response_model=AttackStatus)
async def start_attack(scenario: str, speed: float = Query(10.0, gt=0, le=1000)):
    try:
        engine.start(speed, scenario=scenario)
    except ValueError as error:
        raise HTTPException(404, str(error))
    return engine.status()


@api_router.post("/sim/attack/control/pause", response_model=AttackStatus)
async def pause_attack():
    engine.pause()
    return engine.status()


@api_router.post("/sim/attack/control/step", response_model=AttackStatus)
async def step_attack():
    engine.step()
    return engine.status()


@api_router.get("/sim/attack/status", response_model=AttackStatus)
async def attack_status():
    return engine.status()


@api_router.get("/sim/inbox/{employee_id}", response_model=list[InboxMessage])
async def inbox(employee_id: str):
    if employee_id not in engine.inbox_message_ids_by_employee:
        raise HTTPException(404, "unknown employee")
    return engine.inbox(employee_id)


@api_router.get("/blast-radius/{employee_id}", response_model=BlastRadius)
async def blast_radius(employee_id: str):
    try:
        return compute_blast_radius(engine.organization, employee_id)
    except KeyError:
        raise HTTPException(404, "unknown employee")


@api_router.post("/sim/containment", response_model=list[ContainmentResult])
async def apply_containment(request: ContainmentRequest = Body(...)):
    try:
        return containment.apply(request)
    except PermissionError as error:
        raise HTTPException(403, str(error))
    except ValueError as error:
        raise HTTPException(400, str(error))


@api_router.get("/sim/recovery", response_model=RecoveryStatus)
async def recovery_status():
    return recovery.status()


@api_router.post("/sim/recovery/{item_id}/done", response_model=RecoveryStatus)
async def mark_recovery_item_done(item_id: str):
    try:
        recovery.mark_done(item_id)
    except KeyError:
        raise HTTPException(404, "unknown checklist item")
    return recovery.status()


@api_router.post("/sim/reset", response_model=AttackStatus)
async def reset():
    # Reset the whole demo when a database is configured (the live app); fall back
    # to D's in-memory reset alone when it is not (the standalone dev app).
    from app.db import session as db_session

    if db_session.engine is not None and db_session.SessionLocal is not None:
        from app.simulation.pipeline import reset_all

        reset_all(db_session.SessionLocal)
    else:
        reset_demo()
    return engine.status()
