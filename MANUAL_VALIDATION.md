# Manual portal walkthrough - October 15, 2026

## Scope and isolation

Browser-driven manual checks used three local databases under `tmp/manual-validation`, never the saved engagement or Render database. No automated browser test suite or unit test suite was run. JavaScript syntax and Python compilation checks were run separately.

- Port 8766: fresh case. Assignments, preparation, independent review, adjustments, notes, client questions, permissions, history, attachments and concurrent edits were performed through the portal.
- Port 8767: explicit QA checkpoint. Prerequisite line verifications, form reviews, document dispositions, area conclusions, findings and outside-filing conclusions were populated as fixtures. Every fixture states that it is not a professional conclusion. No signatures or client authorizations were seeded. The preparer, reviewer, partner, both clients, freeze, export, roll-forward and amendment actions were then exercised manually.
- Port 8768: branch of the manually signed and frozen checkpoint, used for the simulated filing lifecycle. The branch retained the actual manual QA signatures and approvals. No external filing or message was transmitted.

This is application workflow validation, not a manual audit of every one of the 627 return amounts or certification of tax correctness.

## Observed results

| Area | Manual action and observed result |
| --- | --- |
| Roles | Switched among all eight identities. Administrator showed administration only; quality reviewer had masked inspection without filing or tax-edit controls; clients had separate portals. |
| Assignments | Daniel assigned Form 4562-E to Marcus. Marcus's assignment count became one and My assignments showed that form. |
| Preparation | Marcus started preparation, opened both rental depreciation calculations, inspected asset detail and saved evidence-backed verifications. |
| Handoff | Submit for review moved the form into Daniel's Ready for you inbox. Daniel began review, confirmed both amounts independently and completed the form review. |
| Attribution | Expanded line history retained Marcus's preparation and Daniel's independent confirmations, with methods, references and explanations displayed as labeled records. |
| Bulk selection | Selecting the page selected both amounts. Fixed the header checkbox so its checked and partial-selection states match the selected rows. |
| Undo | Marcus undid his last verification batch. The affected amount became unverified while the earlier tie-out remained. |
| Adjustments | Priya proposed the duplicate-interest correction from $1,840 to $0. Daniel independently reviewed it. Engine value, working value, reason, evidence and estimated effects remained distinct. |
| Evidence pages | Next moved from page 1 to page 2; typing page 1 returned directly; page 99 produced an inline range error. |
| Exact evidence | Clicking book net income opened D14 page 1 and highlighted the printed 89,834.00 amount. |
| Structured attachments | Attached a nested structured-text record. Opening it showed named fields, currency, Yes/No and nested supporting records, with no raw JSON. |
| Supporting schedules | Opened depreciation, sales, books to tax, rentals/passive, basis/K-1s, retirement/foreign, deductions/credits, payments, state allocation, carryovers and prior-preparer views. Inspected asset and historical-basis drill-downs. |
| Sales filters | Company Corvane Systems Inc plus January-June 2025 narrowed the list to three sales. Clear filters restored the full selection. |
| Versions and scenarios | Opened version comparison, scenario assumptions/results and expanded scenario details. Found and corrected currency formatting on percentage lines. |
| Client questions | Priya assigned a question to Ngozi. Ngozi answered; the answer persisted as evidence. Erik's portal did not show Ngozi's assigned question. |
| Access overrides | Jo blocked Marcus's Log time permission with a reason. Access history recorded the change; Marcus subsequently had no Log time action. |
| Review notes | Partner created a blocking note and resolved it with a recorded conclusion. |
| Premature sign-off | Partner signing on the fresh case was rejected: every form must first be submitted for review. Client approval and freeze remained unavailable. |
| Successful sign-off | On the explicit checkpoint, Priya, Daniel and Helen signed in order through the UI. Each signature appeared under the correct role. |
| Client authorization | Each client separately entered their name, statement and consent. Both approvals were recorded against the package fingerprint. |
| Freeze | Readiness reached zero conditions. Freeze created one snapshot and exposed Open amendment. |
| Export | The portal completed masked binder export after the performance correction. Separately generated the same artifact for inspection: readable HTML, zero em dashes, and zero matches for packet identifier strings of six or more characters. The browser download-listener API timed out, so filesystem delivery through that listener was not verified. |
| Roll-forward | Created the 2026 intake from the frozen snapshot. It displayed the source snapshot, carried records and history. |
| Amendment | Opening amendment preserved the original snapshot, incremented the amendment count and reopened signature/client-approval requirements. |
| Filing simulation | Recorded submission, rejection, resolution, resubmission and acceptance. Resubmission before resolution was rejected as out of sequence. Extension recording was also exercised. |
| Notice response | Saved a CP2000 response draft with supporting evidence. The draft remained in the workpaper; nothing was sent externally. |
| Concurrent sessions | Daniel saved a review checkpoint while Helen had an unsaved note. Helen's stale save was rejected and her entered note remained in the form. |
| Persistence | Reloaded the isolated portal and observed saved assignments, verifications and workflow state. |
| Visuals | Inspected the desktop overview and evidence drawer with the new cream, green and indigo branding. Saved screenshots under `tmp/manual-validation`. |

## Corrections discovered during the walkthrough

- Shared readable presentation now replaces raw JSON in history, evidence, scenarios and supporting records. Structured text attachments are parsed for display; original stored content is retained.
- Em dashes are removed from application copy and normalized when original packet or saved text is displayed. Immutable source data and machine-readable archives remain intact.
- The select-page checkbox now reflects all/partial selection.
- Historical comparisons and scenarios use percentage formatting for rate lines.
- Client summary status now reflects partner review instead of always saying pending.
- Export reuses the immutable packet identifier inventory and reference captions instead of rescanning the whole packet for every linked record. Masking rules remain unchanged. Export controls also show progress and prevent duplicate requests while preparing the binder.

## Limits of this pass

### Interactive guide follow-up

Manually checked the first-visit welcome, starting the staff guide, jumping to Workpapers, closing and reloading without another prompt, replaying from Settings & help, all four Workpapers tips, finishing and returning to the original workspace, separate client onboarding with only the client chapter, and Escape dismissal. These checks used an isolated local database; its revision remained zero. Source review and syntax checks cover the page catalog and role filtering. Other chapters and narrow viewport placement were not individually exercised in this follow-up. Preferences are stored per workspace user in browser local storage, with an in-memory fallback when storage is unavailable.

- The responsive viewport capability did not actually resize the browser: DOM measurement stayed at 1536 pixels. Narrow/mobile behavior is therefore not marked passed.
- Binary-file upload/download, recomputed-version import, every judgment/calculation formula, legal-hold expiry/destruction, and every access-override combination were not individually exercised in this manual pass.
- The prepared checkpoint validates finalization controls after prerequisites exist. Its seeded conclusions do not count as manual preparation or independent review of the entire case.
- Render free-service availability, database expiry and production identity/security boundaries remain as documented in COMPLIANCE.md and DEPLOYMENT.md.
