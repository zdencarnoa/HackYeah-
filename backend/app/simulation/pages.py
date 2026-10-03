"""HTML for the simulated web pages that drive the demo's behaviour:

- a stand-in company sign-in page (the safe, approved one)
- a stand-in phishing login page (the unapproved one the attack points to)
- a "blocked" page shown once containment blocks the link
- a harmless "external site" page for legitimate links

These are deliberately plain and are labelled a SIMULATION at all times. They
are not meant to look like any real brand: the convincing look-and-feel is the
frontend's job (it renders the demo inside the app, with its own framing). What
lives here is only the behaviour.

Safety: the password field has no `name`, the form submits only a flag saying a
password was typed, and nothing typed is stored or forwarded anywhere. A
password never leaves the browser.
"""

from html import escape

from fastapi.responses import HTMLResponse

_STYLE = """
body { margin: 0; font-family: system-ui, "Segoe UI", sans-serif; background: #f3f4f6; color: #111; }
.banner { background: #fff4ce; border-bottom: 3px solid #c19c00; padding: 10px 16px; font-size: 13px; text-align: center; }
.banner strong { letter-spacing: .5px; }
.card { background: #fff; max-width: 400px; margin: 40px auto; padding: 32px; border: 1px solid #e3e3e3; border-radius: 6px; }
h1 { font-size: 20px; margin: 0 0 4px; }
.sub { color: #666; font-size: 13px; margin: 0 0 20px; }
label { display: block; font-size: 13px; margin: 14px 0 4px; }
input { width: 100%; box-sizing: border-box; padding: 9px; border: 1px solid #aaa; border-radius: 4px; font-size: 15px; }
button { margin-top: 20px; width: 100%; background: #0067b8; color: #fff; border: 0; padding: 10px; font-size: 15px; border-radius: 4px; cursor: pointer; }
.safe { color: #107c10; } .danger { color: #a80000; }
.result { max-width: 460px; margin: 40px auto; background: #fff; border: 1px solid #e3e3e3; border-radius: 6px; padding: 32px; }
.result h1 { margin-bottom: 12px; } .result p { line-height: 1.5; }
"""

_SIMULATION_BANNER = (
    "<div class='banner'><strong>SIMULATION</strong> — training demo. "
    "Nothing you type here is stored, sent or used. Do not enter a real password.</div>"
)


def _shell(title: str, inner: str) -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body>{_SIMULATION_BANNER}{inner}</body></html>"
    )


def _login_form(title: str, subtitle: str, post_action: str, hidden_fields: dict[str, str]) -> str:
    hidden = "".join(
        f"<input type='hidden' name='{escape(k)}' value='{escape(v)}'>" for k, v in hidden_fields.items()
    )
    return (
        f"<form class='card' method='post' action='{escape(post_action)}'>"
        f"<h1>{escape(title)}</h1><p class='sub'>{escape(subtitle)}</p>"
        "<label>Email</label><input type='email' name='email' autocomplete='off'>"
        # No `name` on the password field: its value is never submitted.
        "<label>Password</label><input type='password' autocomplete='off' oninput=\"this.form.entered.value='1'\">"
        "<input type='hidden' name='entered' value=''>"
        f"{hidden}<button type='submit'>Sign in</button></form>"
    )


def company_sign_in_page(domain: str) -> HTMLResponse:
    """The real, approved company sign-in page. Signing in here fires no alert."""
    inner = (
        f"<p class='sub' style='text-align:center'>Approved sign-in page &mdash; <span class='safe'>{escape(domain)}</span></p>"
        + _login_form(
            "Lakeside Logistics",
            "Sign in to your company account",
            post_action="/sim/sign-in/company",
            hidden_fields={"domain": domain},
        )
    )
    return _shell("Sign in — Lakeside Logistics", inner)


def phishing_login_page(token: str, shown_domain: str) -> HTMLResponse:
    """The attacker's login page. Submitting it triggers the password-reuse flow."""
    inner = (
        f"<p class='sub' style='text-align:center'>This link goes to <span class='danger'>{escape(shown_domain)}</span>, "
        "which is not a company sign-in domain.</p>"
        + _login_form(
            "Account verification",
            "Sign in to verify your account",
            post_action=f"/r/{token}/submit",
            hidden_fields={},
        )
    )
    return _shell("Account verification", inner)


def phishing_result_page(employee_name: str, event_fired: bool) -> HTMLResponse:
    if event_fired:
        body = (
            "<p>This was a <strong>simulated phishing page</strong>. In a real attack, the password "
            f"{escape(employee_name)} just typed would now be in an attacker's hands.</p>"
            "<p>Because the domain was not on the approved sign-in list, the system raised a "
            "<strong>password-reuse alert</strong> and is already warning the security admin "
            "&mdash; before any report was filed.</p>"
            "<p>Nothing you typed was stored or sent. This is a training simulation.</p>"
        )
    else:
        body = (
            "<p>This was a <strong>simulated phishing page</strong>. No password was entered, so no alert was raised.</p>"
            "<p>Nothing you typed was stored or sent. This is a training simulation.</p>"
        )
    return _shell("Simulated phishing page", f"<div class='result'><h1>Simulated phishing page</h1>{body}</div>")


def blocked_page() -> HTMLResponse:
    body = (
        "<p>This link has been <strong>blocked</strong> by your security team as part of containing a "
        "phishing campaign.</p><p>If you think this is a mistake, contact IT. This is a training simulation.</p>"
    )
    return _shell("Link blocked", f"<div class='result'><h1 class='danger'>Link blocked</h1>{body}</div>")


def external_site_page(url: str) -> HTMLResponse:
    body = (
        f"<p>In a real session this link would open <code>{escape(url)}</code>.</p>"
        "<p>Nothing outside the demo was contacted. This is a training simulation.</p>"
    )
    return _shell("Simulated external site", f"<div class='result'><h1>Simulated external site</h1>{body}</div>")
