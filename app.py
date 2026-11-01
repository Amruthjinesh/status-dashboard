import os
import time
import threading
import urllib.request
import urllib.error
import psycopg
from flask import Flask

DB_HOST = os.getenv("DB_HOST", "postgres")
TARGETS = os.getenv("TARGETS", "jenkins=http://172.31.43.232:8080/login")
INTERVAL = int(os.getenv("INTERVAL", "30"))

def targets():
    return [t.split("=", 1) for t in TARGETS.split(",") if "=" in t]

def connect():
    return psycopg.connect(host=DB_HOST, dbname="status_db", user="dash", password=os.environ["DB_PASSWORD"])

def check(url):
    try:
        urllib.request.urlopen(url, timeout=3)
        return "up"
    except urllib.error.HTTPError:
        return "up"
    except Exception:
        return "down"

def save(name, status):
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                id SERIAL PRIMARY KEY,
                name TEXT,
                status TEXT,
                checked_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        conn.execute("INSERT INTO checks (name, status) VALUES (%s, %s)", (name, status))

def monitor():
    while True:
        for name, url in targets():
            status = check(url)
            save(name, status)
            print(name + ":", status, flush=True)
        time.sleep(INTERVAL)

PAGE = """<!doctype html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>Server Status</title>
<style>
body{margin:0;background:#0f172a;color:#e2e8f0;font-family:system-ui,sans-serif}
.wrap{max-width:520px;margin:48px auto;padding:0 16px}
h1{font-size:22px;margin:0 0 20px;color:#94a3b8;font-weight:600}
.card{background:#1e293b;border-radius:14px;padding:22px;display:flex;align-items:center;gap:18px;margin-bottom:14px}
.dot{width:26px;height:26px;border-radius:50%}
.up{background:#22c55e;box-shadow:0 0 14px #22c55e}
.down{background:#ef4444;box-shadow:0 0 14px #ef4444}
.name{font-size:20px;font-weight:600;text-transform:capitalize}
.sub{font-size:13px;color:#94a3b8;margin-top:4px}
table{width:100%;border-collapse:collapse;background:#1e293b;border-radius:14px;overflow:hidden;margin-top:24px}
th,td{padding:10px 14px;text-align:left;font-size:14px}
th{color:#94a3b8;font-weight:500;border-bottom:1px solid #334155}
tr+tr td{border-top:1px solid #273449}
.pill{padding:2px 10px;border-radius:999px;font-size:12px;font-weight:600}
.pill.up{background:#14532d;color:#86efac;box-shadow:none}
.pill.down{background:#7f1d1d;color:#fca5a5;box-shadow:none}
</style></head><body><div class="wrap">
<h1>Server Status</h1>
%%CARDS%%
<table><tr><th>Server</th><th>Status</th><th>Time (UTC)</th></tr>%%ROWS%%</table>
</div></body></html>"""

app = Flask(__name__)

@app.route("/")
def home():
    with connect() as conn:
        latest = conn.execute(
            "SELECT DISTINCT ON (name) name, status, checked_at FROM checks ORDER BY name, id DESC"
        ).fetchall()
        rows = conn.execute(
            "SELECT name, status, checked_at FROM checks ORDER BY id DESC LIMIT 10"
        ).fetchall()
    cards = "".join(
        f'<div class="card"><div class="dot {s}"></div><div><div class="name">{n} is {s}</div><div class="sub">Last check {w:%H:%M:%S} UTC</div></div></div>'
        for n, s, w in latest
    ) or '<div class="card">No checks yet.</div>'
    body = "".join(
        f'<tr><td>{n}</td><td><span class="pill {s}">{s.upper()}</span></td><td>{w:%H:%M:%S}</td></tr>'
        for n, s, w in rows
    )
    return PAGE.replace("%%CARDS%%", cards).replace("%%ROWS%%", body)

if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    app.run(host="0.0.0.0", port=8000)
