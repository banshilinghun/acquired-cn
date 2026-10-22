#!/usr/bin/env python3
"""批量翻译新单集的标题 / 主题分类 / 一句话简介（任意 OpenAI 兼容端点）。
输出 tools/translations.json（slug → {zh, guest, desc}），增量保存，断点续跑；已有条目不会被覆盖。
环境变量同 gen_zh.py：LLM_API_KEY、LLM_BASE_URL、LLM_MODELS。"""
import json, os, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'translations.json'
BATCH = 16
API = os.environ.get('LLM_BASE_URL', 'https://api.deepseek.com/v1').rstrip('/') + '/chat/completions'
MODELS = [m.strip() for m in os.environ.get('LLM_MODELS', 'deepseek-chat').split(',') if m.strip()]
KEY = os.environ.get('LLM_API_KEY') or os.environ.get('OPENAI_API_KEY')

master = json.load(open(ROOT / 'acq-master.json'))
done = json.load(open(OUT)) if OUT.exists() else {}
todo = [e for e in master if e['slug'] not in done]
print(f'total {len(master)}, done {len(done)}, todo {len(todo)}')
if todo and not KEY:
    sys.exit('缺少 LLM_API_KEY 环境变量')

CATS = '零售、零售与消费、科技、半导体、媒体娱乐、奢侈品、金融投资、体育、汽车、游戏、医疗、商业史、商业战略、访谈、特别节目'
PROMPT = f"""你是资深商业播客中文编辑。下面是 Acquired 播客若干期的英文标题与简介（JSON 数组，项含 slug/title/desc）。
为每一项生成三个字段：
- zh：标题的简体中文译名。公司名用中文圈通行译名（The Home Depot→家得宝，Costco→好市多，Hermès→爱马仕），没有通行译名的保留英文；
  人名用通行中文译名；「Part I / II」译作「（上）/（下）」或「（一）（二）」；「(with X)」译作「（对谈 X）」。
- guest：主题分类，只能从以下选一个：{CATS}。
- desc：一句话中文简介（30-60 字），讲清这期讲的是哪家公司或什么故事、最抓人的一个点；不要「本期」「节目中」这类字眼，不要营销腔和感叹号。
只输出 JSON 对象：{{"items":[{{"slug":"...","zh":"...","guest":"...","desc":"..."}}]}}，不要输出其他任何文字。"""


def _post(body_obj):
    req = urllib.request.Request(API, data=json.dumps(body_obj).encode(), headers={
        'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.load(r)
    data = json.loads(resp['choices'][0]['message']['content'])
    return {it['slug']: {'zh': it['zh'].strip(), 'guest': it['guest'].strip(), 'desc': it['desc'].strip()}
            for it in data.get('items', []) if it.get('slug') and it.get('zh') and it.get('guest') and it.get('desc')}


def call(items, attempt=1):
    payload = {'model': MODELS[(attempt - 1) % len(MODELS)], 'temperature': 0.3, 'max_tokens': 6000,
               'messages': [{'role': 'user', 'content': PROMPT + '\n\n输入：\n' + json.dumps(items, ensure_ascii=False)}]}
    try:
        return _post({**payload, 'response_format': {'type': 'json_object'}})
    except urllib.error.HTTPError as e:
        if e.code == 400:  # 部分端点不认 response_format
            return _post(payload)
        raise


for bi in range(0, len(todo), BATCH):
    chunk = todo[bi:bi + BATCH]
    items = [{'slug': e['slug'], 'title': e['title'], 'desc': (e.get('desc') or '')[:400]} for e in chunk]
    for attempt in range(1, 4):
        try:
            got = {k: v for k, v in call(items, attempt).items() if k in {e['slug'] for e in chunk}}
            if not got:
                raise ValueError('no items parsed')
            done.update(got)
            OUT.write_text(json.dumps(done, ensure_ascii=False, indent=0))
            print(f'batch {bi // BATCH + 1}: +{len(got)}/{len(chunk)} (total {len(done)})')
            break
        except Exception as e:
            print(f'batch {bi // BATCH + 1} attempt {attempt} failed: {type(e).__name__} {e}')
            time.sleep(3 * attempt)

miss = [e['slug'] for e in master if e['slug'] not in done]
print(f'FINISHED total={len(done)} missing={len(miss)} {miss[:10]}')
