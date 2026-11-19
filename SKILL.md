---
name: word-cards
description: 单词卡竖屏视频 — 把任意一组单词做成符合抖音竖屏规格的 1080×1920 视频（带配音、音标、中文、例句，片头口号 + 片尾关注引导）。主题/语言不限，默认写实摄影插画 + Edge 神经语音，片头不显示单词数量。当用户需要把单词做成抖音/小红书竖屏短视频、儿童单词视频、词汇学习视频时使用；也可用于其他语言的视频（改数据与发音即可）。本技能只产出视频，不产出网页。
---

# Skill: word-cards
# 单词卡竖屏视频（word-cards）

## Overview

一条流程产出一样东西：一条由词表数据渲染出的抖音竖屏视频（1080×1920，30fps，每卡停留 3 秒，
带离线合成的英语+中文配音）。

数据唯一来源是 `assets/data.js` 里的一个 `DATA` 数组——改数据即改视频。视频由竖屏场景页
`vertical.html` 逐帧渲染而来；它是**渲染中间产物**，不交付给用户。本技能**不生成点读网页**
（`index.html`），模板里若残留该文件，忽略或删掉即可，不要交付。

**主题不限、语言不限**：词表由用户提供或共同商定（常见主题：四季天气、昆虫、饮品、家电、
食物味道、医院、太阳系、动物园、学校……）。不凑数：用户说多少就做多少，4～14 张是常见甜点区。
做其他语言时只改 `data.js` 的例句与配音参数。

## When to use

用户说"做单词卡视频 / 做成抖音竖屏视频 / 做个 XX 主题的单词视频 / 儿童单词视频"，或给一张
设计参考图要求按图实现。用户要"背单词网页 / 点读卡片网页"时**不适用**——本技能只做视频。

## Dependencies（先自检，缺什么装什么）

```bash
python3 -c "import numpy,scipy,PIL" && ffmpeg -version | head -1 \
  && python3 -c "import edge_tts; print('edge-tts ok')" \
  && node --version
# macOS 专用离线配音回退（可选）：
say -v Samantha -o /tmp/_say_check.aiff "ok"
```

- **playwright-core**（逐帧捕获/验证用）：在本技能目录执行
  `npm install playwright-core --prefix <本技能目录>`，脚本会用 `_pw.cjs` 自动在
  脚本目录/工作目录向上找 `node_modules`；或 `NODE_PATH=<node_modules目录> node ...`。
- **Chrome/Chromium**：渲染脚本默认用 macOS 的
  `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`，
  其他平台/路径用 `--chrome <可执行文件路径>` 覆盖（Linux 传 chromium 即可）。
- **edge-tts** 走网络（微软神经语音）；无网或非 macOS 时退回 `build_audio.py`（macOS `say`，
  时间轴一致，音色降一档）。`say` 自检要写到真实文件，`-o /dev/null` 会误报。
- **生图有两条路线，走之前必须先问用户**（见工作流第 3 步）：云端 ImageGen，或**本地 Draw Things**
  （macOS Apple Silicon，App 内置 HTTP API，离线、免费、无需 key）。用 Draw Things 需先在 App 里
  开启 API Server（Settings → Advanced → API Server：Server Online=ON / Protocol=HTTP /
  TLS=OFF / IP=127.0.0.1），生图期间 App 必须保持打开。检测：`python3 scripts/draw_things_gen.py --check`。

## 默认假设（用户没反对就照做，交付时一句话说明）

- 卡片数 24（4 列 × 6 行）或用户指定；字段：单词 / IPA / 中文 / 英文例句 / 中文译文 / 插图。
- 插图两条路线（见 `references/art-pipeline.md` 与 `references/photo-tile-variant.md`）：
  1. **写实产品摄影风 + 白底抠图**（默认）：无缝纯白背景、柔光、无投影，2×2 网格批量生成后
     切片为透明 WebP（512 画布，44px 内边距）——适合**实体物品**（玩具、昆虫、水果）。
  2. **全幅实景照片 tile**：适合**自然现象、场景、饮品、电器**等白底抠不出来的词
     （白云贴白底会消失、彩虹拱会困白、雾雨雷没有实体）。模板改 3 处 CSS 即可，见变体文档。
