"""Reproduce local evidence. Does not dispatch remote CI or pretend Linux is Windows.
python audit/validate.py --python python --python /path/to/python3.10 --before /path/to/baseline
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', action='append', dest='pythons')
    parser.add_argument('--before', type=Path)
    args = parser.parse_args()
    records = []

    def run(name, cmd, expected=0, env=None):
        start = time.perf_counter()
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, encoding='utf-8', env=env)
        path = ROOT / 'audit' / (name + '.log')
        path.write_text(p.stdout + p.stderr, encoding='utf-8')
        records.append(dict(name=name, command=cmd, expected=expected, returncode=p.returncode,
                            seconds=round(time.perf_counter()-start,3), log=str(path.relative_to(ROOT))))
        print(name,p.returncode,flush=True)
        if p.returncode != expected:
            raise RuntimeError(f'Unexpected result: {path}')

    # Downloaded runner logs require admin (403); this reproduces the reported assertion,
    # not a claim that the sandbox has the identical Ubuntu image font inventory.
    if args.before:
        code = (f"import sys;sys.path.insert(0,{str(args.before.resolve()/'scripts')!r});"
                "import ghost,selftest; ghost._FONT_BOLD_CANDIDATES={r:() for r in ghost._FONT_BOLD_CANDIDATES};"
                "sys.exit(selftest.main())")
        run('repro-415', [sys.executable,'-c',code], expected=1)
    for python in args.pythons or [sys.executable]:
        version = subprocess.check_output([python,'-c','import platform;print(platform.python_version())'],text=True).strip()
        label = version.replace('.','-')
        run('compile-'+label,[python,'-m','compileall','-q','scripts'])
        run('selftest-'+label,[python,'scripts/selftest.py'])
        for suite in ('cases','holdout','transfer'):
            run('bench-'+suite+'-'+label,[python,'scripts/bench.py','--cases',f'benchmark/{suite}.json',
                                          '--out',f'audit/bench-{suite}-{label}.json'])
        # Execute the checked-in smoke run block, using the interpreter under test for its subprocess.
        import yaml
        workflow = yaml.safe_load((ROOT/'.github/workflows/ci.yml').read_text())
        steps = workflow['jobs']['smoke']['steps']
        smoke = next(s['run'] for s in steps if s.get('name','').startswith('Confirm spec'))
        executable = Path(subprocess.check_output([python,'-c','import sys;print(sys.executable)'],text=True).strip())
        environment = dict(os.environ, PATH=str(executable.parent)+os.pathsep+os.environ['PATH'])
        run('smoke-'+label,['bash','-c',smoke],env=environment)
        # All-empty inventories including bold must pass without depending on installed fonts.
        code = ("import sys;sys.path.insert(0,'scripts');import ghost,selftest;"
                "ghost._FONT_CANDIDATES.update({r:() for r in ('cjk','cjk_serif')});"
                "ghost._FONT_BOLD_CANDIDATES.update({r:() for r in ('cjk','cjk_serif')});"
                "sys.exit(selftest.main())")
        # One full no-font run suffices; hermetic font loader tests execute on each version above.
        if python == (args.pythons or [sys.executable])[0]:
            run('no-fonts-'+label,[python,'-c',code])
    run('whitespace',['git','diff','--check'])
    (ROOT/'audit/validation.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


if __name__ == '__main__': main()
