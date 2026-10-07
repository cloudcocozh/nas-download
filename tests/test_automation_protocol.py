"""Exercise real HTTP adapters and async HTTP API at their boundaries."""
import base64, json, tempfile, threading, time, unittest, uuid, sys
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_adapters import Fixture
from test_automations import RAW
from server.app import Application, make_server, ApiError
from server.adapters import QBittorrent,Transmission
from server.sites import Torznab

class AutomationFixture(Fixture):
    def do_GET(self):
        if self.path.endswith('/app/preferences'): return self.send({'save_path':'/downloads'})
        if self.path.endswith('/sync/maindata'): return self.send({'server_state':{'free_space_on_disk':900*1024**3}})
        return super().do_GET()

class AutomationProtocolTests(unittest.TestCase):
    def setUp(self):
        self.http=ThreadingHTTPServer(('127.0.0.1',0),AutomationFixture); self.http.calls=[]; self.http.rpc=[]; self.http.version='v5.2.4'
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True); self.thread.start()
        self.c=dict(id=1,name='engine',type='qbittorrent',url='http://127.0.0.1:%d'%self.http.server_port,username='u',password='p')
    def tearDown(self): self.http.shutdown(); self.http.server_close(); self.thread.join()
    def test_qb_free_space_uses_exact_download_mount_and_marker_in_add(self):
        qb=QBittorrent(self.c); self.assertEqual(qb.automation_space('/downloads'),900*1024**3)
        with self.assertRaises(ApiError): qb.automation_space('/other-volume')
        qb.add({'torrent_base64':base64.b64encode(RAW).decode(),'tags':['nd-auto-operation'],'save_path':'/downloads'})
        payload=self.http.calls[-1][1]; self.assertIn(b'name="tags"\r\n\r\nnd-auto-operation',payload)
    def test_transmission_labels_are_sent_at_add_and_duplicate_return_preserved(self):
        tr=Transmission(self.c); tr.add({'torrent_base64':base64.b64encode(RAW).decode(),'tags':['nd-auto-operation'],'save_path':'/downloads'})
        self.assertEqual(self.http.rpc[-1]['arguments']['labels'],['nd-auto-operation'])
        self.assertEqual(self.http.rpc[-1]['arguments']['download-dir'],'/downloads')
    def test_torznab_requires_explicit_free_factor_and_counts_leechers(self):
        raw=b'<rss xmlns:torznab="http://torznab.com/schemas/2015/feed"><channel><item><title>x</title><enclosure url="http://127.0.0.1/file" length="123"/><torznab:attr name="seeders" value="5"/><torznab:attr name="peers" value="9"/><torznab:attr name="downloadvolumefactor" value="0"/></item></channel></rss>'
        with patch('server.sites.request',return_value=raw):
            rows,_=Torznab({'url':'http://127.0.0.1/api','api_key':'key'}).search('',1,10)
        self.assertEqual(rows[0]['leechers'],4); self.assertEqual(rows[0]['promotion'],'FREE')
        with patch('server.sites.request',return_value=raw.replace(b'value="0"',b'value="0.5"')):
            rows,_=Torznab({'url':'http://127.0.0.1/api','api_key':'key'}).search('',1,10)
        self.assertEqual(rows[0]['promotion'],'')

class AutomationHTTPTests(unittest.TestCase):
    def test_authenticated_async_signin_api_does_not_block_other_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            app=Application(directory,'setup-token'); server=make_server(app,'127.0.0.1',0,directory)
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start(); app.automations.start()
            base='http://127.0.0.1:%d/api/v1'%server.server_port; token=''
            def call(path,data=None,method=None):
                headers={'Content-Type':'application/json','X-Nas-Request':'1'}
                if token: headers['Authorization']='Bearer '+token
                with urlopen(Request(base+path,data=json.dumps(data).encode() if data is not None else None,method=method,headers=headers),timeout=2) as response: return json.load(response)
            entered=threading.Event(); release=threading.Event()
            def wait_signin(cookie): entered.set(); release.wait(3); return {'status':'success','message':'签到成功'}
            try:
                try: call('/automations'); self.fail('unauthenticated automation request accepted')
                except HTTPError as error: self.assertEqual(error.code,401); error.close()
                token=call('/setup',{'setup_token':'setup-token','username':'admin','password':'password-long'})['token']
                a=call('/automations',{'kind':'hdfans_signin','cookie':'uid=1','enabled':True})['item']
                with patch('server.automations.hdfans_signin',side_effect=wait_signin):
                    before=time.monotonic(); run=call('/automations/'+a['id']+'/run',{'request_id':str(uuid.uuid4()),'dry_run':False})
                    self.assertLess(time.monotonic()-before,1); self.assertTrue(entered.wait(2))
                    before=time.monotonic(); listing=call('/automations'); self.assertLess(time.monotonic()-before,1)
                    self.assertEqual(len(listing['items']),1); self.assertIsNotNone(listing['items'][0]['last_run_at'])
                    release.set(); deadline=time.monotonic()+2
                    while time.monotonic()<deadline:
                        state=call('/automation-runs/'+run['run_id'])['item']
                        if state['status']=='completed': break
                        time.sleep(.02)
                    self.assertEqual(state['status'],'completed'); self.assertNotIn('cookie',json.dumps(state))
            finally:
                release.set(); server.shutdown(); server.server_close(); thread.join(); app.automations.close(); app.sites.pool.shutdown(wait=True); app.db.close()

if __name__=='__main__': unittest.main()
