"""Native qB/Transmission deletion and managed-directory wire contracts."""
import base64, threading, unittest
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs
import test_automation_protocol as fixtures
from test_automations import RAW
from server.adapters import QBittorrent,Transmission


class RotationProtocolTests(unittest.TestCase):
    def setUp(self):
        self.http=ThreadingHTTPServer(('127.0.0.1',0),fixtures.AutomationFixture)
        self.http.calls=[]; self.http.rpc=[]; self.http.version='v5.2.4'
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True); self.thread.start()
        self.config={'id':1,'name':'fixture','url':'http://127.0.0.1:%d'%self.http.server_port}
    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join()
    def test_qb_managed_add_preserves_original_layout_and_disables_auto_movement(self):
        qb=QBittorrent(self.config)
        qb.add({'torrent_base64':base64.b64encode(RAW).decode(),'automation_managed':True,'save_path':'/downloads/nd-brush/job/hash','tags':['nd-auto-op']})
        body=self.http.calls[-1][1]
        for field,value in [('savepath','/downloads/nd-brush/job/hash'),('autoTMM','false'),('contentLayout','Original'),('skip_checking','false'),('tags','nd-auto-op')]:
            self.assertIn(('name="'+field+'"\r\n\r\n'+value+'\r\n').encode(),body)
    def test_qb_delete_files_uses_only_hash_scoped_native_api(self):
        qb=QBittorrent(self.config); qb.action('a'*40,'delete',True)
        self.assertEqual(self.http.calls[-1][0],'/api/v2/torrents/delete')
        self.assertEqual(parse_qs(self.http.calls[-1][1].decode()),{'hashes':['a'*40],'deleteFiles':['true']})
    def test_transmission_delete_files_and_real_seeding_counter_use_native_api(self):
        tr=Transmission(self.config); tr.tasks()
        self.assertIn('secondsSeeding',self.http.rpc[-1]['arguments']['fields'])
        tr.action('7','delete',True)
        self.assertEqual(self.http.rpc[-1],{'method':'torrent-remove','arguments':{'ids':[7],'delete-local-data':True}})


if __name__=='__main__': unittest.main()
