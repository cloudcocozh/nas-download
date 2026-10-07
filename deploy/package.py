"""Build clean install/source archives; never includes account data or build caches."""
from pathlib import Path
import argparse
import tarfile
import zipfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--image',type=Path,help='Optional docker-save gzip archive embedded for offline installation')
args=parser.parse_args()
if args.image and not args.image.is_file(): parser.error('--image must name a readable image archive')
root=Path(__file__).resolve().parents[1]
output=root.parent/'outputs';output.mkdir(exist_ok=True)
installer=root/'android/app/src/main/assets/installer.tar.gz';installer.parent.mkdir(parents=True,exist_ok=True)
assert b'\r' not in (root/'install.sh').read_bytes(), 'Linux installer must use LF line endings'
excluded={'.gradle','build','out','__pycache__','evidence','data','engine-config','installer-backups','downloads','.git','avd','ssh-venv','ssh-evidence','source-snapshot-121','.pytest_cache'}
source_extensions={'.py','.js','.cjs','.html','.css','.java','.xml','.gradle','.properties','.ps1','.sh','.md','.txt','.yaml','.yml','.json'}
secret_extensions={'.jks','.keystore','.pem','.key','.p12','.pfx','.sqlite','.sqlite3','.db'}
def clean_source(path):
    relative=path.relative_to(root)
    name=path.name.lower()
    if not path.is_file() or path.is_symlink() or any(part in excluded for part in relative.parts): return False
    if name in ('local.properties','.env','setup-token','secret.key') or name.startswith(('.env.','private.')) or (name.startswith('installer') and name.endswith(('.tar.gz','.bundle'))): return False
    if '.private.' in name or any(name.endswith(ext) for ext in secret_extensions) or '.sqlite3' in name: return False
    return path.suffix.lower() in source_extensions or name in ('dockerfile','.dockerignore','license') or (relative.parts[0]=='licenses' and not any(name.endswith(ext) for ext in secret_extensions))
members=[]
for folder in ('server','web','deploy','licenses'):
    members += [p for p in (root/folder).rglob('*') if clean_source(p) and 'tests' not in p.parts]
members += [root/p for p in ('install.sh','Dockerfile','compose.yaml','compose.bundled.yaml','.dockerignore')]
members += [root/p for p in ('README.md','PRIVACY.md','THIRD_PARTY.md','docs/INSTALL_RELEASE.md','docs/LICENSE_INVENTORY.md','docs/AUTOMATION.md','docs/SITES.md','docs/RELEASE_1_2.md','docs/RELEASE_1_2_1.md','docs/RELEASE_1_3.md','docs/ACCEPTANCE_1_3.md','docs/ACCEPTANCE_1_3.html','docs/QUICK_START_ZH.md','docs/QUICK_START_ZH.html','docs/USER_MANUAL_ZH.md','docs/USER_MANUAL_ZH.html','docs/BUILDING.md','docs/RELEASE_COMPONENTS.json','docs/THIRD_PARTY_SOURCES.json','docs/DEBIAN_PACKAGES.json') if (root/p).is_file()]
if (root/'LICENSE').is_file(): members.append(root/'LICENSE')
with tarfile.open(installer,'w:gz') as archive:
    for path in sorted(members): archive.add(path,arcname=path.relative_to(root).as_posix())
    if args.image: archive.add(args.image,arcname='nas-download-image.tar.gz')
with tarfile.open(output/'Nas-Download-Standalone-1.3.0-install.tar.gz','w:gz') as archive:
    for path in sorted(members): archive.add(path,arcname=path.relative_to(root).as_posix())
    if args.image: archive.add(args.image,arcname='nas-download-image.tar.gz')
source_folders=('server','web','deploy','android','tests')
source_files=set(members)
for folder in source_folders:
    source_files.update(p for p in (root/folder).rglob('*') if clean_source(p))
with zipfile.ZipFile(output/'Nas-Download-Standalone-1.3.0-source.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(source_files):
        if clean_source(path): archive.write(path,arcname='nas-download/'+path.relative_to(root).as_posix())
print('Clean installer and source archives created')
