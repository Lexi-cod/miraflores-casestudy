import copy
import hashlib
import http.cookiejar
import json
from pathlib import Path
import tempfile
import uuid
import threading
import unittest
import urllib.error
import urllib.request
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app


class ReviewControls(unittest.TestCase):
    def setUp(self): self.s=app.initial()
    def act(self, action, payload, user='st-01'):
        return app.mutate(self.s, app.STAFF[user], action, payload)
    def verify(self,keys=None):
        return self.act('verify',dict(keys=keys or ['F1040.1a'],method='agreed_to_source_document',refs=['doc:D08#page1','doc:D09#page1'],note='Matched distinct W-2 box 1 amounts.'))
    def adjust(self):
        return self.act('adjust',dict(key='SchB.1.2',value=0,category='interest',reason='Duplicate sweep account statement.',refs=['doc:D28#page1','doc:D29#page1']))
    def test_exact_source_findings(self):
        c={c['id']:c for c in app.checks(self.s)}
        self.assertEqual(c['duplicate-mileage']['expected'],8100)
        self.assertEqual(c['foreign-rate']['expected'],1871)
        self.assertEqual(c['federal-payments']['delta'],-1000)
        self.assertEqual(c['missing-lot']['expected'],-60)
        self.assertEqual(c['basis-N3']['expected'],-620)
        for item in c.values():
            for r in item['refs']:app.resolve(r,self.s)
    def test_dependency_reaches_1040(self):
        self.assertIn('F1040.11',app.downstream(self.s,['SchB.1.2']))
    def test_originals_never_change(self):
        before=app.digest(app.PACKET);self.adjust()
        self.assertEqual(app.digest(app.PACKET),before)
        self.assertEqual(app.lines(self.s)['SchB.1.2']['value'],1840)
        self.assertEqual(app.effective(self.s,'SchB.1.2'),0)
    def test_adjustments_invalidate_downstream_and_signatures(self):
        self.verify(['F1040.11','F1040.2b']);self.s['signatures']={'reviewer':{'actor':'st-02'}};self.s['approvals']={'cu-01':{}}
        self.adjust();self.assertFalse(self.s['verifications']);self.assertFalse(self.s['signatures']);self.assertFalse(self.s['approvals'])
    def test_estimate_uses_packet_rates(self):
        self.adjust();a=self.s['adjustments']['SchB.1.2'];rates=app.version(self.s)['tax_effect_rates']['interest']
        self.assertEqual(a['federal_estimate'],app.money(-1840*rates['federal_per_dollar']))
    def test_miles_are_not_dollar_effects(self):
        p=dict(key='SchC.44a',value=8100,category='schc_profit',reason='Deduplicate mileage',refs=['doc:D23#page3'])
        with self.assertRaisesRegex(ValueError,'nonmonetary'):self.act('adjust',p)
        p['category']='nonmonetary';self.act('adjust',p)
        self.assertIsNone(self.s['adjustments']['SchC.44a']['federal_estimate'])
    def test_payment_changes_balance_not_total_tax(self):
        self.act('adjust',dict(key='F1040.26',value=12000,category='federal_payment',reason='Agree to IRS transcript',refs=['agency:/irs_account_transcript_2025/0']))
        a=self.s['adjustments']['F1040.26'];self.assertEqual(a['federal_estimate'],0);self.assertEqual(a['federal_balance_effect'],1000)
    def test_independent_arithmetic_detects_stale_engine_total(self):
        v=copy.deepcopy(app.version(self.s));v['version']='v4'
        for l in v['lines']:
            if l['key']=='SchB.1.2':l['value']=0
        self.act('import_version',dict(version=v,reason='Test stale total'))
        c=next(c for c in app.checks(self.s) if c['id']=='arithmetic-SchB.2')
        self.assertEqual(c['expected'],4610)
    def test_nonfinite_adjustment_rejected(self):
        with self.assertRaises(ValueError):self.act('adjust',dict(key='SchB.1.2',value=float('nan'),category='interest',reason='test',refs=['D29']))
    def test_role_restrictions(self):
        for user in ['cu-01','st-05','st-06','st-02']:
            with self.assertRaises(ValueError):self.act('adjust',dict(key='SchB.1.2',value=0),user)
        with self.assertRaises(ValueError):self.act('standards',dict(percent=20,amount=2000))
        self.act('standards',dict(percent=20,amount=2000),'st-05')
        self.assertEqual(app.PACKET['firm']['starter_standards']['variance_review']['flag_if_change_over_percent'],10)
    def test_self_review_prevented(self):
        self.act('verify',dict(keys=['F1040.1a'],method='recalculated',refs=['D08'],note='recalculation'),'st-02')
        with self.assertRaisesRegex(ValueError,'work you prepared'):self.act('sign',{'statement':'Reviewed'},'st-02')
    def test_judgment_requires_authority_and_independent_review(self):
        with self.assertRaises(ValueError):self.act('judgment',dict(subject='x',decision='x',authority='',refs=['D08']))
        self.act('judgment',dict(subject='ca-amt',decision='calculation',authority='attached worksheet',refs=['D08']))
        self.assertTrue(any('independently reviewed' in b for b in app.blockers(self.s)))
        self.act('review_judgment',dict(id=self.s['judgments'][0]['id'],reason='Independently recalculated'),'st-02')
        self.assertFalse(any('independently reviewed' in b for b in app.blockers(self.s)))
    def test_verification_requires_evidence(self):
        with self.assertRaises(ValueError):self.act('verify',dict(keys=['F1040.1a'],method='recalculated',refs=['not-real'],note='check'))
    def test_batch_undo_restores_previous_verification(self):
        self.verify();before=copy.deepcopy(self.s['verifications']['F1040.1a']);self.verify(['F1040.1a','F1040.1z']);self.act('undo_verify',{})
        self.assertEqual(self.s['verifications']['F1040.1a'],before);self.assertNotIn('F1040.1z',self.s['verifications'])
    def test_undo_does_not_erase_another_users_later_work(self):
        self.verify();self.act('verify',dict(keys=['F1040.1a'],method='recalculated',refs=['D08'],note='Second verification'),'st-04');self.act('undo_verify',{})
        self.assertEqual(self.s['verifications']['F1040.1a']['actor'],'st-04')
    def test_pending_documents_block(self):
        for d in app.PACKET['documents']:self.s['documents'][d['id']]={'status':'used'}
        self.s['documents']['D01']['status']='pending'
        self.assertTrue(any('1 documents' in b for b in app.blockers(self.s)))
    def test_initial_return_cannot_be_frozen(self):
        with self.assertRaisesRegex(ValueError,'Filing blocked'):self.act('freeze',{},'st-03')
    def ready_fixture(self):
        self.s['resolutions']={c['id']:{'actor':'st-02'} for c in app.checks(self.s)}
        self.s['documents']={d['id']:{'status':'used'} for d in app.PACKET['documents']}
        self.s['verifications']={l['key']:{'actor':'st-01'} for l in app.version(self.s)['lines']}
        self.s['areas']={a:{} for a in app.AREAS}
        self.s['steps']={step:{} for step in self.s['standards']['required_steps']}
        self.s['signatures']={r:{'actor':a} for r,a in [('preparer','st-01'),('reviewer','st-02'),('partner','st-03')]}
        self.s['approvals']={'cu-01':{},'cu-02':{}}
        self.s['judgments']=[{'subject':'ca-amt','actor':'st-01','reviewed_by':'st-02'}]
    def test_snapshot_freezes_and_amendment_preserves_digest(self):
        self.ready_fixture();self.act('freeze',{},'st-03');snapshot=copy.deepcopy(self.s['snapshots'][0]);self.assertEqual(snapshot['hash'],app.digest(snapshot['record']))
        with self.assertRaisesRegex(ValueError,'frozen'):self.act('note',dict(text='change'))
        self.act('amend',dict(reason='New evidence'),'st-03');self.assertEqual(self.s['snapshots'][0],snapshot);self.assertEqual(self.s['amendment'],1);self.assertFalse(self.s['signatures'])
    def test_open_note_blocks_even_with_ready_fixture(self):
        self.ready_fixture();self.s['notes']=[dict(blocking=True,resolved=False)]
        with self.assertRaises(ValueError):self.act('freeze',{},'st-03')
    def test_import_recomputed_version_preserves_original_and_clears_overlay(self):
        self.adjust();v=copy.deepcopy(app.version(self.s));v['version']='v4'
        for l in v['lines']:
            if l['key']=='SchB.1.2':l['value']=0
        self.act('import_version',dict(version=v,reason='External engine recomputation test'))
        self.assertEqual(self.s['version'],'v4');self.assertFalse(self.s['adjustments']);self.assertEqual(len(app.PACKET['return_versions']),3)
        self.assertEqual(self.s['integrated_adjustments'][0]['adjustments']['SchB.1.2']['value'],0)
    def test_import_rejects_unincorporated_adjustment(self):
        self.adjust();v=copy.deepcopy(app.version(self.s));v['version']='v4'
        with self.assertRaisesRegex(ValueError,'does not incorporate'):self.act('import_version',dict(version=v,reason='test'))
    def test_sensitive_values_masked_everywhere(self):
        data=app.response(self.s,app.STAFF['st-04']);text=json.dumps(data)
        for secret in ['666-41-2287',str(app.PACKET['household']['bank_account_for_refund_or_payment']['account']),'482915','SE45 8000 0000 0412 7783 9901']:
            self.assertNotIn(secret,text)
        self.assertEqual(data['packet']['household']['bank_account_for_refund_or_payment']['account'],'[REDACTED]')
    def test_binary_attachment_withheld(self):
        self.act('evidence',dict(name='test',content='c2VjcmV0',encoding='base64'))
        self.assertIn('REDACTED',app.response(self.s,app.STAFF['st-04'])['state']['evidence'][0]['content'])
    def test_client_projection_has_no_internal_packet(self):
        d=app.response(self.s,app.STAFF['cu-01']);self.assertNotIn('packet',d);self.assertNotIn('events',d['state'])
    def test_administrator_receives_only_operational_data(self):
        self.adjust()
        self.s['tasks']=[dict(id='admin-task',assignee='st-05',title='Review budget'),dict(id='tax-task',assignee='st-01',title='Confidential tax question')]
        self.s['time']=[dict(area='preparation',hours=2,actor='st-01',private_note='Tax detail')]
        self.s['snapshots']=[dict(record=copy.deepcopy(self.s))]
        for reveal in [False,True]:
            d=app.response(self.s,app.STAFF['st-05'],reveal)
            self.assertTrue(d['administration']);self.assertNotIn('packet',d)
            self.assertEqual(set(d['state']),{'revision','standards','frozen','tasks'})
            self.assertEqual([t['id'] for t in d['state']['tasks']],['admin-task'])
            for forbidden in ['SchB.1.2','Confidential tax question','private_note','snapshots','unmasked_view']:
                self.assertNotIn(forbidden,json.dumps(d))
            self.assertEqual(d['capabilities']['views'],['firm'])
    def test_quality_review_stays_masked_even_with_clearance(self):
        u=app.STAFF['st-06'];self.assertTrue(u['sensitive_data_clearance'])
        d=app.response(self.s,u,True)
        self.assertEqual(d['packet']['household']['bank_account_for_refund_or_payment']['account'],'[REDACTED]')
        for action in ['export','export_full','reveal','adjust','verify','sign','standards','budget','replay']:
            self.assertNotIn(action,d['capabilities']['actions'])
        self.assertIn('documents',d['capabilities']['views'])
        self.assertNotIn('filing',d['capabilities']['views'])
    def test_budget_is_admin_only_preserves_tax_signatures_and_packet(self):
        area=next(iter(app.PACKET['firm']['budget_hours']));before=app.digest(app.PACKET)
        for who in ['st-01','st-02','st-03','st-06','cu-01']:
            with self.assertRaises(ValueError):self.act('budget',dict(area=area,hours=12),who)
        self.s['signatures']={'partner':{'actor':'st-03'}}
        self.act('budget',dict(area=area,hours=12),'st-05')
        self.assertEqual(app.budget_hours(self.s)[area],12)
        self.assertIn('partner',self.s['signatures']);self.assertEqual(before,app.digest(app.PACKET))
        for hours in [0,-1,float('inf'),True]:
            with self.assertRaises(ValueError):self.act('budget',dict(area=area,hours=hours),'st-05')
    def test_client_only_sees_own_approval_and_tasks(self):
        self.s['approvals']={'cu-01':{'statement':'My approval'},'cu-02':{'statement':'Private statement'}}
        self.s['tasks']=[dict(id='mine',assignee='cu-01'),dict(id='other',assignee='cu-02')]
        d=app.response(self.s,app.STAFF['cu-01'])
        self.assertEqual(list(d['state']['approvals']),['cu-01'])
        self.assertEqual([t['id'] for t in d['state']['tasks']],['mine'])
    def test_role_capabilities_match_authorities(self):
        expected={'st-01':('adjust','resolve'),'st-02':('resolve','adjust'),'st-03':('freeze','standards'),'st-04':('adjust','reveal'),'st-05':('standards','sign'),'st-06':('seen','verify'),'cu-01':('approve','export'),'cu-02':('approve','sign')}
        for ident,(allowed,denied) in expected.items():
            with self.subTest(user=ident):
                caps=app.capabilities(app.STAFF[ident])
                self.assertIn(allowed,caps['actions']);self.assertNotIn(denied,caps['actions'])
                self.assertTrue(caps['description'])
    def test_audit_hash_chain(self):
        self.verify();self.adjust();prev='0'*64
        for e in self.s['events']:
            self.assertEqual(e['previous_hash'],prev);body={k:v for k,v in e.items() if k!='hash'};self.assertEqual(e['hash'],app.digest(body));prev=e['hash']


class HttpPersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_root=app.ROOT/'tmp';test_root.mkdir(exist_ok=True)
        cls.testdir=test_root/('test-'+uuid.uuid4().hex);cls.testdir.mkdir()
        cls.original=app.DB;app.DB=cls.testdir/'test.sqlite'
        cls.server=app.ThreadingHTTPServer(('127.0.0.1',0),app.Handler);cls.port=cls.server.server_port
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();app.DB=cls.original
        assert cls.testdir.resolve().is_relative_to((app.ROOT/'tmp').resolve())
        for f in cls.testdir.iterdir():f.unlink()
        cls.testdir.rmdir()
    def client(self,who):
        opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.request(opener,'session',{'id':who});return opener
    def request(self,opener,path,body=None):
        req=urllib.request.Request(f'http://127.0.0.1:{self.port}/api/'+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
        try:
            with opener.open(req) as r:return r.status,json.load(r)
        except urllib.error.HTTPError as e:return e.code,json.load(e)
    def test_concurrent_stale_revision_rejected_and_data_persists(self):
        a=self.client('st-01');b=self.client('st-02');_,old=self.request(a,'state');rev=old['state']['revision']
        status,_=self.request(a,'action',dict(revision=rev,action='note',payload=dict(text='HTTP persistence check',blocking=True)))
        self.assertEqual(status,200)
        status,_=self.request(b,'action',dict(revision=rev,action='note',payload=dict(text='stale write')));self.assertEqual(status,409)
        self.assertEqual(app.read_state()['notes'][-1]['text'],'HTTP persistence check')
    def test_client_export_denied(self):
        status,_=self.request(self.client('cu-01'),'export');self.assertEqual(status,403)
    def test_switch_same_browser_updates_identity_capabilities_and_authority(self):
        browser=self.client('st-02')
        for ident in app.STAFF:
            with self.subTest(user=ident):
                status,selected=self.request(browser,'session',{'id':ident})
                self.assertEqual(status,200);self.assertEqual(selected['user']['id'],ident)
                _,state=self.request(browser,'state')
                self.assertEqual(state['user']['id'],ident)
                self.assertEqual(state['capabilities'],app.capabilities(app.STAFF[ident]))
        _,selected=self.request(browser,'session',{'id':'st-05'})
        status,result=self.request(browser,'action',dict(actor_id='st-05',revision=selected['state']['revision'],action='standards',payload=dict(percent=15,amount=1500)))
        self.assertEqual(status,200);self.assertNotIn('events',result['state'])
        self.assertEqual(app.read_state()['events'][-1]['actor'],'st-05')
        _,selected=self.request(browser,'session',{'id':'st-02'})
        status,_=self.request(browser,'action',dict(actor_id='st-02',revision=selected['state']['revision'],action='standards',payload=dict(percent=20,amount=2000)))
        self.assertEqual(status,400)
        self.assertEqual(app.read_state()['standards']['variance_review']['flag_if_change_over_percent'],15)
    def test_stale_tab_cannot_act_as_newly_selected_person(self):
        browser=self.client('st-01');_,selected=self.request(browser,'session',{'id':'st-03'})
        rev=selected['state']['revision']
        status,_=self.request(browser,'action',dict(actor_id='st-01',revision=rev,action='note',payload=dict(text='Must not be attributed to partner')))
        self.assertEqual(status,409);self.assertEqual(app.read_state()['revision'],rev)
    def test_clearance_enforced_and_views_logged(self):
        a=self.client('st-04');status,_=self.request(a,'reveal',{'reason':'test'});self.assertEqual(status,403)
        a=self.client('st-02');status,d=self.request(a,'reveal',{'reason':'test audit access'});self.assertEqual(status,200)
        self.assertEqual(d['state']['events'][-1]['action'],'unmasked_view')
        status,d=self.request(a,'export_full',{'reason':'archive test'});self.assertEqual(status,200)
        self.assertEqual(d['integrity'],app.digest(d['record']))
    def test_admin_and_quality_cannot_bypass_scope_with_direct_requests(self):
        for ident in ['st-05','st-06','cu-01']:
            with self.subTest(user=ident):
                a=self.client(ident);before=app.digest(app.read_state())
                status,_=self.request(a,'export');self.assertEqual(status,403)
                for endpoint in ['reveal','export_full']:
                    status,_=self.request(a,endpoint,{'reason':'Direct request with existing clearance'})
                    self.assertEqual(status,403)
                self.assertEqual(before,app.digest(app.read_state()))
    def test_admin_state_session_and_mutation_responses_never_include_tax_packet(self):
        a=self.client('st-05')
        for endpoint,body in [('session',{'id':'st-05'}),('state',None)]:
            status,d=self.request(a,endpoint,body)
            self.assertEqual(status,200);self.assertTrue(d['administration'])
            self.assertNotIn('packet',d);self.assertNotIn('checks',d);self.assertNotIn('events',d['state'])
        area=next(iter(app.PACKET['firm']['budget_hours']))
        status,d=self.request(a,'action',dict(revision=d['state']['revision'],action='budget',payload=dict(area=area,hours=15)))
        self.assertEqual(status,200);self.assertNotIn('packet',d)
        self.assertEqual(d['administration_data']['budget_hours'][area],15)
    def test_unknown_route_does_not_expose_packet_file(self):
        a=self.client('st-01');req=urllib.request.Request(f'http://127.0.0.1:{self.port}/okafor_lindqvist_2025_packet.json')
        with self.assertRaises(urllib.error.HTTPError) as e:a.open(req)
        self.assertEqual(e.exception.code,404)


if __name__=='__main__':unittest.main(verbosity=2)
