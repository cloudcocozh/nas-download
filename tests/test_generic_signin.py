import json, tempfile, threading, unittest, sys, uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.app import Application, ApiError
from server.signin import clean_config, run_signin

class SigninTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]; owner=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self): self.reply()
            def do_POST(self): self.reply()
            def reply(self):
                body=self.rfile.read(int(self.headers.get('Content-Length',0)))
                owner.calls.append((self.command,self.path,dict(self.headers),body))
                if self.path=='/redirect':
                    self.send_response(302); self.send_header('Location','/leak'); self.end_headers(); return
                content=owner.response.encode(); self.send_response(200); self.send_header('Content-Type','text/plain; charset=utf-8'); self.end_headers(); self.wfile.write(content)
        self.response='签到成功'
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler); self.thread=threading.Thread(target=self.http.serve_forever,daemon=True); self.thread.start()
        self.tmp=tempfile.TemporaryDirectory(); self.app=Application(self.tmp.name,'test')
        self.config={'kind':'http_signin','signin_url':'http://127.0.0.1:'+str(self.http.server_port)+'/checkin','success_contains':'签到成功','already_contains':'已签到','failure_contains':'登录失效','cookie':'private_cookie=1','headers_json':'{"Authorization":"Bearer private-token"}','request_body':'{"action":"sign"}'}
    def tearDown(self):
        self.app.automations.close(); self.app.sites.pool.shutdown(wait=True); self.app.db.close(); self.tmp.cleanup(); self.http.shutdown(); self.http.server_close(); self.thread.join()
    def test_public_configuration_and_create_receipt_hide_all_secrets(self):
        payload=self.config|{'request_id':str(uuid.uuid4())}
        result=self.app.automations.create(payload)
        self.assertFalse(result['enabled']); self.assertTrue(result['has_cookie']); self.assertTrue(result['has_headers_json']); self.assertTrue(result['has_request_body'])
        for key in ('cookie','headers_json','request_body'): self.assertNotIn(key,result)
        self.assertNotIn('private',json.dumps(result)); self.assertEqual(result,self.app.automations.create(payload))
        stored=self.app.db.execute('SELECT config FROM automations').fetchone()[0]; self.assertNotIn('private',stored)
    def test_blank_edit_preserves_secret_fields(self):
        item=self.app.automations.save(self.config)
        self.app.automations.save({'cookie':'','headers_json':'','request_body':''},item['id'])
        raw,_=self.app.automations._config(item['id'])
        for key in ('cookie','headers_json','request_body'): self.assertEqual(self.config[key],raw[key])
    def test_get_parameters_and_credentials_sent_once(self):
        result=run_signin(self.config); self.assertEqual(result['status'],'success'); self.assertEqual(len(self.calls),1)
        method,path,headers,body=self.calls[0]; self.assertEqual(method,'GET'); self.assertIn('action=sign',path); self.assertEqual(headers['Authorization'],'Bearer private-token'); self.assertEqual(body,b'')
        self.assertNotIn('private',json.dumps(result))
    def test_post_json_and_form(self):
        for fmt in ('json','form','text'):
            cfg=self.config|{'method':'POST','request_format':fmt}
            self.assertEqual(run_signin(cfg)['status'],'success')
            body=self.calls[-1][3]
            self.assertEqual(body,b'action=sign' if fmt=='form' else b'{"action":"sign"}')
    def test_redirect_never_receives_credentials(self):
        c=self.config|{'signin_url':self.config['signin_url'].replace('/checkin','/redirect'),'request_body':''}
        self.assertEqual(run_signin(c)['status'],'auth_failure'); self.assertEqual(len(self.calls),1)
    def test_custom_content_type_is_case_insensitive(self):
        for key in ('Content-Type','content-type','CONTENT-TYPE'):
            c=self.config|{'method':'POST','request_format':'json','headers_json':json.dumps({key:'application/vnd.fixture+json'})}
            self.assertEqual(run_signin(c)['status'],'success')
            headers={k.lower():v for k,v in self.calls[-1][2].items()}
            self.assertEqual(headers['content-type'],'application/vnd.fixture+json')
    def test_success_must_be_explicit_failure_takes_priority(self):
        for body,status in [('HTTP accepted','unknown'),('已签到','already_signed'),('签到成功 登录失效','auth_failure')]:
            self.response=body; self.assertEqual(run_signin(self.config)['status'],status)
    def test_unsafe_urls_headers_and_missing_success_rejected(self):
        changes=[{'signin_url':'http://169.254.169.254/latest/'},{'signin_url':'https://example.com/a?token=secret'},{'headers_json':'{"Host":"other.example"}'},{'headers_json':'{"Authorization":"abc\\r\\nX: bad"}'},{'success_contains':''},{'method':'DELETE'}]
        for values in changes:
            with self.assertRaises(ApiError): clean_config(self.config|values)
    def test_scheduler_preview_never_calls_site_and_daily_run_once(self):
        s=self.app.automations; item=s.save(self.config|{'enabled':True})
        rid=str(uuid.uuid4()); s.enqueue(item['id'],rid,True); s._execute(rid)
        self.assertEqual(len(self.calls),0); self.assertEqual(s.run(rid)['status'],'completed')
        for _ in range(2):
            rid=str(uuid.uuid4()); s.enqueue(item['id'],rid,False); s._execute(rid)
        self.assertEqual(len(self.calls),1); self.assertEqual(s.run(rid)['result']['status'],'already_attempted')

if __name__=='__main__': unittest.main()
