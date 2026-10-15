'use strict';

// Presentation of supplied records. Amounts always retain their evidence reference.
let salesFilters={company:'',from:'',to:'',sort:'date'};
function scheduleAmount(value,reference,label=''){
  return value===null||value===undefined?'<span class="muted">Not supplied</span>':`<button class="amount-link" data-ref="${esc(reference)}" aria-label="${esc(label||'Inspect amount and evidence')}">${fmt(value)}</button>`;
}
function scheduleSources(sources,title='Supporting evidence'){
  const list=[...new Set((Array.isArray(sources)?sources:[sources]).filter(Boolean))];
  return list.length?`<details class="trace-details"><summary>${esc(title)} · ${list.length}</summary>${list.map(r=>sourceObject(r)!==undefined||r.startsWith('doc:')?evidenceCard(r):`<p>${esc(r)}</p>`).join('')}</details>`:'';
}
function scheduleRecord(record,path='',key=''){
  if(record===null||record===undefined)return '<span class="muted">Not supplied</span>';
  if(typeof record==='number')return /^(year|life_years)$/.test(key)?esc(record):path?scheduleAmount(record,path):fmt(record);
  if(typeof record!=='object')return esc(String(record));
  if(Array.isArray(record))return `<div class="schedule-record-list">${record.map((r,i)=>`<div>${scheduleRecord(r,path?path+'/'+i:'',key)}</div>`).join('')}</div>`;
  return `<dl class="reference-record">${Object.entries(record).map(([k,v])=>`<div><dt>${esc(friendlyLabel(k))}</dt><dd>${['sources','source_document'].includes(k)?scheduleSources(v):scheduleRecord(v,path?path+'/'+k:'',k)}</dd></div>`).join('')}</dl>`;
}
function scheduleLineRows(lines){
  return `<div class="table-wrap"><table class="compact-table"><thead><tr><th>Return line</th><th class="num">Engine</th><th class="num">Working amount</th><th>Review</th></tr></thead><tbody>${lines.map(l=>`<tr><td>${esc(l.label)}<small>${esc(l.key)}</small></td><td class="num">${inspectAmount(l.value,l.key)}</td><td class="num">${inspectAmount(val(l.key),l.key)}</td><td>${reasonBadges(l)}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">No return lines match this focus.</td></tr>'}</tbody></table></div>`;
}
function scheduleLines(predicate){return rv().lines.filter(l=>predicate(l)&&scopeMatches(l))}
function salesSchedule(){
  const all=rv().lines.filter(l=>l.form==='F8949'),lots=all.filter(l=>!l.key.endsWith('.total')).map(l=>{
    const m=l.label.match(/^(.*?) \(acquired (.*?), sold (.*?);/);
    return {line:l,company:m?m[1].replace(/ \((RSU|ESPP)\)$/,''):l.label.split(' (')[0],acquired:m?.[2]||'',sold:m?.[3]||''};
  });
  const companies=[...new Set(lots.map(x=>x.company))].sort(),s=salesFilters;
  let rows=lots.filter(x=>scopeMatches(x.line)&&(!s.company||x.company===s.company)&&(!s.from||x.sold&&x.sold>=s.from)&&(!s.to||x.sold&&x.sold<=s.to)&&`${x.line.label} ${x.line.key}`.toLowerCase().includes(filter.toLowerCase()));
  rows.sort((a,b)=>s.sort==='company'?a.company.localeCompare(b.company)||a.sold.localeCompare(b.sold):s.sort==='gain'?Number(val(b.line.key))-Number(val(a.line.key)):a.sold.localeCompare(b.sold)||a.company.localeCompare(b.company));
  page=Math.max(0,Math.min(page,Math.max(0,Math.ceil(rows.length/35)-1)));reviewQueue=rows.map(x=>x.line.key);
  const visible=rows.slice(page*35,(page+1)*35),unknown=lots.filter(x=>!x.sold).length;
  return panel('Sales detail',`<div class="toolbar schedule-filters"><label>Company / security<select data-sales-filter="company"><option value="">All companies and securities</option>${companies.map(c=>`<option value="${esc(c)}" ${s.company===c?'selected':''}>${esc(c)}</option>`).join('')}</select></label><label>Sold from<input type="date" data-sales-filter="from" value="${esc(s.from)}"></label><label>Sold through<input type="date" data-sales-filter="to" value="${esc(s.to)}"></label><label>Sort by<select data-sales-filter="sort">${[['date','Sale date'],['company','Company / security'],['gain','Working gain: high to low']].map(([v,t])=>`<option value="${v}" ${s.sort===v?'selected':''}>${t}</option>`).join('')}</select></label><button class="btn small" data-sales-reset>Clear filters</button></div><div class="toolbar"><input id="filter" value="${esc(filter)}" placeholder="Find a sale or return line" aria-label="Find a sale">${btn('Verify selected ('+selection.size+')','verifyBatch','small')}${btn('Undo verification','undoBatch','small')}</div><div class="schedule-summary"><strong>${rows.length} of ${lots.length} sales</strong><span>Working gain / loss for filtered sales: ${fmt(rows.reduce((n,x)=>n+(typeof val(x.line.key)==='number'?val(x.line.key):0),0))}</span></div>${s.from&&s.to&&s.from>s.to?'<p class="queue-explanation">The start date is after the end date. Adjust the date range.</p>':''}${unknown?`<p class="footnote schedule-inset">${unknown} items have no supplied sale date; date filters exclude them.</p>`:''}<div class="table-wrap"><table class="compact-table"><thead><tr>${canAction('verify')?'<th><input type="checkbox" id="select-page" class="select-check" aria-label="Select visible sales"></th>':''}<th>Company / security</th><th>Acquired</th><th>Sold</th><th class="num">Engine gain / loss</th><th class="num">Working gain / loss</th><th>Review</th></tr></thead><tbody>${visible.map(x=>`<tr>${canAction('verify')?`<td><input class="select-check line-select" type="checkbox" value="${esc(x.line.key)}" ${selection.has(x.line.key)?'checked':''} aria-label="Select ${esc(x.line.key)}"></td>`:''}<td>${esc(x.company)}<small>${esc(x.line.key)}${/\((RSU|ESPP)\)/.test(x.line.label)?' · '+esc(x.line.label.match(/\((RSU|ESPP)\)/)[1]):''}</small></td><td>${esc(x.acquired||'Not supplied')}</td><td>${esc(x.sold||'Not supplied')}</td><td class="num">${inspectAmount(x.line.value,x.line.key)}</td><td class="num">${inspectAmount(val(x.line.key),x.line.key)}</td><td>${reasonBadges(x.line)}</td></tr>`).join('')||`<tr><td colspan="7" class="empty">No sales match these filters.</td></tr>`}</tbody></table></div><div class="panel-footer"><span>${rows.length?page*35+1:0}–${Math.min(rows.length,(page+1)*35)} of ${rows.length}</span><div class="pagination"><button class="link-btn" data-page="${page-1}" ${page===0?'disabled':''}>← Previous</button><span>${page+1} / ${Math.max(1,Math.ceil(rows.length/35))}</span><button class="link-btn" data-page="${page+1}" ${(page+1)*35>=rows.length?'disabled':''}>Next →</button></div></div><details class="trace-details schedule-inset"><summary>Form 8949 box totals · full return</summary>${scheduleLineRows(all.filter(l=>l.key.endsWith('.total')&&scopeMatches(l)))}</details>`);
}
document.addEventListener('change',e=>{
  const field=e.target.dataset.salesFilter;if(!field||!canInspect())return;
  salesFilters[field]=e.target.value;page=0;selection.clear();render();
  document.querySelector(`[data-sales-filter="${field}"]`)?.focus();
});
document.addEventListener('click',e=>{if(e.target.closest('[data-sales-reset]')&&canInspect()){salesFilters={company:'',from:'',to:'',sort:'date'};filter='';page=0;selection.clear();render()}});
function rentalSchedule(){
  const groups=['A','B'].map(letter=>{
    const title=lineMap()['SchE.1'+letter]?.value||'Property '+letter;
    const rows=scheduleLines(l=>l.form==='SchE'&&new RegExp('^SchE\\.(?:[1-9]|1[0-9]|2[0-2])'+letter+'$').test(l.key));
    const sale=letter==='B'?scheduleLines(l=>l.form==='F4797'):[];
    return panel(esc(title),`<div class="panel-body"><span class="eyebrow">Property ${letter}</span>${letter==='B'&&lineMap()['F4797.20']?`<p>Acquired / sold: ${inspectAmount(val('F4797.20'),'F4797.20')}</p>`:''}</div>${scheduleLineRows(rows)}${letter==='B'?`<details class="trace-details schedule-inset"><summary>Property sale · Form 4797</summary>${scheduleLineRows(sale)}</details>`:''}`);
  }).join('');
  const other=scheduleLines(l=>l.form==='F8582'||l.form==='SchE'&&!/^SchE\.(?:[1-9]|1[0-9]|2[0-2])[AB]$/.test(l.key));
  reviewQueue=[...scheduleLines(l=>['SchE','F8582','F4797'].includes(l.form))].map(l=>l.key);
  return `<div class="stack">${groups}${panel('Combined passive activity & return totals',scheduleLineRows(other))}</div>`;
}
function basisSchedule(){
  reviewQueue=scheduleLines(l=>l.form==='F7203'||['SchE.28A','SchE.28B'].includes(l.key)).map(l=>l.key);
  const names={scorp_lindqvist_family_woodworks:'Lindqvist Family Woodworks · S corporation',partnership_ridgeline:'Ridgeline · Partnership',ira_nondeductible_basis_ngozi:'Ngozi · Nondeductible IRA basis',home_7709_barton_ridge:'7709 Barton Ridge · Home basis'};
  return `<div class="stack">${Object.entries(D.packet.prior_years.basis_records).map(([key,records])=>panel(names[key]||esc(friendlyLabel(key)),`<div class="panel-body"><h3 class="section-heading">Historical basis records</h3><p class="footnote">Prior-file context; the focus filter applies to current return lines below.</p>${records.map((r,i)=>`<section class="basis-year"><h4>${esc(r.year||r.event)}</h4>${scheduleRecord(Object.fromEntries(Object.entries(r).filter(([k])=>!['year','event','source'].includes(k))),`py:/basis_records/${key}/${i}`)}<p class="footnote">${/^D\d+$/.test(r.source)?`<button class="link-btn" data-ref="${esc(r.source)}">Source document</button>`:esc(r.source)}</p></section>`).join('')}</div>${key==='scorp_lindqvist_family_woodworks'?scheduleLineRows(scheduleLines(l=>l.form==='F7203'||l.key==='SchE.28A'))+`<details class="trace-details schedule-inset"><summary>2024 K-1</summary>${scheduleRecord(D.packet.prior_years.return_2024.K1_1120S,'py:/return_2024/K1_1120S')}</details>`:key==='partnership_ridgeline'?scheduleLineRows(scheduleLines(l=>l.key==='SchE.28B'))+`<details class="trace-details schedule-inset"><summary>2024 K-1</summary>${scheduleRecord(D.packet.prior_years.return_2024.K1_1065,'py:/return_2024/K1_1065')}</details>`:''}`)).join('')}</div>`;
}
function paymentSchedule(){
  const fed=D.packet.tax_agency_records.irs_account_transcript_2025[0],ca=D.packet.tax_agency_records.ftb_account;
  function payments(rows,path){return `<div class="table-wrap"><table class="compact-table"><thead><tr><th>Payment date</th><th>Description</th><th class="num">Agency amount</th></tr></thead><tbody>${rows.map((r,i)=>`<tr><td>${esc(r.date)}</td><td>${esc(r.description||r.note||'Estimated tax payment')}</td><td class="num">${scheduleAmount(r.amount,path+'/'+i)}</td></tr>`).join('')}</tbody></table></div>`}
  return `<div class="stack">${panel('Federal estimated payments',`<div class="schedule-summary"><span>Transcript as of ${esc(fed.as_of)}</span><strong>${scheduleAmount(fed.transactions.reduce((n,r)=>n+(typeof r.amount==='number'?r.amount:0),0),'agency:/irs_account_transcript_2025/0')}</strong></div>${payments(fed.transactions,'agency:/irs_account_transcript_2025/0/transactions')}`)}${panel('California estimated payments',`<div class="schedule-summary"><span>2025 credits · as of ${esc(ca.as_of)}</span><strong>${scheduleAmount(ca.tax_year_2025_payments.reduce((n,r)=>n+r.amount,0),'agency:/ftb_account/tax_year_2025_payments')}</strong></div>${payments(ca.tax_year_2025_payments,'agency:/ftb_account/tax_year_2025_payments')}<details class="trace-details schedule-inset"><summary>Payments designated to 2024 · excluded from 2025</summary>${payments(ca.tax_year_2024_payments_after_filing,'agency:/ftb_account/tax_year_2024_payments_after_filing')}</details>`)}${lineTable(['F2210','FTB5805'],['F1040.26','F1040.25d','F1040.31','F540NR.81','F540NR.82'])}<details class="trace-details"><summary>Confirmations & later agency records</summary>${scheduleSources(['D67','D68'])}${scheduleRecord(D.packet.tax_agency_records.irs_account_transcript_2025.slice(1).map(x=>({as_of:x.as_of,transactions:x.transactions})))}</details></div>`;
}
function carrySchedule(){
  const prior=D.packet.prior_years.carryovers_into_2025,out=rv().carryovers_out;
  function table(obj,path){return `<div class="table-wrap"><table class="compact-table"><thead><tr><th>Carryover / basis item</th><th class="num">Amount</th></tr></thead><tbody>${Object.entries(obj).filter(([k,v])=>typeof v==='number'||v===null).map(([k,v])=>`<tr><td>${esc(friendlyLabel(k))}</td><td class="num">${scheduleAmount(v,path+'/'+k)}</td></tr>`).join('')}</tbody></table></div>`}
  return `<div class="two-col"><div class="stack">${panel('Into 2025 · prior preparer',`<div class="panel-body"><h3>Federal</h3></div>${table(prior,'py:/carryovers_into_2025')}<details class="trace-details schedule-inset"><summary>California carryovers</summary>${table(prior.california,'py:/carryovers_into_2025/california')}<p>${esc(prior.california.note)}</p></details>${scheduleSources(['doc:D06#page6','doc:D06#page9','D07'])}`)}</div><div class="stack">${panel('Into 2026 · engine '+esc(D.state.version.toUpperCase()),`<div class="panel-body"><p class="footnote">Supplied engine balances. Proposed adjustments require a recomputed return before carryforward.</p><h3>Federal</h3></div>${table(out.federal,'schedule:carry/federal')}<details class="trace-details schedule-inset"><summary>California carryovers & depreciation differences</summary>${table(out.california,'schedule:carry/california')}${scheduleRecord(out.california.depreciation_basis_differences,'schedule:carry/california/depreciation_basis_differences')}</details><div class="panel-footer">${btn('Next-year planning','planning','small')}</div>`)}</div></div>`;
}
function priorSchedule(){
  const p=D.packet.prior_years.prior_preparer_workpaper;
  return `<div class="stack">${panel('Prior preparer handoff',`<div class="panel-body"><p>${esc(p.summary_memo)}</p><h3>Prior treatment & assumptions</h3><ul class="schedule-notes">${p.notes.map(n=>`<li>${esc(n)}</li>`).join('')}</ul><h3>Open items at handoff</h3><ul class="schedule-notes">${p.open_items_left_by_prior_preparer.map(n=>`<li>${esc(n)}</li>`).join('')}</ul><p class="footnote">Historical handoff items; current resolution is recorded in Open issues.</p>${scheduleSources([p.source_document,'py:/asset_records'],'Handoff evidence')}</div>`)}${panel('Our recorded changes',`<div class="panel-body">${adjustmentList()}</div>`)}</div>`;
}
function assetWorkspace(a){
  const measures=[['prior_accumulated','Accumulated before 2025'],['depreciation_2025','2025 depreciation'],['accumulated_end','Accumulated at year end'],['difference_from_regular','AMT difference from regular']];
  return `<div class="schedule-summary"><span>${esc(a.activity)}</span>${tag(a.disposed?'Disposed '+a.disposed:'In service',a.disposed?'amber':'green')}</div><dl class="reference-record"><div><dt>Cost</dt><dd>${fmt(a.cost)}</dd></div><div><dt>Land · not depreciated</dt><dd>${fmt(a.land_value_not_depreciated)}</dd></div><div><dt>Placed in service</dt><dd>${esc(a.placed_in_service)}</dd></div><div><dt>Recovery life</dt><dd>${esc(a.life_years)} years</dd></div><div><dt>Method / bonus treatment</dt><dd>${esc(a.method)}</dd></div></dl><div class="table-wrap"><table class="compact-table"><thead><tr><th>Depreciation</th><th class="num">Federal</th><th class="num">California</th><th class="num">AMT</th></tr></thead><tbody>${measures.map(([k,t])=>`<tr><td>${t}</td>${['federal','california','amt'].map(j=>`<td class="num">${a[j]?.[k]===undefined?'Not supplied':fmt(a[j][k])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>${a.disposition?`<h3>Disposition & recapture</h3>${scheduleRecord(a.disposition)}`:''}${scheduleSources(a.sources)}<details class="trace-details"><summary>Where this asset is used</summary>${rv().lines.filter(l=>l.sources?.includes('asset:'+a.asset_id)).map(l=>`<div class="trace-node"><span>${esc(l.label)}</span>${inspectAmount(val(l.key),l.key)}</div>`).join('')||'<p>No direct return-line reference was supplied.</p>'}</details>`;
}
function scheduleReference(r){
  if(r.startsWith('asset:')){const a=objectForRef(r);if(!a)return false;drawer(a.description,assetWorkspace(a)+`<div class="actions">${btn('Link this asset','link','small',`data-source="${esc(r)}"`)}</div>`,'ASSET WORKPAPER',{wide:true});return true}
  if(!r.startsWith('py:/')&&!r.startsWith('agency:/')&&!r.startsWith('schedule:carry/'))return false;
  const carry=r.startsWith('schedule:carry/'),o=carry?r.slice('schedule:carry/'.length).split('/').reduce((a,k)=>a?.[k],rv().carryovers_out):objectForRef(r);
  if(o===undefined)return false;
  const leaf=r.split('/').filter(Boolean).at(-1);
  const title=carry?'Carryforward · '+friendlyLabel(leaf):r.startsWith('agency:/irs_')?'IRS account record':r.startsWith('agency:/ftb_')?'California payment record':/^\d+$/.test(leaf)?'Historical record':friendlyLabel(leaf);
  let evidence=[];
  if(r.startsWith('py:/carryovers'))evidence=['doc:D06#page6','doc:D06#page9','D07'];
  else if(r.startsWith('py:/return_2024'))evidence=['D06'];
  else if(r.startsWith('py:/'))evidence=['D07'];
  if(r.startsWith('agency:/irs_account_transcript_2025/0'))evidence=['D67'];
  if(r.startsWith('agency:/ftb_account'))evidence=['D68'];
  const parent=typeof o!=='object'&&!carry?objectForRef(r.slice(0,r.lastIndexOf('/'))):null;
  const carryLines={capital_loss_short:['SchD.7','SchD.21'],capital_loss_long:['SchD.15','SchD.21'],passive_1450_fremont:['SchE.22A','F8582.4'],passive_1200_barton_hills:['SchE.22B','F8582.4'],minimum_tax_credit_from_2025_amt:['F6251.11'],ira_nondeductible_basis_ngozi:['F8606.14'],scorp_stock_basis_end:['F7203.15']};
  const related=carry?(carryLines[leaf]||[]).filter(k=>lineMap()[k]):[];
  drawer(title,`${carry?`<p class="footnote">Engine ${esc(D.state.version.toUpperCase())} carryforward; proposed adjustments are not recomputed here.</p>`:''}${scheduleRecord(o)}${parent?`<details class="trace-details"><summary>Record context</summary>${scheduleRecord(parent)}</details>`:''}${related.length?`<h3>Related return amounts</h3>${scheduleLineRows(related.map(k=>lineMap()[k]))}`:''}${carry&&rv().assets.some(a=>a.asset_id===leaf)?scheduleSources(['asset:'+leaf],'Asset detail'):''}${scheduleSources(evidence)}<div class="actions">${!carry?btn('Link this record','link','small',`data-source="${esc(r)}"`):''}</div>`,'SUPPORTING RECORD',{wide:true});return true;
}
function supportingSchedule(){
  return ({assets:assetTable,sales:salesSchedule,business:()=>books()+lineTable(['SchC']),rentals:rentalSchedule,basis:basisSchedule,payments:paymentSchedule,carry:carrySchedule,prior:priorSchedule})[recordTab]?.();
}
