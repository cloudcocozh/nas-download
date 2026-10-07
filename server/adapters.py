"""Small fixed-route adapters; no arbitrary proxy and no uncertain mutation retries."""
import base64, http.cookiejar, json, os, secrets, stat
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler,HTTPCookieProcessor,ProxyHandler
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode,urlsplit
from .app import ApiError,validate_url

def absolute_download_path(value):
    if not isinstance(value,str) or not value.startswith('/') or '//' in value or '\\' in value or any(ord(c)<32 or ord(c)==127 for c in value) or any(p in ('.','..') for p in value.split('/')):
        raise ApiError('INVALID_PATH','下载目录必须是规范的绝对路径')
    return value.rstrip('/') or '/'

def verified_storage_path(remote,require_exists=False):
    """Map a downloader path to an operator-mounted, read-only inspection root.

    Lexical containment alone cannot prove a remote path is not a symlink or a
    different filesystem. No mapped root means that proof is unavailable.
    """
    root=os.environ.get('ND_BRUSH_VERIFY_ROOT',''); mount=os.environ.get('ND_BRUSH_VERIFY_MOUNT','')
    if not root or not mount: raise ApiError('STORAGE_UNVERIFIED','清理文件需要配置下载根目录的只读验证挂载',422)
    root=absolute_download_path(root); remote=absolute_download_path(remote)
    if remote!=root and not remote.startswith(root.rstrip('/')+'/'): raise ApiError('STORAGE_UNVERIFIED','下载目录不在只读验证挂载范围内',422)
    base=Path(mount)
    if not base.is_absolute() or not base.is_dir() or base.is_symlink(): raise ApiError('STORAGE_UNVERIFIED','只读验证挂载不可用',422)
    # Include ancestors so a mapped path cannot hide a symlink above the root.
    for parent in (base,*base.parents):
        if parent.is_symlink() or getattr(parent,'is_junction',lambda:False)(): raise ApiError('STORAGE_UNVERIFIED','验证目录包含符号链接',422)
    device=base.stat().st_dev; target=base
    for part in remote[len(root):].strip('/').split('/'):
        if not part: continue
        target=target/part
        try: info=target.lstat()
        except FileNotFoundError:
            if require_exists: raise ApiError('STORAGE_UNVERIFIED','待清理目录在验证挂载中不存在',422)
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(target,'is_junction',lambda:False)() or info.st_dev!=device or not stat.S_ISDIR(info.st_mode):
            raise ApiError('STORAGE_UNVERIFIED','下载目录存在链接、跨文件系统或非目录路径',422)
    return target

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

