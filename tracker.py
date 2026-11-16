"""
CEP Haiti candidate tracker.

Checks the CEP candidate dashboard (https://tableau.cephaiti.ht) and sends
an alert when a candidate is added or removed in these lists:
  - President (national)
  - Senator, Sud-Est
  - Deputy, Jacmel (Sud-Est)
  - Mayor, Jacmel (Sud-Est)

Alerts go to a phone (ntfy app) and/or email, depending on which
settings are filled in. Uses only the Python standard library.

Settings (environment variables / GitHub secrets):
  NTFY_TOPIC      ntfy topic name for phone push alerts (optional)
  SMTP_USER       Gmail address that sends the email (optional)
  SMTP_PASSWORD   Gmail app password (optional)
  EMAIL_TO        where to send email; can be several, comma-separated.
                  A carrier SMS address (e.g. 5551234567@tmomail.net)
                  also works here to get a text message.
  WATCH           which lists to watch, comma-separated.
                  Default: president,senateur_se,depute_jacmel,maire_jacmel
                  Also available: depute_se (all Sud-Est deputies)
"""

import json
import os
import smtplib
import sys
import time
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path

API = os.environ.get("CEP_API", "https://tableau.cephaiti.ht/api/tableau/candidats")
STATE_FILE = Path(__file__).parent / "state" / "known.json"
USER_AGENT = "Mozilla/5.0 (CEP candidate tracker; personal use)"

LISTS = {
    "president":   {"label": "Président",          "params": {"poste": "Président"}},
    "senateur_se": {"label": "Sénateur (Sud-Est)", "params": {"poste": "Sénateur", "departement": "02"}},
    # Sud-Est = département 02. Jacmel = circonscription 044 (deputies), commune 01 (mayors).
    "depute_jacmel": {"label": "Député (Jacmel)",  "params": {"poste": "Député", "departement": "02", "circonscription": "044"}},
    "maire_jacmel":  {"label": "Maire (Jacmel)",   "params": {"poste": "Maire", "departement": "02", "commune": "01"}},
    "depute_se":   {"label": "Député (Sud-Est)",   "params": {"poste": "Député", "departement": "02"}},
}
DEFAULT_WATCH = "president,senateur_se,depute_jacmel,maire_jacmel"

# The 33 presidential candidates shown on 15/11/2026 at 8:22 PM (Haiti time).
# Used only on the very first run, so anyone added after that is reported.
BASELINE_PRESIDENT = {
    "ADRIEN|DANIEST", "BARRAU|LUCIEN OLIVIER", "BASTIEN|KELY C.", "BODEAU|GARY",
    "CELESTIN|JUDE", "DELILLE|LUCMANNE", "DERONNETH|DEUS", "DORFEUILLE|GANDHY",
    "DROUILLARD|MARC ARTHUR", "DUPUY|DOMINIQUE", "DUROCHER|MOISE", "ELIE|JUDE",
    "EMILE|ETZER S.", "GUE|JOANAS", "JEAN-PIERRE|RICARDO", "JEUDY|WILSON",
    "JOSEPH|CLAUDE", "JOSEPH|HANS JACQUES LUDWIG", "JOSEPH|MAXO", "JOSEPH|WILNER",
    "LUMARQUE|JACKY", "MARTELLY|JOSEPH MICHEL", "MOISE|MARIE ETIENNE MARTINE JOSEPH",
    "MOURRA|MUNIR JOSEPH", "MUSCADIN|JEAN ERNEST", "NESTOR|MICHELET",
    "PRIVERT|JOCELERME", "RENOIS|JEAN CLARENS", "SALOMON|JEAN-MARIE JUNIOR",
    "SANON|WALSONN", "SAVARY|MARIE ANNE SAVANNAH HADID", "ST FORT|RENÉ",
    "TARDIEU|PHILIPPE GERARD JERRY",
}
BASELINE_COUNTS = {"president": 33, "senateur_se": 43, "depute_se": 136}


# ---------- fetching ----------

