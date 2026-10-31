# 插图路线 B：全幅实景照片 tile（实战变体）

白底抠图（art-pipeline.md）只适合实体物品。**自然现象、场景、饮品、电器**类词
（sunny、foggy、rainbow、canteen、cola、hospital……）抠不出来：白云贴白底即消失、
彩虹拱会把白困在里面、雾雨雷没有实体。此时改用**全幅照片 tile**：卡片图像窗直接放
圆角写实照片（object-fit: cover）。这套变体在四季天气、昆虫、饮品、家电、学校、
医院、动物园、太阳系八个项目上验证过。

## 1. 模板改 3 处 CSS

### index.html

```css
/* .thumb img：contain → cover，去掉 drop-shadow（照片自带背景，投影会假） */
.thumb img{ object-fit:cover; /* 删掉 filter:drop-shadow(...) */ }

/* .art-panel img（弹窗）：cover + 圆角 + 实体阴影 */
.art-panel img{ width:min(84%,420px); object-fit:cover;
  border-radius:22px; box-shadow:0 24px 44px -26px rgba(50,78,40,.45); }
```

### vertical.html

```css
/* .art / .art img：图像窗放大成 660×372 圆角照片（卡片总高 846px 的余量内） */
.art{ height:380px; }
.art img{ width:660px; height:372px; object-fit:cover;
  border-radius:24px; border:3px solid var(--ink); }

/* .mini img：影集条小卡同步改照片 tile */
.mini img{ width:152px; height:104px; object-fit:cover; border-radius:14px; }
```

图片源用 **1344×768**（横幅，比例 1.75 ≈ 图像窗 1.774），cover 几乎不裁；
正方形源会裁掉上下 44%。格子缩略图（1:1）与弹窗（1:1）从横幅裁两侧，无碍。

## 2. 提示词系统

每张图**单独生成**（不再用 2×2 网格——场景图会串界）。统一风格尾缀：

> 真实摄影风格，超高清细节，主体位于画面中央，画面内无任何文字、水印、边框、品牌标志。

要点：

- **中国样式**：文化场景词直接写中国场景与亚洲面孔（"中国医院门诊大厅、圆形导诊台、
  蓝色候诊椅"、"蓝白色校服"、"不锈钢餐盘"）。西式场景生成了也得返工。
- **人物**：特写面部有 AI 畸形风险。半身像（医生/老师/护士）通常没问题；人群、病人、
  学生用**背影/后脑勺**构图，一句话规避。
- **车辆/瓶子/带字面物体**：必然出现乱码小字和假车牌。提示词写明
  "车身完全无任何文字、字母、数字、车牌"；生成后**放大车头/车身逐块检查**，
  残留的用 PIL 克隆修补：

```python
from PIL import Image, ImageFilter, ImageDraw
im = Image.open("raw.png").convert("RGB")
def clone_patch(im, src_box, dst_box, feather=3):
    w, h = dst_box[2]-dst_box[0], dst_box[3]-dst_box[1]
    patch = im.crop(src_box).resize((w, h))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rectangle([feather, feather, w-feather, h-feather], fill=255)
    im.paste(patch, (dst_box[:2]), mask.filter(ImageFilter.GaussianBlur(feather)))
# 从紧邻的干净区域取样盖过去，纯色平面（车身、天空、墙面）效果最好
clone_patch(im, (430,420,540,460), (310,420,425,460), feather=2)
im.save("raw.png")
```

- **水印**：CogView 等生成器在右下角盖"AI生成"角标，白底抠图路线会残留到切片里，
  全幅图统一 `im.crop((0, 0, w, h-64))` 裁掉底部 64px。
- **风格锚定**：联络表（contact sheet）拼一张缩略图肉眼过一遍——单张看不出的风格漂移
  一眼就能看出；不一致的单独重生成。

## 3. 主题文案替换配方

两页各十几处主题文案，用**带断言的 Python 替换**（找不到即报错，防止静默漏改）：

```python
def rep(path, pairs):
    s = io.open(path, encoding='utf-8').read()
    for a, b in pairs:
        assert a in s, f"{path}: NOT FOUND: {a[:60]}"
        s = s.replace(a, b)
    io.open(path, 'w', encoding='utf-8').write(s)
```

要换的位置（以旧主题值 → 新主题值逐对列出）：

- index.html：`<title>`、eyebrow、`<h1>`、badge 数字、lede、shelf aria-label、
  shelf-meta 数字、colophon、弹窗默认内容（img/word/ipa/zh/example/exampleZh/index/speak aria）、
  art-caption。
- vertical.html：`<title>`、brand h1 与 sub、舞台卡默认内容（word/ipa/zh/exEn/exZh）、
  片头 big/desc/chips、count `00 / N`、footer。

注意 perl 多字节替换在 macOS 上易炸（Unrecognized character），直接用 Python；
新项目从上一个项目复制骨架时，上一个项目已踩过的补丁（如片尾板缩字号）会自动带上。

## 4. 已验证的片尾板补丁（模板已内置）

```js
$('endBoard').innerHTML = DATA.map(d =>
  `<span${d.name.length > 8 ? ' style="font-size:16px"' : ''}>${d.name}</span>`).join('');
```

单词板单元格定宽 178px，超过 8 字符（washing machine / solar system / stethoscope）会截断。
复制旧项目骨架时确认这行补丁还在。

## 5. 限流与失败任务

批量接口（如 CogView flash）高频触发 HTTP 429：workers 降到 2、脚本自动重试（10s/20s 退避）。
批跑完**必须核对 `batch_result.json` 的 success 标志**——日志被 `tail` 截断时会漏看失败任务
（曾漏掉 panda / school 两张）。失败任务逐个补跑，缺图跑 verify_app 会直接红。
