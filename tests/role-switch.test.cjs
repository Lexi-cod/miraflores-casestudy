const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../web/app.js'),'utf8').replace('\nstart();','\n');
function setup(){
  const control={value:'st-02',disabled:false};
  const context=vm.createContext({console,setTimeout:()=>0,clearTimeout(){},setInterval(){},sessionStorage:{setItem(){},getItem(){return null}},document:{activeElement:null,hidden:false,querySelector:s=>s==='#role'?control:null,querySelectorAll:()=>[],addEventListener(){}}});
  vm.runInContext(source,context);
  vm.runInContext(`D={user:{id:'st-02',name:'Daniel Ortiz',role:'reviewer'},capabilities:{actions:['resolve','sign']},state:{revision:5,tasks:[]},staff:[{id:'st-01',name:'Priya Raman',role:'preparer'},{id:'st-02',name:'Daniel Ortiz',role:'reviewer'}]}; render=()=>{};closeDrawer=()=>{};toast=()=>{};`,context);
  return {context,control,run:code=>vm.runInContext(code,context)};
}
const preparer={user:{id:'st-01',name:'Priya Raman',role:'preparer'},capabilities:{actions:['adjust','verify','sign']},state:{revision:5,tasks:[]}};
test('action buttons follow server capabilities',()=>{
  const {run}=setup();assert.equal(run("btn('Adjust','adjust')"),'');assert.match(run("btn('Resolve','resolve')"),/data-action="resolve"/);
  run(`D=${JSON.stringify(preparer)}`);assert.match(run("btn('Adjust','adjust')"),/data-action="adjust"/);assert.equal(run("btn('Resolve','resolve')"),'');
});
test('switcher identifies people and their authority',()=>{
  const {run}=setup();const html=run('roleSwitcher()');assert.match(html,/Priya Raman.*Preparer/);assert.match(html,/Daniel Ortiz.*Reviewer/);assert.match(html,/aria-label="Switch role"/);
});
test('role change uses returned state, clears selection, and changes workspace',async()=>{
  const {context,control,run}=setup();context.fetch=async()=>({ok:true,json:async()=>preparer});run("selection.add('F1040.1a')");
  await run("switchRole('st-01')");assert.equal(run('D.user.id'),'st-01');assert.equal(run('view'),'records');assert.equal(run('selection.size'),0);assert.equal(control.disabled,false);
});
test('in-flight poll cannot overwrite a newly selected role',async()=>{
  const {context,run}=setup();const old=JSON.parse(run('JSON.stringify(D)'));let release;
  context.fetch=async url=>url.endsWith('/state')?new Promise(resolve=>{release=()=>resolve({ok:true,json:async()=>old})}):({ok:true,json:async()=>preparer});
  const pending=run('pollState()');await run("switchRole('st-01')");release();await pending;assert.equal(run('D.user.id'),'st-01');
});
test('failed role change restores previous selection',async()=>{
  const {context,control,run}=setup();control.value='st-01';context.fetch=async()=>({ok:false,status:500,json:async()=>({error:'Unavailable'})});await run("switchRole('st-01')");
  assert.equal(run('D.user.id'),'st-02');assert.equal(control.value,'st-02');assert.equal(control.disabled,false);
});
test('mutation includes expected actor to prevent cross-tab misattribution',async()=>{
  const {context,run}=setup();let sent;context.fetch=async(url,options)=>{sent=JSON.parse(options.body);return {ok:true,json:async()=>({})}};
  await run("api('action',{revision:5,action:'note',payload:{text:'Review'}})");assert.equal(sent.actor_id,'st-02');assert.equal(sent.action,'note');
});

const administrator={user:{id:'st-05',name:'Jo Kimura',role:'firm_administrator'},staff:[{id:'st-05',name:'Jo Kimura',role:'firm_administrator'}],capabilities:{actions:['standards','budget','time','task_update'],views:['firm'],description:'Administration only'},administration:true,administration_data:{budget_hours:{review:10},hours_by_area:{review:2},deadlines:[]},state:{revision:5,standards:{rules:['Independent review required'],variance_review:{flag_if_change_over_percent:10,and_over_amount:1000}},tasks:[]}};
test('administrator cannot navigate, inspect, search or export tax work',()=>{
  const {run}=setup();run(`D=${JSON.stringify(administrator)};view='firm'`);
  for(const view of ['overview','records','documents','filing','activity','review','changes','reconciliation'])assert.equal(run(`canView('${view}')`),false);
  for(const action of ['readiness','export','reveal','fullExport','planning','scenario','versionExample','adjustments','inspectAdjustment','evidenceNav','unknownAction'])assert.equal(run(`canAction('${action}')`),false);
  run("navigate('records');showRef('F1040.1a');showDoc('D08');showFinding('duplicate-interest');search('wages')");
  assert.equal(run('view'),'firm');assert.equal(run('currentDrawer'),null);
});
test('administration portal renders without any tax packet and has only operational controls',()=>{
  const {run,context,control}=setup();const appElement={innerHTML:''};
  context.document.querySelector=s=>s==='#app'?appElement:s==='#role'?control:null;
  run(`D=${JSON.stringify(administrator)};renderAdministration()`);
  assert.match(appElement.innerHTML,/Edit variance thresholds/);assert.match(appElement.innerHTML,/Edit budget hours/);
  assert.match(appElement.innerHTML,/2.0 \/ 10.0 h/);
  assert.deepEqual([...appElement.innerHTML.matchAll(/data-nav="([^"]+)"/g)].map(m=>m[1]),['firm']);
  for(const value of ['global-search','data-ref=','data-action="export"','Review readiness','Return lines','Okafor'])assert.ok(!appElement.innerHTML.includes(value),value);
});
test('quality reviewer can trace masked work but has no preparation, signature or archive buttons',()=>{
  const {run}=setup();run("D.user.role='quality_reviewer';D.capabilities={actions:['seen','time','task_update'],views:['overview','records','documents','reconciliation','changes','review','activity','firm']}");
  assert.equal(run("canView('documents')"),true);assert.equal(run("canAction('scenario')"),true);
  for(const action of ['verify','adjust','sign','resolve','standards','budget','reveal','export','fullExport','readiness','version','replayNext'])assert.equal(run(`canAction('${action}')`),false);
});
test('administrative task responses are limited to the assigned user',()=>{
  const {run}=setup();run(`D=${JSON.stringify(administrator)};D.state.tasks=[{id:'mine',assignee:'st-05'},{id:'other',assignee:'st-01'}]`);
  assert.equal(run("canAction('taskUpdate','mine')"),true);assert.equal(run("canAction('taskUpdate','other')"),false);
});