def get_json(url, tries=3):
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    for attempt in range(1, tries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # network error, timeout, bad JSON
            if attempt == tries:
                raise
            print(f"  retry {attempt} after error: {exc}")
            time.sleep(5 * attempt)


def fetch_list(params):
    """Download every page of one list. The API returns 10 names per page."""
    items, page = [], 1
    while True:
        query = dict(params)
        if page > 1:
            query["page"] = page
        data = get_json(API + "?" + urllib.parse.urlencode(query))
        batch = data.get("items", [])
        items.extend(batch)
        if not batch or len(items) >= data.get("total", 0):
            return items, data.get("total", len(items))
        page += 1


def key(c):
    return f"{c.get('nom', '').strip()}|{c.get('prenom', '').strip()}"


def describe(c):
    place = " / ".join(x for x in c.get("localite", []) if x and x != "National")
    parts = [f"{c.get('prenom', '')} {c.get('nom', '')}".strip(), c.get("structure") or "?"]
    role = (c.get("position") or "").strip()
    if role and role != "Titulaire":  # mayors run as a team: Titulaire + 2 adjoints
        parts.append(role)
    if place:
        parts.append(place)
    return " - ".join(parts)


# ---------- alerts ----------

def send_ntfy(title, body, urgent):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    req = urllib.request.Request(
        f"{server}/{topic}",
        data=body.encode("utf-8"),
        headers={
            # Header values must be plain ASCII.
            "Title": title.encode("ascii", "ignore").decode(),
            "Priority": "high" if urgent else "default",
            "Tags": "rotating_light" if urgent else "ballot_box",
            "Click": "https://tableau.cephaiti.ht/",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    urllib.request.urlopen(req, timeout=30).read()
    print("  ntfy alert sent")


def send_email(title, body):
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    to = [x.strip() for x in os.environ.get("EMAIL_TO", "").split(",") if x.strip()]
    if not (user and password and to):
        return
    msg = MIMEText(body + "\n\nSource: https://tableau.cephaiti.ht/", "plain", "utf-8")
    msg["Subject"] = title
    msg["From"] = user
    msg["To"] = ", ".join(to)
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    with smtplib.SMTP_SSL(host, int(os.environ.get("SMTP_PORT", "465")), timeout=30) as s:
        s.login(user, password)
        s.sendmail(user, to, msg.as_string())
    print("  email sent")


def alert(title, body, urgent=False):
    print(f"\nALERT: {title}\n{body}\n")
    errors = []
    for fn, args in ((send_ntfy, (title, body, urgent)), (send_email, (title, body))):
        try:
            fn(*args)
        except Exception as exc:
            errors.append(f"{fn.__name__}: {exc}")
    if errors:
        print("Alert errors:", *errors, sep="\n  ")


# ---------- main ----------

def main():
    watch = [w.strip() for w in os.environ.get("WATCH") or DEFAULT_WATCH.split(",") if w.strip()]
    state = json.loads(STATE_FILE.read_text("utf-8")) if STATE_FILE.exists() else {}
    first_run = not state
    changed = False
    summary = []

    for name in watch:
        cfg = LISTS[name]
        print(f"Checking {cfg['label']} ...")
        items, total = fetch_list(cfg["params"])
        current = {key(c): describe(c) for c in items}
        roles = {"Titulaire": 0, "1er Adjoint": 1, "2ème Adjoint": 2}
        team_order = {key(c): (c.get("structure") or "", roles.get(c.get("position"), 3), key(c)) for c in items}
        ordered = lambda keys: sorted(keys, key=lambda k: team_order.get(k, ("", 9, k)))
        print(f"  {len(current)} candidates (site says {total})")

        if len(current) < total * 0.9:
            # Partial download: do not treat missing names as removed.
            print("  incomplete download, skipping this list for now")
            continue

        if name in state:
            known = state[name]
        elif name == "president":
            # First run: compare against the names seen on 15/11/2026.
            known = {k: "" for k in BASELINE_PRESIDENT}
        else:
            known = None  # nothing to compare yet

        line = f"{cfg['label']}: {len(current)}"
        if name in BASELINE_COUNTS:
            line += f" ({len(current) - BASELINE_COUNTS[name]:+d} since 15/11 8:22 PM)"
        summary.append(line)

        if known is None:
            print("  first look at this list, saved for next time")
            if not first_run:
                names = "\n".join(f"- {current[k]}" for k in ordered(current))
                alert(f"Now watching {cfg['label']}",
                      f"{len(current)} names on the site now:\n{names}\n\n"
                      "You will get an alert when a name is added or removed.")
        else:
            added = ordered(set(current) - set(known))
            removed = sorted(set(known) - set(current))
            if added:
                lines = "\n".join(f"+ {current[k]}" for k in added)
                alert(
                    f"NEW {cfg['label']} candidate ({len(added)})",
                    f"{lines}\n\nTotal now: {len(current)}",
                    urgent=(name == "president"),
                )
            if removed:
                lines = "\n".join(f"- {known[k] or k.replace('|', ', ')}" for k in removed)
                alert(
                    f"{cfg['label']}: {len(removed)} name(s) removed",
                    f"{lines}\n\nTotal now: {len(current)}",
                )
            if not added and not removed:
                print("  no change")

        if state.get(name) != current:
            state[name] = current
            changed = True

    for old in [k for k in state if k not in watch]:
        del state[old]  # stop keeping lists that are no longer watched
        changed = True

    if first_run:
        alert("CEP tracker is running",
              "Candidates now on the site:\n" + "\n".join(summary) +
              "\n\nYou will get an alert each time a name is added or removed.")
    if changed:
        STATE_FILE.parent.mkdir(exist_ok=True)
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=1, sort_keys=True), "utf-8")
        print("State file updated.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Check failed: {exc}")
        sys.exit(1)
