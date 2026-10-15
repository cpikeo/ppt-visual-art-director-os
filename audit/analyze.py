"""Static inventory and comparable source-size evidence; not a dynamic coverage claim."""
import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = {'assets','compiler','ghost','intelligence','primitives','vao','verify'}


def inventory(root):
    result = {}
    for path in sorted((root/'scripts').glob('*.py')):
        text = path.read_text(encoding='utf-8'); tree = ast.parse(text)
        imports = sorted({n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.ImportFrom) and n.module}
                         | {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names})
        functions = {}
        for node in ast.walk(tree):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                calls = sorted({ast.unparse(n.func) for n in ast.walk(node) if isinstance(n,ast.Call)})
                functions[node.name] = dict(line=node.lineno, end=node.end_lineno, direct_calls=calls)
        result[str(path.relative_to(root))] = dict(lines=len(text.splitlines()), imports=imports,
            local_dependencies=[i for i in imports if i in PRODUCTION or i in {'selftest','bench'}],
            functions=functions, top_level_contracts=[n.targets[0].id for n in tree.body
                if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id.isupper()])
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--before',type=Path,required=True);args=p.parse_args()
    before,after=inventory(args.before),inventory(ROOT)
    size={}
    for group,names in [('production',PRODUCTION),('tests',{'bench','selftest'})]:
        size[group]={}
        for label,values in [('before',before),('after',after)]:
            chosen={k:v['lines'] for k,v in values.items() if Path(k).stem in names}
            size[group][label]=dict(files=len(chosen),lines=sum(chosen.values()),modules=chosen)
    size['scope']='Physical lines including comments/blanks, scripts only. audit harness and hand-authored acceptance input are listed separately; not hidden inside production size.'
    for folder in ('audit','acceptance'):
        files=list((ROOT/folder).glob('*.py'))
        size[folder+'_support']=dict(files=len(files),lines=sum(len(f.read_text().splitlines()) for f in files))
    for name,value in [('architecture-before',before),('architecture-after',after),('size',size)]:
        (ROOT/'audit'/f'{name}.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(size,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
