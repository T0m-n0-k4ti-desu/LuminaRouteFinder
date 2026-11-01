"""Publish a verified EXE, portable ZIP and checksums through GitHub CLI."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

ASSETS=('LuminaRouteFinder.exe','LuminaRouteFinder-Windows-x64.zip','SHA256SUMS.txt')
ROOT=Path(__file__).resolve().parents[1]


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):
            digest.update(chunk)
    return digest.hexdigest()


def verify_assets(folder):
    paths=[Path(folder).resolve()/name for name in ASSETS]
    for path in paths:
        if not path.is_file():raise ValueError(f'Missing release asset: {path.name}')
    checks={}
    for line in paths[2].read_text(encoding='ascii').splitlines():
        if not line.strip():continue
        digest,name=line.split(maxsplit=1)
        if name in checks:raise ValueError('Duplicate checksum entry')
        checks[name]=digest
    if set(checks)!=set(ASSETS[:2]):raise ValueError('Checksums must cover both EXE and ZIP')
    digests={path.name:sha256(path) for path in paths}
    for name,expected in checks.items():
        if digests[name]!=expected:raise ValueError(f'Checksum mismatch: {name}')
    with zipfile.ZipFile(paths[1]) as bundle:
        if sorted(bundle.namelist())!=sorted(['LuminaRouteFinder.exe','gui-settings.json']):
            raise ValueError('Portable ZIP must contain exactly the EXE and settings')
        with bundle.open('LuminaRouteFinder.exe') as stream:
            digest=hashlib.sha256()
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        if digest.hexdigest()!=digests[ASSETS[0]]:raise ValueError('ZIP contains a different EXE')
        config=json.loads(bundle.read('gui-settings.json'))
        if not isinstance(config,dict) or not isinstance(config.get('delete_outputs_on_exit'),bool):raise ValueError('Invalid ZIP settings')
    return paths,digests


def gh(args,json_result=False):
    result=subprocess.run(['gh',*args],check=True,text=True,capture_output=True)
    return json.loads(result.stdout) if json_result else result.stdout.strip()


def publish(tag,repo,folder,dry_run=False):
    if not re.fullmatch(r'v\d+\.\d+(?:\.\d+)?',tag):raise ValueError('Use a stable version tag such as v1.0.2')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('Repository must be OWNER/REPO')
    paths,digests=verify_assets(folder)
    if dry_run:
        return {'tag':tag,'repo':repo,'assets':[p.name for p in paths],'dry_run':True}
    endpoint=f'repos/{repo}/releases?per_page=100'
    releases=gh(['api',endpoint],True)
    release=next((r for r in releases if r['tag_name']==tag),None)
    if release is not None and not release['draft']:
        raise ValueError('Release is already public; refusing to overwrite published assets')
    if release is None:
        gh(['release','create',tag,'--repo',repo,'--draft','--verify-tag','--title',tag,'--generate-notes'])
        release=next(r for r in gh(['api',endpoint],True) if r['tag_name']==tag)
    assets_endpoint=f"repos/{repo}/releases/{release['id']}/assets"
    existing={a['name']:a for a in gh(['api',assets_endpoint],True)}
    pending=[]
    for path in paths:
        asset=existing.get(path.name)
        if asset is None:
            pending.append(path)
        elif asset.get('digest')!='sha256:'+digests[path.name]:
            raise ValueError(f'Draft asset differs; refusing to replace {path.name}')
    if pending:
        gh(['release','upload',tag,*map(str,pending),'--repo',repo])
    uploaded={a['name']:a for a in gh(['api',assets_endpoint],True)}
    for path in paths:
        if uploaded.get(path.name,{}).get('digest')!='sha256:'+digests[path.name]:
            raise ValueError(f'Uploaded asset could not be verified: {path.name}')
    gh(['release','edit',tag,'--repo',repo,'--draft=false','--latest'])
    return {'tag':tag,'url':f'https://github.com/{repo}/releases/tag/{tag}','assets':list(ASSETS)}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tag')
    parser.add_argument('--repo',default=os.environ.get('GITHUB_REPOSITORY','T0m-n0-k4ti-desu/LuminaRouteFinder'))
    parser.add_argument('--dist-dir',type=Path,default=ROOT/'dist')
    parser.add_argument('--dry-run',action='store_true',help='Verify all local assets without accessing GitHub')
    args=parser.parse_args(argv)
    try:
        print(json.dumps(publish(args.tag,args.repo,args.dist_dir,args.dry_run),ensure_ascii=False,indent=2))
    except (ValueError,OSError,subprocess.CalledProcessError) as exc:
        parser.exit(1,f'Release failed: {exc}\n')


if __name__=='__main__':
    main()
