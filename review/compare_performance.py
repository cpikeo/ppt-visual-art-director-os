"""3-round interleaved 5bfb09a vs working-tree deterministic production comparison.
Run from repo: .venv/bin/python review/compare_performance.py --before /tmp/vao-base
Temporary PPTX/preview files live outside repo; summary is review/performance-comparison.json.
This reuses audit/reproduce.py fixture/CLI methods; it DOES NOT measure human/agent BUILD.
"""
import argparse
import copy
import hashlib
import json
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'audit'))
from reproduce import fixtures, cli, write  # noqa: E402


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(before, rounds=3):
    records = []
    with tempfile.TemporaryDirectory(prefix='vao-compare-') as td:
        tmp = Path(td)
        for task, count, images in [('text5', 5, False), ('text15', 15, False),
                                    ('image15', 15, True)]:
            for rnd in range(rounds):
                for version in (('before', 'after') if rnd % 2 == 0 else ('after', 'before')):
                    repo = before if version == 'before' else ROOT
                    work = tmp / f'{task}-{rnd}-{version}'
                    work.mkdir()
                    deck, manifest = fixtures(work, count, images)
                    plan_args = ['plan', work/'brief.json', '--out', work/'plan.json', '--json']
                    if manifest:
                        plan_args += ['--assets-out', manifest]
                    plan_ms, _ = cli(repo, plan_args, work/'plan.log')
                    if manifest:
                        entries = json.loads(manifest.read_text())['assets']
                        for page in deck['slides']:
                            for element in page['elements']:
                                if element['type'] == 'image':
                                    element['asset_id'] = next(a['asset_id'] for a in entries
                                                               if page['id'] in a.get('slide_ids', []))
                        write(work/'spec.json', deck)
                    out = work / 'out.pptx'
                    check_args = ['check', work/'spec.json', out, '--mode', 'release',
                                  '--speed', 'strict', '--json']
                    if manifest:
                        check_args += ['--assets-manifest', manifest]
                    for phase in ('cold', 'warm', 'iteration'):
                        if phase == 'iteration':
                            deck['slides'][0]['elements'][2]['text'] = (deck['slides'][0]['elements'][2]['text']
                                    .replace('架构简单', '执行简单'))
                            write(work/'spec.json', deck)
                        wall, result = cli(repo, check_args, work/f'{phase}.log')
                        delivery = json.loads(out.with_suffix('.manifest.json').read_text())
                        assert delivery['status'] == 'PASS'
                        ghost = delivery['ghost_preview']
                        assert ghost['scope'] == 'full' and ghost['count'] == count
                        records.append(dict(task=task, round=rnd, version=version,
                                            phase=phase, check_ms=round(wall, 2),
                                            plan_ms=round(plan_ms, 2),
                                            output_sha256=digest(out),
                                            preview_sha256=digest(ghost['contact_sheet']),
                                            drawn=result['timing'].get('render_pages_drawn')))
                    print(task, rnd, version, 'PASS', flush=True)
    summaries, pairs = [], []
    for task in ('text5', 'text15', 'image15'):
        for phase in ('cold', 'warm', 'iteration'):
            subset = [r for r in records if r['task'] == task and r['phase'] == phase]
            row = {'task': task, 'phase': phase}
            for version in ('before', 'after'):
                sample = [r['check_ms'] for r in subset if r['version'] == version]
                row[version+'_median_ms'] = round(statistics.median(sample), 2)
                row[version+'_samples_ms'] = sample
            row['delta_percent'] = round(100*(row['after_median_ms']/row['before_median_ms']-1),2)
            summaries.append(row)
            for rnd in range(rounds):
                a = next(r for r in subset if r['round']==rnd and r['version']=='before')
                b = next(r for r in subset if r['round']==rnd and r['version']=='after')
                pairs.append({'task':task,'phase':phase,'round':rnd,
                              'pptx_equal':a['output_sha256']==b['output_sha256'],
                              'preview_equal':a['preview_sha256']==b['preview_sha256']})
    result = {'baseline_commit':'5bfb09a673f7e229e4e8fc5c558d92275f2dc846',
              'method':'3 interleaved paired rounds, fresh process each CLI, strict all pages, application-cache cold / warm / single-page title edit; OS cache not flushed; no human/model BUILD; no external renderer',
              'summaries':summaries,'equality':pairs,'records':records}
    write(ROOT/'review/performance-comparison.json',result)
    assert all(p['pptx_equal'] and p['preview_equal'] for p in pairs), 'Artifact mismatch; inspect comparison'
    assert all(r['drawn']==1 for r in records if r['phase']=='iteration')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--before',type=Path,required=True)
    a=parser.parse_args();r=run(a.before.resolve());
    for s in r['summaries']:
        print(s['task'],s['phase'],s['before_median_ms'],s['after_median_ms'],s['delta_percent'])
    print('equal',sum(p['pptx_equal'] and p['preview_equal'] for p in r['equality']), '/',len(r['equality']))
