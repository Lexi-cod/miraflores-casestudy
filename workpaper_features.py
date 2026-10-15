"""Evidence, case finalization, lifecycle and portable review records.

The supplied engine remains immutable. Estimates never replace computed totals.
"""
import ast
import base64
import copy
import html
import io
import json
import math
import operator
import secrets
import zipfile
import workpaper_calculations
from datetime import datetime, timezone

A = None

def retention_expiry():
    filed=datetime.now(timezone.utc)
    try:return filed.replace(year=filed.year+7).isoformat()
    except ValueError:return filed.replace(year=filed.year+7,day=28).isoformat()

def tax_effect_base(key,delta,category):
    if category=='schc_profit' and key.startswith('SchC.'):
        part=key.split('.')[1]
        expense_lines={str(n) for n in range(8,29)}|{'16a','16b','20a','20b','24a','24b','27a','27b','30'}
        if part in expense_lines:return -delta
    return delta

def bind(app):
    global A
    A = app

def ensure(s):
    s.setdefault('engagement', dict(A.PACKET['firm']['assignment_at_start'], due='2026-10-15', actor='packet', reason='Starting team supplied in firm.assignment_at_start'))
    for key, default in [('review_confirmations',{}),('supplemental_lines',[]),('adjustment_reviews',{}),('calculations',{}),('outside_filings',{}),('related_reviews',{}),('filing_events',[]),('notice_responses',{}),('next_years',{}),('retention',{'years':7,'legal_hold':False}),('answer_evidence',[])]:
        s.setdefault(key, copy.deepcopy(default))
    return s

OUTSIDE = [
    ('foreign-account','Foreign account reporting / FBAR',['D36','F8938.req'], 'Assess separately from Form 8938.'),
    ('dependent-return','Dependent’s own return',['related:0'], 'Confirm dependency treatment agrees with the household.'),
    ('scorp-state','S corporation and Oregon composite return',['related:1','D39','D40'], 'External preparer; reconcile K-1 and state support.'),
    ('partnership-state','Partnership and Arizona composite return',['related:2','D37','D38'], 'External administrator; reconcile K-1 and state supplement.'),
    ('business-information','Business information returns',['SchC.I','SchC.J'], 'Document contractor information-return obligations and completion.'),
]

def adjustment_status(s,key):
    a=s['adjustments'][key];r=s.get('adjustment_reviews',{}).get(key,{})
    valid=r.get('adjustment_hash')==A.digest(a)
    material=max(abs(a.get('federal_estimate') or 0),abs(a.get('california_estimate') or 0))>1000
    return {'reviewed':bool(valid and r.get('reviewer') and r['reviewer']!=a['actor']),
            'partner_required':material,'partner_approved':bool(valid and r.get('partner') and r['partner']!=a['actor']),
            'include':r.get('include',a['category']!='nonmonetary') if valid else a['category']!='nonmonetary',
            'record':r if valid else {}}

def estimate(s):
    selected=[a for k,a in s['adjustments'].items() if adjustment_status(s,k)['include']]
    overlaps=[]
    for i,a in enumerate(selected):
        for b in selected[i+1:]:
            if b['key'] in A.downstream(s,[a['key']]) or a['key'] in A.downstream(s,[b['key']]):overlaps.append([a['key'],b['key']])
    return dict(method='Packet marginal-rate estimate; not a recomputed return',
        federal_tax=sum(a.get('federal_estimate') or 0 for a in selected),
        california_tax=sum(a.get('california_estimate') or 0 for a in selected),
        federal_balance=sum((a.get('federal_estimate') or 0)+(a.get('federal_balance_effect') or 0) for a in selected),
        california_balance=sum((a.get('california_estimate') or 0)+(a.get('california_balance_effect') or 0) for a in selected),
        included=[a['key'] for a in selected],overlaps=overlaps,
        pending=[k for k in s['adjustments'] if not adjustment_status(s,k)['reviewed'] or adjustment_status(s,k)['partner_required'] and not adjustment_status(s,k)['partner_approved']])

