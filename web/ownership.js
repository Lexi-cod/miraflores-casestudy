// Saved ownership and handoffs are separate from verification and signatures.
function assignedForm(id){return D.workflow?.forms.find(f=>f.form===id)}
function ownerName(id,role){const u=D.staff.find(u=>u.id===id);return u&&u.role===role?u.name:'Unassigned'}
function teamCanAllocate(){return canAction('assignForm')&&[D.workflow?.team.reviewer,D.workflow?.team.partner].includes(D.user.id)}
function teamCanManage(){return canAction('manageTeam')&&(D.administration||!D.workflow?.team.partner||D.workflow.team.partner===D.user.id)}
function stageColor(stage){return stage==='reviewed'?'green':stage==='changes_requested'||stage==='unassigned'?'amber':'blue'}
function formOwnerMeta(id){const f=assignedForm(id);if(!f)return '';return `<div class="form-owners"><span><small>Preparer</small>${esc(ownerName(f.preparer,'preparer'))}</span><span><small>Reviewer</small>${esc(ownerName(f.reviewer,'reviewer'))}</span></div><div class="form-state">${tag(f.stage_label,stageColor(f.stage))}<span>Due ${f.due?esc(date(f.due)):'not set'}</span></div>`}
function engagementHeader(){
  const w=D.workflow;if(!w)return '';const t=w.team;
  return `<section class="engagement-ownership" aria-label="Engagement ownership"><div class="ownership-top"><div><span class="eyebrow">${D.administration?'Okafor–Lindqvist · 2025':'Engagement'}</span><strong>${esc(w.stage)}</strong></div><div class="actions">${btn('Team work','teamWork','small')}${teamCanManage()?btn('Manage team','manageTeam','small'):''}</div></div><div class="ownership-people">${[['preparer','Lead preparer'],['reviewer','Reviewer'],['partner','Partner']].map(([r,label])=>`<div><small>${label}</small><strong>${esc(ownerName(t[r],r))}</strong></div>`).join('')}<div><small>Due date</small><strong>${t.due?esc(date(t.due)):'Not set'}</strong></div></div></section>`;
}
function formStageActions(f){
  if(!f||!canAction('formStage')||D.state.frozen)return '';
  const steps=[];
  if(D.user.id===f.preparer&&D.user.role==='preparer'){
    if(['assigned','changes_requested'].includes(f.stage))steps.push(['in_preparation','Start preparation']);
    if(['in_preparation','changes_requested'].includes(f.stage))steps.push(['ready_for_review','Submit for review']);
  }
  if(D.user.id===f.reviewer&&D.user.role==='reviewer'){
    if(f.stage==='ready_for_review')steps.push(['under_review','Begin review']);
    if(f.stage==='under_review')steps.push(['reviewed','Complete form review']);
    if(['ready_for_review','under_review','reviewed'].includes(f.stage))steps.push(['changes_requested','Request changes']);
  }
  return steps.map(([stage,label],i)=>btn(label,'formStage',i===0?'primary small':'small',`data-form="${esc(f.form)}" data-stage="${stage}"`)).join('');
}
function formWorkbar(id){const f=assignedForm(id);if(!f)return '';return `<section class="form-workbar">${formOwnerMeta(id)}<div class="actions">${formStageActions(f)}${teamCanAllocate()?btn('Assign form','assignForm','small',`data-form="${esc(id)}"`):''}</div>${f.stage==='changes_requested'&&f.reason?`<p class="handoff-reason">${esc(f.reason)}</p>`:''}</section>`}
function showTeamWork(){
  const forms=D.workflow.forms;
  drawer('Team work',`<div class="workflow-counts">${Object.entries(D.workflow.counts).map(([label,count])=>tag(`${count} ${esc(label)}`,label==='Reviewed'?'green':'')).join('')}</div><div class="table-wrap"><table class="compact-table"><thead><tr><th>Form</th><th>Preparer</th><th>Reviewer</th><th>Due</th><th>Stage</th><th></th></tr></thead><tbody>${forms.map(f=>`<tr><td>${canInspect()?btn(esc(formName(f.form)),'ownedForm','small',`data-form="${esc(f.form)}"`):esc(formName(f.form))}</td><td>${esc(ownerName(f.preparer,'preparer'))}</td><td>${esc(ownerName(f.reviewer,'reviewer'))}</td><td>${f.due?esc(date(f.due)):'Not set'}</td><td>${tag(f.stage_label,stageColor(f.stage))}</td><td>${teamCanAllocate()?btn('Assign','assignForm','small',`data-form="${esc(f.form)}"`):''}</td></tr>`).join('')}</tbody></table></div>`,'ENGAGEMENT WORK',{wide:true});
}
function personChoices(role,inherit=false){return [...(inherit?[['__inherit__','Use engagement '+(role==='preparer'?'lead preparer':'reviewer')]]:[]),...D.staff.filter(u=>u.role===role).map(u=>[u.id,u.name])];}
function manageTeamForm(){
  const t=D.workflow.team;
  return form('Engagement team',field('preparer','Lead preparer','select',t.preparer||'',personChoices('preparer'))+field('reviewer','Reviewer','select',t.reviewer||'',personChoices('reviewer'))+field('partner','Partner','select',t.partner||'',personChoices('partner'))+field('due','Engagement due date','date',t.due||'2026-10-15')+field('reason','Reason for assignment','textarea'),f=>action('manage_team',f),'Forms inherit this team unless individually assigned. Access permissions remain unchanged.');
}
function assignFormDialog(id){
  const saved=D.state.form_work?.[id]||{},t=D.workflow.team;
  return form('Assign '+formName(id),field('preparer','Preparer','select',saved.preparer||'__inherit__',personChoices('preparer',true))+field('reviewer','Reviewer','select',saved.reviewer||'__inherit__',personChoices('reviewer',true))+`<label>Due date <small>Leave empty to use ${esc(t.due||'engagement due date')}</small><input name="due" type="date" value="${esc(saved.due||'')}"></label>`+field('reason','Handoff / assignment note','textarea'),f=>action('assign_form',{...f,form:id,preparer:f.preparer==='__inherit__'?'':f.preparer,reviewer:f.reviewer==='__inherit__'?'':f.reviewer}));
}
function changeFormStage(id,stage){
  const labels={in_preparation:'Start preparation',ready_for_review:'Submit for review',under_review:'Begin review',reviewed:'Complete form review',changes_requested:'Request changes'};
  const info={ready_for_review:'All current amounts must be verified and working adjustments independently approved. Open findings remain visible to the reviewer.',reviewed:'Requires verified amounts, resolved findings and no open review notes. This does not sign the engagement.',changes_requested:'Records the requested work and reopens engagement signatures.'};
  return form(`${labels[stage]} · ${formName(id)}`,field('reason',stage==='changes_requested'?'Changes required':'Handoff note','textarea'),f=>action('form_stage',{form:id,stage,reason:f.reason}),info[stage]||'');
}
function belongsToMe(l){const f=assignedForm(l.form);return !!f&&((f.preparer===D.user.id&&f.stage!=='reviewed')||(f.reviewer===D.user.id&&f.stage!=='reviewed')||(D.workflow.team.partner===D.user.id&&!D.state.signatures.partner));}
function assignmentInbox(){
  const tasks=D.state.tasks.filter(t=>t.assignee===D.user.id&&t.status==='open');
  const forms=(D.workflow?.forms||[]).filter(f=>!D.state.frozen&&f.stage!=='reviewed'&&((D.user.role==='preparer'&&f.preparer===D.user.id)||(D.user.role==='reviewer'&&f.reviewer===D.user.id)));
  const ready=forms.filter(f=>D.user.role==='preparer'?['assigned','in_preparation','changes_requested'].includes(f.stage):['ready_for_review','under_review'].includes(f.stage));
  const waiting=forms.filter(f=>!ready.includes(f));
  const partner=D.workflow?.team.partner===D.user.id&&!D.state.frozen&&!D.state.signatures?.partner;
  return {tasks,ready,waiting,partner,total:tasks.length+forms.length+Number(partner)};
}
function assignmentBell(){const count=assignmentInbox().total;return `<button class="icon-btn assignment-bell" data-action="notifications" aria-label="Your assigned work: ${count} outstanding items">${icon('bell')}${count?`<span class="assignment-count">${count}</span>`:''}</button>`}
function showAssignmentInbox(){
  const inbox=assignmentInbox();
  const renderForms=items=>items.map(f=>`<div class="assignment-row"><div><strong>${esc(formName(f.form))}</strong><small>${esc(f.stage_label)} · Due ${f.due?esc(date(f.due)):'not set'}</small>${f.stage==='changes_requested'&&f.reason?`<p>${esc(f.reason)}</p>`:''}</div>${btn('Open form','ownedForm','small',`data-form="${esc(f.form)}"`)}</div>`).join('');
  drawer('Your assigned work',inbox.total?`${inbox.partner?`<section class="inbox-section"><h3>Partner oversight</h3><p>${D.state.signatures.reviewer?'Reviewer signed — partner sign-off is next.':`Waiting for preparation and reviewer sign-off. ${esc(D.workflow.stage)}.`}</p><button class="btn small" data-nav="review">Open review &amp; sign-off</button></section>`:''}${inbox.ready.length?`<section class="inbox-section"><h3>Ready for you · ${inbox.ready.length}</h3>${renderForms(inbox.ready)}</section>`:''}${inbox.tasks.length?`<section class="inbox-section"><h3>Open tasks · ${inbox.tasks.length}</h3>${inbox.tasks.map(t=>`<div class="assignment-row"><div><strong>${esc(t.title)}</strong><small>Due ${esc(date(t.due))} · ${esc(t.target||'engagement')}</small></div>${btn('Respond','taskUpdate','small',`data-id="${esc(t.id)}"`)}</div>`).join('')}</section>`:''}${inbox.waiting.length?`<details class="trace-details"><summary>Waiting for handoff · ${inbox.waiting.length}</summary>${renderForms(inbox.waiting)}</details>`:''}`:'<div class="empty">No outstanding forms, handoffs or tasks assigned to you.</div>','ASSIGNMENTS');
}
function ownershipOverview(){
  const w=D.workflow,rows=rv().lines,verified=rows.filter(hasVerification).length,reviewed=w.forms.filter(f=>f.stage==='reviewed').length;
  return `<div class="stats">${stat('Verified amounts',`${verified} / ${rows.length}`,'Current working version','check')}${stat('Open findings',openChecks().length,'Awaiting disposition','alert')}${stat('Forms reviewed',`${reviewed} / ${w.forms.length}`,'Independent form review','layers')}${stat('Open review notes',D.state.notes.filter(n=>!n.resolved).length,'Awaiting resolution','file')}</div><div class="two-col"><div class="stack">${panel('Work status',`<div class="panel-body workflow-counts">${Object.entries(w.counts).map(([label,count])=>tag(`${count} ${esc(label)}`,label==='Reviewed'?'green':'')).join('')}</div>`,btn('Team work','teamWork','small'))}${panel('Open findings',`<ul class="findings">${openChecks().slice(0,5).map(findingRow).join('')||'<li class="empty">No open findings.</li>'}</ul><div class="panel-footer"><button class="link-btn" data-nav="reconciliation">All open issues ${icon('arrow')}</button></div>`)}${summaryPanel()}</div><div class="stack">${panel('Engagement sign-off',`<div class="panel-body">${['preparer','reviewer','partner'].map(r=>`<div class="progress-item"><div><strong>${esc(ownerName(w.team[r],r))}</strong><small>${esc(r)}</small></div><span>${D.state.signatures[r]?tag('Signed','green'):tag('Pending','')}</span></div>`).join('')}<div class="progress-item">Client authorization<span>${Object.keys(D.state.approvals).length} / 2</span></div></div>`)}${panel('Recent activity',`<div class="panel-body">${D.state.events.slice(-3).reverse().map(activityItem).join('')||'<p>No recorded activity.</p>'}</div>`,`<button class="link-btn" data-nav="activity">History</button>`)}</div></div>`;
}
