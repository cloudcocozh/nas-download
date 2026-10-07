import base64, json, tempfile, threading, time, unittest, uuid, sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.app import Application, ApiError

RAW=b'd4:infod6:lengthi123e4:name4:test12:piece lengthi16384e6:pieces20:12345678901234567890ee'

class FakeDownloader:
    def __init__(self): self.items=[]; self.adds=0; self.deletes=0; self.fail_add=False; self.callback=None
    def connect(self): return '5.0'
    def tasks(self): return [dict(i) for i in self.items]
    def automation_space(self,path): return 1000*1024**3
    def add(self,b):
        from server.automations import torrent_hash
        self.adds+=1
        if self.callback: self.callback()
        if self.fail_add: raise OSError('secret credential')
        h=torrent_hash(base64.b64decode(b['torrent_base64']))
        self.items.append(dict(id=h,task_id=h,hash=h,name='same title',size=123,total_size=123,progress=0,uploaded=0,save_path=b['save_path'],tags=b['tags'],added_at=time.time()))
    def action(self,tid,action,delete_data=False):
        assert action=='delete' and delete_data is False
        self.deletes+=1; self.items=[i for i in self.items if i['id']!=tid]

class FakeSite:
    def __init__(self): self.rows=[dict(id='17',name='same title',size=123,seeders=5,leechers=30,promotion='FREE')]
    def search(self,*args): return self.rows,len(self.rows)
    def detail(self,tid): return dict(self.rows[0])
    def torrent(self,tid): return RAW
    def api(self,*args): return {'vip':True,'vipUntil':int(time.time()+86400)}

