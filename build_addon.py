from pathlib import Path
import ast
import hashlib
import shutil
import zipfile

r=Path(__file__).parent
for name in ('engine.py','english.py'):
    shutil.copyfile(r/name,r/'addon/synthDrivers/vdsoft2000'/name)
for p in (r/'addon').rglob('*.py'):ast.parse(p.read_text(encoding='utf-8'))
target=r/'dist/vdsoft2000-0.6.0.nvda-addon'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted((r/'addon').rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:z.write(p,p.relative_to(r/'addon'))
with zipfile.ZipFile(target) as z:
    assert z.testzip() is None
    assert 'manifest.ini' in z.namelist()
    assert 'synthDrivers/vdsoft2000/data/cmudict.txt' in z.namelist()
    assert 'synthDrivers/vdsoft2000/data/CMUdict-license.txt' in z.namelist()
digest=hashlib.sha256(target.read_bytes()).hexdigest()
target.with_suffix('.sha256.txt').write_text(digest+'  '+target.name+'\n')
print(target.resolve(),target.stat().st_size,digest)
