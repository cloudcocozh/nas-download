import json, sys, threading, unittest
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs,urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

class Fixture(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,body,status=200,headers=None):
        raw=body if isinstance(body,bytes) else json.dumps(body).encode(); self.send_response(status)
        for k,v in (headers or {}).items(): self.send_header(k,v)
        self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        path=urlsplit(self.path).path
        if path.endswith('/app/version'): return self.send(self.server.version.encode())
        if path.endswith('/torrents/info'): return self.send([{'hash':'a'*40,'name':'Ubuntu','size':100,'progress':0.5,'state':'downloading','dlspeed':10,'upspeed':2,'save_path':'/downloads','eta':5,'ratio':0.2,'num_seeds':2,'num_leechs':3}])
        if path.endswith('/torrents/files'): return self.send([{'name':'file.iso','size':100,'progress':0.5}])
        if path.endswith('/torrents/trackers'): return self.send([{'url':'https://tracker','status':2,'msg':'working'}])
        self.send({},404)
    def do_POST(self):
        raw=self.rfile.read(int(self.headers.get('Content-Length',0))); self.server.calls.append((self.path,raw))
        if getattr(self.server,'redirect_login',False) and self.path.endswith('/auth/login'): return self.send(b'',302,{'Location':'/api/v2/torrents/delete'})
        if getattr(self.server,'disconnect_mutation',False) and self.path.startswith('/api/v2/torrents/'):
            self.connection.close(); return
        if self.path=='/api/v2/auth/login': return self.send(b'' if self.server.version.startswith('v5.2') else b'Ok.',204 if self.server.version.startswith('v5.2') else 200,{'Set-Cookie':'SID=fixture; Path=/'})
        if self.path=='/api/v2/torrents/add' and self.server.version.startswith('v5.2'):
            pending=getattr(self.server,'pending_add',False)
            return self.send({'success_count':0 if pending else 1,'failure_count':0,'pending_count':1 if pending else 0,'added_torrent_ids':[] if pending else ['a'*40]},202 if pending else 200)
        if self.path.startswith('/api/v2/torrents/'): return self.send(b'' if self.server.version.startswith('v5.2') else b'Ok.',204 if self.server.version.startswith('v5.2') else 200)
        if self.headers.get('X-Transmission-Session-Id')!='fixture-session': return self.send({},409,{'X-Transmission-Session-Id':'fixture-session'})
        req=json.loads(raw); method=req['method']; self.server.rpc.append(req)
        if method=='session-get': args={'version':'4.0.6','rpc-version':17}
        elif method=='torrent-get': args={'torrents':[{'id':7,'hashString':'b'*40,'name':'Debian','totalSize':200,'percentDone':1,'status':6,'rateDownload':0,'rateUpload':8,'downloadDir':'/downloads','eta':-1,'uploadRatio':1.0,'peersSendingToUs':0,'peersGettingFromUs':1,'files':[{'name':'file.iso','length':200,'bytesCompleted':200}],'trackerStats':[{'announce':'https://tracker','lastAnnounceResult':'Success','lastAnnounceSucceeded':True}]}]}
        else: args={}
        self.send({'result':'success','arguments':args})

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Fixture); self.http.calls=[]; self.http.rpc=[]; self.http.version='v5.0.3'
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True); self.thread.start()
        self.config={'id':'test','name':'Fixture','url':'http://127.0.0.1:%d'%self.http.server_port,'username':'user','password':'password','default_save_path':'/downloads'}
    def tearDown(self): self.http.shutdown(); self.http.server_close(); self.thread.join()
    def test_qb5_scoped_stop_delete_and_task_mapping(self):
        from server.adapters import QBittorrent
        qb=QBittorrent(self.config); self.assertEqual(qb.connect(),'v5.0.3'); tasks=qb.tasks(); self.assertEqual(tasks[0]['state'],'downloading'); self.assertEqual(tasks[0]['id'],'a'*40)
        qb.action('a'*40,'pause',False); self.assertEqual(self.http.calls[-1][0],'/api/v2/torrents/stop'); self.assertEqual(parse_qs(self.http.calls[-1][1].decode())['hashes'],['a'*40])
        qb.action('a'*40,'delete',False); self.assertEqual(parse_qs(self.http.calls[-1][1].decode())['deleteFiles'],['false'])
        self.assertEqual(qb.detail('a'*40)['files'][0]['progress'],0.5)
    def test_qb4_pause_and_add_paused_mapping(self):
        from server.adapters import QBittorrent
        self.http.version='v4.6.7'; qb=QBittorrent(self.config); qb.connect(); qb.action('a'*40,'pause',False)
        self.assertEqual(self.http.calls[-1][0],'/api/v2/torrents/pause')
        qb.add({'url':'magnet:?xt=urn:btih:'+'a'*40,'paused':True})
        self.assertIn(b'name="paused"',self.http.calls[-1][1]); self.assertIn(b'true',self.http.calls[-1][1])
    def test_transmission409_negotiation_and_scoped_delete(self):
        from server.adapters import Transmission
        tr=Transmission(self.config); self.assertEqual(tr.connect(),'4.0.6'); self.assertEqual(tr.tasks()[0]['state'],'completed')
        tr.action('7','delete',False); self.assertEqual(self.http.rpc[-1],{'method':'torrent-remove','arguments':{'ids':[7],'delete-local-data':False}})
        self.assertEqual(tr.detail('7')['files'][0]['progress'],1)
    def test_qb_states_truthful_and_full_normalized_fields(self):
        from server.adapters import QBittorrent
        qb=QBittorrent(self.config)
        for raw,progress,state,label in [('stalledUP',1,'completed','做种中·暂无连接'),('queuedUP',1,'queued','排队做种'),('checkingDL',0.5,'checking','校验中'),('error',0.2,'error','错误'),('stoppedUP',1,'paused','已暂停')]:
            t=qb.normalize({'hash':'a'*40,'state':raw,'progress':progress,'size':100})
            self.assertEqual((t['state'],t['state_label']),(state,label)); self.assertEqual(t['total_size'],100)
            for field in ('downloaded','uploaded','tags','category','added_at','completed_at','seeders','leechers'): self.assertIn(field,t)
    def test_login_redirect_never_follows_destination(self):
        from server.adapters import QBittorrent
        from server.app import ApiError
        self.http.redirect_login=True
        with self.assertRaises(ApiError): QBittorrent(self.config).connect()
        self.assertEqual(len(self.http.calls),1)
    def test_uncertain_socket_failure_does_not_resubmit(self):
        import tempfile,uuid
        from server.adapters import QBittorrent
        from server.app import Application
        self.http.disconnect_mutation=True; qb=QBittorrent(self.config); qb.connect()
        with tempfile.TemporaryDirectory() as directory:
            app=Application(directory,setup_token='fixture-install')
            try:
                rid=str(uuid.uuid4()); receipt=app.operation(rid,{'action':'delete'},lambda:qb.action('a'*40,'delete',False))
                self.assertEqual(receipt['status'],'uncertain')
                app.operation(rid,{'action':'delete'},lambda:qb.action('a'*40,'delete',False))
                self.assertEqual(len([p for p,b in self.http.calls if p.endswith('/delete')]),1)
            finally: app.db.close()
    def test_qb52_204_login_and_mutations_supported(self):
        from server.adapters import QBittorrent
        self.http.version='v5.2.4'; qb=QBittorrent(self.config)
        self.assertEqual(qb.connect(),'v5.2.4'); self.assertEqual(qb.tasks()[0]['name'],'Ubuntu')
        qb.add({'url':'magnet:?xt=urn:btih:'+'a'*40,'paused':True})
        for action in ('resume','pause','delete'): qb.action('a'*40,action,False)
    def test_qb52_pending_add_202_acknowledged_without_replay(self):
        from server.adapters import QBittorrent
        self.http.version='v5.2.4'; self.http.pending_add=True
        qb=QBittorrent(self.config); qb.connect(); qb.add({'url':'https://example.test/upload.torrent'})
        self.assertEqual(len([p for p,b in self.http.calls if p.endswith('/add')]),1)

if __name__=='__main__': unittest.main()