class Transport:
    def __init__(self,config):
        self.config=config; self.base=validate_url(config['url']); self.opener=build_opener(ProxyHandler({}),NoRedirect(),HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(self,path,method='GET',body=None,headers=None):
        validate_url(self.base)
        req=Request(self.base+path,data=body,method=method,headers=headers or {})
        try:
            with self.opener.open(req,timeout=12) as r:
                raw=r.read(16*1024*1024+1)
                if len(raw)>16*1024*1024: raise ApiError('DOWNLOADER_RESPONSE','下载器返回数据过大',502)
                return r.status,raw,dict(r.headers)
        except HTTPError as e:
            with e:
                # Error bodies can contain credentials, tracker keys, or internal URLs.
                return e.code,b'',dict(e.headers)
        except (OSError,URLError,TimeoutError): raise ApiError('DOWNLOADER_UNAVAILABLE','无法连接下载器，请检查地址、网络和账号',502)

class QBittorrent(Transport):
    def __init__(self,config): super().__init__(config); self.version=None
    def call(self,route,params=None,post=False,body=None,content_type=None):
        origin=urlsplit(self.base); headers={'Referer':self.base+'/','Origin':origin.scheme+'://'+origin.netloc}
        path='/api/v2/'+route
        if params is not None:
            encoded=urlencode(params).encode()
            if post: body=encoded; content_type='application/x-www-form-urlencoded'
            else: path+='?'+encoded.decode()
        if content_type: headers['Content-Type']=content_type
        status,raw,_=self.request(path,'POST' if post else 'GET',body,headers)
        if status not in (200,204) and not (route=='torrents/add' and status==202): raise ApiError('DOWNLOADER_REJECTED','qBittorrent 拒绝请求，请检查账号与 WebUI 设置',502)
        return raw
    def connect(self):
        if self.version: return self.version
        raw=self.call('auth/login',{'username':self.config.get('username',''),'password':self.config.get('password','')},True)
        # qB 5.2+ uses HTTP 204 for successful empty responses. The following
        # authenticated version request also verifies the cookie session works.
        if raw.strip() not in (b'Ok.',b''): raise ApiError('DOWNLOADER_AUTH','qBittorrent 登录失败',502)
        self.version=self.call('app/version').decode().strip()
        if not self.version.lstrip('v').startswith(('4.','5.')): raise ApiError('UNSUPPORTED_VERSION','仅支持 qBittorrent 4/5',422)
        return self.version
    def getjson(self,route,params=None):
        self.connect()
        try: return json.loads(self.call(route,params))
        except (ValueError,UnicodeError): raise ApiError('DOWNLOADER_RESPONSE','qBittorrent 响应格式无效',502)
    def normalize(self,t):
        raw=t.get('state','unknown'); progress=float(t.get('progress',0))
        if raw in ('error','missingFiles'): state,label='error','错误' if raw=='error' else '文件缺失'
        elif raw.startswith(('paused','stopped')): state,label='paused','已暂停'
        elif raw.startswith('checking') or raw in ('allocating','moving'): state,label='checking',{'allocating':'分配空间','moving':'移动文件'}.get(raw,'校验中')
        elif raw.startswith('queued'): state,label='queued','排队做种' if raw.endswith('UP') else '排队下载'
        elif raw=='stalledUP': state,label='completed','做种中·暂无连接'
        elif raw in ('uploading','forcedUP'): state,label='completed','做种中'
        elif raw=='stalledDL': state,label='downloading','下载中·暂无连接'
        elif raw in ('metaDL','forcedMetaDL'): state,label='downloading','获取种子信息'
        elif raw in ('downloading','forcedDL'): state,label='downloading','下载中'
        elif progress>=1: state,label='completed','已完成'
        else: state,label='error','状态未知'
        size=t.get('size',t.get('total_size',0)); tags=t.get('tags','')
        return {'id':t['hash'],'task_id':t['hash'],'downloader_id':self.config['id'],'downloader_name':self.config['name'],'name':t.get('name',''),'size':size,'total_size':size,'downloaded':t.get('downloaded',round(size*progress)),'uploaded':t.get('uploaded',0),'progress':progress,'state':state,'state_label':label,'raw_state':raw,'download_speed':t.get('dlspeed',0),'upload_speed':t.get('upspeed',0),'save_path':t.get('save_path',''),'eta':t.get('eta',-1),'ratio':t.get('ratio',0),'seeders':t.get('num_seeds',0),'leechers':t.get('num_leechs',0),'swarm_leechers':t.get('num_incomplete',-1),'seeds':t.get('num_seeds',0),'peers':t.get('num_leechs',0),'category':t.get('category',''),'tags':[x.strip() for x in tags.split(',') if x.strip()] if isinstance(tags,str) else tags,'added_at':t.get('added_on',0),'completed_at':t.get('completion_on',0),'seeding_seconds':t.get('seeding_time',0)}
    def tasks(self): return [self.normalize(t) for t in self.getjson('torrents/info')]
    def automation_space(self,path):
        # qB reports free space for its default download directory only. A remote
        # custom path may be another mount; do not pretend that metric covers it.
        prefs=self.getjson('app/preferences')
        path=absolute_download_path(path); default=absolute_download_path(str(prefs.get('save_path','')))
        if path!=default:
            if not path.startswith(default.rstrip('/')+'/'): raise ApiError('SPACE_PATH_UNVERIFIED','qBittorrent 自动化目录必须位于其默认下载目录内',422)
            verified_storage_path(default,True); verified_storage_path(path)
        free=self.getjson('sync/maindata').get('server_state',{}).get('free_space_on_disk')
        if not isinstance(free,(int,float)) or free<0: raise ApiError('SPACE_UNKNOWN','下载器未提供可信的剩余空间',502)
        return int(free)
    def detail(self,tid):
        items=self.getjson('torrents/info',{'hashes':tid})
        if not items: raise ApiError('NOT_FOUND','任务不存在',404)
        files=[{k:f.get(k,0 if k!='name' else '') for k in ('name','size','progress')} for f in self.getjson('torrents/files',{'hash':tid})]
        trackers=[{'url':t.get('url',''),'status':t.get('status',0),'message':t.get('msg','')} for t in self.getjson('torrents/trackers',{'hash':tid})]
        return {'item':self.normalize(items[0]),'files':files,'trackers':trackers}
    def action(self,tid,action,delete_data=False):
        self.connect(); major=int(self.version.lstrip('v').split('.')[0]); route={'pause':'stop' if major>=5 else 'pause','resume':'start' if major>=5 else 'resume','delete':'delete'}[action]
        params={'hashes':tid}
        if action=='delete': params['deleteFiles']='true' if delete_data else 'false'
        self.call('torrents/'+route,params,True)
    def add(self,b):
        self.connect(); major=int(self.version.lstrip('v').split('.')[0]); fields={'savepath':b.get('save_path') or self.config.get('default_save_path',''),'stopped' if major>=5 else 'paused':'true' if b.get('paused',False) else 'false'}
        if b.get('automation_managed'): fields.update({'autoTMM':'false','contentLayout':'Original','skip_checking':'false'})
        if b.get('name'): fields['rename']=b['name']
        if b.get('tags'): fields['tags']=','.join(b['tags'])
        if b.get('url'): fields['urls']=b['url']
        boundary='nd-'+secrets.token_hex(16); chunks=[]
        for key,value in fields.items(): chunks.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+key+'"\r\n\r\n'+str(value)+'\r\n').encode())
        if b.get('torrent_base64'): chunks.append(('--'+boundary+'\r\nContent-Disposition: form-data; name="torrents"; filename="upload.torrent"\r\nContent-Type: application/x-bittorrent\r\n\r\n').encode()+base64.b64decode(b['torrent_base64'])+b'\r\n')
        chunks.append(('--'+boundary+'--\r\n').encode()); raw=self.call('torrents/add',post=True,body=b''.join(chunks),content_type='multipart/form-data; boundary='+boundary)
        if raw.strip() not in (b'Ok.',b''):
            try:
                result=json.loads(raw)
                accepted=isinstance(result,dict) and result.get('failure_count')==0 and (result.get('success_count',0)>0 or result.get('pending_count',0)>0)
            except (ValueError,TypeError): accepted=False
            if not accepted: raise ApiError('DOWNLOADER_REJECTED','qBittorrent 未接受种子',502)

