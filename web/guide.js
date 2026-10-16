'use strict';

// Read-only onboarding: local preferences and navigation, never workpaper actions.
const WorkpaperGuide=(()=>{
  const memory=new Set();
  let dialog=null,mode='',owner='',steps=[],index=0,saved=null,returnFocus=null,oldOverflow='',frame=0;
  const key=()=>`miraflores.guide.v1.${D.user.id}`;
  const seen=()=>{try{return localStorage.getItem(key())==='seen'||memory.has(key())}catch{return memory.has(key())}};
  function remember(){memory.add(key());try{localStorage.setItem(key(),'seen')}catch{}}
  const step=(title,text,target,prepare)=>({title,text,target,prepare});
  function chapters(){
    if(D.client)return [{id:'client',name:'Your tax review',steps:[
      step('Your return at a glance','Start with the federal and California amounts. Your team reviews the return before asking for your approval.','.stats'),
      step('Questions and documents','Answer the questions assigned to you. Your answers stay with the workpaper as evidence for your tax team.',()=>panelWith('Questions from your tax team')),
      step('Review your package','Download your return copy and review the package. Approval becomes available after partner sign-off; updated figures may require a new approval.',()=>panelWith('Review and authorize'))
    ]}];
    const records=(name)=>()=>{recordTab='lines';recordMode=name;activeForm='';filter='';page=0;workScope='all';render()};
    const planning=(name)=>()=>{planningTab=name;render()};
    const review=(name)=>()=>{reviewSection=name;render()};
    const all=[
      {id:'overview',name:'Overview',steps:[
        step('Start with the engagement','An engagement is the work for one client and tax year. See the lead preparer, reviewer, partner and deadline here.','.engagement-ownership'),
        step('Know what needs attention','These counts show verified amounts, open findings and completed reviews. A finding is a possible problem that needs an explanation or correction.','.stats'),
        step('Follow the next step','Use Review readiness for outstanding requirements, or the assignment bell for work assigned to you. Preparation, independent review and sign-off are separate steps.','[data-action="readiness"],.assignment-bell')
      ]},
      {id:'records',name:'Workpapers',steps:[
        step('Start with a form','A workpaper records why a return amount is correct. Open a form, then click an amount to see its source or calculation.','.form-grid',records('forms')),
        step('Resolve open issues','This queue collects differences, missing support and review notes. Record what was wrong and how it was resolved; resolving an issue does not verify the amount.','.work-tabs',records('issues')),
        step('Tie out the numbers','Tie-out means agreeing a return amount to evidence or a calculation. Preparers record verification; reviewers record an independent confirmation.','.work-tabs',records('verify')),
        step('Find supporting detail','Supporting records group depreciation, sales, rentals, basis and other detail. Use Focus to narrow the work to your assignments or items needing attention.','.workpaper-tools',records('forms'))
      ]},
      {id:'documents',name:'Evidence library',steps:[
        step('Find the source','Search the documents provided by the client, often called PBC documents. Open a document to inspect its pages.','.toolbar'),
        step('Trace both directions','Return connections show where each document was used. When you open evidence from an amount, the viewer goes to its page and highlights a matching value when available.','.compact-table thead'),
        step('Account for every document','A document needs a recorded disposition: how it was used, or why it was not needed. Attach messages, files or notes when more support is required.','.panel-footer')
      ]},
      {id:'changes',name:'Changes & planning',steps:[
        step('Compare versions','Compare the original engine output with later versions. Changed amounts and evidence help you focus review on what is different.','.version-selectors',planning('versions')),
        step('Explore a scenario','A scenario is an alternative set of assumptions. Compare its supplied results and document the decision before changing the working return.','.work-tabs',planning('scenarios')),
        step('Plan the next year','Review upcoming changes, payment dates and carryovers. A carryover is an amount that continues into another tax year. Roll-forward preserves useful history for the next preparer.','.work-tabs',planning('planning'))
      ]},
      {id:'review',name:'Review & sign-off',steps:[
        step('Review and hand off','Review notes explain what still needs attention and can block filing. Sign-off records the responsible person accepting their stage of work.','.review-modes',review('review')),
        step('Check completeness','Confirm that all documents, return areas and outside filings were considered. Related returns may need follow-up even when they are prepared elsewhere.','.review-modes',review('completeness')),
        step('Review adjustments','An adjustment changes a working amount while preserving the original and reason. Check evidence and estimated tax effects; required independent approvals must be completed.','.review-modes',review('adjustments'))
      ]},
      {id:'filing',name:'Filing & archive',steps:[
        step('Finish the review first','Readiness lists what must be completed before freezing the workpaper. Freezing preserves a snapshot; an amendment records later changes on top of it.','.notice'),
        step('Record filing activity','Record submissions, rejections and acknowledgments from your filing provider with their evidence. Recording an event here does not transmit a return.',()=>panelWith('Filing lifecycle')),
        step('Keep a reviewable record','Export the binder when you need a portable record. Filing records, notice responses and roll-forward history help the next reviewer follow the work.',()=>panelWith('Archive & handoff'))
      ]},
      {id:'activity',name:'Activity & view logs',steps:[
        step('See who did what','Expand an event to inspect its author, recorded reason and supporting references. This history helps explain how the workpaper reached its current state.','.panel-body'),
        step('Resume your review','Search for a person, action or record. Mark reviewed through now saves your review checkpoint so later changes are easier to identify.','.toolbar')
      ]},
      {id:'firm',name:'Standards & budget',steps:[
        step('Follow firm standards','These rules define review requirements, materiality thresholds and responsibilities. Materiality helps the firm decide which differences need closer attention.',()=>panelWith('Review standards')),
        step('Plan time and deadlines','Track work against the budget and upcoming deadlines. Controls depend on your role; firm administrators manage standards and access.',()=>panelWith('Deadlines')),
        step('Replay help any time','Settings & help lets you replay this guide or choose a specific page. Closing a guide stops it, and it will not automatically return for this user in this browser.','[data-guide-settings]')
      ]},
      {id:'access',name:'People & access',steps:[
        step('Assign responsibilities','A role supplies default permissions. Administrators manage who can do what; assigning work and granting data access are separate decisions.',()=>panelWith('People & access')),
        step('Record access exceptions','Manage access adds or blocks permissions for a person. Record a reason so later administrators can understand the change.',()=>panelWith('Access change history'))
      ]}
    ];
    return all.filter(c=>canView(c.id)&&(!D.administration||['firm','access'].includes(c.id)));
  }
  function panelWith(title){return [...document.querySelectorAll('.panel')].find(p=>p.querySelector('h2')?.textContent===title)}
  function targetOf(s){
    let el=typeof s.target==='function'?s.target():document.querySelector(s.target);
    if(!el||!el.getBoundingClientRect().width)el=document.querySelector('.page-heading,.client-page h1,.content');
    if(el?.getBoundingClientRect().height>innerHeight*.45)el=el.querySelector('.panel-head,.form-card,.stat,thead,.toolbar')||el.firstElementChild||el;
    return el;
  }
  function create(){
    returnFocus=document.activeElement;owner=D.user.id;oldOverflow=document.body.style.overflow;
    dialog=document.createElement('dialog');dialog.className='guide-dialog';dialog.setAttribute('aria-labelledby','guide-title');dialog.setAttribute('aria-describedby','guide-description');
    document.body.append(dialog);dialog.showModal();document.body.style.overflow='hidden';
    dialog.addEventListener('cancel',e=>{e.preventDefault();close()});
    dialog.addEventListener('keydown',e=>{e.stopPropagation();if(e.key==='Escape'){e.preventDefault();close()}else if(mode==='tour'&&!e.target.matches('select,input,textarea')){if(e.key==='ArrowRight'){e.preventDefault();next()}if(e.key==='ArrowLeft'){e.preventDefault();move(index-1)}}});
    dialog.addEventListener('click',e=>{const b=e.target.closest('[data-guide]');if(!b)return;const a=b.dataset.guide;if(a==='close')close();if(a==='start')start();if(a==='back')move(index-1);if(a==='next')next();if(a==='page')start(b.dataset.chapter)});
    dialog.addEventListener('change',e=>{if(e.target.id==='guide-chapter'){const i=steps.findIndex(s=>s.chapter===e.target.value);if(i>=0)move(i)}});
    window.addEventListener('resize',schedule);document.addEventListener('scroll',schedule,true);
  }
  const closeButton=()=>'<button type="button" class="guide-close" data-guide="close" aria-label="Close guide">&times;</button>';
  function welcome(settings=false){
    if(dialog)close(false);
    remember();create();mode=settings?'settings':'welcome';
    const list=chapters();
    dialog.innerHTML=`<div class="guide-wash"></div><section class="guide-card guide-centered">${closeButton()}<div class="guide-kicker">${settings?'SETTINGS & HELP':'WELCOME TO MIRAFLORES'}</div><div class="guide-illustration" aria-hidden="true"><span>Source</span><i></i><span>Review</span><i></i><span>Sign-off</span></div><h2 id="guide-title">${settings?'Your workspace guide':'A clear place to start'}</h2><p id="guide-description">${settings?'Replay the walkthrough or choose a page below.':'Follow a short walkthrough of the pages available to your role. Learn the key terms and where to go next.'} You can go back, jump between pages or close it at any time.</p><button type="button" class="btn primary" data-guide="start">${settings?'Replay full guide':'Start guided tour'}</button><button type="button" class="btn" data-guide="close">${settings?'Close settings':'Skip for now'}</button>${settings?`<h3>Page guides</h3><div class="guide-pages">${list.map(c=>`<button type="button" data-guide="page" data-chapter="${c.id}">${esc(c.name)} <span>${c.steps.length} tips &rarr;</span></button>`).join('')}</div>`:'<p class="guide-tip">Find this again in Settings & help.</p>'}<p class="guide-preference">First-visit preferences are saved for this workspace user in this browser.</p></section>`;
    dialog.querySelector('[data-guide="start"]').focus();
  }
  function capture(){return {view,filter,jurisdiction,statusFilter,page,recordTab,recordMode,activeForm,workScope,planningTab,reviewSection,selection:[...selection],x:scrollX,y:scrollY}}
  function start(chapter){
    if(requestBusy||switchingRole)return;
    if(!dialog){remember();create()}
    saved=capture();mode='tour';
    steps=chapters().filter(c=>!chapter||c.id===chapter).flatMap(c=>c.steps.map(s=>({...s,chapter:c.id,chapterName:c.name})));
    if(!steps.length)return close();
    move(0);
  }
  function move(i){
    if(i<0||i>=steps.length||!dialog)return;
    index=i;const s=steps[index];
    if(s.chapter!=='client'&&!canView(s.chapter))return close(false);
    if(s.chapter!=='client'&&view!==s.chapter)navigate(s.chapter);
    s.prepare?.();
    const chaptersInTour=[...new Map(steps.map(s=>[s.chapter,s.chapterName]))];
    dialog.innerHTML=`<div class="guide-highlight" aria-hidden="true"></div><section class="guide-card">${closeButton()}<div class="guide-kicker">QUICK GUIDE <span>${index+1} / ${steps.length}</span></div><label class="guide-page-label" for="guide-chapter">Page<select id="guide-chapter">${chaptersInTour.map(([id,name])=>`<option value="${id}" ${id===s.chapter?'selected':''}>${esc(name)}</option>`).join('')}</select></label><h2 id="guide-title">${esc(s.title)}</h2><p id="guide-description" aria-live="polite">${esc(s.text)}</p><div class="guide-progress" role="progressbar" aria-label="Tour progress" aria-valuemin="0" aria-valuemax="${steps.length}" aria-valuenow="${index+1}"><span style="width:${(index+1)/steps.length*100}%"></span></div><div class="guide-actions"><button type="button" class="btn" data-guide="back" ${index===0?'disabled':''}>Back</button><button type="button" class="btn primary" data-guide="next">${index===steps.length-1?'Finish tour':'Next'}</button></div><p class="guide-tip">Close or press Esc to return to your work.</p></section>`;
    const target=targetOf(s);
    target?.scrollIntoView({block:'start',inline:'nearest',behavior:'instant'});
    if(!target?.closest('.sidebar'))window.scrollBy({top:-90,behavior:'instant'});
    document.body.style.overflow='hidden';position();dialog.querySelector('[data-guide="next"]').focus({preventScroll:true});schedule();
  }
  function next(){if(index===steps.length-1)close();else move(index+1)}
  function schedule(){cancelAnimationFrame(frame);frame=requestAnimationFrame(position)}
  function position(){
    if(mode!=='tour'||!dialog)return;
    const target=targetOf(steps[index]),card=dialog.querySelector('.guide-card'),highlight=dialog.querySelector('.guide-highlight');
    if(!target||!card)return;
    const r=target.getBoundingClientRect(),w=window.innerWidth,h=window.innerHeight,pad=12;
    const top=Math.max(8,r.top-5),left=Math.max(8,r.left-5),right=Math.min(w-8,r.right+5),bottom=Math.min(h-8,r.bottom+5);
    Object.assign(highlight.style,{top:top+'px',left:left+'px',width:Math.max(0,right-left)+'px',height:Math.max(0,bottom-top)+'px'});
    const cw=card.offsetWidth,ch=card.offsetHeight;
    let x=Math.min(w-cw-pad,Math.max(pad,left)),y=bottom+14;
    if(y+ch>h-pad){if(top-ch-14>=pad)y=top-ch-14;else if(left-cw-14>=pad){x=left-cw-14;y=Math.max(pad,(h-ch)/2)}else if(right+cw+14<w-pad){x=right+14;y=Math.max(pad,(h-ch)/2)}else y=Math.max(pad,h-ch-pad)}
    Object.assign(card.style,{left:x+'px',top:y+'px'});
  }
  function close(restore=true){
    if(!dialog)return;
    const sameUser=owner===D?.user.id,previous=saved;
    saved=null;mode='';steps=[];cancelAnimationFrame(frame);
    window.removeEventListener('resize',schedule);document.removeEventListener('scroll',schedule,true);
    dialog.close();dialog.remove();dialog=null;document.body.style.overflow=oldOverflow;
    if(restore&&previous&&sameUser&&(D.client||canView(previous.view))){
      ({view,filter,jurisdiction,statusFilter,page,recordTab,recordMode,activeForm,workScope,planningTab,reviewSection}=previous);selection=new Set(previous.selection);render();window.scrollTo({left:previous.x,top:previous.y,behavior:'instant'});
    }
    if(returnFocus?.isConnected)returnFocus.focus({preventScroll:true});else document.querySelector('[data-guide-settings]')?.focus({preventScroll:true});
  }
  function sync(){
    if(!D?.user)return;
    if(dialog&&(owner!==D.user.id||mode==='tour'&&steps.some(s=>s.chapter!=='client'&&!canView(s.chapter))))close(false);
    if(!document.querySelector('[data-guide-settings]')){
      const holder=document.createElement('div');holder.className=document.querySelector('.sidebar')?'nav guide-utility':'guide-client-settings';
      holder.innerHTML=`<button type="button" class="${D.client?'btn small':''}" data-guide-settings>${icon('settings')} Settings & help</button>`;
      const sidebar=document.querySelector('.sidebar');if(sidebar)sidebar.append(holder);else document.querySelector('.client-page>.role-control')?.after(holder);
      holder.querySelector('button').onclick=()=>{if(!requestBusy&&!switchingRole&&!document.querySelector('.drawer'))welcome(true)};
    }
    if(dialog){schedule();return}
    if(!seen()&&!document.querySelector('.drawer')){
      if(requestBusy||switchingRole)setTimeout(sync,250);else welcome();
    }
  }
  return {sync,isOpen:()=>!!dialog};
})();