def adjustment_blockers(s,keys=None):
    result=[]
    for k in s['adjustments']:
        if keys is not None and k not in keys:continue
        r=adjustment_status(s,k)
        if not r['reviewed']:result.append(k+': adjustment needs independent review')
        if r['partner_required'] and not r['partner_approved']:result.append(k+': adjustment needs partner approval')
    if estimate(s)['overlaps']:result.append('Resolve overlapping tax-effect estimates before finalizing')
    return result

def extra_blockers(s):
    pending=[x[1] for x in OUTSIDE if s.get('outside_filings',{}).get(x[0],{}).get('status') not in ['not_applicable','completed','external_confirmed']]
    pending += [x['label'] for k,x in s.get('outside_filings',{}).items() if k.startswith('custom-') and x['status'] not in ['not_applicable','completed','external_confirmed']]
    return adjustment_blockers(s)+([f'{len(pending)} outside filings need an applicability / completion conclusion'] if pending else [])

def package(s):
    return dict(year=2025,version=s['version'],packet_sha256=A.digest(A.PACKET),engine_summary=A.version(s)['summary'],
        amounts={k:A.effective(s,k) for k in A.lines(s)},adjustments=s['adjustments'],adjustment_reviews=s.get('adjustment_reviews',{}),
        judgments=s['judgments'],outside_filings=s.get('outside_filings',{}),amendment=s['amendment'])

def package_hash(s):return A.digest(package(s))

def review_hash(s):
    records={k:s.get(k) for k in ['verifications','calculations','resolutions','notes','judgments','evidence','answer_evidence','links','documents','areas','standards','related_reviews']}
    records['steps']={k:v for k,v in s['steps'].items() if k not in ['Reviewer sign-off','Partner sign-off','Client approval and e-file authorization']}
    return A.digest(dict(package=package(s),review=records))

def resolve(ref,s):
    if ref.startswith('answer:'):return next(x for x in s.get('answer_evidence',[]) if x['id']==ref)
    if ref.startswith('note:'):return next(x for x in s['notes'] if x['id']==ref[5:])
    if ref.startswith('related:'):
        index=int(ref[8:]);A.require(0<=index<len(A.PACKET['household']['related_returns']),'Unknown related return.')
        return A.PACKET['household']['related_returns'][index]
    if ref.startswith('priorasset:'):return next(x for x in A.PACKET['prior_years']['asset_records'] if x['asset_id']==ref[11:])
    if ref.startswith('nextyear:'):return s['next_years'][ref[9:]]
    if ref.startswith('version:'):
        _,v,k=ref.split(':',2)
        return next(l for version in A.versions(s) if version['version']==v for l in version['lines'] if l['key']==k)
    raise ValueError('Unknown evidence reference: '+ref)

def scalar(s,ref):
    x=A.resolve(ref,s)
    if ref in A.lines(s):x=A.effective(s,ref)
    elif isinstance(x,dict):x=x.get('value')
    A.require(isinstance(x,(float,int)) and not isinstance(x,bool) and math.isfinite(x),'Reference must resolve to a numeric value: '+ref)
    return x

def calculate(s,expression,refs):
    A.require(len(expression)<=1200 and 0<len(refs)<=100,'Use up to 100 references and a short expression.')
    values={f'x{i+1}':scalar(s,r) for i,r in enumerate(refs)}
    ops={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}
    funcs={'min':min,'max':max,'round':round,'abs':abs}
    def visit(n):
        if isinstance(n,ast.Expression):return visit(n.body)
        if isinstance(n,ast.Constant) and type(n.value) in [int,float]:return n.value
        if isinstance(n,ast.Name) and n.id in values:return values[n.id]
        if isinstance(n,ast.BinOp) and type(n.op) in ops:return ops[type(n.op)](visit(n.left),visit(n.right))
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return visit(n.operand)*(1 if isinstance(n.op,ast.UAdd) else -1)
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in funcs and not n.keywords:return funcs[n.func.id](*[visit(v) for v in n.args])
        raise ValueError('Use x1, x2, numbers, + - * / and min, max, round or abs only.')
    try:
        tree=ast.parse(expression,mode='eval');A.require(len(list(ast.walk(tree)))<=300,'Expression is too complex.');result=visit(tree)
    except (SyntaxError,ZeroDivisionError,OverflowError,TypeError,RecursionError) as ex:raise ValueError('Invalid calculation: '+str(ex))
    A.require(isinstance(result,(int,float)) and math.isfinite(result) and abs(result)<1e15,'Calculation is outside the allowed range.')
    return dict(result=result,values=values,input_hash=A.digest(values))