class Transmission(Transport):
    def __init__(self,config):
        super().__init__(config); self.session_id=''; self.version=None
        p=urlsplit(self.base)
        self.rpc_path='' if p.path.endswith('/rpc') else '/rpc' if p.path.rstrip('/').endswith('/transmission') else '/transmission/rpc'
    def rpc(self,method,args=None):
        body=json.dumps({'method':method,'arguments':args or {}}).encode(); headers={'Content-Type':'application/json','Authorization':'Basic '+base64.b64encode((self.config.get('username','')+':'+self.config.get('password','')).encode()).decode(),'X-Transmission-Session-Id':self.session_id}
        status,raw,rh=self.request(self.rpc_path,'POST',body,headers)
        if status==409:
            sid=next((v for k,v in rh.items() if k.lower()=='x-transmission-session-id'),None)
            if not sid: raise ApiError('DOWNLOADER_RESPONSE','Transmission 会话协商失败',502)
            self.session_id=sid; headers['X-Transmission-Session-Id']=sid
            # A 409 specifically means no RPC was executed; this is the only retry.
            status,raw,_=self.request(self.rpc_path,'POST',body,headers)
        if status!=200: raise ApiError('DOWNLOADER_REJECTED','Transmission 拒绝请求，请检查 RPC 账号和白名单',502)
        try: response=json.loads(raw)
        except (ValueError,UnicodeError): raise ApiError('DOWNLOADER_RESPONSE','Transmission 响应格式无效',502)
        if response.get('result')!='success': raise ApiError('DOWNLOADER_REJECTED','Transmission 未接受操作',502)
        return response.get('arguments',{})
    def connect(self):
        if not self.version:
            self.version=self.rpc('session-get').get('version','')
            if not self.version.startswith('4.'): raise ApiError('UNSUPPORTED_VERSION','仅支持 Transmission 4',422)
        return self.version
    def normalize(self,t):
        progress=t.get('percentDone',0); raw=t.get('status',0); state={0:'paused',1:'checking',2:'checking',3:'queued',4:'downloading',5:'queued',6:'completed'}.get(raw,'error'); label={0:'已暂停',1:'排队校验',2:'校验中',3:'排队下载',4:'下载中',5:'排队做种',6:'做种中' if t.get('rateUpload',0)>0 else '做种中·暂无连接'}.get(raw,'状态未知')
        if t.get('error',0): state,label='error','错误'
        size=t.get('totalSize',0)
        return {'id':str(t['id']),'task_id':str(t['id']),'hash':t.get('hashString',''),'downloader_id':self.config['id'],'downloader_name':self.config['name'],'name':t.get('name',''),'size':size,'total_size':size,'downloaded':t.get('downloadedEver',round(size*progress)),'uploaded':t.get('uploadedEver',0),'progress':progress,'state':state,'state_label':label,'raw_state':str(raw),'download_speed':t.get('rateDownload',0),'upload_speed':t.get('rateUpload',0),'save_path':t.get('downloadDir',''),'eta':t.get('eta',-1),'ratio':t.get('uploadRatio',0),'seeders':t.get('peersSendingToUs',0),'leechers':t.get('peersGettingFromUs',0),'swarm_leechers':-1,'seeds':t.get('peersSendingToUs',0),'peers':t.get('peersGettingFromUs',0),'category':'','tags':t.get('labels',[]),'added_at':t.get('addedDate',0),'completed_at':t.get('doneDate',0),'seeding_seconds':t.get('secondsSeeding',0)}
    def torrents(self,tid=None,detail=False):
        self.connect(); fields=['id','hashString','name','totalSize','percentDone','status','rateDownload','rateUpload','downloadDir','eta','uploadRatio','peersSendingToUs','peersGettingFromUs','downloadedEver','uploadedEver','labels','addedDate','doneDate','secondsSeeding','error','errorString']
        if detail: fields+=['files','trackerStats']
        args={'fields':fields}
        if tid is not None: args['ids']=[int(tid) if tid.isdigit() else tid]
        return self.rpc('torrent-get',args).get('torrents',[])
    def tasks(self): return [self.normalize(t) for t in self.torrents()]
    def automation_space(self,path):
        self.connect(); free=self.rpc('free-space',{'path':path}).get('size-bytes')
        if not isinstance(free,(int,float)) or free<0: raise ApiError('SPACE_UNKNOWN','下载器未提供可信的剩余空间',502)
        return int(free)
    def detail(self,tid):
        items=self.torrents(tid,True)
        if not items: raise ApiError('NOT_FOUND','任务不存在',404)
        t=items[0]; files=[{'name':f['name'],'size':f['length'],'progress':f['bytesCompleted']/f['length'] if f['length'] else 1} for f in t.get('files',[])]
        trackers=[{'url':v.get('announce',''),'status':'working' if v.get('lastAnnounceSucceeded') else 'error','message':v.get('lastAnnounceResult','')} for v in t.get('trackerStats',[])]
        return {'item':self.normalize(t),'files':files,'trackers':trackers}
    def action(self,tid,action,delete_data=False):
        self.connect(); args={'ids':[int(tid) if tid.isdigit() else tid]}
        if action=='delete': args['delete-local-data']=delete_data
        self.rpc({'pause':'torrent-stop','resume':'torrent-start','delete':'torrent-remove'}[action],args)
    def add(self,b):
        self.connect(); args={'paused':b.get('paused',False)}
        args['metainfo' if b.get('torrent_base64') else 'filename']=b.get('torrent_base64') or b.get('url')
        path=b.get('save_path') or self.config.get('default_save_path','')
        if path: args['download-dir']=path
        if b.get('tags'): args['labels']=b['tags']
        return self.rpc('torrent-add',args)
