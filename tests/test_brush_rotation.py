"""Brush lifecycle tests exercise persisted ownership and actual file safety gates."""
import base64, os, tempfile, time, unittest
from pathlib import Path
from unittest.mock import patch
import test_automations as fixtures
from server.app import ApiError
from server.automations import torrent_manifest
from server.adapters import QBittorrent, Transmission, verified_storage_path


class RotationTests(unittest.TestCase):
    setUp=fixtures.AutomationTests.setUp
    tearDown=fixtures.AutomationTests.tearDown
    create=fixtures.AutomationTests.create
    runjob=fixtures.AutomationTests.runjob
    def test_new_add_gets_exclusive_directory_and_policy_snapshot(self):
        a=self.create(enabled=True,retention_policy='no_obligation')
        self.runjob(a)
        item=self.d.items[0]
        self.assertEqual(item['save_path'],'/downloads/nd-brush/'+a['id']+'/'+item['id'])
        own=self.s.owned(a['id'])[0]
        self.assertEqual(own['retention_policy'],'no_obligation')
        self.assertEqual(own['files'],[{'name':'test','size':123}])

    def test_explicit_policy_can_retire_and_unchanged_candidate_stays_out(self):
        a=self.create(enabled=True,auto_delete=True,retention_policy='no_obligation')
        self.runjob(a); item=self.d.items[0]; now=time.time()
        item.update(progress=1,added_at=now-86400)
        self.app.db.execute('UPDATE automation_owned SET added_at=?',(now-86400,))
        self.app.db.execute('INSERT INTO automation_samples VALUES(?,?,?,?)',('1',item['id'],now-3601,0)); self.app.db.commit()
        run=self.runjob(a)
        self.assertEqual(self.d.deletes,1); self.assertEqual(self.d.adds,1)
        self.assertEqual(run['result']['retention'][0]['deleted'],True)

    def test_bad_policy_is_rejected(self):
        with self.assertRaises(ApiError): self.create(retention_policy='trust-me')

    def mapped(self):
        root=Path(self.tmp.name)/'downloads'; root.mkdir(exist_ok=True)
        env=patch.dict(os.environ,{'ND_BRUSH_VERIFY_ROOT':'/downloads','ND_BRUSH_VERIFY_MOUNT':str(root)})
        env.start(); self.addCleanup(env.stop)
        self.d=FileDownloader(root); self.app.adapter=lambda c:self.d
        return root

    def mature(self,item,seconds=86400,ratio=2,uploaded=0):
        now=time.time(); item.update(progress=1,state='completed',added_at=now-86400,seeding_seconds=seconds,ratio=ratio,leechers=0,uploaded=uploaded)
        self.app.db.execute('UPDATE automation_owned SET added_at=? WHERE info_hash=?',(now-86400,item['id']))
        self.app.db.execute('INSERT INTO automation_samples VALUES(?,?,?,?)',('1',item['id'],now-3601,0)); self.app.db.commit()

    def test_add_delete_measure_space_then_replace(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); old=self.d.items[0]; oldpath=self.d.local(old['save_path'])/'test'; self.mature(old)
        raw=fixtures.RAW.replace(b'4:test',b'4:next'); self.site.torrent=lambda tid:raw
        self.site.rows[0]['id']='18'; self.d.events.clear()
        result=self.runjob(a)
        self.assertEqual(result['result']['reason'],'added'); self.assertEqual(self.d.deletes,1); self.assertEqual(self.d.adds,2)
        self.assertFalse(oldpath.exists()); self.assertEqual(len(self.d.items),1)
        deletion=self.d.events.index('delete'); added=self.d.events.index('add')
        self.assertIn('space',self.d.events[deletion+1:added]); self.assertIn('tasks',self.d.events[deletion+1:added])

    def test_delete_http_success_without_file_removal_blocks_replacement(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); self.mature(self.d.items[0]); self.d.keep_files=True
        self.site.torrent=lambda tid:fixtures.RAW.replace(b'4:test',b'4:next')
        result=self.runjob(a); self.assertEqual(result['status'],'needs_review'); self.assertEqual(self.d.adds,1)
        self.runjob(a); self.assertEqual(self.d.deletes,1); self.assertEqual(self.d.adds,1)

    def test_space_not_released_cannot_be_inferred_from_successful_delete(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); self.mature(self.d.items[0]); self.d.free=50*1024**3
        self.site.torrent=lambda tid:fixtures.RAW.replace(b'4:test',b'4:next')
        result=self.runjob(a); self.assertEqual(result['result']['reason'],'disk_or_capacity_limit'); self.assertEqual(self.d.deletes,1); self.assertEqual(self.d.adds,1)

    def test_unchanged_deleted_torrent_never_loops_but_improvement_can_reenter(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); self.mature(self.d.items[0]); self.runjob(a); self.runjob(a)
        self.assertEqual(self.d.adds,1)
        self.site.rows[0]['leechers']=31
        self.runjob(a); self.assertEqual(self.d.adds,2); self.assertEqual(self.s.owned(a['id'])[0]['state'],'active')
        self.assertEqual(self.app.db.execute('SELECT COUNT(*) FROM automation_intent_history').fetchone()[0],2)

    def test_seed_hours_and_ratio_must_both_be_satisfied(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='seed_hours_ratio',min_seed_hours=12,min_ratio=1.5)
        self.runjob(a); item=self.d.items[0]; self.mature(item,seconds=11*3600,ratio=2)
        self.assertEqual(self.runjob(a)['result']['retention'][0]['reason'],'seed_hours_required')
        item.update(seeding_seconds=13*3600,ratio=1)
        self.assertEqual(self.runjob(a)['result']['retention'][0]['reason'],'share_ratio_required')
        item['ratio']=1.5; self.runjob(a); self.assertEqual(self.d.deletes,1)

    def test_changing_policy_does_not_release_unknown_legacy_ownership(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True)
        self.runjob(a); self.mature(self.d.items[0]); self.s.save({'retention_policy':'no_obligation'},a['id'])
        self.assertEqual(self.runjob(a)['result']['retention'][0]['reason'],'obligations_unknown'); self.assertEqual(self.d.deletes,0)

    def test_manual_path_overlap_protects_both_tasks(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); item=self.d.items[0]; self.mature(item)
        self.d.items.append(dict(id='a'*40,save_path=item['save_path'],progress=1,size=123,tags=[]))
        self.assertEqual(self.runjob(a)['result']['retention'][0]['reason'],'shared_storage'); self.assertEqual(self.d.deletes,0)

    def test_manual_root_files_inside_owned_directory_are_protected(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); item=self.d.items[0]; self.mature(item)
        self.d.items.append(dict(id='a'*40,save_path='/downloads',progress=1,size=123,tags=[],files=[{'name':item['save_path'][len('/downloads/'):]+'/test','size':123}]))
        self.assertEqual(self.runjob(a)['result']['retention'][0]['reason'],'shared_storage'); self.assertEqual(self.d.deletes,0)

    def test_permanent_protection_wins_and_manual_same_hash_is_never_adopted(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); item=self.d.items[0]; self.mature(item); self.s.protect(a['id'],item['id'])
        self.assertEqual(self.runjob(a)['result']['retention'][0]['reason'],'permanent_protection'); self.assertEqual(self.d.deletes,0)
        item['tags']=[]; self.runjob(a); self.assertEqual(self.d.deletes,0)

    def test_untracked_file_or_changed_file_list_blocks_deletion(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); item=self.d.items[0]; self.mature(item); local=self.d.local(item['save_path']); (local/'manual.txt').write_text('manual')
        self.assertEqual(self.runjob(a)['result']['retention'][0]['reason'],'storage_files_unverified'); self.assertEqual(self.d.deletes,0)
        (local/'manual.txt').unlink(); item['files']=[{'name':'other','size':123}]
        self.assertEqual(self.runjob(a)['result']['retention'][0]['reason'],'files_changed'); self.assertEqual(self.d.deletes,0)

    def test_hard_link_file_blocks_deletion(self):
        root=self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); item=self.d.items[0]; self.mature(item); os.link(self.d.local(item['save_path'])/'test',root/'manual-copy')
        self.assertEqual(self.runjob(a)['result']['retention'][0]['reason'],'storage_files_unverified'); self.assertEqual(self.d.deletes,0)

    def test_one_bad_torrent_only_is_removed_per_run(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); self.site.torrent=lambda tid:fixtures.RAW.replace(b'4:test',b'4:next'); self.runjob(a)
        for item in self.d.items: self.mature(item)
        self.runjob(a); self.assertEqual(self.d.deletes,1)

    def test_effective_upload_keeps_completed_torrent(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); self.mature(self.d.items[0],uploaded=150*1024**2)
        self.assertEqual(self.runjob(a)['result']['retention'][0]['reason'],'uploading_effectively'); self.assertEqual(self.d.deletes,0)

    def test_low_demand_needs_the_full_window(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation',low_leechers=1)
        self.runjob(a); item=self.d.items[0]; self.mature(item); item['swarm_leechers']=0
        self.assertEqual(self.runjob(a)['result']['retention'][0]['reason'],'insufficient_demand_samples')
        self.app.db.execute('INSERT INTO automation_demand_samples VALUES(?,?,?,?)',('1',item['id'],time.time()-3601,5)); self.app.db.commit()
        self.assertEqual(self.runjob(a)['result']['retention'][0]['reason'],'active_demand'); self.assertEqual(self.d.deletes,0)

    def test_uncertain_delete_later_reconciles_only_when_files_are_gone(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); item=self.d.items[0]; self.mature(item); self.d.keep_files=True
        self.assertEqual(self.runjob(a)['status'],'needs_review'); self.runjob(a)
        self.assertEqual(self.s.owned(a['id'])[0]['state'],'active')
        (self.d.local(item['save_path'])/'test').unlink()
        result=self.runjob(a); self.assertEqual(result['status'],'completed'); self.assertEqual(self.s.owned(a['id'])[0]['state'],'removed')
        self.assertEqual(self.d.adds,1); self.assertEqual(self.d.deletes,1)

    def test_data_delete_rechecks_files_immediately_before_mutation(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); item=self.d.items[0]; self.mature(item)
        original=self.d.detail; calls=[]
        def changed(tid):
            result=original(tid); calls.append(tid)
            if len(calls)==2: result['files']=[{'name':'manual.txt','size':123}]
            return result
        self.d.detail=changed
        self.assertEqual(self.runjob(a)['result']['retention'][0]['reason'],'files_changed'); self.assertEqual(self.d.deletes,0)

    def test_readmission_after_lost_response_keeps_new_policy_and_new_owner(self):
        self.mapped(); a=self.create(enabled=True,auto_delete=True,delete_data=True,retention_policy='no_obligation')
        self.runjob(a); self.mature(self.d.items[0]); self.runjob(a)
        self.site.rows[0]['leechers']=31; original=self.d.add
        def lost(body): original(body); raise OSError('lost')
        self.d.add=lost
        self.assertEqual(self.runjob(a)['status'],'needs_review'); self.runjob(a)
        own=self.s.owned(a['id'])[0]; self.assertEqual(own['state'],'active'); self.assertEqual(own['retention_policy'],'no_obligation')
        self.assertEqual(self.d.adds,2)

    def test_remote_path_validation_rejects_traversal(self):
        self.mapped()
        for value in ('/downloads/../manual','/downloads/./manual','//downloads','/downloads\\manual','/downloads/\x00manual'):
            with self.subTest(value=value),self.assertRaises(ApiError): self.create(save_path=value)


class MetainfoSafetyTests(unittest.TestCase):
    def test_exact_info_bytes_define_hash_and_piece_count_must_match_size(self):
        import hashlib
        info=fixtures.RAW[7:-1]
        self.assertEqual(torrent_manifest(fixtures.RAW)[0],hashlib.sha1(info).hexdigest())
        with self.assertRaises(ApiError): torrent_manifest(fixtures.RAW.replace(b'i123e',b'i32769e'))

    def test_metainfo_path_traversal_symlinks_and_aliases_are_rejected(self):
        def encode(value):
            if type(value) is int: return b'i'+str(value).encode()+b'e'
            if isinstance(value,bytes): return str(len(value)).encode()+b':'+value
            if isinstance(value,list): return b'l'+b''.join(encode(v) for v in value)+b'e'
            return b'd'+b''.join(encode(k)+encode(v) for k,v in sorted(value.items()))+b'e'
        base={b'name':b'root',b'piece length':16384,b'pieces':b'x'*20}
        bad=[{b'files':[{b'length':123,b'path':[b'..',b'manual']}]},
             {b'files':[{b'length':123,b'path':[b'file'],b'attr':b'l',b'symlink path':[b'manual']}]},
             {b'length':123,b'name.utf-8':b'manual'},
             {b'files':[{b'length':41,b'path':[p]} for p in (b'file',b'FILE',b'other')]},
             {b'files':[{b'length':41,b'path':p} for p in ([b'a'],[b'a-b'],[b'a',b'file'])]}]
        for extra in bad:
            with self.subTest(extra=extra),self.assertRaises(ApiError): torrent_manifest(encode({b'info':base|extra}))


class StorageAdapterTests(unittest.TestCase):
    def test_qb_child_space_requires_verified_mapping_on_same_volume(self):
        qb=QBittorrent({'id':1,'name':'fixture','url':'http://127.0.0.1:8080'})
        qb.getjson=lambda route,params=None: {'save_path':'/downloads'} if route=='app/preferences' else {'server_state':{'free_space_on_disk':1234}}
        with patch.dict(os.environ,{'ND_BRUSH_VERIFY_ROOT':'','ND_BRUSH_VERIFY_MOUNT':''}):
            self.assertEqual(qb.automation_space('/downloads'),1234)
            with self.assertRaises(ApiError): qb.automation_space('/downloads/nd-brush/id/hash')
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'ND_BRUSH_VERIFY_ROOT':'/downloads','ND_BRUSH_VERIFY_MOUNT':root}):
            self.assertEqual(qb.automation_space('/downloads/nd-brush/id/hash'),1234)
            with self.assertRaises(ApiError): qb.automation_space('/downloads-other/nd-brush')
            with self.assertRaises(ApiError): verified_storage_path('/downloads/../other')

    def test_seeding_seconds_are_actual_downloader_counters(self):
        c={'id':1,'name':'fixture','url':'http://127.0.0.1:8080'}
        self.assertEqual(QBittorrent(c).normalize({'hash':'a'*40,'seeding_time':123})['seeding_seconds'],123)
        self.assertEqual(Transmission(c).normalize({'id':7,'secondsSeeding':456})['seeding_seconds'],456)

    def test_rotation_demand_is_not_number_of_connected_peers(self):
        c={'id':1,'name':'fixture','url':'http://127.0.0.1:8080'}
        qb=QBittorrent(c)
        self.assertEqual(qb.normalize({'hash':'a'*40,'num_leechs':0,'num_incomplete':30})['swarm_leechers'],30)
        self.assertEqual(qb.normalize({'hash':'a'*40,'num_leechs':0})['swarm_leechers'],-1)
        self.assertEqual(Transmission(c).normalize({'id':7,'peersGettingFromUs':0})['swarm_leechers'],-1)

    def test_verification_rejects_symbolic_link_directory(self):
        with tempfile.TemporaryDirectory() as root,patch.dict(os.environ,{'ND_BRUSH_VERIFY_ROOT':'/downloads','ND_BRUSH_VERIFY_MOUNT':root}):
            target=Path(root)/'target'; target.mkdir(); link=Path(root)/'alias'
            try: link.symlink_to(target,target_is_directory=True)
            except OSError: self.skipTest('OS does not allow symlink creation for this account')
            with self.assertRaises(ApiError): verified_storage_path('/downloads/alias')


class FileDownloader(fixtures.FakeDownloader):
    def __init__(self,root):
        super().__init__(); self.root=root; self.events=[]; self.free=1000*1024**3; self.keep_files=False
    def local(self,path): return self.root/path[len('/downloads/'):]
    def tasks(self): self.events.append('tasks'); return super().tasks()
    def automation_space(self,path): self.events.append('space'); return self.free
    def add(self,b):
        self.events.append('add'); super().add(b)
        _,_,files=torrent_manifest(base64.b64decode(b['torrent_base64'])); item=self.items[-1]; item['files']=files
        for file in files:
            path=self.local(item['save_path'])/file['name']; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(b'x'*file['size'])
    def detail(self,tid):
        item=next(t for t in self.items if t['id']==tid)
        return {'item':dict(item),'files':item.get('files',[])}
    def action(self,tid,action,delete_data=False):
        assert action=='delete'; self.events.append('delete'); self.deletes+=1
        item=next(t for t in self.items if t['id']==tid)
        if delete_data and not self.keep_files:
            for file in item['files']: (self.local(item['save_path'])/file['name']).unlink()
        self.items=[t for t in self.items if t['id']!=tid]


if __name__=='__main__': unittest.main()
