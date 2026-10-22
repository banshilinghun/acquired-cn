#!/usr/bin/env python3
"""与 Acquired 官方 RSS 对账，生成主数据，并抓取 acquired.fm 单集页上的官方文稿与 YouTube ID。

输出：
  tools/acq-master.json     全部单集元数据（num/title/date/slug/season/episode/acqUrl/ytId/duration/desc）
  tools/feed_audio.json     官方 MP3 直链（by_slug）
  tools/official/{slug}.txt 官方文稿（"说话人 (hh:mm:ss): 文本"，时间戳取自官方章节；「§ 章节名」为官方章节标题）

用法：
  python3 tools/fetch_acquired.py            # 增量：只抓缺文稿 / 缺 YouTube 的单集
  python3 tools/fetch_acquired.py --force    # 全部重抓
  python3 tools/fetch_acquired.py --no-pages # 只对账 RSS，不抓单集页
"""
import html
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'official'
OUT.mkdir(exist_ok=True)
FEED_URL = 'https://feeds.transistor.fm/acquired'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
NS = {'itunes': 'http://www.itunes.com/dtds/podcast-1.0.dtd',
      'content': 'http://purl.org/rss/1.0/modules/content/'}


def get(url, timeout=40):
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    for k in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            err = e
            time.sleep(1.5 * (k + 1))
    raise err


def slugify(t):
    t = t.lower().replace('&', 'and')
    t = re.sub(r"[’'`.]", '', t)
    return re.sub(r'[^a-z0-9]+', '-', t).strip('-')


def text(h):
    h = re.sub(r'<br\s*/?>', '\n', h or '')
    h = re.sub(r'</p>\s*', '\n\n', h)
    return html.unescape(re.sub(r'<[^>]+>', '', h)).strip()


def first_para(h):
    """RSS 描述的首段（去掉赞助、链接列表等尾部）。"""
    m = re.search(r'<p>(.*?)</p>', h or '', re.S)
    t = ' '.join(text(m.group(1) if m else h).split())
    t = re.split(r'\s*(?:Sponsors?:|Links?:|Carve ?Outs?:|Note:|This episode is brought)', t)[0]
    return t.strip()[:600]


SITEMAP_URL = 'https://www.acquired.fm/sitemap.xml'
MANUAL_URL = {  # 标题与官网路径差异过大、模糊匹配兜不住的少数早期单集
    'eventbrite-with-julia-and-kevin-hartz': 'eventbrite',
    'bungie-with-xbox-co-founder-ed-fries': 'episode-4-bungie',
}


def _norm(s):
    s = re.sub(r'^(acquired-)?(special-episode-)?(season-\d+-)?(episode-\d+-?)?', '', s)
    s = re.sub(r'^(special-|adapting-episode-\d+-)', '', s)
    return '-'.join(w for w in s.split('-') if w not in ('the', 'and', 'with', 'a', 'part', 'i', 'ii', 'iii'))


def map_urls(items):
    """早期单集的 RSS link 指向首页，用官网 sitemap 模糊匹配出真实单集页路径。"""
    import difflib
    try:
        site = set(re.findall(r'acquired\.fm/episodes/([^<\s/]+)', get(SITEMAP_URL)))
    except Exception as e:
        print('sitemap 获取失败，跳过 URL 匹配：', e)
        return
    taken = {x['slug'] for x in items if x['slug'] in site}
    left = site - taken
    todo = [x for x in items if x['slug'] not in site]
    pairs = sorted(((difflib.SequenceMatcher(None, _norm(x['slug']), _norm(c)).ratio(), k, c)
                    for k, x in enumerate(todo) for c in left), reverse=True)
    got, used = {}, set()
    for k, x in enumerate(todo):
        if MANUAL_URL.get(x['slug']) in left:
            got[k] = MANUAL_URL[x['slug']]
            used.add(got[k])
    for r, k, c in pairs:
        if r >= 0.55 and k not in got and c not in used:
            got[k], _ = c, used.add(c)
    for k, x in enumerate(todo):
        x['acqUrl'] = f'https://www.acquired.fm/episodes/{got[k]}' if k in got else None


