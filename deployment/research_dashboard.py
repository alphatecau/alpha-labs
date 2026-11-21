"""Server-rendered views for the read-only research account."""
from html import escape


CSS = b"""
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#0b0f10;color:#f1f4ea}
*{box-sizing:border-box}body{margin:0}main{max-width:66rem;margin:auto;padding:clamp(1rem,5vw,4rem)}
header{display:flex;flex-wrap:wrap;gap:1rem;align-items:center;justify-content:space-between}
header a,button{color:#c2f766}a{color:#c2f766}header a{font-weight:700;text-decoration:none}
button{background:transparent;border:1px solid #63784e;border-radius:.25rem;padding:.7rem 1rem;font:inherit}
h1{font-size:clamp(2rem,6vw,4rem);line-height:1.08;margin:2.5rem 0 1rem}p{color:#c0c9c2;line-height:1.55}
ul{padding:0;list-style:none}li{border-top:1px solid #334038;padding:1rem 0}
code,time,li strong{display:block;overflow-wrap:anywhere}time,code{margin-top:.4rem;color:#bcc7bf}
a:focus-visible,button:focus-visible{outline:2px solid #c2f766;outline-offset:3px}
"""


def _page(title, content, *, signed_in=False):
    action = ('<form method="post" action="/auth/logout"><button type="submit">Sign out</button></form>'
              if signed_in else '')
    return (f'<!doctype html><html lang="en-AU"><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{title} | Alpha Labs</title><link rel="stylesheet" href="/dashboard.css">'
            '<main><header><a href="https://alpha-labs-intelligence.alpha-tec-au86.chatgpt.site/">'
            f'ALPHA LABS</a>{action}</header><h1>{title}</h1>{content}</main></html>').encode()


def dashboard(runs):
    entries = ''.join(
        f'<li><strong>{escape(row["run_id"])}</strong><time>{escape(row["created_at"])}</time>'
        f'<code>SHA-256 {escape(row["evidence_sha256"])}</code></li>' for row in runs
    )
    records = f'<ul>{entries}</ul>' if entries else '<p>Your account has no recorded research runs.</p>'
    return _page('Research dashboard', '<h2>Your recent research runs</h2>' + records
                 + '<p>Up to 50 runs from your account. Live trading is disabled.</p>'
                 + '<a href="https://alpha-labs-intelligence.alpha-tec-au86.chatgpt.site/#findings">'
                   'View public historical results</a>', signed_in=True)


def signed_out():
    return _page('Signed out', '<p>Your Alpha Labs session has ended.</p><a href="/auth/login">Sign in</a>')


def access_message(heading, message):
    return _page(heading, f'<p>{message}</p><a href="/auth/login">Sign in</a>')
