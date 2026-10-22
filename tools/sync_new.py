#!/usr/bin/env python3
"""每日追新（可放 crontab / GitHub Actions）：
  1) fetch_acquired.py   与官方 RSS 对账，补元数据、音频直链、官方文稿与 YouTube ID
  2) translate_titles.py 为新单集生成中文标题 / 分类 / 简介（需 LLM_API_KEY；没有则跳过）
  3) gen_zh.py           为有文稿但没有精读的单集生成中文精读（需 LLM_API_KEY；--no-zh 跳过）
  4) build.py            全量构建；设置了 DEPLOY_TARGET 则 rsync 部署

用法：python3 tools/sync_new.py [--dry-run] [--no-zh] [--zh-limit=N]
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / 'tools'
PY = sys.executable
args = sys.argv[1:]
dry = '--dry-run' in args
zh_limit = next((a.split('=', 1)[1] for a in args if a.startswith('--zh-limit=')), '5')
has_key = bool(os.environ.get('LLM_API_KEY') or os.environ.get('OPENAI_API_KEY'))


def run(*cmd):
    print('$', ' '.join(cmd), flush=True)
    if not dry:
        subprocess.run(cmd, cwd=ROOT, check=True)


before = {e['slug'] for e in json.load(open(T / 'acq-master.json'))} if (T / 'acq-master.json').exists() else set()
run(PY, 'tools/fetch_acquired.py')
if not dry:
    after = [e for e in json.load(open(T / 'acq-master.json')) if e['slug'] not in before]
    print(f'新单集：{len(after)} ' + ', '.join(e['title'] for e in after[:10]))
if has_key:
    run(PY, 'tools/translate_titles.py')
    if '--no-zh' not in args:
        run(PY, 'tools/gen_zh.py', f'--limit={zh_limit}')
else:
    print('未设置 LLM_API_KEY：跳过标题翻译与中文精读生成（新单集将以英文标题上线）')
run(PY, 'tools/build.py')
target = os.environ.get('DEPLOY_TARGET')
if target:
    run('rsync', '-az', '--delete', '--exclude', '.well-known', 'site/', target)
print('done')
