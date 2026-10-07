import tempfile,time,unittest,json,threading
import uuid
from unittest.mock import patch
from server.app import Application,ApiError
from server.sites import Torznab,MTeam

class SitesTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.app=Application(self.tmp.name,'setup'); self.session={'id':'fixture'}
    def tearDown(self):
        self.app.sites.pool.shutdown(wait=True); self.app.db.close(); self.tmp.cleanup()
    def call(self,m,p,b=None,q=None): return self.app.dispatch(m,p,q or {},b or {},self.session,'127.0.0.1')
    def site(self):
        with patch('server.sites.validate_url',side_effect=lambda v:v):
            return self.call('POST','/sites',{'name':'Fixture','type':'torznab','url':'http://127.0.0.1:9999/api','api_key':'private-key'})['item']
    def test_encrypted_and_public(self):
        site=self.site(); self.assertNotIn('api_key',site)
        stored=self.app.db.execute('SELECT config FROM sites').fetchone()[0]; self.assertNotIn('private-key',stored)
        updated=self.call('PATCH','/sites/'+site['id'],{'api_key':''})['item']; self.assertTrue(updated['has_api_key'])
    def test_search_poll_and_owner(self):
        self.site()
        with patch.object(Torznab,'search',return_value=([{'id':'1','name':'Demo','_url':'secret'}],51)):
            jid=self.call('POST','/searches',{'query':'Demo','page':2})['search_id']
            for _ in range(100):
                result=self.call('GET','/searches/'+jid)
                if result['status']=='completed': break
                time.sleep(.005)
            self.assertEqual(result['total'],1); self.assertNotIn('_url',result['items'][0]); self.assertEqual(result['page'],2)
            with self.assertRaises(ApiError): self.app.sites.dispatch('GET','/searches/'+jid,{}, {},{'id':'other'})
    def test_cancel_discards_late_results(self):
        self.site(); gate=threading.Event()
        def slow(*args): gate.wait(1); return ([{'id':'late','name':'Late'}],1)
        with patch.object(Torznab,'search',side_effect=slow):
            jid=self.call('POST','/searches',{})['search_id']; self.call('DELETE','/searches/'+jid); gate.set()
            time.sleep(.02); result=self.call('GET','/searches/'+jid)
            self.assertEqual(result['status'],'cancelled'); self.assertEqual(result['items'],[])
    def test_torznab_rejects_external_download(self):
        xml=b'<rss><channel><item><title>X</title><enclosure url="http://evil.invalid/file"/></item></channel></rss>'
        with patch('server.sites.request',return_value=xml):
            rows,_=Torznab({'url':'http://127.0.0.1/api','api_key':'secret'}).search('x',1,20)
            self.assertEqual(rows,[])
    def test_mteam_rejects_untrusted_token_target(self):
        adapter=MTeam({'url':'https://api.m-team.cc/api','api_key':'x'})
        with patch.object(adapter,'detail',return_value={}),patch.object(adapter,'api',return_value='https://evil.invalid/file'):
            with self.assertRaises(ApiError): adapter.torrent('123')
    def test_search_errors_are_explicit(self):
        self.site()
        with patch.object(Torznab,'search',side_effect=ApiError('SITE_AUTH','凭据错误',502)):
            jid=self.call('POST','/searches',{})['search_id']
            for _ in range(100):
                result=self.call('GET','/searches/'+jid)
                if result['status']=='completed': break
                time.sleep(.005)
            self.assertEqual(result['errors'][0]['code'],'SITE_AUTH')
    def test_site_download_uncertain_never_fetches_or_submits_twice(self):
        site=self.site(); self.app.sites.results[(site['id'],'1')]=(time.time(),{'id':'1','_url':'http://127.0.0.1:9999/file'})
        body={'request_id':str(uuid.uuid4()),'downloader_id':1,'paused':True}
        from unittest.mock import Mock
        downloader=Mock(); downloader.add.side_effect=OSError('connection lost')
        with patch.object(self.app,'config',return_value={'id':1,'type':'qbittorrent'}),patch.object(self.app,'adapter',return_value=downloader),patch('server.sites.request',return_value=b'd4:infodee') as fetch:
            path='/sites/'+site['id']+'/torrents/1/download'
            first=self.call('POST',path,body); second=self.call('POST',path,body)
            self.assertEqual(first['operation']['status'],'uncertain'); self.assertEqual(first,second)
            self.assertEqual(fetch.call_count,1); self.assertEqual(downloader.add.call_count,1)

if __name__=='__main__': unittest.main()
