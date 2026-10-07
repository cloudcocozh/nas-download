"""One product supervisor, with API retained for engine diagnostics."""
import os, signal, threading, time
from deploy.runtime import EngineSupervisor,enroll_engine,make_engine_probe,scheduler_allowed
from deploy.engine_config import configure_engine
from server.app import Application, make_server

def main():
 app=Application('/data',os.environ.get('ND_SETUP_TOKEN')); engine=None
 mode=os.environ.get('ND_ENGINE_MODE','existing')
 if mode not in ('embedded','existing'): raise ValueError('invalid engine mode')
 if mode=='embedded':
  password=os.environ.get('ND_ENGINE_PASSWORD','')
  profile=configure_engine('/config',password,os.environ.get('ND_PEER_PORT','7121')); enroll_engine(app,password)
  probe=make_engine_probe(profile,password)
  os.environ.update(XDG_CONFIG_HOME='/config',XDG_DATA_HOME='/config')
  engine=EngineSupervisor(['/app/qbittorrent-nox','--webui-port=8080','--confirm-legal-notice'],probe)
  app.engine_status=engine.status
 else: app.engine_status=lambda:dict(mode='existing',ready=True,state='external')
 http=make_server(app,'0.0.0.0',7120,'/app/web'); done=threading.Event()
 def stop(*_): app.stopping=True; done.set()
 signal.signal(signal.SIGTERM,stop); signal.signal(signal.SIGINT,stop)
 thread=threading.Thread(target=http.serve_forever); thread.start(); scheduler=False
 try:
  while not done.is_set():
   if engine: engine.tick()
   if not scheduler and scheduler_allowed(app.data/'.install-maintenance',app.engine_status()): app.automations.start(); scheduler=True
   done.wait(1)
 finally:
  app.stopping=True; app.automations.close(); http.shutdown(); thread.join(); http.server_close()
  if not http.drain_handlers(60):
   # Operation receipts were committed as uncertain before execution. Never
   # close shared DB/engine under active handlers; container-level failure is
   # deliberately distinct from a completed graceful shutdown.
   print('Shutdown handler deadline exceeded',flush=True)
   os._exit(1)
  app.sites.pool.shutdown(wait=True)
  if engine: engine.stop()
  app.db.close()

if __name__=='__main__': main()