- 中国用户默认**中国样式**：场景/人物类图直接在提示词里写中国场景与亚洲面孔
  （医院、学校、食堂等），避免生成西式场景后返工。车辆/瓶身类生成物常带乱码小字和假车牌，
  生成后放大检查，用邻近区域克隆修补（PIL 即可）。
- 视觉：白卡 + 3px 黑描边 + 主色投影底块，单词压在彩色笔刷高亮上，中文加粗；每张卡按索引
  循环换主色（红/橙/青/蓝/紫），进度条同步换色。
- **片头不出现单词数量**：标题只写主题，品牌条不写数量，进度计数在片头整段隐藏，片尾也不报数。
- **片头固定口号**：大字两行「每天一分钟 / 开口学英语」分四拍升入，主题徽章「今日主题 · XX」压在顶上，
  口播由 `--intro-text` 传入（INTRO 4.4s）。品牌条整条视频常驻同一句口号，每帧都在强化记忆点。
- **片尾账号 CTA 动效**（OUTRO 7.4s，不写期数）：打卡徽章 → 头像弹入（彩色光环旋转 + 高光扫过）→
  @喜悦学英语 → 「一起开口读英语」→ 点赞 / 收藏 / 关注 三枚抖音样式按钮依次弹入后轻浮动。
  头像放 `assets/img/account-avatar.png`（方图即可，圆形裁切 + 白边）；换账号名/口号只改
  `vertical.html` 的 `acc-name`/`acc-slogan` 文案与音频 outro 文本。
- 视频节奏：每张卡 3.0 秒；配音 = 单词 + 中文，**例句只上屏不朗读**（3 秒读不完，见下）。
- 配音：Edge 神经语音（`en-US-JennyNeural` + `zh-CN-XiaoxiaoNeural`，英文 -8%、中文 -4% 语速），
  无网时退回 `build_audio.py`（`say`），时间轴完全一致。
- 字体自托管（模板内已带 `nunito-var.woff2`），避免首帧字体回退。

用户要 5 秒/卡或要朗读例句时，改 `vertical.html` 的 `DWELL` 并给 `build_audio.py` 传同样的
`--dwell`，其余时长与帧数自动跟随。

## 工作流

**0. 依赖自检**（见上 Dependencies）。

**1. 起项目** — 复制模板，命名 `<主题>-cards/`：

```bash
cp -R assets/app-template/. <项目目录>/
```

只需要 `vertical.html` 和 `assets/`（data.js / fonts / img）。模板里的 `index.html` 是旧版点读页，
本技能不生成、不交付，删掉或忽略。**不要清空 `assets/img/` 里的 `account-avatar.png`**（片尾头像）。

**2. 写数据** — 用用户的词表重写 `assets/data.js`（字段照模板抄）：

```js
const DATA = [ { name:'teddy bear', ipa:'/ˈtedi ber/', zh:'泰迪熊',
                 example:'She hugs her teddy bear every night.',
                 exampleZh:'她每晚都抱着她的泰迪熊。', img:'assets/img/teddy-bear.webp' }, ... ];
```

IPA 用真音标字符（ˈ ˌ ə ɒ ː），别用拼音式重音；音标跟配音口音一致更自然（模板惯例是美音）。
`img` 的 slug 要和 `name` 对齐，切片时无需映射表。
分组主题（如"四季 + 天气"）把组名本身做成第一张卡：seasons 开头、weather 开头。