def confirmation_status(s):
    line_map=A.lines(s)
    return {uid:{k:{**c,'current':k in line_map and c.get('version')==s['version'] and c.get('value')==A.effective(s,k) and c.get('preparation_hash')==A.digest(s['verifications'].get(k))} for k,c in records.items()} for uid,records in s.get('review_confirmations',{}).items()}

def projection(s):
    calculations={}
    for k,c in s.get('calculations',{}).items():
        try:
            current=calculate(s,c['expression'],c['refs']);calculations[k]={**c,'current':current,'stale':current['input_hash']!=c['input_hash']}
        except (ValueError,KeyError,StopIteration):calculations[k]={**c,'stale':True}
    confirmations=confirmation_status(s)
    return dict(derivations=workpaper_calculations.explain_all(A,s),review_confirmations=confirmations,finding_summary=finding_estimates(s),estimate=estimate(s),adjustment_status={k:adjustment_status(s,k) for k in s['adjustments']},
        calculations=calculations,package_hash=package_hash(s),outside_catalog=[dict(id=i,label=l,refs=r,hint=h) for i,l,r,h in OUTSIDE],
        next_years=s.get('next_years',{}),retention=s.get('retention',{}))

def finding_estimates(s):
    """Nonoverlapping source-error estimates, distinct from reviewer adjustments."""
    mapping={'duplicate-interest':('interest',1),'duplicate-revenue':('schc_profit',1),'duplicate-mileage':('schc_profit',-A.PACKET['engine_reference']['parameters']['mileage_rate']), 'basis-N1':('stcg',1),'basis-N3':('stcg',1),'basis-N4':('ltcg',1),'missing-lot':('stcg',1),'foreign-rate':('interest',1),'mortgage-duplicate':('itemized',1),'software':('schc_profit',-1),'utilities':('schc_profit',-1),'vehicle-gift':('itemized',1)}
    checks=A.checks(s);rates=A.effect_rates(s);rows={};fed=ca=payments=0
    for c in checks:
        ident=c['id'];federal=california=payment=0;available=False
        if ident in mapping and c['expected'] is not None:
            category,mult=mapping[ident];delta=(c['expected']-(c['actual'] or 0))*mult
            federal=A.money(delta*rates[category]['federal_per_dollar']);california=A.money(delta*rates[category]['california_per_dollar']);available=True
        elif ident in ['federal-payments','state-payments']:
            payment=c['actual']-c['expected'];available=True
        rows[ident]=dict(federal=federal,california=california,payment_balance=payment,available=available)
        if c['kind']=='Independent check':fed+=federal;ca+=california;payments+=payment
    return dict(errors=sum(c['kind']=='Independent check' for c in checks),judgments=sum(c['kind']=='Judgment required' for c in checks),diagnostics=sum(c['kind']=='Engine diagnostic' for c in checks),federal=A.money(fed),california=A.money(ca),tax=A.money(fed+ca),payment_balance=payments,net_balance=A.money(fed+ca+payments),rows=rows)

ACTIONS={'add_line','review_adjustment','calculation','outside_filing','related_review','filing_event','notice_response','roll_forward','nextyear_update','retention_policy'}

def actions(role):
    result=set()
    if role=='preparer':result.add('add_line')
    if role in A.EDITORS:result.update({'calculation','outside_filing','related_review','notice_response','nextyear_update'})
    if role in ['reviewer','partner']:result.add('review_adjustment')
    if role=='partner':result.update({'filing_event','roll_forward'})
    if role=='firm_administrator':result.add('retention_policy')
    return result

