import tempfile, unittest
from pathlib import Path
from deploy.runtime import EngineSupervisor, enroll_engine
from deploy.engine_config import configure_engine
from server.app import Application, ApiError

class RuntimeTests(unittest.TestCase):
 def test_configuration_preserves_password_and_state(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'qBittorrent'; p.mkdir(); f=p/'qBittorrent.conf'
   f.write_text('[Preferences]\nWebUI\\Password_PBKDF2=existing\nWebUI\\Username=custom\nWebUI\\Address=*\n[Other]\nkeep=yes\n')
   configure_engine(d,'different',7121)
   s=f.read_text(); self.assertIn('Password_PBKDF2=existing',s); self.assertIn('Username=custom',s); self.assertIn('Address=127.0.0.1',s); self.assertIn('keep=yes',s)
 def test_enrollment_preserves_external_and_exact_old_id(self):
  with tempfile.TemporaryDirectory() as d:
   app=Application(d,'setup'); enroll_engine(app,'secret')
   self.assertEqual(app.configs()[0]['url'],'http://127.0.0.1:8080'); self.assertEqual(app.configs()[0]['id'],1)
   app.db.close()
 def test_unmarked_old_url_not_adopted(self):
  import json
  with tempfile.TemporaryDirectory() as d:
   app=Application(d,'setup'); c=dict(id=7,type='qbittorrent',url='http://qbittorrent:8080',password='old')
   app.db.execute('INSERT INTO downloaders VALUES(?,?)',('7',app.cipher.encrypt(json.dumps(c).encode()).decode())); app.db.commit()
   enroll_engine(app,'secret'); self.assertEqual(app.configs()[0],c); app.db.close()
 def test_finite_restarts_and_diagnostic_state(self):
  class Proc:
   def poll(self): return 1
  launches=[]
  s=EngineSupervisor(['stub'],lambda:False,max_restarts=2,backoff=0,spawn=lambda *a,**k: launches.append(1) or Proc())
  for _ in range(6): s.tick()
  self.assertEqual(len(launches),3); self.assertEqual(s.status()['state'],'failed'); self.assertFalse(s.status()['ready'])
 def test_shutdown_blocks_adapter(self):
  with tempfile.TemporaryDirectory() as d:
   app=Application(d,'setup'); app.stopping=True
   with self.assertRaises(ApiError): app.adapter({'type':'qbittorrent'})
   app.db.close()
 def test_process_shutdown_waits(self):
  class Proc:
   def poll(self): return None
   def terminate(self): events.append('terminate')
   def wait(self,timeout): events.append('wait')
  events=[]; s=EngineSupervisor(['stub'],lambda:True,spawn=lambda *a,**k:Proc()); s.tick(); s.stop()
  self.assertEqual(events,['terminate','wait']); self.assertEqual(s.status()['state'],'stopped')
 def test_maintenance_health_and_route_gate(self):
  with tempfile.TemporaryDirectory() as d:
   app=Application(d,'setup'); (app.data/'.install-maintenance').touch()
   app.engine_status=lambda:dict(mode='embedded',ready=False,state='recovering')
   h=app.dispatch('GET','/health',{}, {},None,'local'); self.assertFalse(h['ok']); self.assertTrue(h['maintenance'])
   with self.assertRaises(ApiError): app.dispatch('POST','/setup',{}, {},None,'local')
   app.db.close()
 def test_marked_migration_keeps_password_and_id(self):
  import json
  with tempfile.TemporaryDirectory() as d:
   app=Application(d,'setup'); (app.data/'bundled-enrolled').touch()
   c=dict(id=9,type='qbittorrent',url='http://qbittorrent:8080',password='user-change',username='custom')
   app.db.execute('INSERT INTO downloaders VALUES(?,?)',('9',app.cipher.encrypt(json.dumps(c).encode()).decode())); app.db.commit()
   enroll_engine(app,'secret'); got=app.configs()[0]
   self.assertEqual(got['id'],9); self.assertEqual(got['password'],'user-change'); self.assertEqual(got['url'],'http://127.0.0.1:8080'); app.db.close()
 def test_unready_live_process_eventually_fails(self):
  class Proc:
   def poll(self): return None
  s=EngineSupervisor(['stub'],lambda:False,spawn=lambda *a,**k:Proc(),startup_timeout=0)
  s.tick(); self.assertEqual(s.status()['state'],'failed'); self.assertFalse(s.status()['ready'])
 def test_engine_probe_independent_of_deleted_or_edited_downloader(self):
  from deploy.runtime import make_engine_probe
  seen=[]
  class Adapter:
   def __init__(self,c): seen.append(c.copy())
   def connect(self): return "v5.2.4"
  with tempfile.TemporaryDirectory() as d:
   app=Application(d,'setup'); enroll_engine(app,'env-secret')
   profile=Path(d)/'qb.conf'; profile.write_text('[Preferences]\nWebUI\\Username=custom\n')
   probe=make_engine_probe(profile,'env-secret',Adapter)
   app.db.execute('DELETE FROM downloaders'); app.db.commit()
   self.assertTrue(probe())
   import json
   edited=dict(id=1,type='qbittorrent',url='http://external.invalid:1234',username='changed',password='edited')
   app.db.execute('INSERT INTO downloaders VALUES(?,?)',('1',app.cipher.encrypt(json.dumps(edited).encode()).decode())); app.db.commit()
   self.assertTrue(probe())
   class Proc:
    def poll(self): return None
   supervisor=EngineSupervisor(['stub'],probe,startup_timeout=0,spawn=lambda *a,**k:Proc())
   supervisor.tick(); self.assertEqual(supervisor.status()['state'],'ready')
   self.assertEqual(seen[-1]['username'],'custom'); self.assertEqual(seen[-1]['password'],'env-secret')
   self.assertEqual(seen[-1]['url'],'http://127.0.0.1:8080'); app.db.close()
 def test_scheduler_requires_ready_engine_and_no_maintenance(self):
  from deploy.runtime import scheduler_allowed
  with tempfile.TemporaryDirectory() as d:
   marker=Path(d)/'.install-maintenance'
   self.assertFalse(scheduler_allowed(marker,{'ready':False}))
   self.assertTrue(scheduler_allowed(marker,{'ready':True}))
   marker.touch(); self.assertFalse(scheduler_allowed(marker,{'ready':True}))
 def test_server_drain_waits_for_active_handler(self):
  import threading, urllib.request
  from server.app import make_server
  entered=threading.Event(); release=threading.Event(); drained=threading.Event(); closed=[]
  class App:
   def dispatch(self,*args): entered.set(); release.wait(3); return {'ok':True}
  with tempfile.TemporaryDirectory() as d:
   http=make_server(App(),'127.0.0.1',0,d)
   thread=threading.Thread(target=http.serve_forever); thread.start()
   client=threading.Thread(target=lambda:urllib.request.urlopen('http://127.0.0.1:'+str(http.server_port)+'/api/v1/health').read()); client.start()
   self.assertTrue(entered.wait(2)); http.shutdown()
   closer=threading.Thread(target=lambda:(http.drain_handlers(3),closed.extend(['engine','database']),drained.set())); closer.start()
   self.assertFalse(drained.wait(.1)); self.assertEqual(closed,[]); release.set(); self.assertTrue(drained.wait(2)); self.assertEqual(closed,['engine','database'])
   closer.join(); client.join(); thread.join(); http.server_close()
 def test_mutation_execution_gate_after_shutdown(self):
  with tempfile.TemporaryDirectory() as d:
   app=Application(d,'setup'); app.stopping=True; effects=[]
   with self.assertRaises(ApiError): app.mutate(1,lambda:effects.append(1))
   self.assertEqual(effects,[]); app.db.close()
 def test_real_adapter_health_with_nonempty_torrents(self):
  import json,threading
  from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
  from unittest.mock import patch
  from deploy.runtime import make_engine_probe
  routes=[]
  class Fixture(BaseHTTPRequestHandler):
   def log_message(self,*args): pass
   def send(self,raw,status=200,cookie=False):
    self.send_response(status)
    if cookie:self.send_header('Set-Cookie','SID=runtime-fixture; Path=/')
    self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
   def do_POST(self):
    self.rfile.read(int(self.headers.get('Content-Length',0)))
    routes.append(self.path);self.send(b'',204,True)
   def do_GET(self):
    routes.append(self.path)
    if self.headers.get('Cookie')!='SID=runtime-fixture':return self.send(b'',403)
    if self.path.endswith('/app/version'):return self.send(b'v5.2.4')
    if self.path.endswith('/torrents/info'):return self.send(json.dumps([dict(hash='a'*40,name='own-fixture',progress=1,state='stalledUP')]).encode())
    self.send(b'',404)
  http=ThreadingHTTPServer(('127.0.0.1',0),Fixture);thread=threading.Thread(target=http.serve_forever);thread.start()
  try:
   with tempfile.TemporaryDirectory() as d:
    profile=Path(d)/'qb.conf';profile.write_text('[Preferences]\nWebUI\\Username=admin\n')
    with patch('deploy.runtime.ENGINE_URL','http://127.0.0.1:'+str(http.server_port)):
     probe=make_engine_probe(profile,'runtime-secret')
     self.assertTrue(probe())
    self.assertIn('/api/v2/auth/login',routes);self.assertIn('/api/v2/app/version',routes);self.assertNotIn('/api/v2/torrents/info',routes)
  finally:http.shutdown();http.server_close();thread.join()