模板的可见文案是玩具主题的，换主题时连文案一起改。**只需改 `vertical.html` 一处**（`<title>`、
品牌区、舞台卡默认内容、片头 chips/kicker、count）。**建议**：把主题文案集中成一次带断言的
Python 替换（找不到就报错，防止静默漏改）。

**3. 生成插图** — **先问用户选哪条生图路线，别默认**：

> "插图用哪种方式生成？① 本地 Draw Things（离线免费，需 App 开着并开启 API Server）
> ② 云端 ImageGen（需联网、按张计费）"

- **选 Draw Things**（本地路线，详见 `references/draw-things.md`）：
  1. 先 `python3 scripts/draw_things_gen.py --check` 探活；不通就提示用户在 App 里开 API Server，
     别往下走。
  2. 按 `references/art-pipeline.md` 的 2×2 提示词模板写 manifest（`defaults` + `grids`，
     每张卡一个 `prompt` 或四个 `quadrants`），`steps`/`cfg` 按当前加载的模型来
     （FLUX schnell：steps=4、cfg=1.0；SDXL/SD1.5：steps≈25、cfg≈7）。模型由 App 当前加载的
     决定，请求里改不了——先问用户或用 `--check` 输出确认。
  3. 批量生成网格 PNG：`python3 scripts/draw_things_gen.py --manifest grids.json --out /tmp/dtgrids`。
     2×2 网格图直接进下一步切片；**Draw Things 输出没有 ImageGen 水印，别裁底部**。
  4. 切片：`python3 scripts/slice_grid.py --grid /tmp/dtgrids/<grid>.png --names ... --out assets/img`
     （或先用现有 `slice_grid.py --manifest` 把网格登记好）。
- **选 ImageGen**（云端路线，默认）：详见 `references/art-pipeline.md`（白底抠图路线）与
  `references/photo-tile-variant.md`（全幅照片路线）。生成后统一：裁掉右下角生成器水印
  （通常裁底部 60–64px 即可）→ WebP q88 入 `assets/img/`。批量接口常见限流（HTTP 429）：自动重试，
  仍失败的任务**逐个补跑**，并复查 `batch_result.json` 的 success 标志，别只看日志尾部。

两条路线最后都要：联络表（contact sheet）肉眼过一遍风格一致性与生成伪影，再往下走。
**本地 Draw Things 生图完成后照常回到第 4 步验证场景，再走第 5–8 步渲染视频**——生图方式不影响
后续流程，数据唯一来源始终是 `assets/data.js`。

**4. 验证竖屏场景** — 必须走 HTTP（`file://` 会让字体与截图检查失真）。用 `--video-only`
只跑竖屏场景检查，不需要 `index.html`：

```bash
python3 -m http.server 4317 --bind 127.0.0.1
node scripts/verify_app.cjs --vertical http://127.0.0.1:4317/vertical.html \
  --video-only --expect <卡片数>
```

5 项检查（图片解码、`SCENE.TOTAL`、全时间轴 NaN 扫描、卡片落位、横向溢出）。**全绿再往下做**，
否则视频里会复刻同样的缺陷。竖屏场景契约见 `references/vertical-video.md`。

**5. 预览竖屏帧** — 先看 2–5 帧，别急着全量捕获：

```bash
node scripts/render_frames.cjs --url http://127.0.0.1:4317/vertical.html \
  --out /tmp/vcheck --preview 1.4,3.9,5.2,40,80
```

**6. 配音** — Edge 神经语音（默认），逐卡给出占位表；有告警说明该卡在当前 `--dwell` 下放不下：

```bash
python3 scripts/build_audio_neural.py --data <项目>/assets/data.js --out /tmp/track.wav \
  --intro-text "每天一分钟，开口学英语。" \
  --outro-text "<主题>单词，全部打卡。关注喜悦学英语，一起开口读英语。"
```