class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.app=Application(self.tmp.name,'setup'); self.s=getattr(self.app,'automations',None)
        self.d=FakeDownloader(); self.site=FakeSite()
        self.app.adapter=lambda c:self.d
        cfg=dict(id=1,name='engine',type='qbittorrent',url='http://localhost:8080',default_save_path='/downloads')
        self.app.db.execute('INSERT INTO downloaders VALUES(?,?)',('1',self.app.cipher.encrypt(json.dumps(cfg).encode()).decode()))
        site=dict(id='site1',name='M-Team',type='mteam',url='https://api.m-team.cc/api',api_key='not-real',enabled=True)
        self.app.db.execute('INSERT INTO sites VALUES(?,?)',('site1',self.app.cipher.encrypt(json.dumps(site).encode()).decode())); self.app.db.commit()
        self.app.sites.adapter=lambda c:self.site
    def tearDown(self):
        if self.s: self.s.close()
        self.app.sites.pool.shutdown(wait=True); self.app.db.close(); self.tmp.cleanup()
    def create(self,**kw):
        return self.app.dispatch('POST','/automations',{},dict(kind='brush',site_id='site1',downloader_id=1,**kw),{'id':'session'},'test')['item']
    def runjob(self,a,dry_run=False,rid=None):
        r=self.s.enqueue(a['id'],rid or str(uuid.uuid4()),dry_run)
        self.s._execute(r['run_id'])
        return self.s.run(r['run_id'])
    def test_defaults_and_encrypted_cookie(self):
        a=self.create(); self.assertFalse(a['enabled']); self.assertFalse(a['auto_delete']); self.assertEqual(a['concurrent'],8)
        with self.assertRaises(ApiError): self.runjob(a)
        result=self.app.dispatch('POST','/automations',{},dict(kind='hdfans_signin',cookie='uid=42; passhash=private'),{'id':'session'},'test')
        self.assertNotIn('private',json.dumps(result)); self.assertTrue(result['item']['has_cookie'])
        self.assertNotIn('passhash',str(self.app.db.execute('SELECT config FROM automations').fetchall()))
    def test_creation_uuid_same_body_replays_original_receipt(self):
        rid=str(uuid.uuid4()); first=self.create(request_id=rid)
        second=self.create(request_id=rid)
        self.assertEqual(first,second); self.assertEqual(len(self.s.list()),1)
        with self.assertRaises(ApiError) as error: self.create(request_id=rid,name='changed')
        self.assertEqual(error.exception.code,'REQUEST_ID_CONFLICT')
    def test_creation_receipt_survives_restart_and_does_not_recreate_deleted_task(self):
        rid=str(uuid.uuid4()); first=self.create(request_id=rid)
        self.s.dispatch('DELETE','/automations/'+first['id'],{},{}); other=Application(self.tmp.name,'setup')
        try:
            response=other.dispatch('POST','/automations',{},dict(kind='brush',site_id='site1',downloader_id=1,request_id=rid),{'id':'session'},'test')
            self.assertEqual(response['item'],first); self.assertEqual(other.automations.list(),[])
        finally: other.automations.close(); other.sites.pool.shutdown(wait=True); other.db.close()
    def test_creation_receipt_failure_rolls_back_task_and_retry_is_safe(self):
        self.app.db.execute("CREATE TRIGGER fail_receipt BEFORE INSERT ON automation_creates BEGIN SELECT RAISE(ABORT,'fixture failure'); END"); self.app.db.commit()
        rid=str(uuid.uuid4())
        with self.assertRaises(Exception): self.create(request_id=rid)
        self.assertEqual(self.s.list(),[])
        self.app.db.execute('DROP TRIGGER fail_receipt'); self.app.db.commit()
        first=self.create(request_id=rid); self.assertEqual(self.create(request_id=rid),first)
    def test_creation_uuid_is_serialized_across_database_connections(self):
        from concurrent.futures import ThreadPoolExecutor
        other=Application(self.tmp.name,'setup'); body=dict(kind='brush',site_id='site1',downloader_id=1,request_id=str(uuid.uuid4()))
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(lambda app:app.dispatch('POST','/automations',{},body,{'id':'session'},'test')['item'],[self.app,other]))
            self.assertEqual(results[0],results[1]); self.assertEqual(len(self.s.list()),1)
        finally: other.automations.close(); other.sites.pool.shutdown(wait=True); other.db.close()
    def test_add_bound_by_hash_and_marker_survives_restart(self):
        a=self.create(enabled=True); r=self.runjob(a); self.assertEqual(r['status'],'completed'); self.assertEqual(self.d.adds,1)
        self.assertEqual(len(self.s.owned(a['id'])),1)
        self.runjob(a); self.assertEqual(self.d.adds,1)
        from server.automations import AutomationService
        again=AutomationService(self.app); self.assertEqual(again.owned(a['id'])[0]['task_id'],self.d.items[0]['id']); again.close()
    def test_uncertain_add_is_durable_and_not_replayed(self):
        a=self.create(enabled=True); self.d.fail_add=True; rid=str(uuid.uuid4())
        r=self.runjob(a,rid=rid); self.assertEqual(r['status'],'needs_review')
        self.runjob(a,rid=rid); self.runjob(a); self.assertEqual(self.d.adds,1)
        self.assertNotIn('credential',json.dumps(self.s.logs(a['id'])))
    def test_delayed_add_reconciles_marker_and_hash_without_replay(self):
        original=self.d.add
        def uncertain(body): original(body); raise OSError('response lost')
        self.d.add=uncertain; a=self.create(enabled=True)
        self.assertEqual(self.runjob(a)['status'],'needs_review'); self.assertEqual(self.s.owned(a['id']),[])
        self.runjob(a); self.assertEqual(self.d.adds,1); self.assertEqual(len(self.s.owned(a['id'])),1)
    def test_reconcile_does_not_claim_preexisting_task_with_copied_marker(self):
        original=self.d.add
        def uncertain(body): original(body); self.d.items[0]['added_at']-=86400; raise OSError('response lost')
        self.d.add=uncertain; a=self.create(enabled=True); self.runjob(a); self.runjob(a)
        self.assertEqual(self.s.owned(a['id']),[]); self.assertEqual(self.d.adds,1)
    def test_manual_same_hash_never_owned_or_mutated(self):
        from server.automations import torrent_hash
        h=torrent_hash(RAW); self.d.items=[dict(id=h,hash=h,name='same title',progress=1,size=123,tags=[],uploaded=0)]
        a=self.create(enabled=True,auto_delete=True); self.runjob(a)
        self.assertEqual(self.d.adds,0); self.assertEqual(self.d.deletes,0); self.assertEqual(self.s.owned(a['id']),[])
    def test_capacity_counts_paused_manual_incomplete_tasks(self):
        self.d.items=[dict(id=str(i),progress=0.3,size=123,tags=[],state='paused') for i in range(8)]
        a=self.create(enabled=True); r=self.runjob(a); self.assertEqual(self.d.adds,0); self.assertEqual(r['result']['reason'],'concurrency_limit')
    def test_disk_reserve_and_outstanding_downloads_gate_add(self):
        self.d.automation_space=lambda p:110*1024**3
        self.d.items=[dict(id='manual',progress=0,size=20*1024**3,tags=[])]
        a=self.create(enabled=True); self.runjob(a); self.assertEqual(self.d.adds,0)
    def test_dry_run_never_adds_or_claims_daily(self):
        a=self.create(); r=self.runjob(a,True); self.assertEqual(self.d.adds,0); self.assertEqual(r['result']['would_add'],['17'])
    def test_stop_cancels_queued_and_disables(self):
        a=self.create(enabled=True); r=self.s.enqueue(a['id'],str(uuid.uuid4()),False); self.s.stop(a['id']); self.s._execute(r['run_id'])
        self.assertEqual(self.d.adds,0); self.assertFalse(self.s.get(a['id'])['enabled']); self.assertEqual(self.s.run(r['run_id'])['status'],'cancelled')
    def test_stop_works_after_referenced_downloader_removed(self):
        a=self.create(enabled=True); self.app.db.execute('DELETE FROM downloaders'); self.app.db.commit()
        self.s.stop(a['id']); self.assertFalse(self.s.get(a['id'])['enabled'])
    def test_nonfree_requires_verified_current_vip_and_explicit_selection(self):
        self.site.rows[0]['promotion']='NORMAL'; a=self.create(enabled=True,only_free=False,promotions=['FREE','NORMAL'])
        self.site.api=lambda *a:{'vip':True,'vipUntil':int(time.time()-1)}
        self.runjob(a); self.assertEqual(self.d.adds,0)
        self.site.api=lambda *a:{'vip':True,'vipUntil':int(time.time()+86400)}
        self.runjob(a); self.assertEqual(self.d.adds,1)
    def test_unknown_obligation_and_permanent_protection_block_deletion(self):
        a=self.create(enabled=True,auto_delete=True); self.runjob(a)
        h=self.d.items[0]['id']; self.d.items[0]['progress']=1
        self.app.db.execute('UPDATE automation_owned SET added_at=?',(time.time()-86400,)); self.app.db.commit()
        self.s.protect(a['id'],h,'permanent'); self.runjob(a)
        self.assertEqual(self.d.deletes,0); self.assertEqual(len(self.s.protections(a['id'])),1)
    def test_unknown_obligation_blocks_otherwise_eligible_retirement(self):
        a=self.create(enabled=True,auto_delete=True); self.runjob(a); h=self.d.items[0]['id']; now=time.time()
        self.d.items[0].update(progress=1,added_at=now-86400)
        self.app.db.execute('UPDATE automation_owned SET added_at=?',(now-86400,))
        self.app.db.execute('INSERT INTO automation_samples VALUES(?,?,?,?)',('1',h,now-3601,0)); self.app.db.commit()
        result=self.runjob(a); self.assertEqual(result['result']['retention'][0]['reason'],'obligations_unknown'); self.assertEqual(self.d.deletes,0)
    def test_uncertain_delete_never_replays(self):
        a=self.create(enabled=True,auto_delete=True); self.runjob(a); h=self.d.items[0]['id']; now=time.time()
        self.d.items[0].update(progress=1,added_at=now-86400)
        self.app.db.execute("UPDATE automation_owned SET added_at=?,obligations='verified_clear'",(now-86400,))
        self.app.db.execute('INSERT INTO automation_samples VALUES(?,?,?,?)',('1',h,now-3601,0)); self.app.db.commit()
        def fail(*args): self.d.deletes+=1; raise OSError('uncertain')
        self.d.action=fail
        self.assertEqual(self.runjob(a)['status'],'needs_review'); self.runjob(a); self.assertEqual(self.d.deletes,1)
    def test_daily_schedule_persisted_and_attempt_never_repeated(self):
        a=self.s.save(dict(kind='hdfans_signin',cookie='uid=1',enabled=True))
        first=a['next_run']; self.assertEqual(self.s.get(a['id'])['next_run'],first)
        with patch('server.automations.hdfans_signin',return_value={'status':'success','message':'签到成功'}) as call:
            self.runjob(a); self.runjob(a); self.assertEqual(call.call_count,1)
    @staticmethod
    def stamp(value): return datetime.fromisoformat(value).replace(tzinfo=timezone(timedelta(hours=8))).timestamp()
    def stale_daily(self):
        a=self.s.save(dict(kind='hdfans_signin',cookie='uid=1',enabled=True,window_start='08:00',window_end='10:00'))
        self.app.db.execute('UPDATE automations SET next_run=? WHERE id=?',(self.stamp('2026-10-05T09:00:00'),a['id'])); self.app.db.commit(); return a
    def test_downtime_after_window_schedules_tomorrow_without_queueing(self):
        a=self.stale_daily()
        with patch('server.automations.time.time',return_value=self.stamp('2026-10-06T23:00:00')),patch.object(self.s.pool,'submit'):
            self.s._tick()
        self.assertEqual(self.s.logs(a['id']),[])
        self.assertGreaterEqual(self.s.get(a['id'])['next_run'],self.stamp('2026-10-07T08:00:00'))
        self.assertLess(self.s.get(a['id'])['next_run'],self.stamp('2026-10-07T10:00:00'))
    def test_downtime_before_window_schedules_today_without_queueing(self):
        a=self.stale_daily()
        with patch('server.automations.time.time',return_value=self.stamp('2026-10-06T07:00:00')),patch.object(self.s.pool,'submit'):
            self.s._tick()
        self.assertEqual(self.s.logs(a['id']),[])
        self.assertGreaterEqual(self.s.get(a['id'])['next_run'],self.stamp('2026-10-06T08:00:00'))
        self.assertLess(self.s.get(a['id'])['next_run'],self.stamp('2026-10-06T10:00:00'))
    def test_downtime_inside_window_queues_once_and_schedules_tomorrow(self):
        a=self.stale_daily()
        with patch('server.automations.time.time',return_value=self.stamp('2026-10-06T09:00:00')),patch.object(self.s.pool,'submit'):
            self.s._tick(); self.s._tick()
        self.assertEqual(len(self.s.logs(a['id'])),1); self.assertTrue(self.s.logs(a['id'])[0]['scheduled'])
        self.assertGreaterEqual(self.s.get(a['id'])['next_run'],self.stamp('2026-10-07T08:00:00'))
    def test_next_day_restart_does_not_run_yesterdays_missed_window(self):
        a=self.stale_daily(); other=Application(self.tmp.name,'setup')
        try:
            with patch('server.automations.time.time',return_value=self.stamp('2026-10-07T00:01:00')),patch.object(other.automations.pool,'submit'):
                other.automations._tick()
            self.assertEqual(other.automations.logs(a['id']),[])
            self.assertGreaterEqual(other.automations.get(a['id'])['next_run'],self.stamp('2026-10-07T08:00:00'))
        finally: other.automations.close(); other.sites.pool.shutdown(wait=True); other.db.close()
    def test_previously_queued_scheduled_signin_rechecks_window_before_network(self):
        a=self.stale_daily(); run=self.s.enqueue(a['id'],str(uuid.uuid4()),False,scheduled=True)
        with patch('server.automations.time.time',return_value=self.stamp('2026-10-06T23:00:00')),patch('server.automations.hdfans_signin') as signin:
            self.s._execute(run['run_id'])
        self.assertEqual(signin.call_count,0); self.assertEqual(self.s.run(run['run_id'])['result']['reason'],'outside_window')
        self.assertEqual(self.app.db.execute('SELECT COUNT(*) FROM automation_daily').fetchone()[0],0)
    def test_legacy_queue_schema_migrates_without_unplanned_overnight_requests(self):
        a=self.stale_daily(); rid=str(uuid.uuid4())
        self.app.db.execute('DROP TABLE automation_runs')
        self.app.db.execute('CREATE TABLE automation_runs(id TEXT PRIMARY KEY,automation_id TEXT NOT NULL,generation INTEGER NOT NULL,dry_run INTEGER NOT NULL,status TEXT NOT NULL,created_at REAL NOT NULL,started_at REAL,finished_at REAL,result TEXT NOT NULL)')
        self.app.db.execute('INSERT INTO automation_runs VALUES(?,?,?,?,?,?,?,?,?)',(rid,a['id'],1,0,'queued',self.stamp('2026-10-06T09:00:00'),None,None,'{}')); self.app.db.commit()
        other=Application(self.tmp.name,'setup')
        try:
            self.assertTrue(other.automations.run(rid)['scheduled'])
            with patch('server.automations.time.time',return_value=self.stamp('2026-10-06T23:00:00')),patch('server.automations.hdfans_signin') as signin:
                other.automations._execute(rid)
            self.assertEqual(signin.call_count,0); self.assertEqual(other.automations.run(rid)['result']['reason'],'outside_window')
        finally: other.automations.close(); other.sites.pool.shutdown(wait=True); other.db.close()
    def test_scheduler_single_instance_and_nonblocking_enqueue(self):
        from server.automations import AutomationService
        other=AutomationService(self.app)
        try: self.assertTrue(self.s.acquire_lease()); self.assertFalse(other.acquire_lease())
        finally: other.close()
    def test_delete_data_rejected(self):
        with self.assertRaises(ApiError): self.create(delete_data=True)
    def test_actual_metainfo_size_prevents_underreported_candidate_admission(self):
        huge=RAW.replace(b'lengthi123e',b'lengthi600000000000e')
        self.site.torrent=lambda tid:huge
        a=self.create(enabled=True); self.runjob(a); self.assertEqual(self.d.adds,0)
    def test_disk_rechecked_after_slow_site_lookup(self):
        values=iter([1000*1024**3,50*1024**3]); self.d.automation_space=lambda p:next(values)
        a=self.create(enabled=True); self.runjob(a); self.assertEqual(self.d.adds,0)
    def test_disable_during_site_request_prevents_add(self):
        a=self.create(enabled=True)
        def torrent(tid): self.s.stop(a['id']); return RAW
        self.site.torrent=torrent; self.runjob(a); self.assertEqual(self.d.adds,0)
    def test_low_upload_needs_full_hour_and_clear_obligations(self):
        a=self.create(enabled=True,auto_delete=True); self.runjob(a); h=self.d.items[0]['id']; now=time.time()
        self.d.items[0].update(progress=1,added_at=now-86400)
        self.app.db.execute("UPDATE automation_owned SET added_at=?,obligations='verified_clear'",(now-86400,))
        self.app.db.execute('INSERT INTO automation_samples VALUES(?,?,?,?)',('1',h,now-3601,0)); self.app.db.commit()
        self.runjob(a); self.assertEqual(self.d.deletes,1); self.assertEqual(self.s.owned(a['id'])[0]['state'],'removed')
        self.runjob(a); self.assertEqual(self.d.deletes,1); self.assertEqual(self.d.adds,1)
    def test_deleted_and_readded_task_does_not_match_ownership(self):
        a=self.create(enabled=True,auto_delete=True); self.runjob(a)
        self.d.items[0]['added_at']+=3600; self.runjob(a); self.assertEqual(self.d.deletes,0)
    def test_random_schedule_survives_database_reopen(self):
        a=self.s.save(dict(kind='hdfans_signin',cookie='uid=1')); other=Application(self.tmp.name,'setup')
        try: self.assertEqual(other.automations.get(a['id'])['next_run'],a['next_run']); self.assertFalse(other.automations.acquire_lease() if self.s.acquire_lease() else True)
        finally: other.automations.close(); other.sites.pool.shutdown(wait=True); other.db.close()
    def test_scheduler_consumes_job_without_phone_or_polling(self):
        a=self.create(enabled=True); queued=self.s.enqueue(a['id'],str(uuid.uuid4()),False); self.s.start()
        deadline=time.monotonic()+3
        while self.s.run(queued['run_id'])['status'] in ('queued','running') and time.monotonic()<deadline: time.sleep(.02)
        self.assertEqual(self.s.run(queued['run_id'])['status'],'completed'); self.assertEqual(self.d.adds,1)
    def test_promotion_rechecked_before_mutation(self):
        self.site.detail=lambda tid:dict(self.site.rows[0],promotion='NORMAL')
        a=self.create(enabled=True); self.runjob(a); self.assertEqual(self.d.adds,0)
    def test_simultaneous_runs_cannot_admit_two_into_last_slot(self):
        from concurrent.futures import ThreadPoolExecutor
        self.d.items=[dict(id='manual-'+str(i),progress=0,size=10,tags=[]) for i in range(7)]
        a=self.create(enabled=True); b=self.create(enabled=True)
        ar=self.s.enqueue(a['id'],str(uuid.uuid4()),False); br=self.s.enqueue(b['id'],str(uuid.uuid4()),False)
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(self.s._execute,[ar['run_id'],br['run_id']]))
        self.assertEqual(self.d.adds,1); self.assertEqual(len(self.d.items),8)

