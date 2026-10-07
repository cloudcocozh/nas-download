import argparse, os
from .app import Application,make_server

def main():
    parser=argparse.ArgumentParser(description='Nas Download standalone service'); parser.add_argument('--host',default='0.0.0.0'); parser.add_argument('--port',type=int,default=7120); parser.add_argument('--data',default='./data'); parser.add_argument('--web',default='./web'); args=parser.parse_args()
    app=Application(args.data,os.environ.get('ND_SETUP_TOKEN'))
    if app.generated_setup and not app.configured(): print('Nas Download 初始化码: '+app.setup_token,flush=True)
    http=make_server(app,args.host,args.port,args.web)
    app.automations.start()
    try: http.serve_forever()
    except KeyboardInterrupt: pass
    finally: http.server_close(); app.automations.close(); app.sites.pool.shutdown(wait=True); app.db.close()

if __name__=='__main__': main()
