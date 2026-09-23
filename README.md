# Azhar Registration Watcher

An autonomous monitoring system that watches Al-Azhar University's
postgraduate admissions portal (PGS) for the exact moment registration
opens, and fires an instant WhatsApp alert — running entirely in the cloud,
with no server, browser, or personal device required to stay online.

---

## Overview

This project started as a manual "keep refreshing the page" problem and
evolved into a fully unattended, cloud-native monitoring pipeline with
authenticated scraping, external reliable scheduling, and templated
WhatsApp alerting.

| | |
|---|---|
| **Language** | Python |
| **Execution** | GitHub Actions (scheduled/dispatched workflow) |
| **External Scheduler** | cron-job.org |
| **Messaging** | Twilio WhatsApp API |
| **HTTP/Parsing** | `requests`, `BeautifulSoup4` |
| **Hosting** | GitHub (private repository) |

---

## Core Features

### 1. Authenticated, Browser-Free Scraping
- Logs into the portal's Odoo-based authentication endpoint (`/web/login`)
  using `requests.Session()` — extracting and submitting the CSRF token
  exactly as a real browser would, with no headless browser or Selenium
  dependency
- Fetches the "New Request" form and parses the `<select name="faculty_id">`
  element to detect registration status: an empty options list means
  closed, populated options mean the window has opened
- The exact target selector was reverse-engineered by inspecting the live
  DOM via browser DevTools, since the portal blocks automated crawling
  (`robots.txt`) and offers no public API

### 2. Reliable External Scheduling
- GitHub Actions' native `schedule` trigger is documented as best-effort
  and can silently delay runs by hours under platform load — unacceptable
  for a time-sensitive alert
- Decoupled scheduling from execution: **cron-job.org** calls the GitHub
  REST API (`workflow_dispatch`) every 10 minutes on a guaranteed interval,
  authenticated with a fine-grained, repository-scoped Personal Access
  Token

### 3. Trial-Account-Compliant WhatsApp Alerting
- Sends alerts via the **Twilio WhatsApp API**
- Free-form message bodies are only deliverable within a 24-hour session
  window on a Twilio trial account; outside that window Twilio silently
  rejects them. Resolved by creating and referencing a pre-approved
  **Content Template** (`ContentSid`) instead of a raw `Body` parameter,
  making delivery reliable regardless of session state
- Supports multiple recipients via independent secret-stored numbers

### 4. Security Hardening
- No credentials are ever committed to the codebase — email, password, and
  API credentials are injected at runtime via **GitHub Actions Secrets**
  (encrypted at rest, redacted from logs)
- The scheduler's GitHub token is **fine-grained**: scoped to this single
  repository only, with `Actions: Read and write` and nothing broader
- Repository is private; a deliberate, documented SSL-verification
  trade-off (see below) was made only after confirming the read-only,
  non-transactional nature of the request justified it

### 5. Full Run Logging
- Every execution logs its outcome — login success/failure, number of
  faculty options found, alert sent/failed with the raw provider response —
  to GitHub Actions' run history for auditability and debugging

---

## Architecture

```
cron-job.org (external scheduler, 10-min interval)
        │  POST /workflows/check.yml/dispatches
        ▼
GitHub Actions (check.yml)
        │  runs on ubuntu-latest
        ▼
azhar_watcher_lite.py
        │  1. Authenticate  (requests.Session, CSRF-aware)
        │  2. Fetch /my/requests/new
        │  3. Parse faculty_id <select> options
        ▼
Twilio WhatsApp API (approved Content Template)
        │
        ▼
   WhatsApp alert → recipient(s)
```

---

## Tech Stack

- **Python 3.11** — `requests`, `BeautifulSoup4`
- **GitHub Actions** — scheduled/dispatched execution, encrypted secrets management
- **cron-job.org** — guaranteed-interval scheduling via GitHub's REST API
- **Twilio WhatsApp API** — Content Templates for trial-account-compliant messaging
- **GitHub Fine-Grained Personal Access Tokens** — scoped, single-repo authentication

---

## Engineering Challenges Solved

1. **Broken SSL certificate chain** — the target server's certificate
   chain is incomplete; browsers tolerate this silently, but Python's
   `requests` correctly raises `SSLCertVerificationError`. Diagnosed the
   root cause and applied a deliberate, documented trade-off
   (`session.verify = False`) after confirming it was acceptable for this
   specific read-only, non-financial use case.
2. **Twilio trial session-window restriction** — diagnosed a silent
   delivery failure to a generic `"Invalid or disallowed parameters"`
   error, traced it to trial-account template requirements, and resolved
   it by building and wiring in an approved WhatsApp Content Template.
3. **Unreliable native cron scheduling** — identified that GitHub's
   built-in scheduler could not guarantee timing under load, and
   re-architected the trigger path to use an external scheduler calling
   GitHub's dispatch API directly, decoupling "when it runs" from "where
   it runs."

---

## Files

| File | Purpose |
|---|---|
| `azhar_watcher_lite.py` | Main script — authentication, status detection, WhatsApp alerting, logging |
| `requirements.txt` | Python dependencies |
| `.github/workflows/check.yml` | GitHub Actions workflow definition (scheduled + externally dispatched) |

---

## Setup

1. Clone this repository.
2. Add the following repository secrets (**Settings → Secrets and
   variables → Actions**):
   `AZHAR_EMAIL`, `AZHAR_PASSWORD`, `TWILIO_ACCOUNT_SID`,
   `TWILIO_AUTH_TOKEN`, `WHATSAPP_TO_1` (optionally `WHATSAPP_TO_2`).
3. The workflow is pre-configured to run `azhar_watcher_lite.py` on every
   scheduled/dispatched trigger.
4. *(Recommended)* Register a free account on cron-job.org and configure
   it to `POST` every 10 minutes to:
   `https://api.github.com/repos/<owner>/<repo>/actions/workflows/check.yml/dispatches`
   with header `Authorization: Bearer <fine-grained-token>`.

---

## Notes

Built for personal, non-commercial use to monitor a single public
university admissions page the author is a registered applicant on — not
intended for high-frequency scraping or any use that would burden the
target server. The project is a small, complete case study in
authenticated automation, provider-limitation debugging, and reliability
engineering under third-party platform constraints.
