"""Portable wrapper over evaluation/results/export_trajectory.py.

Deduplicate physical copies using authentic run metadata. Prefer an existing
indexed source, then a canonical task directory. The native exporter creates
the index; this wrapper never edits index records itself.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import sys


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',required=True,type=Path)
    ap.add_argument('--dry-run',action='store_true')
    args=ap.parse_args()
    root=args.root.resolve()
    if sys.platform=='win32' and not str(root).startswith('\\\\?\\'):
        root=Path('\\\\?\\'+str(root))
    script=root.parent/'export_trajectory.py'
    spec=importlib.util.spec_from_file_location('canonical_timeline_exporter',script)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=mod
    spec.loader.exec_module(mod)
    index=root/'trajectory_timelines/trajectory_timeline_index.json'
    preferred={x['source'] for x in json.loads(index.read_text(encoding='utf-8'))['trajectories']} if index.exists() else set()
    groups={}
    for p in mod.iter_acp_files(root):
        meta=mod.discover_meta(p.parent.parent)
        key=(meta.task_id,meta.method_id,meta.run_id,meta.condition)
        groups.setdefault(key,[]).append(p)
    chosen=[]
    for paths in groups.values():
        indexed=[p for p in paths if p.relative_to(root).as_posix() in preferred]
        canonical=[p for p in paths if p.relative_to(root).as_posix().startswith('tasks/')]
        chosen.append((indexed or canonical or paths)[0])
    mod.iter_acp_files=lambda _:iter(sorted(chosen))
    return mod.main(['--root',str(root)]+(['--dry-run'] if args.dry_run else []))


if __name__=='__main__':raise SystemExit(main())
