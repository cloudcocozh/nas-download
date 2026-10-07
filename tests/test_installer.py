"""Linux-only installer guards. Fake Docker verifies writes, never creates containers."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import socket
import sys

class PortPreflightTests(unittest.TestCase):
    def run_check(self, port):
        env=dict(os.environ,ND_BIND='127.0.0.1',ND_PORT=str(port))
        return subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'deploy'/'check_ports.py'),'existing'],env=env,capture_output=True,text=True)
    def test_occupied_port_reports_failure(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));listener.listen()
            result=self.run_check(listener.getsockname()[1])
            self.assertEqual(result.returncode,3)
    def test_released_port_passes(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        self.assertEqual(self.run_check(port).returncode,0)

@unittest.skipIf(os.name == 'nt', 'Run these on Linux NAS staging with fake Docker')
class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root/'source'
        shutil.copytree(Path(__file__).resolve().parents[1], self.source,
                        ignore=shutil.ignore_patterns('android','data','evidence','__pycache__'))
        self.bin = self.root/'bin'; self.bin.mkdir()
        fake = self.bin/'docker'; fake.write_text('#!/bin/sh\nexit 0\n'); fake.chmod(0o700)
        self.env = dict(os.environ, PATH=str(self.bin)+':'+os.environ['PATH'])
    def tearDown(self): self.temp.cleanup()
    def install(self, target, **flags):
        args=['sh',str(self.source/'install.sh'),'--dir',str(target),'--bind','127.0.0.1']
        flags.setdefault('mode','existing')
        for key,value in flags.items(): args += ['--'+key,str(value)]
        return subprocess.run(args,env=self.env,capture_output=True,text=True,timeout=15)
    def test_empty_target_and_owned_upgrade(self):
        target=self.root/'service'
        result=self.install(target)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((target/'.nas-download-install').read_text().strip(),'nas-download-v1')
        self.assertIn('NAS_DOWNLOAD_READY=http://127.0.0.1:7120',result.stdout)
        self.assertIn('NAS_DOWNLOAD_SETUP_CODE=',result.stdout)
        self.assertEqual((target/'.env').stat().st_mode & 0o777,0o600)
        self.assertEqual(self.install(target).returncode,0)
    def test_default_mode_is_integrated(self):
        target=self.root/'default'
        result=subprocess.run(['sh',str(self.source/'install.sh'),'--dir',str(target)],env=self.env,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual((target/'.nas-download-mode').read_text().strip(),'bundled')
        self.assertTrue((target/'engine-config').is_dir())
    def test_failed_upgrade_restores_matching_state_and_env(self):
        target=self.root/'upgrade'; self.assertEqual(self.install(target,mode='bundled').returncode,0)
        (target/'data'/'keep').write_text('before')
        (target/'engine-config'/'resume').write_text('original-engine-state')
        before=(target/'.env').read_bytes()
        (self.bin/'docker').write_text('#!/bin/sh\ncase "$*" in *" exec "*) exit 1;; esac\nexit 0\n')
        sleep=self.bin/'sleep'; sleep.write_text('#!/bin/sh\nexit 0\n'); sleep.chmod(0o700)
        result=self.install(target,mode='bundled')
        self.assertEqual(result.returncode,4,result.stderr)
        self.assertEqual((target/'data'/'keep').read_text(),'before')
        self.assertEqual((target/'engine-config'/'resume').read_text(),'original-engine-state')
        self.assertEqual((target/'.env').read_bytes(),before)
        self.assertFalse((target/'data'/'.install-maintenance').exists())
        self.assertTrue(list((target/'installer-backups').glob('*/state/data/keep')))
    def test_state_nested_symlink_fails_before_docker_changes(self):
        target=self.root/'links'; self.assertEqual(self.install(target,mode='bundled').returncode,0)
        outside=self.root/'outside'; outside.mkdir()
        (target/'data'/'alias').symlink_to(outside,target_is_directory=True)
        self.assertNotEqual(self.install(target,mode='bundled').returncode,0)
        self.assertEqual(list(outside.iterdir()),[])
    def test_offline_image_load_and_no_build(self):
        (self.source/'nas-download-image.tar.gz').write_bytes(b'fixture')
        calls=self.root/'calls'
        (self.bin/'docker').write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "'+str(calls)+'"\nexit 0\n')
        self.assertEqual(self.install(self.root/'offline').returncode,0)
        log=calls.read_text(); self.assertIn('load -i ',log)
        self.assertNotIn(' build ',log)
    def test_parallel_install_lock_blocks_second_installer(self):
        target=self.root/'locked';self.assertEqual(self.install(target).returncode,0)
        (target/'.installer-lock').mkdir()
        before=(target/'.env').read_bytes()
        result=self.install(target)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual((target/'.env').read_bytes(),before)
        self.assertTrue((target/'.installer-lock').is_dir())
    def test_occupied_directory_untouched(self):
        target=self.root/'other';target.mkdir();(target/'keep').write_text('untouched')
        self.assertNotEqual(self.install(target).returncode,0)
        self.assertEqual(list(target.iterdir()),[target/'keep'])
    def test_target_and_parent_symlink_rejected(self):
        actual=self.root/'actual';actual.mkdir();link=self.root/'linked';link.symlink_to(actual,target_is_directory=True)
        self.assertNotEqual(self.install(link).returncode,0)
        self.assertNotEqual(self.install(link/'child').returncode,0)
        self.assertEqual(list(actual.iterdir()),[])
    def test_root_aliases_rejected(self):
        for target in ('/','//','/./','/tmp/../','/tmp//unsafe'):
            self.assertNotEqual(self.install(target).returncode,0,target)
    def test_symlink_marker_rejected(self):
        target=self.root/'existing';target.mkdir();fake=self.root/'marker';fake.write_text('nas-download-v1')
        (target/'.nas-download-install').symlink_to(fake)
        self.assertNotEqual(self.install(target).returncode,0)
    def test_mode_change_does_not_create_engine(self):
        target=self.root/'service';self.assertEqual(self.install(target).returncode,0)
        result=self.install(target,mode='bundled')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((target/'engine-config').exists())
    def test_invalid_port_rejected(self):
        for port in ('80','65535','7120;id','-1'):
            self.assertNotEqual(self.install(self.root/'unused',port=port).returncode,0)
    def test_invalid_bind_rejected(self):
        for bind in ('999.0.0.1','1.2.3','1..2.3'):
            self.assertNotEqual(self.install(self.root/'unused',bind=bind).returncode,0)
    def test_health_failure_never_claims_ready(self):
        (self.bin/'docker').write_text('#!/bin/sh\ncase "$*" in *" exec "*) exit 1;; esac\nexit 0\n')
        sleep=self.bin/'sleep';sleep.write_text('#!/bin/sh\nexit 0\n');sleep.chmod(0o700)
        result=self.install(self.root/'service')
        self.assertEqual(result.returncode,4)
        self.assertNotIn('NAS_DOWNLOAD_READY=',result.stdout)
    def test_port_conflict_never_claims_ready(self):
        (self.bin/'docker').write_text('#!/bin/sh\ncase "$*" in *check_ports.py*) exit 3;; esac\nexit 0\n')
        result=self.install(self.root/'service')
        self.assertEqual(result.returncode,3)
        self.assertNotIn('NAS_DOWNLOAD_READY=',result.stdout)
    def test_state_symlink_rejected(self):
        target=self.root/'service';self.assertEqual(self.install(target).returncode,0)
        outside=self.root/'outside';outside.write_text('untouched')
        (target/'.env').unlink();(target/'.env').symlink_to(outside)
        self.assertNotEqual(self.install(target).returncode,0)
        self.assertEqual(outside.read_text(),'untouched')
    def test_bundled_upgrade_keeps_downloads_and_secrets(self):
        target=self.root/'service';downloads=self.root/'custom downloads'
        first=self.install(target,mode='bundled',downloads=downloads)
        self.assertEqual(first.returncode,0,first.stderr)
        before=(target/'.env').read_text()
        (target/'data'/'keep').write_text('retained')
        self.assertEqual(self.install(target,mode='bundled').returncode,0)
        self.assertEqual((target/'.env').read_text(),before)
        self.assertEqual((target/'data'/'keep').read_text(),'retained')
        self.assertTrue(list((target/'installer-backups').glob('*/.env')))

if __name__=='__main__': unittest.main()