def mutate(s,u,a,p):
    ensure(s);role=u['role'];uid=u['id']
    def text(k):
        v=str(p.get(k,'')).strip();A.require(v and len(v)<=20000,k.replace('_',' ').title()+' is required.');return v
    def refs():
        rr=p.get('refs',[]);A.require(isinstance(rr,list) and rr,'Evidence references are required.')
        for r in rr:A.resolve(r,s)
        return rr
    stamp=dict(actor=uid,at=A.now())
    if a=='add_line':
        key=text('key');form=text('form');line=text('line');label=text('label');rr=refs()
        A.require(key==form+'.'+line and key not in A.lines(s),'Use an unused key in the form.line format.')
        A.require(form in {l['form'] for l in A.version(s)['lines']},'Choose an existing form.')
        value=p.get('value');A.require(type(value) in [int,float] and math.isfinite(value) and abs(value)<1e14,'Enter a finite amount.')
        category=text('category');rates=A.effect_rates(s);A.require(category in rates,'Unknown effect category.')
        example=next(l for l in A.version(s)['lines'] if l['form']==form)
        added=dict(key=key,form=form,line=line,label=label,value=0,engine_present=False,inputs=[],sources=rr,rule='R-WORKPAPER-ADDITION',jurisdiction=example['jurisdiction'],version=s['version'],**stamp)
        A.require(not A.nonmonetary(added) or category=='nonmonetary','Use nonmonetary for quantities.')
        s['supplemental_lines'].append(added)
        effect_base=tax_effect_base(key,value,category)
        s['adjustments'][key]=dict(**stamp,key=key,original=None,value=value,delta=value,effect_base=effect_base,reason=text('reason'),refs=rr,category=category,federal_estimate=None if category=='nonmonetary' else A.money(effect_base*rates[category]['federal_per_dollar']),california_estimate=None if category=='nonmonetary' else A.money(effect_base*rates[category]['california_per_dollar']),federal_balance_effect=-value if category=='federal_payment' else None,california_balance_effect=-value if category=='california_payment' else None)
        A.reopen_form_work(s,'Missing detail added; include it in the form tie-out.',{form})
        return True
    if a=='review_adjustment':
        key=text('key');adj=s['adjustments'][key];A.require(adj['actor']!=uid,'You cannot approve your own adjustment.')
        record=s['adjustment_reviews'].get(key,{})
        if record.get('adjustment_hash')!=A.digest(adj):record={}
        include=p.get('include',True);A.require(type(include) is bool,'Choose whether to include this effect.')
        if role=='reviewer':
            record=dict(reviewer=uid,at=A.now(),reason=text('reason'),refs=refs(),include=include,adjustment_hash=A.digest(adj))
        else:
            A.require(record.get('reviewer') and record['reviewer']!=uid,'Independent reviewer approval is required before partner approval.')
            A.require(include==record['include'],'A reviewer must change the inclusion decision before partner approval.')
            record.update(partner=uid,partner_at=A.now(),partner_reason=text('reason'),partner_refs=refs())
        s['adjustment_reviews'][key]=record
        return True
    if a=='calculation':
        key=text('key');A.require(key in A.lines(s),'Unknown return line.');rr=refs();A.require(key not in rr and not any(r in A.downstream(s,[key]) for r in rr),'Calculation inputs cannot depend on the result.');expression=text('expression');value=calculate(s,expression,rr)
        s['calculations'][key]=dict(**stamp,key=key,expression=expression,refs=rr,explanation=text('explanation'),**value)
        for k in A.downstream(s,[key]):s['verifications'].pop(k,None)
        A.reopen_form_work(s,'Calculation changed; inspect the updated derivation.',A.changed_forms(s,{'key':key}))
        return True
    if a=='outside_filing':
        ident=p.get('id') or 'custom-'+secrets.token_hex(5);status=text('status')
        A.require(ident in [x[0] for x in OUTSIDE] or ident.startswith('custom-'),'Unknown outside-filing obligation.')
        A.require(status in ['pending','required','not_applicable','completed','external_confirmed'],'Invalid outside-filing status.')
        owner=text('owner');A.require(owner in A.STAFF,'Unknown owner.')
        due=text('due');datetime.strptime(due,'%Y-%m-%d')
        s['outside_filings'][ident]=dict(**stamp,id=ident,label=text('label'),status=status,owner=owner,due=due,reason=text('reason'),refs=refs())
        return True
    if a=='related_review':
        ident=text('id');A.require(ident.startswith('related:'),'Choose a related return.');A.resolve(ident,s)
        s['related_reviews'][ident]=dict(**stamp,reason=text('reason'),refs=refs())
        return True
    if a=='filing_event':
        A.require(s.get('engagement',{}).get('partner')==uid,'Only the engagement partner can record filing lifecycle events.')
        jurisdiction=text('jurisdiction');A.require(jurisdiction in ['federal','california'],'Choose a filing jurisdiction.')
        kind=text('kind');events=[e for e in s['filing_events'] if e['jurisdiction']==jurisdiction and e['cycle']==s['amendment']]
        last=next((e['kind'] for e in reversed(events) if e['kind'] in ['submitted','rejected','rejection_resolved','resubmitted','accepted']),None)
        allowed={'extension':True,'submitted':last is None,'rejected':last in ['submitted','resubmitted'], 'rejection_resolved':last=='rejected','resubmitted':last=='rejection_resolved','accepted':last in ['submitted','resubmitted'],'payment':True,'refund':True}
        A.require(allowed.get(kind,False),'That event is out of sequence for this filing cycle.')
        if kind in ['submitted','resubmitted']:A.require(not A.blockers(s),'Complete readiness and current client authorizations before recording submission.')
        if kind=='accepted':
            previous=next(e for e in reversed(events) if e['kind'] in ['submitted','resubmitted'])
            A.require(previous['package_hash']==package_hash(s),'The return changed after submission; record a new submission.')
        dated=text('date');datetime.strptime(dated,'%Y-%m-%d')
        s['filing_events'].append(dict(**stamp,id='filing-'+secrets.token_hex(5),jurisdiction=jurisdiction,kind=kind,date=dated,reason=text('reason'),refs=refs(),cycle=s['amendment'],package_hash=package_hash(s),mode='Simulated case record — no transmission'))
        return False
    if a=='notice_response':
        ident=text('id');A.require(any(n['id']==ident for n in A.PACKET['tax_agency_records']['notices']),'Unknown notice.')
        status=text('status');A.require(status in ['draft','reviewed'],'Invalid response status.')
        old=s['notice_responses'].get(ident,{})
        if status=='reviewed':
            A.require(role in ['reviewer','partner'] and old and old['actor']!=uid,'An independent reviewer must approve the saved response.')
            A.require(old['package_hash']==package_hash(s),'The return package changed. Update the draft before review.')
            old.update(reviewed_by=uid,reviewed_at=A.now(),review_reason=text('reason'),status=status)
        else:old=dict(**stamp,status=status,text=text('text'),refs=refs(),package_hash=package_hash(s))
        s['notice_responses'][ident]=old
        return False
    if a=='roll_forward':
        A.require(s['frozen'],'Freeze the source engagement before rolling it forward.')
        year='2026';A.require(year not in s['next_years'],'The next-year engagement already exists; use its work queue.')
        snapshot=s['snapshots'][-1]
        s['next_years'][year]=dict(id='nextyear:'+year,year=2026,stage='Intake',source_version=s['version'],source_snapshot_hash=snapshot['hash'],source_package_hash=package_hash(s),source_history=copy.deepcopy(s['events']),carryovers=copy.deepcopy(A.version(s)['carryovers_out']),basis=dict(prior_history=copy.deepcopy(A.PACKET['prior_years']['basis_records']),current_year_lines={l['key']:A.effective(s,l['key']) for l in A.version(s)['lines'] if l['form'] in ['F7203','SchE','F8606']},version=s['version']),assets=copy.deepcopy(A.version(s)['assets']),adjustment_followups=copy.deepcopy(s['adjustments']),team=copy.deepcopy(s['engagement']),work=[],reason=text('reason'),**stamp)
        return False
    if a=='nextyear_update':
        year=text('year');record=s['next_years'][year];kind=text('kind');A.require(kind in ['task','complete','stage'],'Unknown next-year action.')
        if kind=='complete':
            task=next(x for x in record['work'] if x['id']==p['id']);A.require(task['owner']==uid or role in ['reviewer','partner'],'Only the owner or reviewer can close this item.');task.update(status='done',completed_by=uid,completed_at=A.now(),completion=text('reason'))
        elif kind=='stage':
            stage=text('stage');A.require(stage in ['Intake','Documents requested','Preparation'],'No next-year computed return is available yet.');record.update(stage=stage)
        else:
            owner=text('owner');A.require(owner in A.STAFF,'Unknown owner.');due=text('due');datetime.strptime(due,'%Y-%m-%d')
            record['work'].append(dict(id=secrets.token_hex(5),title=text('title'),owner=owner,due=due,status='open',**stamp))
        return False
    if a=='retention_policy':
        A.require(type(p.get('legal_hold')) is bool,'Choose a legal-hold setting.')
        s['retention'].update(legal_hold=p['legal_hold'],reason=text('reason'),**stamp)
        return False
    raise ValueError('Unknown workpaper action.')

