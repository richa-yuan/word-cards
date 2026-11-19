# word-cards — 单词卡竖屏视频（通用技能包）

把任意一组单词做成一样东西：**抖音竖屏视频**（数据唯一来源 `assets/data.js`，改数据即改视频）。

- **抖音竖屏视频**：1080×1920 / 30fps，每卡停 3 秒，Edge 神经语音配音（片头口号 + 单词 + 中文 +
  片尾关注引导），片头不报数，首尾淡入淡出，H.264 High / yuv420p(bt709) / AAC，直接可发抖音/小红书。

本技能**不产出点读网页**（`index.html`）。视频由竖屏场景页 `vertical.html` 逐帧渲染而来，
该文件是渲染中间产物，不交付给用户。

主题不限（四季天气、昆虫、饮品、家电、食物味道、医院、太阳系、动物园、学校……均已跑通），
语言不限（换例句与配音参数即可）。

## 包内容

```
word-cards/
├── SKILL.md                      # 技能说明（Agent Skills 格式，YAML frontmatter）
├── README.md                     # 本文件：依赖与各工具安装法
├── package.json                  # npm install playwright-core 用
├── scripts/                      # 8 个流水线脚本（node/python/bash，无硬编码路径）
│   ├── verify_app.cjs            # --video-only 竖屏场景 5 项检查（无需 index.html）
│   ├── render_frames.cjs         # 竖屏帧逐帧捕获（--preview 抽帧预览）
│   ├── build_audio_neural.py     # Edge 神经语音配音（默认，需网络）
│   ├── build_audio.py            # macOS say 离线配音回退
│   ├── slice_grid.py             # 2×2 白底网格 → 透明 WebP 切片
│   ├── draw_things_gen.py        # 本地 Draw Things 生图（HTTP 直连 7860，离线免费）
│   ├── encode.sh                 # ffmpeg 编码（色彩空间/规格自动校正）
│   └── _pw.cjs                   # playwright-core 依赖解析器
├── references/                   # 深度参考（实现要点、踩坑、三条插图路线）
│   ├── card-app.md  ├── vertical-video.md
│   ├── art-pipeline.md  ├── photo-tile-variant.md
│   └── draw-things.md            # 本地 Draw Things 路线（离线生图）
└── assets/app-template/          # 竖屏渲染模板（24 词玩具示例 + 字体 + 示例图）
    ├── vertical.html             # 确定性场景：片头 → N 卡 → 片尾
    └── assets/ (data.js, fonts/, img/)
```

## 环境要求

| 依赖 | 用途 | 说明 |
|---|---|---|
| node ≥ 18 | verify / 逐帧捕获 | + `npm install playwright-core --prefix <本目录>` |
| Chrome / Chromium | 无头渲染 | macOS 用默认路径；其他平台传 `--chrome <路径>` |
| python3 + numpy scipy pillow | 切片 / 修图 | `pip3 install numpy scipy pillow` |
| edge-tts | 神经语音配音 | `pip3 install edge-tts`（需网络） |
| ffmpeg ≥ 6 | 编码 | brew / apt 均可 |
| macOS `say`（可选） | 离线配音回退 | 非 macOS 无此回退，但 edge-tts 可用 |
| Draw Things App（可选） | 本地离线生图 | Apple Silicon + 免费；需 App 开着并在设置里开启 HTTP API Server（见 references/draw-things.md） |

生图有两条路线，**用前先问用户**：① 云端 ImageGen（各 Agent 自带接口，按张计费、需联网）；
② 本地 Draw Things（`draw_things_gen.py` 直连本机 API，离线免费）。提示词模板见 references。

## 安装到各工具

技能本体就是一个文件夹 + 一份 SKILL.md（Agent Skills 通用格式）。按工具三选一：

### ① 原生支持 Skills 的 Agent（WorkBuddy / ZCode / Claude Code 等）

```bash
# WorkBuddy
cp -R word-cards ~/.workbuddy/skills/word-cards
# ZCode
cp -R word-cards ~/.zcode/skills/word-cards
# Claude Code
cp -R word-cards ~/.claude/skills/word-cards
```

装完在新会话里说"做个动物园单词卡视频"即可触发。首次使用前在技能目录跑一次
`npm install playwright-core --prefix ~/.<tool>/skills/word-cards`。

### ② Codex CLI 等支持 AGENTS.md 的工具

Codex 没有技能目录，把技能挂进项目指令：

```bash
cp -R word-cards ~/skills/word-cards        # 放在固定位置
```

在项目 `AGENTS.md`（或 `~/.codex/AGENTS.md`）里追加：

```markdown
## 单词卡技能
做单词卡竖屏视频任务时，先完整阅读 ~/skills/word-cards/SKILL.md 并按其工作流执行，
脚本在 ~/skills/word-cards/scripts/，模板复制自 ~/skills/word-cards/assets/app-template/。
参考文档按需读取 ~/skills/word-cards/references/ 下对应文件。
```

### ③ DeepSeek 等纯对话式 Agent（无文件系统技能机制）

两类用法：

- **有 shell/代码执行**：把 `word-cards/` 上传到工作区或让 Agent 下载，然后把 SKILL.md
  全文贴进系统提示/项目说明，附一句"技能文件在 ./word-cards/，脚本可直接执行"。
- **纯对话（无执行环境）**：把 SKILL.md 当作生成规范使用——Agent 按它产出
  `vertical.html` 场景页 + `assets/data.js` 词表和提示词，用户本地（或任意有
  node+ffmpeg 的机器）跑 `scripts/` 完成验证、配音与编码。SKILL.md 的工作流每一步
  都标了所需脚本与参数，脱离本包也能照做。

## 快速开始（装好后 3 分钟跑通模板）

```bash
cp -R word-cards/assets/app-template/. demo/ && cd demo
python3 -m http.server 4317 --bind 127.0.0.1 &
node <skill>/scripts/verify_app.cjs --vertical http://127.0.0.1:4317/vertical.html \
  --video-only --expect 24   # 5 项全绿，不需要 index.html
python3 <skill>/scripts/build_audio_neural.py --data assets/data.js \
  --out /tmp/track.wav --intro-text "每天一分钟，开口学英语。" \
  --outro-text "玩具单词，全部打卡。关注喜悦学英语，一起开口读英语。"
node <skill>/scripts/render_frames.cjs --url http://127.0.0.1:4317/vertical.html \
  --out /tmp/frames --fps 30 --size 1080x1920 --q 92
bash <skill>/scripts/encode.sh /tmp/frames /tmp/track.wav "demo.mp4" 30 1080x1920
```

然后换自己的词表（重写 `assets/data.js` + 清空 `assets/img/` 重新生图 + 替换 `vertical.html`
主题文案），完整流程见 SKILL.md 工作流。交付物只有 MP4，没有网页。
