# AGENTS.md：Acquired 中文精读 交接说明

面向接手本项目的开发者或 AI 代理（如 Meta Muse Code：在项目根目录运行 `muse`）。读完这一页即可继续开发。

## 1. 项目是什么

Acquired 播客（acquired.fm）的中文导航站，纯静态站点。线上地址：https://acquired.quova.me
改编自 joeseesun/lexfridman-cn（MIT），架构与阅读体验沿用上游。

## 2. 目录与数据流

```
tools/fetch_acquired.py   RSS + 官网单集页 → tools/acq-master.json、tools/feed_audio.json、tools/official/{slug}.txt（官方文稿，不入库）
tools/translations.json   217 期中文标题 / 分类(guest 字段) / 简介，人工整理
tools/gen_zh.py           官方文稿 → LLM → site/zh/{slug}.html（中文精读 HTML 片段）并登记 site/data/zh-index.json
tools/translate_titles.py 新单集的中文标题与简介（LLM）
tools/build.py            生成 site/ep/*、archive、sitemap、feed、llms.txt、OG 卡片、data/episodes.json
tools/brand.py icons      生成站点图标（png/ico 不入库，构建时生成）
tools/sync_new.py         日常更新：fetch → translate → gen_zh → build
build.sh                  Cloudflare Pages 构建入口
site/                     静态站根目录；app.js 首页，ep.js 单集页（播放器、tab、阅读设置），sw.js 离线缓存
```

生成产物（site/ep、site/og、site/data/episodes.json 等）在 .gitignore 里，每次构建重新生成。

## 3. 本地运行

```bash
pip install requests Pillow
python3 tools/fetch_acquired.py        # --force 全量重抓；--no-pages 只更新 RSS
python3 tools/brand.py icons
python3 tools/build.py
python3 -m http.server 8123 -d site
```

## 4. 部署

- GitHub：banshilinghun/acquired-cn，分支 main。
- Cloudflare Pages 项目 `acquired-cn`（账号 Banshilinghun@gmail.com's Account），连接上面的仓库，推送 main 自动构建，约 4 分钟。
  - 构建命令 `bash build.sh`，输出目录 `site`，环境变量 `SITE_DOMAIN=https://acquired.quova.me`、`PYTHON_VERSION=3.13`。
- 域名：quova.me 托管在 Cloudflare；`acquired` CNAME → `acquired-cn.pages.dev`（已开代理）。

## 5. 中文精读生成

gen_zh.py 走任意 OpenAI 兼容的 `/chat/completions`：

```bash
export LLM_BASE_URL=http://127.0.0.1:<端口>/v1   # 例如本地 magpie 反代
export LLM_API_KEY=<key>                         # 免费端点可不设
export LLM_MODELS=kimi-k2.6,glm-5.1              # 逗号分隔，失败自动换下一个
export LLM_MAX_TOKENS=16000
python3 tools/gen_zh.py --only=home-depot        # 支持逗号分隔多个 slug
python3 tools/gen_zh.py --limit=20               # 从新到旧，已生成的自动跳过
```

写作规范（提示词已内置，人工修改时也要遵守）：
- 只用 `p / h2 / ul / ol / li / blockquote / strong / em`，不要 h1、不要内联样式。
- h2 标题不要加“一、二、”编号（页面目录会自动编号）。
- 不用破折号（—— 或 —）。
- 不少于 5000 汉字；按时间线讲公司史，保留 7 Powers、Bull/Bear、Playbook、Quintessence 等分析；跳过赞助与 Carve-outs。
- 结尾一个“要点回顾”列表。
- 示例：site/zh/seinfeld.html。

用 Meta Model API（Muse）生成：

```bash
export LLM_BASE_URL=https://api.meta.ai/v1      # Chat Completions，无结尾斜杠
export LLM_API_KEY=$MODEL_API_KEY               # 在 https://dev.meta.ai/ 生成
export LLM_MODELS=muse-spark-1.3,muse-wonder-1.0
export LLM_MAX_TOKENS=32000                      # 推理模型，给足输出预算，避免只有思考没有正文
python3 tools/gen_zh.py --only=home-depot
```

注意：opencode 官方免费模型只能在 OpenCode 客户端内使用，直连会返回 FreeTierError；当前 Console Key 返回 “Model access is disabled”，需在 Console 开通余额或模型权限。

## 6. 现状

| 项目 | 数量 |
| --- | --- |
| 单集 | 217（RSS 不含预告；chase-center-summer-update 官网无页面） |
| 官方英文文稿 | 175 |
| YouTube | 79 |
| 中文标题/简介 | 217 |
| 中文精读 | 1（seinfeld） |

## 7. 待办（按优先级）

1. **批量生成中文精读**（约 174 期）。先跑 home-depot 检查质量，再分批 `--limit=20`，提交 `site/zh` 与 `site/data/zh-index.json`。
2. **英文文稿逐字高亮跟读**（单集页“英文文稿” tab）：
   - 目标：播放时高亮当前词与句，自动滚动跟随，点击句子跳播；暂停或用户手动滚动时停止跟随，数秒后恢复。
   - 时间轴来源：官方文稿只有章节级时间戳。RSS 中极少数单集（如 Home Depot）带 `podcast:transcript` VTT（句级），可直接用，句内按字符比例插值到词。其余需用 WhisperX / wav2vec2 对“官方文稿 + 官方音频”做强制对齐，输出 `site/data/align/{slug}.json`（建议格式：`[[startMs, endMs, "word"], ...]` 按段分组），build.py 在文稿 HTML 里给每个词加 `data-t`。
   - 风险：音频经 `dai.transistor.fm` 动态插入广告，不同请求的广告时长可能不同，导致整体偏移。需实测；可在开头与每章开头做锚点自动校准。
   - 计算量：全站约 700 小时音频，建议 GPU 或 Apple 芯片本地跑；先做 microsoft 原型。
3. **国内播放兜底**：音频链路 pscrb.fm(AWS) → media.transistor.fm → dai.transistor.fm(Cloudflare)，国内大概率可播但可能慢；YouTube 不可用。建议在播放器 `error`/长时间 `stalled` 时提示并给出小宇宙、Apple 播客链接。不要转存音频（版权）。
4. 可选：GitHub Actions 定时运行 sync_new.py（需在仓库 Secrets 配 `LLM_API_KEY`，并注意 API 费用）。

## 8. 安全

- 不要把任何 token / API Key 写进仓库或提交记录。
- 此前在聊天中出现过的 GitHub PAT 与 opencode Key 应作废并重新生成。
- 官方文稿全文（tools/official/）不入库。