class ParsingTests(unittest.TestCase):
    def test_vip_requires_true_flag_and_supports_member_status(self):
        from server.automations import vip_expiry
        self.assertEqual(vip_expiry({'memberStatus':{'vip':True,'vipUntil':'2026-10-31 10:44:17'}}),1793414657)
        self.assertEqual(vip_expiry({'vip':False,'vipUntil':4102444800}),0)
        self.assertEqual(vip_expiry({'vipUntil':4102444800}),0)
    def test_attendance_never_calls_login_or_challenge_success(self):
        from server.automations import parse_attendance
        self.assertEqual(parse_attendance('签到成功')['status'],'success')
        self.assertEqual(parse_attendance('今天已经签到')['status'],'already_signed')
        self.assertEqual(parse_attendance('<input name="username"><input name="password">签到成功')['status'],'auth_failure')
        self.assertEqual(parse_attendance('Cloudflare Just a moment 验证码 签到成功')['status'],'challenge')
        self.assertEqual(parse_attendance('历史连续签到记录')['status'],'unknown')
        self.assertEqual(parse_attendance('<script>const label="签到成功";</script>普通页面')['status'],'unknown')
        self.assertEqual(parse_attendance('<input name = "username"><input name = "password">签到成功')['status'],'auth_failure')
    def test_malformed_torrent_and_v2_only_fail_closed(self):
        from server.automations import torrent_hash
        for raw in (b'djunk',b'd4:infod12:meta versioni2eee',RAW+b'junk'):
            with self.assertRaises(ApiError): torrent_hash(raw)

if __name__=='__main__': unittest.main()
