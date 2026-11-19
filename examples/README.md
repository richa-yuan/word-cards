# 成品示例

两个用本技能生成的完整成品，均为 **12 词 / 动漫全幅风格**。每个目录自成一体，
含网页三件套（`index.html`、`vertical.html`、`assets/data.js`）、全部插画与字体，
可直接本地跑通；`preview-*.png` 是成片抽帧，用于快速看效果。

| 示例 | 主题 | 词表 |
|---|---|---|
| `travel-cards/` | 旅行 | airplane, suitcase, passport, hotel, beach, camera, train, map, ticket, backpack, compass, souvenir |
| `airport-cards/` | 机场 | airport, terminal, runway, control tower, check-in, security, boarding pass, gate, baggage claim, flight attendant, duty-free, departure board |

## 本地预览

```bash
cd examples/travel-cards          # 或 airport-cards
python3 -m http.server 4317 --bind 127.0.0.1
# 打开 http://127.0.0.1:4317/index.html
```

网页发音走浏览器本地 `speechSynthesis`，无需联网。

## 重新生成竖屏视频

示例目录刻意不含 MP4（两个视频约 30MB）。用仓库根目录的脚本从词表重新渲染：

```bash
cd examples/travel-cards
python3 -m http.server 4317 --bind 127.0.0.1 &   # 后台起服务
python3 ../../scripts/build_audio_neural.py --data assets/data.js \
  --out /tmp/track.wav --intro-text "每天一分钟，开口学英语。" \
  --outro-text "旅行单词，全部打卡。关注喜悦学英语，一起开口读英语。"
node ../../scripts/render_frames.cjs --url http://127.0.0.1:4317/vertical.html \
  --out /tmp/frames --fps 30 --size 1080x1920 --q 92
bash ../../scripts/encode.sh /tmp/frames /tmp/track.wav "demo.mp4" 30 1080x1920
```

机场示例把 `--outro-text` 里的「旅行」换成「机场」即可。详细流程见根目录 `SKILL.md`。

## 插画说明

插图由云端 ImageGen 生成（1536×1024 动漫赛璐璐风，逐张生成，裁掉底部 64px 水印后转 WebP q88）。
带文字的物体（登机牌、航班显示屏）会有少量 AI 生成的乱码小字，属生成器常见伪影，不影响主体识别。
换主题时清空 `assets/img/` 再重新生图，但保留 `account-avatar.png`（片尾头像）。