换音色用 `--en-voice` / `--zh-voice`（`edge-tts --list-voices` 可查）；语速用 `--en-rate -8%`。
无网络时退回离线方案：`python3 scripts/build_audio.py --data ... --out /tmp/track.wav --outro-text "..."`。
脚本会报出配音实际结束点和剩余视觉留白，留白不足 0.6 秒会告警——收尾句宁可短，也别贴着片尾。

**7. 全量捕获 + 编码**（24 卡 ≈ 2 分钟捕获；视频约 80 秒 / 18MB）：

```bash
node scripts/render_frames.cjs --url http://127.0.0.1:4317/vertical.html \
  --out /tmp/frames --fps 30 --size 1080x1920 --q 92
bash scripts/encode.sh /tmp/frames /tmp/track.wav "<主题>单词卡-抖音竖屏-1080x1920.mp4" 30 1080x1920
```

**8. 验收** — `encode.sh` 末尾会打印 `ffprobe` 结果，逐项确认：`yuv420p(tv, bt709/unknown/unknown)`、
`h264 (High)`、30 fps、`aac LC 44100 Hz stereo`、`Duration` 与 `SCENE.TOTAL` 一致。再抽看片头、
第 1 卡、中段、片尾 4 帧确认文字无 NaN/空位、长词不截断。视频规格与布局安全区见
`references/vertical-video.md`。

## 踩坑清单（每条都真实付出过代价）

- 主卡长词（>820px）由 `fitWord()` 自动缩放，别删这个函数；片尾影集条长词也靠它兜底。
- 生成器水印固定在右下角，白底抠图会把它留在切片里；全幅图直接裁底部 64px。
- 中国样式：文化场景词直接用中国场景提示词；车辆/瓶子类必有乱码小字，生成后放大检查 + 克隆修补。
- 换词表不清空 `assets/img/` 会留僵尸图；替换主题文案不带断言会静默漏改。
- 清空 `assets/img/` 时**保留 `account-avatar.png`**，删了它片尾头像就是一张破图。
- 预览帧抽在 0.1s 会看到卡片起飞半程——这是动画不是 bug，抽 t=卡内 1.6s 判断排版。
- 单线程 `http.server` 并发捕获偶发 `ERR_CONNECTION_RESET`：重抽即可，不是图片坏。

## 交付时要说明的事

配音只读单词和中文、例句未朗读（3 秒装不下，需 4.5–5 秒/卡，代价是片长翻倍）；无 BGM（本地无
授权音源，可另找并压低 12dB）；配音是 Edge 神经语音（需联网，离线时退回系统 `say`）。这三点是
产品取舍，主动讲清楚，别等用户问。**交付物只有 MP4，不交付网页。**

## Resources

- `assets/app-template/` — 竖屏渲染模板（vertical.html + assets/data.js 词表示例 + fonts + 示例图）。
  复制即用；其中的 index.html 为旧版遗留，不使用。
- `references/vertical-video.md` — `seek(t)` 场景契约、时间轴数学、视觉规范、抖音安全区、
  编码参数、音频预算。
- `references/card-app.md` — 历史参考：旧版点读网页的实现要点（本技能不产出网页，仅在需要
  恢复网页功能时查阅）。
- `references/art-pipeline.md` — 白底抠图路线：2×2 提示词模板、硬约束、切片参数、成品质检。
- `references/photo-tile-variant.md` — 全幅照片 tile 路线：改哪 3 处 CSS、主题文案替换配方、
  生成限流/水印/车辆乱码的实战处理。
- `references/draw-things.md` — 本地 Draw Things 路线：开启 API Server、manifest 写法、
  模型/steps/cfg 选择、健康检查与常见坑。
- `scripts/` — `verify_app.cjs`（`--video-only` 竖屏场景检查）`render_frames.cjs`
  `build_audio_neural.py` `build_audio.py` `slice_grid.py` `draw_things_gen.py`（本地生图，
  HTTP 直连 7860）`encode.sh` `_pw.cjs`（依赖解析器）。
- `package.json` — `npm install playwright-core` 用。
