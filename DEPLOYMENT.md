# Free Render submission deployment

Application URL: https://miraflores-casestudy.onrender.com/ (Render deployment created October 15, 2026).

Target repository: `https://github.com/Lexi-cod/miraflores-casestudy`.

`render.yaml` configures a **Free web service** and **Free Postgres database**. It contains no paid disk or paid compute plan.

1. Publish this project's source to the dedicated repository. Exclude `data/`, `.backups/`, `.env`, exports and credentials. The parent user-profile repository is unrelated and must not be published.
2. In Render, choose **New ? Blueprint**, connect the repository and review that both resources use **Free**. Render links `DATABASE_URL`, generates `WORKPAPER_ENCRYPTION_SECRET` and installs `requirements.txt`.
3. The app starts with the supplied packet and its assigned team. Saved records, attachments and audit history go into Postgres, so web-service restarts do not erase work.
4. Use the HTTPS service URL as the submission link. Free services sleep after inactivity; allow for a cold start.
5. **Export before database expiry.** This database expires **November 14, 2026**, as shown in Render. Free Postgres expires 30 days after creation, becomes inaccessible, then is deleted after a 14-day upgrade grace period. This user-selected 30-day deployment is a submission demo, not seven-year record storage. Record the actual expiry date after provisioning and download a full review binder before then.

Render limits a workspace to one free Postgres database. If one already exists, connect a suitable existing demo database only with the owner's authorization; do not overwrite another project's records. No automatic upgrade or paid fallback is configured. Keep account spending limits aligned with the no-paid requirement; Render can charge for usage overages when billing is enabled.

Preserve `WORKPAPER_ENCRYPTION_SECRET` when restoring or updating. Losing it makes encrypted saved work unreadable. Set secrets only in Render or a local gitignored key file; never commit them. Local development keeps using the existing SQLite database. Publishing source does not migrate local saved work.

The app calls no external AI or analytics. Hosted records reside on Render. The role switcher is deliberately open for the fictional case study; see COMPLIANCE.md for production identity and filing boundaries.

Sources: [Render Free service and database limitations](https://render.com/docs/free), [Render Blueprint fields](https://render.com/docs/blueprint-spec).

Deployment dashboard: https://dashboard.render.com/web/srv-db8kq7c9v7es73ekod20

Blueprint: https://dashboard.render.com/blueprint/exs-db8kpil9fdbs739niut0

The web service and Postgres both show **Free**. Database status is **Available**. The first service deployment succeeded; application interaction checks were not run.