def parse_feed():
    root = ET.fromstring(get(FEED_URL).encode())
    items = []
    for it in root.findall('./channel/item'):
        g = lambda tag: (it.findtext(tag, default='', namespaces=NS) or '').strip()
        if g('itunes:episodeType') == 'trailer':
            continue
        link = g('link')
        m = re.search(r'acquired\.fm/episodes/([\w-]+)', link)
        slug = m.group(1) if m else slugify(g('title'))
        enc = it.find('enclosure')
        d = parsedate_to_datetime(g('pubDate')).date().isoformat()
        items.append({
            'title': g('title'), 'date': d, 'slug': slug,
            'season': int(g('itunes:season')) if g('itunes:season').isdigit() else None,
            'episode': int(g('itunes:episode')) if g('itunes:episode').isdigit() else None,
            'acqUrl': f'https://www.acquired.fm/episodes/{slug}',
            'duration': int(g('itunes:duration')) if g('itunes:duration').isdigit() else None,
            'desc': first_para(g('content:encoded') or g('description')),
            'audio': enc.get('url') if enc is not None else None,
            'guid': g('guid'),
        })
    map_urls(items)
    items.sort(key=lambda x: (x['date'], x['title']))
    seen = set()
    for i, x in enumerate(items, 1):
        x['num'] = i
        while x['slug'] in seen:          # 极少数同名单集
            x['slug'] += '-2'
        seen.add(x['slug'])
    return items[::-1]


CH_RE = re.compile(r'data-chapters="([^"]*)"')
BODY_RE = re.compile(r'<div class="episode-rich-text[^"]*">(.*?)</div>', re.S)
YT_RE = re.compile(r'class="listen-link-row[^"]*"><a href="https://(?:(?:www\.)?youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})')
SPK_RE = re.compile(r'^(Ben|David|[A-Z][\w.\'’-]+(?: [A-Z][\w.\'’-]+){0,3}):\s+(.*)$', re.S)


def parse_page(page):
    """返回 (transcript_text | None, ytId | None)。"""
    chapters = {}
    m = CH_RE.search(page)
    if m:
        for ln in html.unescape(m.group(1)).splitlines():
            if '|' in ln:
                ts, title = ln.split('|', 1)
                chapters[title.strip()] = ts.strip()
    i = page.find('id="transcript"')
    seg = page[i:] if i >= 0 else ''
    b = BODY_RE.search(seg)
    tr = None
    if b:
        lines, pending_ts, last = [], '00:00:00', ''
        for tag, inner in re.findall(r'<(h[1-6]|p)[^>]*>(.*?)</\1>', b.group(1), re.S):
            t = ' '.join(text(inner).split())
            if not t:
                continue
            if tag.startswith('h'):
                pending_ts = chapters.get(t, pending_ts)
                lines.append(f'\n§ {t}')
                continue
            sm = SPK_RE.match(t)
            name, body = (sm.group(1), sm.group(2)) if sm else (last, t)
            last = name or last
            stamp = f' ({pending_ts})' if pending_ts else ''
            pending_ts = ''
            lines.append(f'{name}{stamp}: {body}' if name else body)
        tr = '\n'.join(lines).strip() or None
        if tr and len(tr) < 2000:      # 只有零碎片段时视为无文稿
            tr = None
    # 主视频：「收听方式」一栏里的 YouTube 链接
    m = YT_RE.search(page)
    yt = m.group(1) if m else None
    return tr, yt


def main():
    force = '--force' in sys.argv
    old = {}
    mp = ROOT / 'acq-master.json'
    if mp.exists():
        old = {e['slug']: e for e in json.load(open(mp))}
    eps = parse_feed()
    print(f'RSS: {len(eps)} 期（不含预告）')
    audio = {'by_slug': {e['slug']: e.pop('audio') for e in eps if e.get('audio')}}
    for e in eps:
        o = old.get(e['slug'], {})
        e['ytId'] = o.get('ytId')
        e['officialTranscript'] = o.get('officialTranscript')

    def work(e):
        dest = OUT / f"{e['slug']}.txt"
        if not e.get('acqUrl'):
            return 'no-page'
        if not force and dest.exists() and e.get('ytId'):
            return 'skip'
        try:
            page = get(e['acqUrl'])
        except Exception as ex:
            return f'fail {ex}'
        tr, yt = parse_page(page)
        e['ytId'] = e.get('ytId') or yt
        if tr:
            dest.write_text(tr)
            e['officialTranscript'] = e['acqUrl'] + '#transcript'
        return 'ok' if tr else 'no-transcript'

    if '--no-pages' not in sys.argv:
        with ThreadPoolExecutor(6) as ex:
            res = list(ex.map(work, eps))
        for k in sorted(set(r.split()[0] for r in res)):
            print(f'  {k}: {sum(1 for r in res if r.split()[0] == k)}')
    for e in eps:
        if e.get('acqUrl') and (OUT / f"{e['slug']}.txt").exists():
            e['officialTranscript'] = e['acqUrl'] + '#transcript'
    mp.write_text(json.dumps(eps, ensure_ascii=False, indent=1))
    (ROOT / 'feed_audio.json').write_text(json.dumps(audio, ensure_ascii=False))
    print(f"acq-master.json: {len(eps)} 期，文稿 {sum(1 for e in eps if e.get('officialTranscript'))}，"
          f"YouTube {sum(1 for e in eps if e.get('ytId'))}")


if __name__ == '__main__':
    main()
