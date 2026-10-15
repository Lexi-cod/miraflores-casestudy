# Miraflores evidence workpaper

Click an amount, see its source page, and leave an attributed tie-out. Reviewers can follow each correction through independent approval and sign-off without returning a separate list of review notes.

The app calls no external AI, analytics, fonts or CDNs. Local mode stores work on your computer; the submission deployment stores it in your Render database. The supplied household is fictional.

## Submission link

App: **https://miraflores-casestudy.onrender.com/**. Hosting: **Render Free web service + Free Postgres**, using `https://github.com/Lexi-cod/miraflores-casestudy`. The free database expires **November 14, 2026**; export the binder before then. See [DEPLOYMENT.md](DEPLOYMENT.md) for setup and export instructions. No paid resources are configured.

## Portal workflow

1. **Overview:** source-error count, estimated tax and payment effects, engagement owners, progress and recent work.
2. **Workpapers:** By form, Open issues and To tie out share one workspace. Open a form to inspect clickable amounts; large schedules use paginated detail. Primary evidence opens at its source page with a matching-text highlight. Supporting records and complete source-to-return trails expand when needed. Document a formula using linked numeric inputs, propose an adjustment or add missing detail. Engine values remain preserved.
3. **Evidence library:** account for every PBC document; inspect pages, extraction readings, direct destinations and downstream return use. Attach files, messages and notes. Client answers receive stable evidence references.
4. **Changes & planning:** compare versions, inspect supplied what-ifs, record decisions and create a 2026 intake from a frozen engagement, with carried records, history and assigned work. Optional version imports stay under Advanced.
5. **Review & sign-off:** review notes, assignments, independent judgments and ordered signatures. Completeness tracks outside filings and related returns. Adjustment review records independent approval, partner approval over $1,000 and whether a tax effect belongs in the total. Overlapping effects must be resolved.
6. **Filing & archive:** readiness, immutable filing snapshots, amendments, recorded extension/submission/rejection/acceptance events and notice responses. Export a portable HTML review binder, structured record and permitted attachments. Open its `index.html` offline or print it to PDF.
7. **Client portal:** own questions, return copy and typed authorization bound to the reviewed package fingerprint. Changes reopen approval.
8. **Firm administration:** team, role defaults, individual permission overrides, standards, time/budget and retention holds. Administrators receive operational records without the tax packet.

Priya Raman prepares, Daniel Ortiz reviews and Helen Strand signs as partner. Forms inherit those assignments unless delegated. The assignment bell shows work and handoffs for the selected person. Marcus Bell remains masked unless an administrator changes his clearance. Role defaults and workflow gates are enforced on the server.

## Local run

Python 3.11+:

```powershell
py app.py
```

Open `http://127.0.0.1:8765`. Existing saved work remains in `data/workpaper.sqlite`. `Start-Workpaper.ps1` starts a hidden background process. `PORT`, `HOST` and `WORKPAPER_DB` are configurable. Local SQLite mode works without third-party packages. Install `requirements.txt` when using encrypted state or Postgres.

Each browser tab has its own selected session. Revision checks reject stale writes; the portal refreshes other-session changes when no input or drawer is active. Batch verification supports undo.

## Submission documents

- [CONCEPT.md](CONCEPT.md): core idea, data model and AI disclosure.
- [FINDINGS.md](FINDINGS.md): one findings table with source evidence and estimated effects.
- [COMPLIANCE.md](COMPLIANCE.md): requirement coverage and exact case/production boundaries.
- [DEPLOYMENT.md](DEPLOYMENT.md): free Render configuration and operational instructions.
- [VALIDATION.md](VALIDATION.md): validation record. This update uses source inspection and syntax checks only; no automated tests or browser checks were run, as requested.
