# Azhar Registration Watcher

An automated monitoring system that watches Al-Azhar University's postgraduate
admissions portal (PGS) for the moment registration opens, and sends an
instant WhatsApp alert — running fully autonomously in the cloud, with no
server or device required to stay online.

## Problem

Al-Azhar University's Master's/PhD registration portal opens on an
unannounced schedule. Manually refreshing the page for days at a time is
impractical, and missing the opening window can mean waiting an entire
academic cycle. This project removes the need for manual checking entirely.

## How It Works

1. **Scheduled trigger** — an external scheduler (cron-job.org) calls the
   GitHub Actions API every 10 minutes to dispatch a workflow run. This
   external trigger was added because GitHub's own cron scheduler is
   "best-effort" and can be delayed by hours during high-load periods —
   unsuitable for time-sensitive monitoring.
2. **Authenticated session** — a Python script (`azhar_watcher_lite.py`)
   authenticates against the portal's Odoo-based login endpoint
   (`/web/login`) using `requests.Session()`, replicating the exact
   form submission (including CSRF token extraction) a browser would send —
   without needing a full browser or Selenium.
3. **Status detection** — the script fetches the "New Request" form and
   inspects the `<select name="faculty_id">` element. An empty options list
   means registration is closed; populated options mean it has opened. This
   selector was identified by inspecting the live DOM via browser DevTools.
4. **Alerting** — on detecting an open registration window, the script
   sends a WhatsApp message via the Twilio API to one or more recipients,
   using an approved WhatsApp Content Template (required for reliable
   delivery on a Twilio trial account).
5. **Logging** — every run logs its outcome (login success, number of
   options found, alert sent/failed) to GitHub Actions' run history for
   auditability.

## Architecture

```
cron-job.org (external scheduler, 10-min interval)
        │  POST /workflows/check.yml/dispatches
        ▼
GitHub Actions (check.yml)
        │  runs on ubuntu-latest
        ▼
azhar_watcher_lite.py
        │  1. Authenticate (requests.Session, CSRF-aware)
        │  2. Fetch /my/requests/new
        │  3. Parse faculty_id <select> options
        ▼
Twilio WhatsApp API (Content Template)
        │
        ▼
   WhatsApp alert to recipient(s)
```

## Tech Stack

- **Python 3.11** — `requests`, `BeautifulSoup4`
- **GitHub Actions** — CI/CD-style scheduled execution, secrets management
- **cron-job.org** — external, reliable-interval scheduling via GitHub's
  REST API (`workflow_dispatch` events)
- **Twilio WhatsApp API** — Content Templates for trial-account-compliant
  messaging
- **GitHub Fine-Grained Personal Access Tokens** — scoped, repo-limited
  authentication for the external scheduler

## Security Design

- No credentials are stored in code. Email, password, and API credentials
  are injected at runtime via **GitHub Actions Secrets** (encrypted at rest,
  never exposed in logs).
- The GitHub Personal Access Token used by the external scheduler is
  **fine-grained**, scoped to this single repository, and limited to
  `Actions: Read and write` — no broader account access.
- The repository is private.

## Engineering Challenges Solved

- **Broken SSL certificate chain**: the target server's certificate chain
  is incomplete, which browsers silently tolerate but Python's `requests`
  correctly rejects. Diagnosed via `SSLCertVerificationError` and resolved
  with a documented, deliberate trade-off (`session.verify = False`) after
  confirming the risk was acceptable for this read-only, non-transactional
  use case.
- **Twilio trial account restrictions**: free-form WhatsApp messages are
  only deliverable within a 24-hour session window; outside that window,
  Twilio requires a pre-approved **Content Template**. Resolved by creating
  and referencing an approved template via `ContentSid` instead of a raw
  `Body` parameter.
- **Unreliable native cron scheduling**: GitHub Actions' built-in
  `schedule` trigger is explicitly documented as best-effort and can be
  delayed under load. Resolved by decoupling scheduling from execution —
  an external service (cron-job.org) triggers the workflow via the GitHub
  REST API on a guaranteed interval instead.

## Setup

1. Fork/clone this repository.
2. Add the following repository secrets (Settings → Secrets and
   variables → Actions):
   `AZHAR_EMAIL`, `AZHAR_PASSWORD`, `TWILIO_ACCOUNT_SID`,
   `TWILIO_AUTH_TOKEN`, `WHATSAPP_TO_1` (and optionally `WHATSAPP_TO_2`).
3. The workflow (`.github/workflows/check.yml`) is pre-configured to run
   `azhar_watcher_lite.py` on each scheduled/dispatched trigger.
4. (Optional but recommended) Register a free account on cron-job.org and
   configure it to send a `POST` request every 10 minutes to:
   `https://api.github.com/repos/<owner>/<repo>/actions/workflows/check.yml/dispatches`
   with an `Authorization: Bearer <token>` header, for reliable timing.

## Disclaimer

Built for personal, non-commercial use to monitor a single public
university admissions page the author is a registered user of. Not
intended for high-frequency scraping or any use that would burden the
target server.
