# Requirements completion update ? October 15, 2026

Implemented clickable form amounts, missing working detail, recorded calculations, transitive source use, answer/note evidence, independent adjustment approvals, outside-filing/related-return conclusions, package-bound authorizations, simulated filing lifecycle, notice responses, portable binders, next-year intake, per-tab sessions, encrypted-state support and retention controls. Free Render Postgres deployment support replaces the proposed paid disk configuration.

Validation for this revision is limited to source/schema inspection, Python AST parsing and JavaScript syntax checks. **No automated tests or browser checks were run**, as requested. Existing older test results do not validate this revision. New workflows, PostgreSQL operation, encryption, retention, exports and visual behavior still need the user's manual review. Deployment status checks, if performed, confirm provisioning only.

Saved case work is preserved; no review, adjustment, authorization or filing completion is seeded. Earlier code is backed up under `.backups/requirements-completion-20261015-143358`.

Suggested manual walkthrough: preparer opens a form and traces a source; records a formula/adjustment; reviewer approves it; partner approves a material effect; clients download/authorize the reviewed package; partner records simulated filing and freeze; prepare/review a notice response and export the binder; create 2026 intake. Readiness prerequisites remain required rather than being bypassed for this walkthrough.

---

## Portal simplification ? October 15, 2026

Unified layout retained; layout switching and Season replay removed. Added a combined assignment inbox, To tie out label, contextual schedules, a next-year planning tab, collapsed advanced imports, and one export location. Time/budget and deployment details are secondary. No saved engagement data was changed.

JavaScript syntax checks and Python source parsing passed. No automated tests or browser checks were run, per user instruction. Manual UI/workflow validation remains outstanding; earlier validation below does not validate this revision.

## Engagement ownership update ? October 15, 2026

Added persisted team/form ownership, inherited assignments, due dates, stage handoffs, owner-restricted independent review and signature gates, operational-only administrator visibility, and a shorter overview. The current case team was assigned through a system-attributed setup event; no work was marked completed.

Validation for this update is limited to static JavaScript syntax checks, Python source parsing, and source inspection. No automated tests or browser checks were run at the user's request; manual workflow validation remains outstanding.

## Workspace layout preview ? October 15, 2026

Implemented unified Workpapers, reason badges and focus filters, targeted assignments, read-only version comparisons, scenario summaries, and a browser-local Previous layout toggle. Saved engagement records were not reset.

Only JavaScript syntax checks and Python source parsing were run for this change. No automated tests or browser checks were run, as requested. The older validation results below do not validate this layout revision. Manual interaction review remains with the user.

# Validation record

## Form review and evidence tracing update

Added form grouping, an open-item queue, clickable amounts and calculation components, a side-by-side number/source workspace, source-text highlights, collapsible supporting details, trace breadcrumbs and save-and-next review actions. No automated tests or browser checks were run for this update, at the user's request. Earlier test results below do not validate these changes.

## Document page navigation update

The document viewer now has Previous/Next buttons, an editable page counter with Enter-to-jump validation, left/right keyboard navigation outside editable fields, and direction-aware transitions that respect reduced-motion preferences. Page changes refresh source text, extracted values and page-specific return connections without adding drawer history entries. No automated tests or browser checks were run, at the user's request.

## People & access update

Role assignment, default permissions, per-person allow/block overrides and access history have been added. No automated tests or browser checks were run for this update, at the user's request. The results below describe earlier versions, not validation of this update.

## Role scope tightening

- **38 Python tests and 10 JavaScript tests passed**, plus the JavaScript syntax check. Tests use an isolated database.
- Administrator responses to session selection, state reads and mutations omit the tax packet, findings, review notes, event payloads, attachments and snapshots. Only operational standards, budget totals, deadlines and explicitly assigned administrative tasks are returned.
- Direct export and unmask requests from administrators, quality reviewers and clients return HTTP 403 without changing state, even if the packet's staff record grants sensitive-data clearance.
- Navigation and detail/search access follow server-provided views. Unknown UI actions are denied. Quality reviewers retain masked evidence tracing and history but have no tax-edit, signature, export or unmask controls.
- Budget edits are administrator-only, validate hours, preserve the original packet and do not invalidate tax sign-offs. Client approval projections exclude the other client's statement.
- Browser checked all eight identities. Administrator has a single Standards & budget navigation item and a working budget-edit dialog; quality reviewer has no Filing & archive navigation, export or unmask button. Both clients receive separate portals. No engagement records were changed by browser checks; revision 7 was preserved.

## Role-switch repair

- Reproduced the original placement defect: the selector began at y=790 in a 686-pixel viewport, below the visible fixed sidebar.
- Moved the selector to the sticky header; final browser observation showed y=29–57 within a 742-pixel viewport.
- Server-provided capabilities now determine action visibility and are enforced before mutations. Role labels and authority summaries distinguish each workspace.
- Switching returns the selected identity and its state in one response. In-flight polls cannot overwrite a switch; mutation requests carry the expected actor to reject stale-tab misattribution. Local server cookies are scoped by port.
- **32 Python tests and 6 JavaScript tests passed.** Tests cover every identity, permissions, allowed/denied server mutations, switch failure recovery and polling races.
- Verified all eight selectable identities in Chrome: preparer adjustment controls, reviewer disposition controls, partner filing controls, administrator standards, quality-review restrictions, limited-clearance restrictions and both client portals. Final tab is left in the reviewer workspace.
- Existing engagement records were preserved. Browser checks changed roles and opened views; they did not create reviews, adjustments or approvals.

## Original build validation

- Python control / HTTP suite: **29 tests passed** (`py -m unittest discover -s tests -v`). Tests use a separate disposable database.
- JavaScript syntax: `node --check web/app.js` passed.
- Running local build: `/`, `/app.js`, `/styles.css` and `/api/bootstrap` all returned HTTP 200 after the final server restart.
- Chrome visual inspection: overview layout, progress indicator, readable source pages, finding details and source-to-return navigation inspected.
- Chrome navigation checks: all twelve workpaper record tabs rendered; version comparison showed 89 changes from v2 to v3.
- The remaining browser sweep was interrupted by Chrome automation timeouts. A final screenshot and mobile-viewport check were not completed. The later back-navigation/accessibility refinement passed syntax checking but was not rechecked in Chrome.
- No actual engagement reviews, corrections, sign-offs or client approvals were fabricated for demonstration. The live database remains at initial revision 0. Scripted filing events are not treated as actual filing status.

The test suite verifies application controls, not tax-law correctness or production security certification. See `COMPLIANCE.md` for the complete deployment boundary.
