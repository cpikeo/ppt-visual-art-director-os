"""Read/parse all tracked files in the base repository and record their scope.
This is a coverage inventory, NOT a claim that every historical log was re-executed.
"""
import ast
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().rstrip('\0').split('\0')
rows=[]
for rel in tracked:
    p=ROOT/rel
    raw=p.read_bytes()
    row={'path':rel,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    if p.suffix=='.py':
        tree=ast.parse(raw.decode('utf-8'),filename=rel)
        row['kind']='python';row['functions']=sum(isinstance(n,ast.FunctionDef) for n in tree.body)
    elif p.suffix=='.json':
        val=json.loads(raw.decode('utf-8'));row['kind']='json';row['root_type']=type(val).__name__
    elif p.suffix=='.pptx':
        with zipfile.ZipFile(p) as z: row['pptx_parts']=len(z.namelist());row['zip_corrupt_part']=z.testzip()
        row['kind']='pptx'
    elif p.suffix in ('.md','.txt','.yml','.toml','.csv','.log','.patch','.pyc','.gitignore') or p.name.startswith('.'):
        raw.decode('utf-8');row['kind']='text';row['lines']=len(raw.splitlines())
    elif p.suffix in ('.png','.jpg'):
        row['kind']='image'
    else: row['kind']='other'
    rows.append(row)
result={'baseline_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'tracked_count':len(rows),'by_root':{},'rows':rows,'note':'Paths are tracked in HEAD; file bytes are read from the current working tree (may be modified). New untracked review/ and benchmark fixture files are not included. Audit is historical evidence, not rerun.'}
for r in rows:
    first=r['path'].split('/')[0];result['by_root'][first]=result['by_root'].get(first,0)+1
(ROOT/'review/inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(result['tracked_count'],result['by_root'])
