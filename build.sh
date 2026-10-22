#!/usr/bin/env bash
# Cloudflare Pages / CI 构建入口：输出目录为 site/
set -euo pipefail
python3 -m pip install --quiet --disable-pip-version-check requests Pillow
python3 tools/fetch_acquired.py
python3 tools/brand.py icons
python3 tools/build.py
