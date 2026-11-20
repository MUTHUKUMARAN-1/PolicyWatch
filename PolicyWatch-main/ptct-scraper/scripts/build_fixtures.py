"""Generates the SYNTHETIC offline fixture pages (authorised sample pages for FR-06).

These are invented 'Acme' policy pages used for reproducible tests; they are not copies of any real site.
Run:  python scripts/build_fixtures.py
"""
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "fixtures"

PRIVACY = {
    "Information We Collect": "We collect account details you provide, such as your name and email address. We also collect device and usage data when you use the service.",
    "How We Use Information": "We use your information to provide and improve the service, to communicate with you, and to keep the service secure.",
    "Sharing": "We share information with service providers who help us operate the service. We do not sell your personal information.",
    "Data Retention": "We keep your information for 30 days after you close your account, unless the law requires us to keep it longer.",
    "Your Rights": "You may access, correct or delete your personal information by contacting our privacy team.",
}
TERMS = {
    "Acceptance of Terms": "By using the service you agree to these terms. If you do not agree, you must not use the service.",
    "Accounts": "You are responsible for keeping your password confidential and for all activity under your account.",
    "Acceptable Use": "You agree not to misuse the service, attempt unauthorised access, or interfere with other users.",
    "Termination": "We may suspend or end your access if you break these terms. You may close your account at any time.",
    "Liability": "The service is provided as is. To the extent allowed by law we are not liable for indirect losses.",
}


def layout_a(title, date, secs, banner=False, extra_wrap=False, ws=False, container_id="policy-content"):
    """Privacy-style layout: <main id=policy-content>."""
    body = []
    for h, t in secs.items():
        p = f"<p>{t}</p>"
        if extra_wrap:
            p = f'<div class="blk-x9"><span class="t">{t}</span></div>'
        body.append(f"<section><h2>{h}</h2>{p}</section>")
    sep = "\n\n      " if ws else ""
    banner_html = '<div class="cookie-banner">We use cookies. Accept?</div><nav>Home | Help | Contact</nav>' if banner else ""
    return f"""<!doctype html><html><head><title>{title} - Acme</title></head><body>
{banner_html}
<main id="{container_id}">
<h1>{title}</h1>
<p class="last-updated">Last updated: {date}</p>
{sep.join(body)}
</main><footer>(c) Acme Inc.</footer></body></html>"""


def layout_b(title, date, secs):
    """Terms-style layout: different markup (<article class=tos>, <h3> headings, <time>)."""
    body = "".join(f"<div class='clause'><h3>{h}</h3><div>{t}</div></div>" for h, t in secs.items())
    return f"""<!doctype html><html><head><title>{title}</title></head><body>
<header><h1 class="doc-title">{title}</h1><time class="eff">Effective {date}</time></header>
<article class="tos">{body}</article></body></html>"""


def w(name, html):
    (OUT / name).write_text(html, encoding="utf-8")


def edit(secs, **kw):
    d = dict(secs)
    for k, v in kw.items():
        d[k.replace("_", " ")] = v
    return d


def build():
    OUT.mkdir(exist_ok=True)
    P, D = PRIVACY, "January 1, 2026"
    # ---- change-case fixtures (privacy layout)
    w("privacy_v1.html", layout_a("Privacy Policy", D, P))
    w("privacy_whitespace_only.html", layout_a("Privacy Policy", D, P, ws=True))
    w("privacy_markup_only.html", layout_a("Privacy Policy", D, P, extra_wrap=True))
    w("privacy_cookie_banner.html", layout_a("Privacy Policy", D, P, banner=True))
    w("privacy_retention_edit.html", layout_a("Privacy Policy", D, edit(P, Data_Retention="We keep your information for 90 days after you close your account, unless the law requires us to keep it longer.")))
    p_added = dict(P); p_added["Children's Privacy"] = "Our service is not directed to children under 13 and we do not knowingly collect their data."
    w("privacy_section_added.html", layout_a("Privacy Policy", D, p_added))
    p_removed = {k: v for k, v in P.items() if k != "Sharing"}
    w("privacy_section_removed.html", layout_a("Privacy Policy", D, p_removed))
    w("privacy_date_only.html", layout_a("Privacy Policy", "March 15, 2026", P))
    w("privacy_title_changed.html", layout_a("Privacy Notice", D, P))
    p_multi = dict(edit(P, Sharing="We share information with service providers and advertising partners. We do not sell your personal information.")); p_multi["Cookies"] = "We use cookies to remember your preferences and measure usage."
    w("privacy_multi_change.html", layout_a("Privacy Policy", "April 2, 2026", p_multi))
    w("privacy_selector_changed.html", layout_a("Privacy Policy", D, P, container_id="content-v2"))
    w("privacy_empty.html", "<!doctype html><html><head><title>Privacy</title></head><body><main id='policy-content'></main></body></html>")
    p_renamed = {("What We Collect" if k == "Information We Collect" else k): v for k, v in P.items()}
    w("privacy_heading_renamed.html", layout_a("Privacy Policy", D, p_renamed))
    # curly-quote variant: typographic only
    base = layout_a("Privacy Policy", D, edit(P, Sharing="We share information with service providers who help us operate the service. We don't sell your personal information."))
    w("privacy_straight_quote.html", base)
    w("privacy_curly_quote.html", base.replace("don't", "don\u2019t"))
    # ---- terms layout (second source)
    T, TD = TERMS, "2026-01-01"
    w("terms_v1.html", layout_b("Terms of Service", TD, T))
    w("terms_v2.html", layout_b("Terms of Service", "2026-03-01", edit(T, Termination="We may suspend or end your access without notice if you break these terms. You may close your account at any time.")))
    w("terms_format_only.html", layout_b("Terms of Service", "2026-03-01", edit(T, Termination="We may suspend or end your access without notice if you break these terms.  You may close your account at any time.")).replace("<div class='clause'>", "<div class='clause' data-x='1'>"))
    # ---- demo scenario pages for privacy source
    w("demo_privacy_v1.html", layout_a("Privacy Policy", D, P))
    w("demo_privacy_v2.html", layout_a("Privacy Policy", "March 15, 2026", p_added_retention()))
    w("demo_privacy_v2_format.html", layout_a("Privacy Policy", "March 15, 2026", p_added_retention(), ws=True, extra_wrap=True))
    w("demo_privacy_selector_changed.html", layout_a("Privacy Policy", "March 15, 2026", p_added_retention(), container_id="content-v2"))


def p_added_retention():
    d = edit(PRIVACY, Data_Retention="We keep your information for 90 days after you close your account, unless the law requires us to keep it longer.")
    d["Children's Privacy"] = "Our service is not directed to children under 13 and we do not knowingly collect their data."
    return d


if __name__ == "__main__":
    build()
    print("fixtures written to", OUT)
