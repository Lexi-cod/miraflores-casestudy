"""Persistent evidence workpaper for the supplied fictional household."""
import base64
import copy
import hashlib
import json
import math
import os
import re
import secrets
import sqlite3
import threading
import sys
import workpaper_features as features
import workpaper_storage as storage
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
PACKET = json.loads((ROOT / 'okafor_lindqvist_2025_packet.json').read_text(encoding='utf-8'))
DB = Path(os.environ.get('WORKPAPER_DB', str(ROOT / 'data' / 'workpaper.sqlite')))
LOCK = threading.RLock()
SESSIONS = {}
STAFF = {x['id']: x for x in PACKET['firm']['staff'] + PACKET['firm']['client_users']}
EDITORS = {'preparer', 'reviewer', 'partner'}
ROLE_ACTIONS = {
    'preparer': {'verify','undo_verify','adjust','undo_adjust','reopen','note','judgment','evidence','link','document','area','step','sign','version','import_version','task','task_update'},
    'reviewer': {'verify','undo_verify','resolve','reopen','note','resolve_note','judgment','review_judgment','evidence','link','document','area','step','sign','version','task','task_update'},
    'partner': {'verify','undo_verify','resolve','reopen','note','resolve_note','judgment','review_judgment','evidence','link','document','area','step','sign','freeze','amend','version','task','task_update'},
    'firm_administrator': {'standards','budget','task_update','manage_access'},
    'quality_reviewer': {'task_update'},
    'client': {'approve','task_update'},
}
ROLE_DESCRIPTIONS = {
    'preparer': 'Prepare evidence, verify lines, propose adjustments and import recomputed returns. Review approval requires another person.',
    'reviewer': 'Disposition findings, resolve review notes, independently review judgments and sign reviewer approval.',
    'partner': 'Review and sign partner approval, freeze a ready filing, and open amendments.',
    'firm_administrator': 'Manage staff roles, access permissions, firm standards, budgets and administrative tasks.',
    'quality_reviewer': 'Inspect masked evidence, tie-outs, review decisions and audit history. Mark your review checkpoint and respond to assigned tasks; no tax edits, sign-offs, exports or unmasking.',
    'client': 'Answer your assigned questions and approve your return after partner sign-off.',
}
REVIEW_VIEWS = ['overview','reconciliation','documents','records','changes','review','activity','firm']
ROLE_VIEWS = {
    'preparer': REVIEW_VIEWS + ['filing'],
    'reviewer': REVIEW_VIEWS + ['filing'],
    'partner': REVIEW_VIEWS + ['filing'],
    'quality_reviewer': REVIEW_VIEWS,
    'firm_administrator': ['firm','access'],
    'client': ['overview'],
}

TAX_STAFF = ['preparer','reviewer','partner','quality_reviewer']
ACCESS_FEATURES = [
    dict(id='case_calculations',label='Document calculations and completeness',detail='Save derivations, outside-filing conclusions and related-return work.',actions=['calculation','outside_filing','related_review'],roles=['preparer','reviewer','partner']),
    dict(id='adjustment_approval',label='Review estimated adjustments',detail='Independently approve changes and their inclusion in the estimated effect.',actions=['review_adjustment'],roles=['reviewer','partner']),
    dict(id='case_lifecycle',label='Record case filing and carryforward',detail='Record simulated filing events and roll a frozen engagement forward.',actions=['filing_event','roll_forward'],roles=['partner']),
    dict(id='retention',label='Manage retention holds',detail='Place or release a legal hold with a recorded reason.',actions=['retention_policy'],roles=['firm_administrator']),
    dict(id='engagement_team',label='Manage engagement team',detail='Designate the lead preparer, reviewer, partner and due date.',actions=['manage_team'],roles=['firm_administrator','partner']),
    dict(id='form_allocation',label='Allocate forms',detail='The engagement reviewer or partner can delegate form ownership.',actions=['assign_form'],roles=['reviewer','partner']),
    dict(id='form_handoffs',label='Submit and review assigned forms',detail='Move your assigned work through preparation and independent review.',actions=['form_stage'],roles=['preparer','reviewer','partner']),
    dict(id='verification',label='Verify tie-outs',detail='Record and undo evidence-backed line verifications.',actions=['verify','undo_verify'],roles=TAX_STAFF),
    dict(id='evidence',label='Manage evidence',detail='Attach evidence, link records and disposition documents.',actions=['evidence','link','document'],roles=TAX_STAFF),
    dict(id='notes',label='Create review notes',detail='Add review notes, including notes that block filing.',actions=['note'],roles=TAX_STAFF),
    dict(id='judgments',label='Document judgments',detail='Record decisions, supporting evidence and authority.',actions=['judgment'],roles=TAX_STAFF),
    dict(id='assignments',label='Create assignments',detail='Assign work and prepare questions for clients.',actions=['task'],roles=TAX_STAFF),
    dict(id='adjustments',label='Propose adjustments',detail='Prepare adjustments and import recomputed returns. Preparer role required.',actions=['adjust','undo_adjust','import_version','add_line'],roles=['preparer']),
    dict(id='review_decisions',label='Approve review decisions',detail='Disposition findings, resolve notes and review judgments independently.',actions=['resolve','resolve_note','review_judgment'],roles=['reviewer','partner']),
    dict(id='signoff',label='Sign off',detail='Sign at the assigned role level. Independent review and ordering still apply.',actions=['sign'],roles=['preparer','reviewer','partner']),
    dict(id='filing',label='Freeze filing and open amendments',detail='Partner role and all filing prerequisites required.',actions=['freeze','amend'],roles=['partner']),
    dict(id='versions',label='Change working version',detail='Select an existing engine version and reopen review.',actions=['version'],roles=['preparer','reviewer','partner']),
    dict(id='export',label='Export masked workpaper',detail='Download the masked evidence and review record.',actions=['export'],roles=TAX_STAFF),
    dict(id='sensitive',label='Access sensitive data',detail='View identifiers and download full archives with a recorded business reason.',actions=['reveal','export_full'],roles=TAX_STAFF),
    dict(id='standards',label='Edit firm standards',detail='Change variance thresholds. Changes reopen sign-offs.',actions=['standards'],roles=['firm_administrator']),
    dict(id='budget',label='Edit budgets',detail='Set budget hours by work area.',actions=['budget'],roles=['firm_administrator']),
    dict(id='time',label='Log time',detail='Record time against engagement budget areas.',actions=['time'],roles=TAX_STAFF+['firm_administrator']),
]

def effective_user(s,u):
    original=STAFF[u['id']]
    saved=s.get('user_access',{}).get(u['id'],{})
    result=copy.deepcopy(original)
    result['role']=saved.get('role',original['role'])
    result['access_overrides']=copy.deepcopy(saved.get('overrides',{}))
    mode=result['access_overrides'].get('sensitive','default')
    result['sensitive_data_clearance']=(mode=='allow' or mode=='default' and original.get('sensitive_data_clearance',False)) and result['role'] in TAX_STAFF
    return result

def capabilities(u,s=None):
    if s is not None:u=effective_user(s,u)
    actions=set(ROLE_ACTIONS.get(u['role'],set())) | features.actions(u['role'])
    if u['role'] in {'firm_administrator','partner'}:actions.add('manage_team')
    if u['role'] in {'reviewer','partner'}:actions.add('assign_form')
    if u['role'] in EDITORS:actions.add('form_stage')
    if u['role'] in EDITORS:actions.update({'export','seen','time'})
    if u['role']=='quality_reviewer':actions.update({'seen','time'})
    if u['role']=='firm_administrator':actions.add('time')
    if u['role'] in EDITORS and u.get('sensitive_data_clearance'):actions.update({'reveal','export_full'})
    for feature in ACCESS_FEATURES:
        mode=u.get('access_overrides',{}).get(feature['id'],'default')
        if mode=='deny':actions.difference_update(feature['actions'])
        elif mode=='allow' and u['role'] in feature['roles']:actions.update(feature['actions'])
    custom=bool(u.get('access_overrides'))
    description=ROLE_DESCRIPTIONS.get(u['role'],'') if not custom else 'Custom access assigned by your administrator. Available controls reflect your current permissions; independent review and filing prerequisites still apply.'
    views=list(ROLE_VIEWS.get(u['role'],[]))
    if ('export' in actions or 'export_full' in actions) and 'filing' not in views:views.append('filing')
    return dict(actions=sorted(actions),views=views,description=description)