def make_authorization(s,u,p):
    name=str(p.get('signed_name','')).strip();A.require(name.casefold()==u['name'].casefold(),'Type your full name as displayed in the client portal.')
    A.require(p.get('consent') is True,'Confirm you reviewed the package and authorize this case filing.')
    return dict(at=A.now(),revision=s['revision'],signed_name=name,actor=u['id'],statement=str(p.get('statement','')).strip(),package_hash=package_hash(s),
        version=s['version'],engine_summary=copy.deepcopy(A.version(s)['summary']),estimate=estimate(s),authorization='Electronic case-study authorization; not an executed IRS Form 8879 or live transmission')

def artifact(s,u,scope='review',notice=None):
    """Return a self-contained, printable HTML + JSON + attachments ZIP."""
    full=scope=='full';client=scope=='client'
    allowed=(u['role']=='client') if client else ('export_full' if full else 'export') in A.capabilities(u)['actions']
    A.require(allowed,'Export is not permitted.')
    if full:A.require(u.get('sensitive_data_clearance',False),'Sensitive-data clearance is required.')
    if client:A.require(not notice,'Notice responses belong to the internal workpaper.')
    packet=copy.deepcopy(A.PACKET);state=copy.deepcopy(s)
    if not full:packet=A.redact(packet);state=A.redact(state)
    if client:
        state={k:state.get(k) for k in ['version','adjustments','approvals','frozen','amendment']}
        state['approvals']={k:v for k,v in state['approvals'].items() if k==u['id']}
        state['adjustments']={k:{field:a.get(field) for field in ['key','original','value','delta','federal_estimate','california_estimate']} for k,a in state['adjustments'].items()}
    esc=lambda x:html.escape(str(x if x is not None else ''))
    def ident(ref):return 'r-'+base64.urlsafe_b64encode(ref.encode()).decode().rstrip('=')
    def link(ref):
        try:
            item=A.resolve(ref,s)
            if not full:item=A.redact(item)
            caption=item.get('label') or item.get('description') or item.get('title') or ref if isinstance(item,dict) else ref
            number=item.get('value') if isinstance(item,dict) else item
            if type(number) in [int,float]:caption=str(caption)+' · '+f'{number:,.2f}'
        except (ValueError,KeyError,StopIteration,IndexError):caption=ref
        return '<a href="#'+ident(ref)+'">'+esc(caption)+'</a>'
    def table(headers,rows):return '<table><thead><tr>'+''.join('<th>'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in r)+'</tr>' for r in rows)+'</tbody></table>'
    def label(key):
        return str(key).replace('_',' ').replace('sha256','SHA-256').capitalize()
    def readable(value,key=''):
        if value is None:return '<span class="muted">Not supplied</span>'
        if isinstance(value,bool):return 'Yes' if value else 'No'
        if isinstance(value,(int,float)):
            unitless=key in ['year','revision','amendment','id','batch_event','life_years','years','page','page_count','hours','value_type'] or 'ratio' in key or 'rate' in key or 'percent' in key
            return esc(f'{value:,}' if unitless else f'${value:,.2f}')
        if isinstance(value,str):
            if key in ['refs','sources','source','evidence_ref'] and (value in A.lines(s) or value.startswith(('ev-','doc:','asset:','py:/','agency:/','answer:','evidence:','ref:param.','qa-','msg-','call-','D'))):return link(value)
            if key in ['actor','reviewer','partner','owner','assignee','reviewed_by','answered_by','resolved_by']:
                return esc(A.STAFF.get(value,{}).get('name',value))
            return esc(value)
        if isinstance(value,list):return '<ol>'+''.join('<li>'+readable(item,key)+'</li>' for item in value)+'</ol>' if value else '<span class="muted">None recorded</span>'
        if isinstance(value,dict):
            if not value:return '<span class="muted">None recorded</span>'
            if value.get('unit') in ['ratio','number'] and type(value.get('value')) in [int,float]:
                return esc(value.get('label','Value'))+': '+esc(f"{value['value']:,.6f}".rstrip('0').rstrip('.'))
            return '<dl>'+''.join('<div><dt>'+esc(label(k))+'</dt><dd>'+readable(v,k)+'</dd></div>' for k,v in value.items() if k not in ['content','encoding','_before','previous_hash'])+'</dl>'
        return esc(value)
    title='Client return copy' if client else 'Notice response record' if notice else 'Examiner and review record'
    body='<h1>'+title+'</h1><p>Okafor–Lindqvist · TY 2025 · '+esc(s['version'])+'</p><p>Package fingerprint: '+esc(package_hash(s))+'</p><p>Engine totals are preserved. Adjustment effects are packet-rate estimates, not recomputed tax totals.</p>'
    body+='<h2>Return summary</h2>'+table(['Jurisdiction','Engine totals'],[[esc(j.title()),readable(v)] for j,v in A.version(s)['summary'].items()])
    estimate_record=estimate(s)
    if client:estimate_record={k:v for k,v in estimate_record.items() if isinstance(v,(int,float))}
    body+='<h2>Estimated adjustment effects</h2>'+readable(estimate_record)
    if notice:
        n=next(n for n in packet['tax_agency_records']['notices'] if n['id']==notice);r=state.get('notice_responses',{}).get(notice,{})
        body+='<h2>'+esc(n['type'])+'</h2><p>'+esc(r.get('text','No response drafted.'))+'</p><p>'+esc(r.get('status','Not started'))+'</p>'+''.join(link(x)+' ' for x in r.get('refs',[]))
    report_lines=A.version(s)['lines'] if full else A.redact(A.version(s)['lines'])
    working={l['key']:A.effective(s,l['key']) for l in A.version(s)['lines']}
    if not full:working=A.redact(working)
    body+='<h2>Return amounts</h2>'+table(['Line','Description','Engine','Working','Support'],[[f'<span id="{ident(l["key"])}">'+esc(l['key'])+'</span>',esc(l['label']),esc(l['value']) if l.get('engine_present',True) else 'Not in engine',esc(working[l['key']]),'' if client else ' '.join(link(r) for r in l['sources']+l['inputs'])] for l in report_lines])
    body+='<h2>Authorizations</h2>'+readable(state.get('approvals',{}))
    if not client:
        state['review_confirmations']=confirmation_status(s)
        if not full:state['review_confirmations']=A.redact(state['review_confirmations'])
        body+='<h2>Review record</h2>'+''.join('<details open><summary>'+esc(label(k))+'</summary>'+readable(state.get(k))+'</details>' for k in ['verifications','review_confirmations','adjustments','adjustment_reviews','calculations','resolutions','notes','judgments','outside_filings','related_reviews','signatures','filing_events','notice_responses'])
        derivations=workpaper_calculations.explain_all(A,s)
        if not full:derivations=A.redact(derivations)
        body+='<h2>Arithmetic checks</h2><p>Read-only checks using supplied rules. Differences do not change engine or working return amounts.</p>'
        body+=''.join('<details><summary>'+esc(key+' · '+A.lines(s)[key]['label'])+'</summary>'+table(['Step','Engine-input check'],[[esc(step['label']),esc(f"{step['value']:,.6f}" if step['unit']=='ratio' else f"{step['value']:,.2f}")] for step in d['engine']['steps']])+'<p>Rounded result: '+esc(d['engine']['rounded'])+' · Difference from engine: '+esc(d['engine']['difference'])+'</p>'+('<h3>Working-input check</h3>'+readable(d['working']) if d['working'] and (d['working']['steps']!=d['engine']['steps'] or d['working']['difference']!=d['engine']['difference']) else '')+'</details>' for key,d in derivations.items())
        for d in packet['documents']:
            body+=f'<h2 id="{ident(d["id"])}">'+esc(d['id']+' · '+d['title'])+'</h2>'
            for pg in d['pages']:
                body+=f'<h3 id="{ident("doc:"+d["id"]+"#page"+str(pg["page"]))}">Page '+esc(pg['page'])+'</h3><pre>'+esc(pg['printed_content'])+'</pre>'
                for e in packet['extracted_values']:
                    if e['document_id']==d['id'] and e['page']==pg['page']:body+=f'<p id="{ident(e["id"])}">'+esc(e['id']+' · '+e['label']+': '+str(e['value']))+'</p>'
        for e in state.get('answer_evidence',[]):body+=f'<section id="{ident(e["id"])}"><h3>Client / colleague response</h3>'+readable(e)+'</section>'
        for n in state.get('notes',[]):body+=f'<section id="{ident("note:"+n["id"])}"><h3>Review note</h3><p>'+esc(n['text'])+'</p></section>'
        # Include every additional referenced object so the report works offline.
        refs={r for l in A.version(s)['lines'] for r in l['sources']}
        refs.update(r for e in s['events'] for r in e.get('payload',{}).get('refs',[]))
        refs.update(e['id'] for e in s['evidence'])
        refs.update('related:'+str(i) for i in range(len(packet['household']['related_returns'])))
        refs.update(r for a in A.version(s)['assets'] for r in a.get('sources',[]))
        refs.update('asset:'+a['asset_id'] for a in A.version(s)['assets'])
        refs.update(r for d in derivations.values() for r in d['engine']['refs'])
        for ref in sorted(refs):
            if ref in A.lines(s) or ref.startswith(('ev-','doc:')) or any(d['id']==ref for d in packet['documents']):continue
            try:x=A.resolve(ref,s);x=x if full else A.redact(x)
            except (ValueError,KeyError,StopIteration,IndexError):x={'reference':ref,'status':'Reference unavailable in this version'}
            if isinstance(x,dict) and x.get('encoding')=='base64':
                if full:
                    safe=x['id'].replace(':','-')+'-'+''.join(c for c in x['name'] if c.isalnum() or c in '._-')
                    body+=f'<section id="{ident(ref)}"><h3>'+esc(x['name'])+'</h3><a href="attachments/'+esc(safe)+'">Open attachment</a><p>SHA-256 '+esc(x['sha256'])+'</p></section>'
                else:body+=f'<section id="{ident(ref)}"><h3>'+esc(x['name'])+'</h3><p>Binary content requires a cleared full archive.</p></section>'
                continue
            body+=f'<section id="{ident(ref)}"><h3>'+esc(ref)+'</h3>'+readable(x)+'</section>'
        body+='<h2>Attributed history</h2>'+table(['When','Who','Action','Details'],[[esc(e['at']),esc(e['name']),esc(label(e['action'])),readable(e['payload'])] for e in state['events']])
    markup='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+title+'</title><style>body{font:14px system-ui;max-width:1150px;margin:40px auto;padding:0 20px;color:#18352b}h1,h2,h3{break-after:avoid}table{border-collapse:collapse;width:100%;margin:20px 0}td,th{border:1px solid #cbd6d0;padding:8px;text-align:left;vertical-align:top}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px system-ui}a{color:#236f50}section{margin:24px 0}dl{margin:0}dl>div{display:grid;grid-template-columns:minmax(130px,1fr) minmax(0,3fr);gap:16px;padding:7px 0;border-bottom:1px solid #e5ece8}dt{font-weight:600}dd{margin:0;overflow-wrap:anywhere}details{border:1px solid #dce5df;border-radius:6px;padding:14px;margin:12px 0}summary{font-weight:600;cursor:pointer}.muted{color:#65766e}li{margin:8px 0}@media print{body{margin:0}thead{display:table-header-group}tr{break-inside:avoid}}</style>'+body+'</html>'
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('index.html',markup)
        z.writestr('record.json',json.dumps(dict(packet=None if client else packet,state=state,package_hash=package_hash(s)),ensure_ascii=False,indent=2))
        for e in state.get('evidence',[]) if not client else []:
            if e.get('encoding')=='base64' and full:
                safe=e['id'].replace(':','-')+'-'+''.join(c for c in e['name'] if c.isalnum() or c in '._-')
                z.writestr('attachments/'+safe,base64.b64decode(e['content']))
    return dict(filename='miraflores-'+scope+('-'+notice if notice else '')+'.zip',mime='application/zip',content=base64.b64encode(output.getvalue()).decode())
