# Acquired 中文精读

Acquired 播客的中文导航站：一个纯静态站点，收录 Acquired 全部单集，提供中文标题与简介、官方音频与 YouTube、英文官方文稿（带章节时间戳，可点击跳播）、AI 中文精读、全文搜索与 RSS。

本项目改编自 [joeseesun/lexfridman-cn](https://github.com/joeseesun/lexfridman-cn)（MIT），沿用其静态站架构与阅读体验，数据源、文案、配色与精读提示词都针对 [Acquired](https://www.acquired.fm/) 重写。

在线访问：<https://acquired.quova.me>

## 现状

| 项目 | 数量 |
| --- | --- |
| 单集（RSS，不含预告） | 217 |
| 官方英文文稿（acquired.fm） | 175 |
| YouTube 视频 | 79 |
| 中文标题 / 分类 / 简介 | 217（人工整理，`tools/translations.json`） |
| 中文精读 | 1 篇示例（`site/zh/seinfeld.html`），其余由 LLM 管线批量生成 |

## 快速开始

```bash
pip install requests          # 仅 gen_zh / translate_titles 需要
python3 tools/fetch_acquired.py   # 抓 RSS + 官网单集页 → acq-master.json、feed_audio.json、tools/official/*.txt
python3 tools/build.py            # 生成 site/ 下所有页面、sitemap、feed、OG 卡片
python3 -m http.server 8123 -d site
```

`fetch_acquired.py` 参数：`--force` 重新抓取所有官网页面；`--no-pages` 只更新 RSS。

## 站点配置（环境变量）

| 变量 | 说明 | 默认 |
| --- | --- | --- |
| `SITE_DOMAIN` | 正式域名，用于 canonical、sitemap、RSS、OG | `https://acquired.quova.me` |
| `SITE_AUTHOR` / `SITE_AUTHOR_URL` | 页脚署名 | `Acquired 中文精读` / 空 |
| `SITE_REPO` | 页脚仓库链接 | 上游仓库 |
| `SITE_CONTACT` | 联系方式链接 | 仓库 issues |

## 中文精读管线

精读通过任意 OpenAI 兼容接口生成（默认 DeepSeek）：

```bash
export LLM_API_KEY=sk-...
export LLM_BASE_URL=https://api.deepseek.com/v1   # 可选
export LLM_MODELS=deepseek-chat                   # 可选，逗号分隔做回退
python3 tools/gen_zh.py --limit 5                 # 从最新一期开始生成 5 篇
python3 tools/gen_zh.py --only costco,nvidia      # 指定单集
python3 tools/build.py
```

提示词针对 Acquired 的结构：按时间线讲公司史，保留 7 Powers、Bull/Bear、Playbook、Quintessence 等分析段，跳过赞助与 Carve-outs；输出只允许 `p/h2/ul/ol/li/blockquote/strong/em`，不少于 5000 字。生成结果写入 `site/zh/{slug}.html` 并登记到 `site/data/zh-index.json`。

日常更新可以一键跑：

```bash
python3 tools/sync_new.py --zh-limit=3  # 抓新期 → 翻译标题 → 生成精读 → 构建（可选 rsync 部署）
```

新单集的中文标题与简介由 `tools/translate_titles.py` 调同一个 LLM 接口生成，并追加到 `translations.json`。

## 部署

`site/` 是纯静态目录，可以放到任意静态托管。本仓库用 Cloudflare Pages 连接 GitHub 自动部署：

- 构建命令：`bash build.sh`（安装依赖 → 抓取 RSS 与官方文稿 → 生成图标 → 构建）
- 输出目录：`site`
- 自定义域名：`acquired.quova.me`

推送到 `main` 即自动重新构建上线。换域名时设置 `SITE_DOMAIN` 环境变量。

## 内容与版权

- 音频、视频、官方文稿版权归 Acquired（Ben Gilbert、David Rosenthal）所有。本站只链接官方资源，官方文稿全文不入库（`tools/official/` 已加入 `.gitignore`）。
- 中文精读由 AI 基于官方文稿改写，并非官方翻译，可能存在偏差，以原音频与官方文稿为准。
- 本项目与 Acquired 官方无关。如果你喜欢这档节目，请去 [acquired.fm](https://www.acquired.fm/) 支持他们。

## 致谢与许可

代码基于 [lexfridman-cn](https://github.com/joeseesun/lexfridman-cn)（作者：向阳乔木），以 MIT 许可发布，见 [LICENSE](LICENSE)。
