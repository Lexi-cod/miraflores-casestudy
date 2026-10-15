'use strict';
function brandWordmark(){return '<span class="brand-wordmark">mira<span>flores</span><b>.</b></span>'}
function recordPresentation(value,key='',path=''){
  if(value===null||value===undefined)return '<span class="muted">Not supplied</span>';
  if(typeof value==='boolean')return value?'Yes':'No';
  if(typeof value==='number'){
    const plain=/^(year|years|id|revision|batch_event|amendment|page|page_count|life_years|hours|count|index)$/.test(key)||/rate|ratio|percent|confidence|miles|days|quantity/.test(key);
    const text=/^(year|id|revision|batch_event|amendment|page|index)$/.test(key)?esc(String(value)):plain?esc(value.toLocaleString('en-US',{maximumFractionDigits:6})):fmt(value);
    return path?`<button class="amount-link" data-ref="${esc(path)}">${text}</button>`:text;
  }
  if(typeof value==='string'){
    if(/^(status|stage|verification_kind|role|decision|action|kind)$/.test(key))return esc(value.replaceAll('_',' '));
    if(/^(actor|owner|assignee|reviewer|partner|preparer|reviewed_by|answered_by|resolved_by)$/.test(key))return esc(who(value));
    if(/^(refs|sources|source|target|key|keys|evidence_ref)$/.test(key)&&canInspect()&&(sourceObject(value)!==undefined||value.startsWith('doc:'))){
      const o=sourceObject(value),page=value.match(/^doc:(D\d+)#page(\d+)$/),doc=page&&D.packet?.documents.find(d=>d.id===page[1]);
      const label=doc?`${doc.title} · page ${page[2]}`:o?.label||o?.title||o?.description||value;
      return `<button class="link-btn record-reference" data-ref="${esc(value)}">${esc(label)}</button>`;
    }
    if(/^[\[{]/.test(value.trim())){try{return recordPresentation(JSON.parse(value),key,path)}catch{}}
    return esc(value);
  }
  if(Array.isArray(value))return value.length?`<ul class="readable-list">${value.map((v,i)=>`<li>${recordPresentation(v,key,path?path+'/'+i:'')}</li>`).join('')}</ul>`:'<span class="muted">None recorded</span>';
  const entries=Object.entries(value).filter(([k])=>!['content','encoding','_before'].includes(k));
  return `<dl class="reference-record readable-record">${entries.map(([k,v])=>`<div><dt>${esc(friendlyLabel(k))}</dt><dd>${typeof v==='number'&&value.key&&['old','new','value','original'].includes(k)?displayValue(v,value.key):recordPresentation(v,k,path?path+'/'+k:'')}</dd></div>`).join('')||'<p>Nothing recorded.</p>'}</dl>${value._before?`<details class="trace-details"><summary>Previous record</summary>${recordPresentation(value._before)}</details>`:''}${value.content?`<details class="trace-details"><summary>Evidence content</summary>${value.encoding==='base64'?'<p>Use the attachment download to open this file.</p>':evidenceText(value.content)}</details>`:''}`;
}
function evidenceText(text){try{return recordPresentation(JSON.parse(text))}catch{return `<div class="page-text">${esc(text)}</div>`}}