def access_directory(s):
    people=[]
    for original in STAFF.values():
        u=effective_user(s,original);saved=s.get('user_access',{}).get(u['id'],{})
        defaults={}
        for role in ROLE_ACTIONS:
            candidate={**original,'role':role,'access_overrides':{}}
            actions=capabilities(candidate)['actions']
            defaults[role]={f['id']:all(a in actions for a in f['actions']) for f in ACCESS_FEATURES}
        people.append(dict(id=u['id'],name=u['name'],role=u['role'],client=original['role']=='client',overrides=u['access_overrides'],defaults=defaults,actions=capabilities(u)['actions'],updated_at=saved.get('at'),updated_by=saved.get('actor'),reason=saved.get('reason')))
    return dict(people=people,features=ACCESS_FEATURES,roles=[r for r in ROLE_ACTIONS if r!='client'],history=[e for e in reversed(s['events']) if e['action']=='manage_access'])

def budget_hours(s):
    return s.get('budget_hours',PACKET['firm']['budget_hours'])
AREAS = ['Intake & identity', 'Wages & stock compensation', 'Investments & digital assets', 'Business', 'Rentals & sale', 'Pass-throughs & basis', 'Retirement & foreign', 'Deductions & credits', 'Payments', 'California', 'Outside filings']

def now(): return datetime.now(timezone.utc).isoformat()
def digest(obj): return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
def money(v): return float(Decimal(str(v)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP))
def whole(v): return int(Decimal(str(v)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
def initial():
    return features.ensure(dict(revision=0, version='v3', adjustments={}, verifications={}, resolutions={}, notes=[], judgments=[], evidence=[], links=[], documents={}, areas={}, steps={}, signatures={}, approvals={}, tasks=[], time=[], events=[], snapshots=[], frozen=False, amendment=0, replay=-1, standards=copy.deepcopy(PACKET['firm']['starter_standards']), seen={}, imported_versions=[], integrated_adjustments=[]))

class ClosingConnection(sqlite3.Connection):
    def __exit__(self,*args):
        try:return super().__exit__(*args)
        finally:self.close()

def connect():
    database_url=os.environ.get('DATABASE_URL')
    if database_url:c=storage.PostgresConnection(database_url)
    else:
        if os.environ.get('RENDER')=='true':raise RuntimeError('DATABASE_URL is required on free Render; local storage is ephemeral.')
        DB.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(DB, timeout=10, factory=ClosingConnection)
    c.execute('CREATE TABLE IF NOT EXISTS workpaper (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL)')
    try:storage.enforce_retention(c)
    except Exception:
        c.close();raise
    c.execute('INSERT OR IGNORE INTO workpaper VALUES (1, ?)', (storage.encode(initial()),))
    c.commit()
    return c

def read_state():
    with connect() as c: return features.ensure(storage.decode(c.execute('SELECT payload FROM workpaper WHERE id=1').fetchone()[0]))

def versions(s): return PACKET['return_versions'] + s.get('imported_versions', [])
def version(s):
    base=next(v for v in versions(s) if v['version']==s['version'])
    added=[l for l in s.get('supplemental_lines',[]) if l['version']==s['version'] and l['key'] not in {x['key'] for x in base['lines']}]
    return {**base,'lines':base['lines']+added} if added else base
def lines(s): return {l['key']: l for l in version(s)['lines']}
def effective(s, key): return s['adjustments'].get(key, {}).get('value', lines(s)[key]['value'])

def nonmonetary(line):
    return bool(re.search(r'\bmiles\b|\bdays\b|\bratio\b|\bpercentage\b|\bpercent\b|\bsq ft\b|divided by',line['label'],re.I))

def effect_rates(s):
    rates=copy.deepcopy(version(s)['tax_effect_rates'])
    for category,fed,ca in [('federal_credit',-1,0),('california_credit',0,-1),('federal_payment',0,0),('california_payment',0,0),('nonmonetary',0,0)]:
        rates[category]=dict(federal_per_dollar=fed,california_per_dollar=ca)
    return rates

def downstream(s, refs):
    found = set(refs)
    while True:
        found.update('asset:'+a['asset_id'] for a in version(s)['assets'] if found.intersection(a.get('sources',[])))
        new = {l['key'] for l in version(s)['lines'] if found.intersection(l['inputs'] + l['sources'] + s.get('calculations',{}).get(l['key'],{}).get('refs',[]))}
        if new.issubset(found): return sorted(found)
        found.update(new)

def resolve(ref, s):
    if ref in lines(s): return lines(s)[ref]
    if ref.startswith('doc:'):
        ident, pg = ref[4:].split('#page')
        return next(p for d in PACKET['documents'] if d['id']==ident for p in d['pages'] if p['page']==int(pg))
    if re.fullmatch(r'D\d+', ref): return next(d for d in PACKET['documents'] if d['id']==ref)
    if ref.startswith('ev-'): return next(e for e in PACKET['extracted_values'] if e['id']==ref)
    if ref.startswith(('qa-', 'msg-', 'call-')):
        return next(e for values in PACKET['client'].values() for e in values if e['id']==ref)
    if ref.startswith(('py:/', 'agency:/')):
        obj = PACKET['prior_years' if ref.startswith('py:') else 'tax_agency_records']
        for k in ref.split(':/',1)[1].split('/'):
            k = k.replace('~1','/').replace('~0','~')
            obj = obj[int(k)] if isinstance(obj,list) else obj[k]
        return obj
    if ref.startswith('asset:'): return next(a for a in version(s)['assets']+PACKET['prior_years']['asset_records'] if a['asset_id']==ref[6:])
    if ref.startswith('household:'): return next(p for p in PACKET['household']['people'] if p['id']==ref[10:])
    if ref.startswith('timeline:'): return next(t for t in PACKET['timeline'] if t['id']==ref[9:])
    if ref.startswith('ref:param.'): return PACKET['engine_reference']['parameters'][ref[10:]]
    if ref.startswith('ref:fx.SEK.'): return PACKET['fx_rates']['SEK_per_USD'][ref[11:]]
    if ref.startswith('evidence:'): return next(e for e in s['evidence'] if e['id']==ref)
    return features.resolve(ref,s)

def checks(s):
    ls=lines(s); result=[]
    def add(ident,title,key,expected,refs,detail,kind='Independent check',severity='high'):
        actual=ls.get(key,{}).get('value')
        result.append(dict(id=ident,title=title,key=key,actual=actual,expected=expected,delta=money(expected-actual) if isinstance(expected,(int,float)) and isinstance(actual,(int,float)) else None,refs=refs,detail=detail,kind=kind,severity=severity,affected=downstream(s,[key]),resolution=s['resolutions'].get(ident)))
    add('duplicate-interest','Bank sweep interest counted twice','SchB.1.2',0,['doc:D28#page1','doc:D29#page1'], 'Both statements identify the same Northlake bank sweep account ending 7731 and $1,840. Exclude the duplicate only after documenting the match.')
    add('duplicate-revenue','Card receipts already included in books','SchC.1',151300,['doc:D14#page1','doc:D15#page3','doc:D21#page1'],'The deposit detail explicitly includes the $12,400 Paywell receipts in project revenue. The engine adds them again.')
    mileage=PACKET['documents'][22]['pages']
    unique={}
    for p in mileage:
        body=p['printed_content']; trips=re.findall(r'\d{4}-\d{2}-\d{2}[^;]*?\d+ mi\b', body)
        if trips: unique[';'.join(trips)]=sum(int(re.search(r'(\d+) mi$',t).group(1)) for t in trips)
    add('duplicate-mileage','The mileage log includes a duplicate page','SchC.44a',sum(unique.values()),['doc:D23#page2','doc:D23#page3'],'Independent trip summation deduplicates identical trip sequences. Page 3 is a second scan of page 2; 3,700 miles were counted twice.')
    for lot,proceeds,basis in [('N1',19240,19100),('N3',18480,19100),('N4',15300,9420)]:
        key=next(k for k in ls if k.endswith('.'+lot))
        add('basis-'+lot,'RSU supplemental basis not applied · '+lot,key,proceeds-basis,['doc:D11#page2','doc:D28#page3'],f'The supplemental statement gives adjusted basis of ${basis:,.2f}. The engine uses zero. Match acquisition, quantity and sale before approval.')
    add('missing-lot','A sale on page 32 never reached the return','F8949.B.M18',-60,['doc:D31#page32'],'M18: proceeds $250 less basis $310 = $60 loss. The original detail subtotal omits this page. Add the missing sale as working detail and adjust the related subtotal with an evidence-backed estimate; a note alone does not insert the amount.')
    rate=PACKET['fx_rates']['SEK_per_USD']['2025_average']
    add('foreign-rate','Foreign interest uses the prior-year FX rate','SchB.1.6',whole(18450/rate),['doc:D36#page1','ref:fx.SEK.2025_average'],'SEK 18,450 / '+str(rate)+' (packet 2025 average). The engine uses the 2024 rate of 10.56.')
    add('mortgage-duplicate','Payoff interest included a second time','SchA.8a',19697,['doc:D55#page1','doc:D56#page1'],'The $2,150 payoff interest is already included in the $13,900 Form 1098 amount. $13,900 + $997 + $4,800 = $19,697.')
    irs=sum(t['amount'] for t in PACKET['tax_agency_records']['irs_account_transcript_2025'][0]['transactions'] if t['code']=='670')
    add('federal-payments','Estimated payments disagree with IRS records','F1040.26',irs,['agency:/irs_account_transcript_2025/0','qa-41'],'The client estimated the fourth payment at $4,000; the IRS transcript records $3,000. Total confirmed estimates: $12,000.')
    ca=next((l['key'] for l in ls.values() if l['rule']=='R-CA-ESTIMATED-PAYMENTS'),None)
    if ca: add('state-payments','A California payment belongs to tax year 2024',ca,10500,['doc:D68#page1','agency:/ftb_account'],'The September $3,500 payment was designated 2024 and remains a 2024 credit. Obtain a transfer before treating it as a 2025 payment.')
    add('utilities','Personal use remains in business utilities','SchC.25',2172,['doc:D15#page2','call-01'],'Client call: 70% of $2,160 telephone + 50% of $1,320 internet = $2,172. Requires documented business-use judgment.',kind='Judgment required')
    add('software','Personal subscription in business expenses','SchC.27a.1',6634,['doc:D15#page1','call-01'],'The client identified $216 Spotify Family as personal. $6,850 minus $216 = $6,634.')
    add('vehicle-gift','Vehicle valuation conflicts with sale proceeds','F8283.A1.vehicle',2900,['doc:D66#page1','qa-39'],'The engine uses donor estimated value $6,000; Form 1098-C shows $2,900 proceeds. Reviewer must document the applicable treatment and authority.',kind='Judgment required')
    add('health-eligibility','Health insurance eligibility needs a decision','Sch1.17',None,['qa-25','doc:D25#page1'],'Client reports eligibility for employer family coverage. Review the deduction and record authority; no legal conclusion is inferred from the extraction.',kind='Judgment required')
    add('hvac','Full HVAC replacement classified as repairs','SchE.14A',None,['doc:D47#page1','call-01'],'A new heat pump, air handler and line set may require capitalization and depreciation. Record treatment, authority and asset impact.',kind='Judgment required')
    add('ca-wages','California wages conflict with move-date paystub','SchCA540NR.1.E',None,['doc:D73#page1','doc:D09#page1','qa-45'],'Halvorsen W-2 reports $111,300 California wages, while move-date paystub shows $22,469. Confirm sourcing and stock-compensation allocation.',kind='Judgment required')
    for d in version(s)['diagnostics']:
        if d['severity']=='warning': add('engine-'+d['code'],d['code'].replace('_',' ').title(),d['refs'][0] if d['refs'] else '',None,d['refs'],d['message'],'Engine diagnostic','medium')
    # R-SUM is explicitly an arithmetic combination, not necessarily addition.
    # Independently check only unambiguous carries and explicit additive formulas.
    for l in ls.values():
        if l['rule']=='R-CARRY' and len(l['inputs'])==1 and l['inputs'][0] in ls:
            expected=ls[l['inputs'][0]]['value']
            if l['value']!=expected: add('carry-'+l['key'],'Carried value does not agree',l['key'],expected,l['inputs'],'Independent equality check of a carry rule.')
    sums=['SchB.2','SchB.6','SchC.28','SchA.17','F1040.9','F1040.14','F1040.18','F1040.24','F1040.25d','F1040.33']
    differences=['SchC.29','SchC.31','F1040.11','F1040.15','F1040.22','F1040.37']
    for key in sums+differences:
        l=ls.get(key)
        if not l or not l['inputs']:continue
        values=[Decimal(str(ls[k]['value'])) for k in l['inputs']]
        expected=sum(values) if key in sums else values[0]-sum(values[1:])
        if key in ['F1040.15','F1040.22','F1040.37']:expected=max(Decimal(0),expected)
        expected=whole(expected)
        if l['value']!=expected:add('arithmetic-'+key,'Independent arithmetic does not agree',key,expected,l['inputs'],'Explicit addition/subtraction formula, evaluated independently of the engine. Inspect the component lines before approval.')
    return result

def blockers(s):
    b=[]
    w=workflow(s)
    if any(not assigned_person(s,w['team'].get(r,''),r) for r in ['preparer','reviewer','partner']):b.append('Assign a lead preparer, reviewer and partner')
    if any(f['stage']!='reviewed' for f in w['forms']):b.append('All forms require completed independent review')
    pending=[c for c in checks(s) if c['id'] not in s['resolutions']]
    if pending:b.append(f'{len(pending)} unresolved reconciliation findings')
    if any(not n.get('resolved') for n in s['notes']):b.append('Open review notes')
    missing=[d for d in PACKET['documents'] if d['id'] not in s['documents'] or s['documents'][d['id']]['status']=='pending']
    if missing:b.append(f'{len(missing)} documents need an explicit disposition')
    if len(s['areas'])<len(AREAS):b.append('All review areas must be considered')
    unverified=[l for l in version(s)['lines'] if l['key'] not in s['verifications']]
    if unverified:b.append(f'{len(unverified)} return lines still require verification')
    for step in s['standards']['required_steps']:
        if step not in s['steps']:b.append(step)
    for role in ['preparer','reviewer','partner']:
        if role not in s['signatures']:b.append(role.title()+' signature required')
        elif s['signatures'][role].get('content_hash')!=features.review_hash(s):b.append(role.title()+' signature needs renewal for changed review content')
    if not all(s['approvals'].get(u['id'],{}).get('package_hash')==features.package_hash(s) for u in PACKET['firm']['client_users']):b.append('Both clients must approve this revision and authorize e-filing')
    b.extend(features.extra_blockers(s))
    if not any(j.get('subject')=='ca-amt' and j.get('reviewed_by') and j['reviewed_by']!=j['actor'] for j in s['judgments']):b.append('California AMT requires an independently reviewed calculation (judgment subject: ca-amt)')
    if any(not j.get('reviewed_by') for j in s['judgments']):b.append('Professional judgments require independent review')
    return list(dict.fromkeys(b))

def event(s,u,action,payload):
    prev=s['events'][-1]['hash'] if s['events'] else '0'*64
    e=dict(id=len(s['events'])+1,at=now(),actor=u['id'],name=u['name'],role=u.get('role','system'),action=action,payload=copy.deepcopy(payload),previous_hash=prev)
    e['hash']=digest(e);s['events'].append(e)

def invalidate(s):
    if s['signatures'] or s['approvals']:
        s['signatures']={};s['approvals']={}
    for step in ['Reviewer sign-off','Partner sign-off','Client approval and e-file authorization']:s['steps'].pop(step,None)

def invalidate_review_confirmation(s,role):
    # Confirmation records do not replace preparer work or reopen its handoff.
    levels=['reviewer','partner'] if role=='reviewer' else ['partner']
    for level in levels:
        s['signatures'].pop(level,None)
        s['steps'].pop(level.title()+' sign-off',None)
    s['approvals']={}
    s['steps'].pop('Client approval and e-file authorization',None)

def require(ok,msg):
    if not ok:raise ValueError(msg)

FORM_STAGES={'unassigned':'Unassigned','assigned':'Assigned','in_preparation':'In preparation','ready_for_review':'Ready for review','under_review':'Under review','changes_requested':'Changes requested','reviewed':'Reviewed'}

def assigned_person(s,ident,role):
    return bool(ident in STAFF and effective_user(s,STAFF[ident])['role']==role)

def form_assignment(s,form):
    team=s.get('engagement',{});saved=s.get('form_work',{}).get(form,{})
    result={key:saved.get(key) or team.get(key,'') for key in ['preparer','reviewer','due']}
    result.update(form=form,stage=saved.get('stage','assigned'),override=any(saved.get(k) for k in ['preparer','reviewer','due']))
    if not assigned_person(s,result['preparer'],'preparer') or not assigned_person(s,result['reviewer'],'reviewer'):result['stage']='unassigned'
    result['stage_label']=FORM_STAGES[result['stage']]
    result['reason']=saved.get('reason','')
    return result

def workflow(s,operational=False):
    forms=[form_assignment(s,f) for f in sorted({l['form'] for l in version(s)['lines']})]
    team=s.get('engagement',{})
    stages=[f['stage'] for f in forms]
    if s['frozen']:stage='Filed'
    elif not all(assigned_person(s,team.get(r,''),r) for r in ['preparer','reviewer','partner']) or 'unassigned' in stages:stage='Unassigned'
    elif 'partner' in s['signatures']:stage='Signed off'
    elif 'reviewer' in s['signatures']:stage='Ready for partner sign-off'
    elif 'changes_requested' in stages:stage='Changes requested'
    elif all(x=='reviewed' for x in stages):stage='Ready for reviewer sign-off' if 'preparer' in s['signatures'] else 'Ready for preparer sign-off'
    elif 'under_review' in stages:stage='Under review'
    elif all(x in ['ready_for_review','reviewed'] for x in stages):stage='Ready for review'
    elif any(x!='assigned' for x in stages):stage='In preparation'
    else:stage='Assigned'
    if operational:
        forms=[{k:v for k,v in f.items() if k!='reason'} for f in forms]
        team={k:v for k,v in team.items() if k in ['preparer','reviewer','partner','due']}
    return dict(team=team,forms=forms,stage=stage,counts={label:stages.count(key) for key,label in FORM_STAGES.items() if key in stages})

def reopen_form_work(s,reason,forms=None):
    for f in {l['form'] for l in version(s)['lines']}:
        if forms is not None and f not in forms:continue
        row=s.setdefault('form_work',{}).setdefault(f,{})
        if row.get('stage') in ['ready_for_review','under_review','reviewed']:
            row.update(stage='changes_requested',reason=reason,at=now(),actor='system')

def changed_forms(s,p):
    rows=version(s)['lines'];keys=set(p.get('keys',[]))
    keys.update(x for x in [p.get('key'),p.get('target'),p.get('source')] if x)
    refs=set(p.get('refs',[]));refs.update(x for x in [p.get('id'),p.get('source'),p.get('target')] if x)
    for c in checks(s):
        if c['id']==p.get('id'):keys.update([c['key'],*c['affected']])
    for n in s['notes']:
        if n['id']==p.get('id'):keys.add(n['target'])
    for j in s['judgments']:
        if j['id']==p.get('id'):keys.add(j['subject']);refs.update(j['refs'])
    refs.update(e['id'] for e in PACKET['extracted_values'] if e['document_id'] in refs)
    keys.update(l['key'] for l in rows if l['form'] in keys or any(r in refs or any(r.startswith('ev:'+x+':') for x in refs) for r in l['sources']))
    again=True
    while again:
        extra={l['key'] for l in rows if set(l['inputs']).intersection(keys)}-keys
        again=bool(extra);keys.update(extra)
    return {l['form'] for l in rows if l['key'] in keys} or None

def workflow_action(s,u,a,p):
    team=s.get('engagement',{});forms={l['form'] for l in version(s)['lines']}
    reason=str(p.get('reason','')).strip();require(reason,'Reason or handoff note is required.')
    def due(value):
        require(isinstance(value,str),'Invalid due date.')
        if value:
            try:datetime.strptime(value,'%Y-%m-%d')
            except ValueError:raise ValueError('Use a valid due date (YYYY-MM-DD).')
        return value
    if a=='manage_team':
        require(u['role']=='firm_administrator' or not team.get('partner') or u['id']==team['partner'],'Only the engagement partner or administrator can change the team.')
        for r in ['preparer','reviewer','partner']:require(assigned_person(s,p.get(r,''),r),'Choose a current '+r+'.')
        before={f:form_assignment(s,f) for f in forms}
        s['engagement']={r:p[r] for r in ['preparer','reviewer','partner']}
        s['engagement'].update(due=due(p.get('due','')),actor=u['id'],at=now(),reason=reason)
        changed={f for f in forms if any(before[f][r]!=form_assignment(s,f)[r] for r in ['preparer','reviewer'])}
        reopen_form_work(s,'Team assignment changed; review the handoff.',changed)
        p['before']=team
        return
    f=p.get('form');require(f in forms,'Choose a current return form.')
    row=form_assignment(s,f)
    if a=='assign_form':
        require(u['id'] in [team.get('reviewer'),team.get('partner')],'Only the engagement reviewer or partner can allocate forms.')
        for r in ['preparer','reviewer']:require(not p.get(r) or assigned_person(s,p[r],r),'Choose a current '+r+'.')
        saved=s.setdefault('form_work',{}).setdefault(f,{})
        saved.update(preparer=p.get('preparer',''),reviewer=p.get('reviewer',''),due=due(p.get('due','')),actor=u['id'],at=now(),assignment_reason=reason)
        if any(row[r]!=form_assignment(s,f)[r] for r in ['preparer','reviewer']):reopen_form_work(s,'Assignment changed; review the handoff.',{f})
        p['before']=row
        return
    step=p.get('stage');current=row['stage'];is_preparer=u['id']==row['preparer'] and u['role']=='preparer';is_reviewer=u['id']==row['reviewer'] and u['role']=='reviewer'
    allowed={'in_preparation':is_preparer and current in ['assigned','changes_requested'], 'ready_for_review':is_preparer and current in ['in_preparation','changes_requested'], 'under_review':is_reviewer and current=='ready_for_review', 'changes_requested':is_reviewer and current in ['ready_for_review','under_review','reviewed'], 'reviewed':is_reviewer and current=='under_review'}
    require(allowed.get(step,False),'This handoff is not available to you at the current stage.')
    rows=[l for l in version(s)['lines'] if l['form']==f];keys={l['key'] for l in rows}
    if step in ['ready_for_review','reviewed']:
        require(all(k in s['verifications'] and s['verifications'][k].get('version')==s['version'] and s['verifications'][k].get('value')==effective(s,k) for k in keys),'Verify every current amount in this form before handing it off.')
        require(not features.adjustment_blockers(s,keys),'Review the form adjustments and resolve overlapping estimated effects first.')
    if step=='reviewed':
        require(not any(c['id'] not in s['resolutions'] and (c['key'] in keys or keys.intersection(c['affected'])) for c in checks(s)),'Disposition the findings affecting this form first.')
        require(not any(not n.get('resolved') and n['target'] in keys|{f,'engagement'} for n in s['notes']),'Resolve blocking review notes first.')
        prepared={s['verifications'][k]['actor'] for k in keys}
        prepared.update(e['actor'] for e in s['events'] if (e['action'] in ['adjust','calculation','add_line'] or e['action']=='verify' and e.get('role')=='preparer') and (e['payload'].get('key') in keys or keys.intersection(e['payload'].get('keys',[]))))
        require(u['id'] not in prepared,'You cannot review a form you prepared or verified.')
    s.setdefault('form_work',{}).setdefault(f,{}).update(stage=step,reason=reason,actor=u['id'],at=now())
    p['before']=current

def mutate(s,u,a,p):
    u=effective_user(s,u)
    require(a in capabilities(u)['actions'],'This role is not authorized for this action.')
    role=u['role']; work=role in EDITORS
    if a not in ['seen','time','amend','approve','manage_access','filing_event','notice_response','roll_forward','nextyear_update','retention_policy']:
        require(not s['frozen'],'Filed workpaper is frozen. Open an amendment first.')
    def editor():require(work or role=='quality_reviewer','This role cannot modify the workpaper.')
    def text(k):
        v=str(p.get(k,'')).strip(); require(bool(v),k.replace('_',' ').title()+' is required.');return v
    def refs():
        rr=p.get('refs',[]);require(isinstance(rr,list) and len(rr)>0,'At least one evidence reference is required.')
        for r in rr:resolve(r,s)
        return rr
    material=True
    if a in features.ACTIONS:
        material=features.mutate(s,u,a,p)
    elif a in ['manage_team','assign_form','form_stage']:
        workflow_action(s,u,a,p)
        if a=='form_stage' and p.get('stage')!='changes_requested':material=False
    elif a=='manage_access':
        ident=text('user_id');require(ident in STAFF,'Unknown person.')
        require(STAFF[ident]['role']!='client','Client identities cannot be reassigned to staff roles.')
        assigned=text('role');require(assigned in ROLE_ACTIONS and assigned!='client','Choose a staff role.')
        overrides=p.get('overrides',{});require(isinstance(overrides,dict),'Invalid access overrides.')
        catalog={f['id']:f for f in ACCESS_FEATURES};clean={}
        for key,mode in overrides.items():
            require(key in catalog and mode in ['default','allow','deny'],'Invalid access permission.')
            require(assigned in catalog[key]['roles'],'This permission requires a different role: '+catalog[key]['label'])
            if mode!='default':clean[key]=mode
        remaining=[person for person in STAFF.values() if person['id']!=ident and effective_user(s,person)['role']=='firm_administrator']
        require(assigned=='firm_administrator' or remaining,'At least one firm administrator must remain.')
        before=effective_user(s,STAFF[ident]);reason=text('reason')
        s.setdefault('user_access',{})[ident]=dict(role=assigned,overrides=clean,actor=u['id'],at=now(),reason=reason)
        if not s['frozen']:reopen_form_work(s,'Assigned staff access changed; review the handoff.',{f for f in {l['form'] for l in version(s)['lines']} if ident in [form_assignment(s,f)['preparer'],form_assignment(s,f)['reviewer']]})
        p.clear();p.update(user_id=ident,role=assigned,overrides=clean,reason=reason,before=dict(role=before['role'],overrides=before['access_overrides']))
        if not s['frozen']:invalidate(s)
        material=False
    elif a=='verify':
        editor();keys=p.get('keys',[]);require(0<len(keys)<=100,'Select 1–100 lines.')
        method=text('method');require(method in s['standards']['verification_types'],'Choose a firm verification method.')
        rr=refs();note=text('note')
        confirmation=role in ['reviewer','partner']
        p['verification_kind']='review_confirmation' if confirmation else 'preparer_tie_out'
        store=s.setdefault('review_confirmations',{}).setdefault(u['id'],{}) if confirmation else s['verifications']
        p['_before']={k:copy.deepcopy(store.get(k)) for k in keys}
        for k in keys:
            require(k in lines(s),'Unknown line.')
            if confirmation:
                prepared=s['verifications'].get(k,{})
                require(prepared and prepared.get('value')==effective(s,k) and prepared.get('version')==s['version'],'A current preparer tie-out is required before reviewer confirmation: '+k)
                require(prepared['actor']!=u['id'] and not any(x.get('actor')==u['id'] for x in [s['adjustments'].get(k,{}),s.get('calculations',{}).get(k,{})]),'You cannot independently confirm your own work.')
            calculation=s.get('calculations',{}).get(k)
            if method=='recalculated' and calculation:
                current=features.calculate(s,calculation['expression'],calculation['refs']);require(abs(current['result']-effective(s,k))<=0.51,'Recorded calculation differs from '+k+'. Resolve the amount before marking it recalculated.')  # Preserve the calculation author's original record.
            store[k]=dict(actor=u['id'],at=now(),method=method,refs=rr,note=note,value=effective(s,k),version=s['version'],batch_event=len(s['events'])+1,kind=p['verification_kind'],preparation_hash=digest(s['verifications'].get(k)))
        if confirmation:
            invalidate_review_confirmation(s,role)
            material=False
    elif a=='undo_verify':
        editor();last=next((e for e in reversed(s['events']) if e['actor']==u['id'] and e['action']=='verify' and not any(z['action']=='undo_verify' and z['payload'].get('event_id')==e['id'] for z in s['events'])),None)
        require(last is not None,'No verification batch to undo.')
        confirmation=last['payload'].get('verification_kind')=='review_confirmation'
        store=s.setdefault('review_confirmations',{}).setdefault(u['id'],{}) if confirmation else s['verifications']
        for k in last['payload']['keys']:
            if store.get(k,{}).get('batch_event')==last['id']:
                before=last['payload'].get('_before',{}).get(k)
                if before:store[k]=before
                else:store.pop(k,None)
        p['event_id']=last['id']
        if confirmation:
            invalidate_review_confirmation(s,role)
            material=False
    elif a=='adjust':
        require(role=='preparer','Only preparers can propose adjustments.')
        k=text('key');require(k in lines(s),'The line must exist in the selected engine version.')
        v=p.get('value');require(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and abs(v)<1e14,'Enter a finite numeric value.')
        category=text('category');rates=effect_rates(s); require(category in rates,'Unknown effect category.')
        require(not nonmonetary(lines(s)[k]) or category=='nonmonetary','Use the nonmonetary category for miles, days or ratios. Recompute affected monetary lines separately.')
        old=lines(s)[k]['value'];require(isinstance(old,(int,float)),'Only numeric lines can be adjusted.')
        rr=refs();reason=text('reason');delta=money(v-old);effect_base=features.tax_effect_base(k,delta,category)
        s['adjustments'][k]=dict(key=k,original=old if lines(s)[k].get('engine_present',True) else None,value=v,delta=delta,effect_base=effect_base,reason=reason,refs=rr,category=category,actor=u['id'],at=now(),federal_estimate=money(effect_base*rates[category]['federal_per_dollar']),california_estimate=money(effect_base*rates[category]['california_per_dollar']))
        if category=='nonmonetary':s['adjustments'][k].update(federal_estimate=None,california_estimate=None)
        s['adjustments'][k].update(federal_balance_effect=-delta if category=='federal_payment' else None,california_balance_effect=-delta if category=='california_payment' else None)
        for target in downstream(s,[k]):s['verifications'].pop(target,None)
        for c in checks(s):
            if k in c['affected']:s['resolutions'].pop(c['id'],None)
    elif a=='undo_adjust':
        require(role=='preparer','Only preparers can revert adjustments.');key=text('key');s['adjustments'].pop(key,None);s['supplemental_lines']=[l for l in s.get('supplemental_lines',[]) if not (l['key']==key and l['version']==s['version'])];s['verifications']={};s['resolutions']={}
    elif a=='resolve':
        require(role in {'reviewer','partner'},'A reviewer or partner must disposition findings.')
        ident=text('id');require(ident in [c['id'] for c in checks(s)],'Unknown finding.')
        require(not any(j.get('actor')==u['id'] and j.get('subject')==ident for j in s['judgments']),'You cannot review your own judgment.')
        finding=next(c for c in checks(s) if c['id']==ident)
        require(not any(s['adjustments'].get(k,{}).get('actor')==u['id'] for k in finding['affected']),'You cannot review your own adjustment.')
        s['resolutions'][ident]=dict(actor=u['id'],at=now(),reason=text('reason'),refs=refs())
    elif a=='reopen':editor();s['resolutions'].pop(text('id'),None)
    elif a=='note':
        editor();s['notes'].append(dict(id=secrets.token_hex(6),text=text('text'),target=p.get('target','engagement'),blocking=True,actor=u['id'],at=now(),resolved=False))
    elif a=='resolve_note':
        require(role in {'reviewer','partner'},'Reviewer or partner required.')
        n=next(n for n in s['notes'] if n['id']==p['id']);n.update(resolved=True,resolution=text('reason'),resolved_by=u['id'],resolved_at=now())
    elif a=='judgment':
        editor();s['judgments'].append(dict(id=secrets.token_hex(6),subject=text('subject'),decision=text('decision'),authority=text('authority'),refs=refs(),actor=u['id'],at=now()))
    elif a=='review_judgment':
        require(role in {'reviewer','partner'},'Reviewer or partner required.')
        j=next(j for j in s['judgments'] if j['id']==p['id']);require(j['actor']!=u['id'],'You cannot review your own judgment.')
        j.update(reviewed_by=u['id'],reviewed_at=now(),review_reason=text('reason'))
    elif a=='evidence':
        editor();name=text('name');content=text('content'); require(len(content)<=7_000_000,'Maximum attachment size is 5 MB.')
        s['evidence'].append(dict(id='evidence:'+secrets.token_hex(6),name=name,content=content,mime=p.get('mime','text/plain'),encoding=p.get('encoding','text'),sha256=hashlib.sha256(content.encode()).hexdigest(),actor=u['id'],at=now(),target=p.get('target','engagement')))
    elif a=='link':
        editor();resolve(text('source'),s);resolve(text('target'),s);s['links'].append(dict(source=p['source'],target=p['target'],reason=text('reason'),actor=u['id'],at=now()))
    elif a=='document':
        editor();require(p.get('id') in [d['id'] for d in PACKET['documents']],'Unknown document.')
        require(p.get('status') in ['used','duplicate','superseded','outside_scope','pending'],'Invalid disposition.')
        s['documents'][p['id']]=dict(status=p['status'],reason=text('reason'),actor=u['id'],at=now())
    elif a=='area':editor();require(p.get('name') in AREAS,'Unknown area.');s['areas'][p['name']]=dict(reason=text('reason'),actor=u['id'],at=now(),refs=refs())
    elif a=='step':
        editor();name=text('name'); require(name in s['standards']['required_steps'],'Unknown step.')
        require(name not in ['Reviewer sign-off','Partner sign-off','Client approval and e-file authorization'],'Use the signature and approval controls for this step.')
        s['steps'][name]=dict(reason=text('reason'),refs=refs(),actor=u['id'],at=now())
    elif a=='sign':
        editor();level=role; require(level in ['preparer','reviewer','partner'],'Invalid signature role.')
        require(s.get('engagement',{}).get(level)==u['id'],'Only the assigned engagement '+level+' can sign.')
        stages=[f['stage'] for f in workflow(s)['forms']]
        require(all(x in ['ready_for_review','under_review','reviewed'] for x in stages),'Every form must be submitted for review first.')
        if level in ['reviewer','partner']:require(all(x=='reviewed' for x in stages),'Every form requires completed independent review first.')
        prepared={v['actor'] for v in list(s.get('calculations',{}).values())+list(s['adjustments'].values())+list(s['verifications'].values())+s['judgments']+list(s['documents'].values())+list(s['areas'].values())}
        require(level=='preparer' or u['id'] not in prepared,'You cannot review or sign off on work you prepared.')
        if level=='reviewer':require('preparer' in s['signatures'],'Preparer sign-off is required first.')
        if level=='partner':require('reviewer' in s['signatures'],'Reviewer sign-off is required first.')
        require(not any(not n['resolved'] for n in s['notes']),'Resolve all open review notes first.')
        require(not any(c['id'] not in s['resolutions'] for c in checks(s)),'Resolve reconciliation findings first.')
        require(not features.extra_blockers(s),'Complete adjustment approvals and outside-filing conclusions first.')
        s['signatures'][level]=dict(actor=u['id'],at=now(),revision=s['revision'],content_hash=features.review_hash(s),statement=text('statement'))
        if level in ['reviewer','partner']:s['steps'][level.title()+' sign-off']=s['signatures'][level]
        material=False
    elif a=='approve':
        require(role=='client','Client role required.');require(not s['frozen'],'Already frozen.');require('partner' in s['signatures'],'Partner sign-off is required before client approval.')
        s['approvals'][u['id']]=features.make_authorization(s,u,p)
        if len(s['approvals'])==2:s['steps']['Client approval and e-file authorization']={'at':now()}
        material=False
    elif a=='freeze':
        require(role=='partner','Only a partner can freeze filing.');require(not blockers(s),'Filing blocked: '+'; '.join(blockers(s)[:5]))
        s.setdefault('retention',{}).update(filed_at=now(),expires_at=features.retention_expiry());snapshot=copy.deepcopy(s);snapshot.pop('snapshots',None);s['snapshots'].append(dict(at=now(),hash=digest(snapshot),record=snapshot));s['frozen']=True;material=False
    elif a=='amend':
        require(role=='partner' and s['frozen'],'A partner can amend a frozen return.');text('reason');s['frozen']=False;s['amendment']+=1
    elif a=='version':
        editor();require(p.get('version') in [v['version'] for v in versions(s)],'Invalid version.');require(not s['adjustments'],'Revert adjustments before changing the engine version.');s['version']=p['version'];s['verifications']={};s['resolutions']={}
    elif a=='import_version':
        require(role=='preparer','A preparer must import recomputed forms.')
        v=copy.deepcopy(p.get('version'));require(isinstance(v,dict),'Upload a version JSON object.')
        template=version(s)
        for key in ['version','computed_at','lines','summary','tax_effect_rates','assets','diagnostics','documents_used','documents_superseded','carryovers_out']:
            require(key in v,'Missing version field: '+key)
        require(isinstance(v['version'],str) and re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',v['version']), 'Version ID must contain letters, numbers, hyphens or underscores.')
        require(v['version'] not in [x['version'] for x in versions(s)],'Version ID already exists.')
        require(isinstance(v['lines'],list) and 0<len(v['lines'])<=10000,'Invalid lines.')
        keys=set()
        for l in v['lines']:
            require(isinstance(l,dict) and all(k in l for k in ['key','value','form','line','label','jurisdiction','inputs','sources','rule']),'Malformed return line.')
            require(isinstance(l['key'],str) and l['key'] not in keys,'Duplicate or invalid line key.');keys.add(l['key'])
            require(isinstance(l['value'],(str,int,float)) and not isinstance(l['value'],bool),'Invalid line value.')
            if isinstance(l['value'],(int,float)):require(math.isfinite(l['value']),'Non-finite amount.')
            require(isinstance(l['inputs'],list) and isinstance(l['sources'],list),'Inputs and sources must be lists.')
        require(set(lines(s)).issubset(keys),'Imported version must retain existing line keys; use zero for removed lines and document the change.')
        for l in v['lines']:
            for r in l['inputs']:require(r in keys,'Missing input line: '+str(r))
            for r in l['sources']:
                if r not in keys and not r.startswith('asset:'):resolve(r,s)
        for k,adjust in s['adjustments'].items():
            actual=next(l['value'] for l in v['lines'] if l['key']==k)
            require(actual==adjust['value'],'Recomputed line does not incorporate proposed adjustment: '+k)
        for jurisdiction in ['federal','california']:
            require(all(isinstance(v['summary'].get(jurisdiction,{}).get(k),(int,float)) for k in template['summary'][jurisdiction]),'Missing numeric summary values.')
        for category,rate in template['tax_effect_rates'].items():
            require(category in v['tax_effect_rates'] and all(isinstance(v['tax_effect_rates'][category].get(k),(int,float)) for k in rate),'Invalid tax-effect rates.')
        require(isinstance(v['assets'],list) and isinstance(v['diagnostics'],list),'Invalid assets or diagnostics.')
        v['trigger']=text('reason');v['imported_by']=u['id'];v['imported_at']=now();v['source_sha256']=digest(p['version'])
        s.setdefault('integrated_adjustments',[]).append(dict(version=v['version'],adjustments=copy.deepcopy(s['adjustments']),at=now()))
        s.setdefault('imported_versions',[]).append(v);s['version']=v['version'];s['adjustments']={};s['verifications']={};s['resolutions']={};s['steps']={};s['areas']={}
    elif a=='standards':
        require(role=='firm_administrator','Only the firm administrator can change standards.');v=p.get('percent');amount=p.get('amount');require(isinstance(v,(int,float)) and 0<=v<=100 and isinstance(amount,(int,float)) and amount>=0,'Invalid thresholds.');s['standards']['variance_review'].update(flag_if_change_over_percent=v,and_over_amount=amount)
    elif a=='budget':
        area=text('area');hours=p.get('hours')
        require(area in PACKET['firm']['budget_hours'],'Unknown budget area.')
        require(isinstance(hours,(int,float)) and not isinstance(hours,bool) and math.isfinite(hours) and 0<hours<=10000,'Budget hours must be between 0 and 10,000.')
        s.setdefault('budget_hours',copy.deepcopy(PACKET['firm']['budget_hours']))[area]=hours
        material=False
    elif a=='task':
        editor();assignee=text('assignee');require(assignee in STAFF,'Unknown assignee.');target=p.get('target','engagement');require(target=='engagement' or target in lines(s) or target in {l['form'] for l in version(s)['lines']} or target in {c['id'] for c in checks(s)},'Choose an existing form, return line or finding.');s['tasks'].append(dict(id=secrets.token_hex(6),title=text('title'),target=target,assignee=assignee,due=text('due'),actor=u['id'],at=now(),status='open',client_visible=effective_user(s,STAFF[assignee])['role']=='client'))
    elif a=='task_update':
        t=next(t for t in s['tasks'] if t['id']==p['id']);require(work or t['assignee']==u['id'],'Task is not assigned to you.');t.update(status='answered' if role=='client' else 'done',answer=text('answer'),answered_by=u['id'],answered_at=now());eid='answer:'+secrets.token_hex(8);s.setdefault('answer_evidence',[]).append(dict(id=eid,task_id=t['id'],question=t['title'],answer=t['answer'],target=t.get('target','engagement'),actor=u['id'],at=now()));t['evidence_ref']=eid
    elif a=='time':
        require(role!='client','Staff only.');hours=float(p.get('hours',0));require(0<hours<=24,'Hours must be between 0 and 24.');area=text('area');require(area in PACKET['firm']['budget_hours'],'Unknown budget area.');s['time'].append(dict(area=area,hours=hours,actor=u['id'],at=now()));material=False
    elif a=='seen':s['seen'][u['id']]=len(s['events']);material=False
    else:raise ValueError('Unknown action.')
    if material:
        invalidate(s)
        if a in ['adjust','undo_adjust','verify','undo_verify','version','import_version','link','document','reopen','amend']:
            reopen_form_work(s,'Workpaper changed after submission; review before resubmitting.',None if a in ['version','import_version','amend'] else changed_forms(s,p))
        elif a in ['note','judgment','review_judgment','resolve','resolve_note','evidence']:
            completed={f for f in (changed_forms(s,p) or {l['form'] for l in version(s)['lines']}) if form_assignment(s,f)['stage']=='reviewed'}
            reopen_form_work(s,'Review record changed; review before resubmitting.',completed)
    s['revision']+=1;event(s,u,a,p);return s

_REDACTION_CACHE = None

def redaction_secrets():
    # The delivered packet is immutable; reuse its identifier inventory across records.
    global _REDACTION_CACHE
    if _REDACTION_CACHE is not None and _REDACTION_CACHE[0] is PACKET:
        return _REDACTION_CACHE[1]
    secret=set()
    def collect(x):
        if isinstance(x,dict):
            for k,v in x.items():
                if k=='account' or any(w in k.lower() for w in ['ssn','account_number','routing','ip_pin','ero_pin','efin','ptin','dob','license_number']):
                    if isinstance(v,(str,int)) and len(str(v))>=4:secret.add(str(v))
                collect(v)
        elif isinstance(x,list):
            for v in x:collect(v)
    collect(PACKET)
    for ev in PACKET['extracted_values']:
        if ev['value_type'] in ['ssn','account_number'] or any(w in ev['field'] for w in ['pin','license']):
            secret.add(str(ev['value']));secret.add(ev['text_as_read'])
    ordered=tuple(sorted(secret,key=len,reverse=True))
    _REDACTION_CACHE=(PACKET,ordered)
    return ordered

def redact(obj):
    # Redact embedded occurrences too, including document prose and free-text events.
    secret=redaction_secrets()
    def scrub(x):
        if isinstance(x,str):
            x=re.sub(r'\b\d{3}-\d{2}-\d{4}\b','•••-••-••••',x)
            for v in secret:
                if len(v)>=4:x=x.replace(v,'[REDACTED]')
            return x
        if isinstance(x,dict):return {k:('[REDACTED]' if k=='account' or any(w in k.lower() for w in ['ssn','account_number','routing','ip_pin','ero_pin','efin','ptin','dob','license_number']) else scrub(v)) for k,v in x.items()}
        if isinstance(x,list):return [scrub(v) for v in x]
        if str(x) in secret:return '[REDACTED]'
        return x
    out=scrub(obj)
    # Binary attachments cannot be safely text-redacted; withhold their payloads.
    def strip(x):
        if isinstance(x,dict):
            if x.get('encoding')=='base64':x['content']='[REDACTED: attachment requires sensitive-data clearance]'
            for v in x.values():strip(v)
        elif isinstance(x,list):
            for v in x:strip(v)
    strip(out);return out

def response(s,u,reveal=False):
    u=effective_user(s,u)
    staff=[effective_user(s,person) for person in STAFF.values()]
    # Project by responsibility before serialization: hiding navigation is not authorization.
    if u['role']=='firm_administrator':
        return redact(dict(user=u,staff=staff,capabilities=capabilities(u),administration=True,access=access_directory(s),
            workflow=workflow(s,operational=True),retention=s.get('retention',{}),
            administration_data=dict(budget_hours=budget_hours(s),deadlines=PACKET['firm']['deadlines'],
                hours_by_area={area:sum(t['hours'] for t in s['time'] if t['area']==area) for area in budget_hours(s)}),
            state=dict(revision=s['revision'],standards=s['standards'],frozen=s['frozen'],
                tasks=[t for t in s['tasks'] if t['assignee']==u['id']])))
    if u['role']=='client':
        return dict(user=u,staff=staff,capabilities=capabilities(u),client=True,state=dict(revision=s['revision'],tasks=[t for t in s['tasks'] if t['assignee']==u['id']],approvals={k:v for k,v in s['approvals'].items() if k==u['id']},frozen=s['frozen']),summary=version(s)['summary'],authorization_package=dict(package_hash=features.package_hash(s),estimate=features.estimate(s),version=s['version']),ready='partner' in s['signatures'])
    payload=dict(user=u,staff=staff,capabilities=capabilities(u),packet=PACKET,state=s,workflow=workflow(s),features=features.projection(s),checks=checks(s),blockers=blockers(s),areas=AREAS)
    return payload if reveal and 'reveal' in capabilities(u)['actions'] else redact(payload)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,obj,ctype='application/json'):
        body=json.dumps(obj,ensure_ascii=False,allow_nan=False).encode() if ctype=='application/json' else obj
        self.send_response(status);self.send_header('Content-Type',ctype+'; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'");self.end_headers();self.wfile.write(body)
    def user(self):
        if self.headers.get('X-Workpaper-Session'):return STAFF.get(SESSIONS.get(self.headers['X-Workpaper-Session'],''))
        cookie=dict(x.strip().split('=',1) for x in self.headers.get('Cookie','').split(';') if '=' in x)
        return STAFF.get(SESSIONS.get(cookie.get(f'wp_session_{self.server.server_port}',''),''))
    def do_GET(self):
        try:self.get_response()
        except storage.RetiredRecord as e:self.send(410,{'error':str(e)})

    def get_response(self):
        path=urlparse(self.path).path
        if path=='/health':return self.send(200,{'status':'ok'})
        if path=='/api/bootstrap':
            with LOCK:
                s=read_state()
                return self.send(200,dict(staff=[effective_user(s,u) for u in STAFF.values()],mode='local-demo'))
        if path.startswith('/api/'):
            u=self.user()
            if not u:return self.send(401,{'error':'Select a role to start the local demonstration.'})
            with LOCK:
                s=read_state();u=effective_user(s,u)
                if path=='/api/state':return self.send(200,response(s,u))
                if path=='/api/export':
                    if 'export' not in capabilities(u)['actions']:return self.send(403,{'error':'This role cannot export tax records.'})
                    return self.send(200,dict(format='miraflores-workpaper-1',exported_at=now(),packet_sha256=digest(PACKET),record=response(s,u),export_scope='Masked, self-contained review record; attachment content withheld',retention='7 years after actual filing; production destruction requires an external retention service'))
            return self.send(404,{'error':'Not found'})
        files={'/':'index.html','/app.js':'app.js','/review.js':'review.js','/workspace.js':'workspace.js','/ownership.js':'ownership.js','/features.js':'features.js','/schedules.js':'schedules.js','/styles.css':'styles.css','/brand.css': 'brand.css', '/presentation.js':'presentation.js','/fraunces.woff2':'fraunces.woff2','/poppins.woff2':'poppins.woff2'}
        if path not in files:return self.send(404,{'error':'Not found'})
        f=ROOT/'web'/files[path];ct={'html':'text/html','js':'text/javascript','css':'text/css','woff2':'font/woff2'}[f.suffix[1:]];self.send(200,f.read_bytes(),ct)
    def do_POST(self):
        try:
            host=self.headers.get('Host','');origin=self.headers.get('Origin')
            allowed_hosts=[f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}']+[h for h in [os.environ.get('RENDER_EXTERNAL_HOSTNAME'),os.environ.get('WORKPAPER_HOSTNAME')] if h];require(host in allowed_hosts,'Untrusted host.')
            require(not origin or origin in ['http://'+host,'https://'+host],'Cross-origin request rejected.')
            require(self.headers.get('Content-Type','').startswith('application/json'),'JSON content type required.')
            size=int(self.headers.get('Content-Length',0));require(0<size<=8_000_000,'Invalid request size.')
            p=json.loads(self.rfile.read(size));path=urlparse(self.path).path
            if path=='/api/session':
                require(p.get('id') in STAFF,'Unknown user.');token=secrets.token_urlsafe(32);SESSIONS[token]=p['id']
                with LOCK:body=json.dumps(dict(response(read_state(),STAFF[p['id']]),session_token=token),ensure_ascii=False,allow_nan=False).encode()
                self.send_response(200);self.send_header('Set-Cookie',f'wp_session_{self.server.server_port}={token}; HttpOnly; SameSite=Strict; Path=/');self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body);return
            u=self.user();require(u is not None,'Select a role first.')
            if p.get('actor_id') is not None and p['actor_id']!=u['id']:
                return self.send(409,{'error':'The active role changed in another tab. Refresh before saving; no action was performed.'})
            with LOCK:
                with connect() as c:
                    c.execute('BEGIN IMMEDIATE');s=features.ensure(storage.decode(c.execute('SELECT payload FROM workpaper WHERE id=1').fetchone()[0]));u=effective_user(s,u)
                    if path=='/api/report':
                        scope=p.get('scope','review');require(scope in ['review','full','client'],'Invalid report scope.');require(scope!='full' or bool(str(p.get('reason','')).strip()),'A business reason is required for the full archive.');report=features.artifact(s,u,scope,p.get('notice'));event(s,u,'report_export',dict(scope=scope,notice=p.get('notice'),reason=p.get('reason','')));s['revision']+=1
                    elif path in ['/api/reveal','/api/export_full']:
                        permission='reveal' if path=='/api/reveal' else 'export_full'
                        if permission not in capabilities(u)['actions']:
                            return self.send(403,{'error':'This role cannot access unmasked tax records or full archives.'})
                        require(u.get('sensitive_data_clearance',False),'Sensitive-data clearance is required.')
                        require(bool(str(p.get('reason','')).strip()),'Business reason required.')
                        event(s,u,'unmasked_export' if path=='/api/export_full' else 'unmasked_view',{'scope':'entire case packet and workpaper','reason':str(p['reason'])});s['revision']+=1
                    else:
                        if p.get('revision')!=s['revision']:return self.send(409,{'error':'Another session changed this workpaper. Refresh and retry; your change was not saved.'})
                        s=mutate(s,u,p.get('action'),p.get('payload',{}))
                    c.execute('UPDATE workpaper SET payload=? WHERE id=1',(storage.encode(s),));c.commit()
                if path=='/api/report':return self.send(200,report)
                if path=='/api/export_full':return self.send(200,dict(format='miraflores-full-archive-1',exported_at=now(),packet_sha256=digest(PACKET),record=response(s,u,True),integrity=digest(response(s,u,True))))
                self.send(200,response(s,u,path=='/api/reveal'))
        except storage.RetiredRecord as e:self.send(410,{'error':str(e)})
        except (ValueError,KeyError,StopIteration,TypeError,IndexError) as e:self.send(400,{'error':str(e) or 'Invalid record or reference.'})
        except Exception as e:
            print(type(e).__name__,str(e));self.send(500,{'error':'The operation failed and was not committed.'})

def retention_worker():
    while True:
        threading.Event().wait(3600)
        try:
            with LOCK:connect().close()
        except storage.RetiredRecord:SESSIONS.clear()
        except Exception:print('Retention sweep failed; investigate storage before the next deadline.',flush=True)

features.bind(sys.modules[__name__])

if __name__=='__main__':
    port=int(os.environ.get('PORT','8765'))
    with connect() as c:storage.migrate_encryption(c)
    threading.Thread(target=retention_worker,daemon=True).start()
    print(f'Miraflores workpaper: http://127.0.0.1:{port} (local role-switching demonstration)',flush=True)
    ThreadingHTTPServer((os.environ.get('HOST','127.0.0.1'),port),Handler).serve_forever()
