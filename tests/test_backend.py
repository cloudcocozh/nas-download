import base64, json, tempfile, threading, unittest, uuid, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

class BackendTests(unittest.TestCase):
    def setUp(self):
        from server.app import Application, make_server
        self.tmp = tempfile.TemporaryDirectory()
        self.app = Application(self.tmp.name, setup_token='install-secret')
        self.http = make_server(self.app, '127.0.0.1', 0, self.tmp.name)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True); self.thread.start()
        self.base = 'http://127.0.0.1:%d/api/v1' % self.http.server_port
        self.token = None
    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join(); self.app.db.close(); self.tmp.cleanup()
    def call(self, path, data=None, method=None, headers=None):
        h = {'Content-Type':'application/json', 'X-Nas-Request':'1'}
        if self.token: h['Authorization']='Bearer '+self.token
        h.update(headers or {})
        req=Request(self.base+path, data=json.dumps(data).encode() if data is not None else None, headers=h, method=method)
        try:
            with urlopen(req) as r: return r.status,json.load(r),dict(r.headers)
        except HTTPError as e:
            with e: return e.code,json.load(e),dict(e.headers)
    def setup(self):
        status,data,h=self.call('/setup',{'setup_token':'install-secret','username':'admin','password':'long-password'})
        self.assertEqual(status,200); self.token=data['token']; return h
    def test_setup_auth_logout_and_cookie_flags(self):
        self.assertEqual(self.call('/me')[0],401)
        h=self.setup(); self.assertIn('HttpOnly',h['Set-Cookie']); self.assertIn('SameSite=Strict',h['Set-Cookie'])
        self.assertEqual(self.call('/setup',{'setup_token':'install-secret','username':'other','password':'long-password'})[0],409)
        self.assertEqual(self.call('/me')[1]['username'],'admin')
        self.call('/logout',{}); self.assertEqual(self.call('/me')[0],401)
    def test_pair_one_time_and_expiry(self):
        self.setup(); code=self.call('/pair-codes',{})[1]['code']; self.token=None
        self.assertEqual(self.call('/pair',{'code':code,'label':'phone'})[0],200)
        self.assertEqual(self.call('/pair',{'code':code,'label':'phone'})[0],401)
    def test_origin_and_csrf(self):
        self.assertEqual(self.call('/setup',{},headers={'Origin':'https://evil.test'})[0],403)
        self.assertEqual(self.call('/login',{},headers={'X-Nas-Request':''})[0],403)
    def test_downloader_urls_block_metadata_and_credentials(self):
        self.setup()
        for url in ['http://169.254.169.254','http://[::ffff:169.254.169.254]','http://u:p@localhost:8080','http://localhost/#frag','file:///tmp/x']:
            self.assertEqual(self.call('/downloaders/test',{'type':'qbittorrent','url':url,'username':'u','password':'p'})[0],400)
    def test_receipt_never_replays_uncertain(self):
        self.setup()
        from server.app import ApiError
        calls=[]
        def fail(): calls.append(1); raise OSError('secret password should not leak')
        rid=str(uuid.uuid4())
        first=self.app.operation(rid,{'action':'pause'},fail)
        second=self.app.operation(rid,{'action':'pause'},fail)
        self.assertEqual(first['status'],'uncertain'); self.assertEqual(second['status'],'uncertain'); self.assertEqual(len(calls),1)
        self.assertNotIn('secret',json.dumps(first))
        with self.assertRaises(ApiError): self.app.operation(rid,{'action':'delete'},fail)
    def test_expired_sessions_and_pair_codes_rejected(self):
        self.setup(); code=self.call('/pair-codes',{})[1]['code']
        self.app.db.execute('UPDATE pairs SET expires_at=0'); self.app.db.commit()
        self.assertEqual(self.call('/pair',{'code':code})[0],401)
        self.app.db.execute('UPDATE sessions SET expires_at=0'); self.app.db.commit()
        self.assertEqual(self.call('/me')[0],401)
    def test_pair_consumption_atomic(self):
        self.setup(); code=self.call('/pair-codes',{})[1]['code']; self.token=None
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(lambda _:self.call('/pair',{'code':code,'label':'phone'})[0],range(2)))
        self.assertEqual(sorted(statuses),[200,401])
    def test_login_rate_limit(self):
        self.setup(); self.token=None
        for _ in range(10): self.assertEqual(self.call('/login',{'username':'wrong','password':'wrong'})[0],401)
        self.assertEqual(self.call('/login',{'username':'wrong','password':'wrong'})[0],429)
    def test_empty_body_logout_and_cookie_device_revoke(self):
        self.setup(); devices=self.call('/devices')[1]['items']; self.assertEqual(len(devices),1)
        self.assertEqual(self.call('/logout',method='POST')[0],200)
        self.assertEqual(self.call('/me')[0],401)
    def test_completed_receipt_persists_restart_without_replay(self):
        from server.app import Application
        self.setup(); rid=str(uuid.uuid4()); called=[]
        self.app.operation(rid,{'action':'pause'},lambda:called.append(1))
        second=Application(self.tmp.name,setup_token='install-secret')
        try:
            receipt=second.operation(rid,{'action':'pause'},lambda:called.append(1))
            self.assertEqual(receipt['status'],'completed'); self.assertEqual(called,[1])
        finally: second.db.close()
    def test_uuid_case_does_not_bypass_idempotency(self):
        self.setup(); rid=str(uuid.uuid4()); calls=[]
        first=self.app.operation(rid,{'request_id':rid,'action':'pause'},lambda:calls.append(1))
        second=self.app.operation(rid.upper(),{'request_id':rid.upper(),'action':'pause'},lambda:calls.append(1))
        self.assertEqual(first['request_id'],second['request_id']); self.assertEqual(calls,[1])
        self.assertEqual(self.call('/operations/'+rid.upper())[1]['operation']['request_id'],rid)
    def test_encrypted_downloaders_scoped_actions_and_filters(self):
        from test_adapters import Fixture
        fixture=ThreadingHTTPServer(('127.0.0.1',0),Fixture); fixture.calls=[]; fixture.rpc=[]; fixture.version='v5.0.3'
        thread=threading.Thread(target=fixture.serve_forever,daemon=True); thread.start()
        try:
            self.setup(); url='http://127.0.0.1:%d'%fixture.server_port
            status,result,_=self.call('/downloaders',{'name':'Fixture','type':'qbittorrent','url':url,'username':'fixture-user','password':'distinct-secret-password'})
            self.assertEqual(status,200); did=result['item']['id']; self.assertIsInstance(did,int)
            self.assertNotIn('password',json.dumps(result)); self.assertNotIn(b'distinct-secret-password',(Path(self.tmp.name)/'nas-download.sqlite3').read_bytes())
            tasks=self.call('/tasks?downloader_id='+str(did)+'&state=downloading&query=Ubuntu')[1]
            self.assertEqual(tasks['total'],1); self.assertEqual(tasks['items'][0]['total_size'],100); self.assertEqual(tasks['items'][0]['downloaded'],50)
            path='/tasks/%s/%s/action'%(did,'a'*40)
            self.assertEqual(self.call(path,{'request_id':str(uuid.uuid4()),'action':'delete','delete_data':'false'})[0],400)
            self.assertEqual(self.call('/tasks/%s/all/action'%did,{'request_id':str(uuid.uuid4()),'action':'delete'})[0],400)
            rid=str(uuid.uuid4()); payload={'request_id':rid,'action':'delete','delete_data':False}
            self.assertEqual(self.call(path,payload)[1]['operation']['status'],'completed')
            calls=len([c for c in fixture.calls if c[0].endswith('/delete')]); self.call(path,payload)
            self.assertEqual(len([c for c in fixture.calls if c[0].endswith('/delete')]),calls)
            self.assertEqual(self.call('/operations/'+rid)[1]['operation']['status'],'completed')
            self.assertEqual(self.call('/tasks?downloader_id=987654')[0],404)
            rid=str(uuid.uuid4())
            self.assertEqual(self.call('/tasks/add',{'downloader_id':did,'request_id':rid,'url':'magnet:?xt=urn:btih:'+'c'*40})[1]['operation']['status'],'completed')
            self.call('/downloaders/'+str(did),{},method='DELETE')
            self.assertEqual(self.call('/tasks/add',{'downloader_id':did,'request_id':rid,'url':'magnet:?xt=urn:btih:'+'c'*40})[1]['operation']['status'],'completed')
            new=self.call('/downloaders',{'name':'New','type':'qbittorrent','url':url})[1]['item']['id']
            self.assertGreater(new,did)
        finally: fixture.shutdown(); fixture.server_close(); thread.join()
    def test_snapshot_cache_expiry_invalidation_existing_test_and_v2_hash(self):
        import time
        from test_adapters import Fixture
        fixture=ThreadingHTTPServer(('127.0.0.1',0),Fixture); fixture.calls=[]; fixture.rpc=[]; fixture.version='v5.0.3'
        thread=threading.Thread(target=fixture.serve_forever,daemon=True); thread.start()
        try:
            self.setup(); url='http://127.0.0.1:%d'%fixture.server_port
            did=self.call('/downloaders',{'name':'Cached','type':'qbittorrent','url':url,'username':'fixture-user','password':'retained-password'})[1]['item']['id']
            fixture.calls.clear()
            for query in ('?downloader_id='+str(did),'?downloader_id='+str(did)+'&offset=1','?downloader_id=all&query=Ubuntu'): self.assertEqual(self.call('/tasks'+query)[0],200)
            self.assertEqual(len([p for p,b in fixture.calls if p.endswith('/auth/login')]),1)
            time.sleep(2.1); self.call('/tasks?downloader_id='+str(did))
            self.assertEqual(len([p for p,b in fixture.calls if p.endswith('/auth/login')]),2)
            self.assertEqual(self.call('/downloaders/test',{'downloader_id':did,'password':''})[0],200)
            self.assertIn(b'password=retained-password',fixture.calls[-1][1])
            self.assertEqual(self.call('/tasks/%s/%s/action'%(did,'e'*64),{'request_id':str(uuid.uuid4()),'action':'pause'})[0],200)
            count=len([p for p,b in fixture.calls if p.endswith('/auth/login')]); self.call('/tasks?downloader_id='+str(did))
            self.assertEqual(len([p for p,b in fixture.calls if p.endswith('/auth/login')]),count+1)
        finally: fixture.shutdown(); fixture.server_close(); thread.join()
    def test_transmission_file_name_metadata_accepted(self):
        from test_adapters import Fixture
        fixture=ThreadingHTTPServer(('127.0.0.1',0),Fixture); fixture.calls=[]; fixture.rpc=[]; fixture.version='v5.0.3'
        thread=threading.Thread(target=fixture.serve_forever,daemon=True); thread.start()
        try:
            self.setup(); did=self.call('/downloaders',{'type':'transmission','url':'http://127.0.0.1:%d'%fixture.server_port})[1]['item']['id']
            result=self.call('/tasks/add',{'downloader_id':did,'request_id':str(uuid.uuid4()),'torrent_base64':base64.b64encode(b'd4:infodee').decode(),'name':'upload.torrent'})
            self.assertEqual(result[0],200); self.assertEqual(result[1]['operation']['status'],'completed')
            self.assertNotIn('name',fixture.rpc[-1]['arguments'])
        finally: fixture.shutdown(); fixture.server_close(); thread.join()

if __name__ == '__main__': unittest.main()
