"""Build a reproducible, dependency-free source zip from the reviewed file list."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile
ROOT=Path(__file__).resolve().parents[1]

def build(output):
    entries={}
    for name in (ROOT/'RELEASE_FILES.txt').read_text().splitlines():
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or not path.parts or name in entries:
            raise ValueError('Invalid or duplicate release path')
        source=ROOT/name
        if any(p.is_symlink() for p in [source,*source.parents]) or not source.is_file():
            raise ValueError('Release inputs must be regular files')
        entries[name]=source.read_bytes()
    manifest={name:hashlib.sha256(data).hexdigest() for name,data in sorted(entries.items())}
    entries['SHA256SUMS.json']=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as stream, zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as archive:
        for name,data in sorted(entries.items()):
            info=zipfile.ZipInfo('decisionguard-v1/'+name, date_time=(2026,1,1,0,0,0))
            info.external_attr=0o100644<<16
            archive.writestr(info,data)
    return {'files':len(manifest),'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    print(json.dumps(build(p.parse_args().output)))
