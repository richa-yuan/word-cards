# 本地生图路线：Draw Things（离线、免费、Apple Silicon）

适合已在本机装了 Draw Things、想省云端费用或完全离线跑的场合。它和 ImageGen 路线产出
**同一种 2×2 网格 PNG**，后面 `slice_grid.py` 切片、网页、视频流程完全不变。

## 1. 开启 API Server（一次性）

Draw Things 自带 AUTOMATIC1111 兼容的 HTTP API，但**默认关闭**。App 里操作：

1. 打开 Draw Things（生图期间必须保持打开——App 就是 server，退了 server 就没了）。
2. 左侧齿轮 **Settings → Advanced → API Server**。
3. 四个开关必须这样设，否则 curl 会静默挂住：
   - **Server Online = ON**（绿色）
   - **Protocol = HTTP**（不是 gRPC——最常见的坑）
   - **TLS = OFF**（本地自签证书只会添乱）
   - **IP = 127.0.0.1**（别用默认的 allow all，别暴露到局域网）
4. Bridge Mode 关掉（那是走 Draw Things 云中转，跟离线目的相反）。
5. 加载一个生图模型（API 用的是 App **当前加载**的模型，请求里没法指定）。

探活（注意是真实小图生成，不是查端点）：

```bash
python3 scripts/draw_things_gen.py --check
# PASS  Draw Things replied in 1.3s; model is loaded and warm.
```

## 2. 两个 Draw Things 特有的坑

- **没有 `/sdapi/v1/sd-models`**：查模型列表会 404。别拿标准 WebUI 的探活法，会误判成服务没开。
  本脚本 `--check` 用一次 64×64 / steps=1 的真实生成探活，能拿到图就说明服务+模型都就绪。
- **模型由 App 决定**：FLUX.1-schnell 用 `steps=4, cfg=1.0`（cfg 调高会过曝、发色焦）；
  SD1.5 / SDXL 用 `steps≈25, cfg≈7`。选错参数出来的图不是噪声就是过饱和。不确定就问用户
  当前加载的是什么模型，或先用 `--check` 后手动画一张确认风格。
- **宽高必须是 64 的倍数**：1024×1024 最稳（切片后每象限 512，正好等于 `slice_grid.py` 的
  `--canvas`，不重采样）。
- **首次生成慢**：App 启动后第一次调用要 30–60s 预热。脚本默认 180s 超时 + 3 次退避重试，
  足够扛住。

## 3. 批量生成（推荐）

把 `art-pipeline.md` 的提示词模板填进 manifest。每张卡一个网格，两种写法：

```json
{
  "defaults": {
    "steps": 4,
    "cfg_scale": 1.0,
    "size": "1024x1024",
    "negative_prompt": "text, label, logo, watermark, signature, hands, props, shadows"
  },
  "grids": [
    {
      "out": "grid1.png",
      "prompt": "A 2x2 grid of four separate photorealistic studio product photographs, ... seamless pure white background ... top-left [a soft brown plush teddy bear]; top-right [wooden building blocks]; bottom-left [a blue toy train]; bottom-right [a doll in yellow]. Each centered in its own quadrant, generous white margins, nothing crossing center lines, identical softbox lighting, no text."
    },
    {
      "out": "grid2.png",
      "quadrants": [
        "photorealistic product photo of a red kite, pure white background, centered",
        "photorealistic product photo of a brown ball, pure white background, centered",
        "photorealistic product photo of a robot toy, pure white background, centered",
        "photorealistic product photo of a wooden puzzle, pure white background, centered"
      ]
    }
  ]
}
```

- `prompt`：一条提示词让模型画整张 2×2（省调用、风格最统一；要求模型听得懂"quadrant"）。
- `quadrants`：分别生成四张再合成 2×2（模型不擅长分格时用，稳但调用多 4 倍）。
  每张临时象限图用完即删。

```bash
python3 scripts/draw_things_gen.py --manifest grids.json --out /tmp/dtgrids
# PASS / ok  grid1.png ... / ok grid2.png composed from 4 quadrants
```

单张快速试：

```bash
python3 scripts/draw_things_gen.py \
  --prompt "A 2x2 grid of ... " --out /tmp/grid1.png \
  --steps 4 --cfg 1.0 --size 1024x1024
```

可选参数：`--host` / `--port`（默认 127.0.0.1:7860）、`--timeout`（默认 180）、
`--retries` / `--retry-wait`、`--seed`（≥0 固定种子可复现，默认 -1 随机）、`--negative`。

## 4. 切片（和云端路线完全相同）

**Draw Things 输出没有 ImageGen 那种右下角水印——不要裁底部 60px**，直接切片：

```bash
python3 scripts/slice_grid.py --grid /tmp/dtgrids/grid1.png \
  --names teddy-bear,building-blocks,toy-train,doll --out assets/img
# 或一次性登记多个网格
python3 scripts/slice_grid.py --manifest /tmp/slice-manifest.json --out assets/img
```

后面照旧走：联络表肉眼过一遍 → 第 4 步验证网页 → 配音 → 全量捕获 → 编码。

## 5. 排障

| 症状 | 原因 | 处理 |
|---|---|---|
| `Connection refused` / `Errno 61` | App 没开，或 Server Online 没打开 | 打开 App 并开 API Server |
| `--check` 挂住无响应 | Protocol 选了 gRPC | Settings 里改回 HTTP |
| `/sd-models` 404 | Draw Things 没实现这个端点 | 正常，用 `--check` 代替 |
| 图是噪声 / 不像提示词 | steps=1~2 | schnell 用 4，SDXL 用 25 |
| 颜色焦、过饱和 | cfg 对 schnell 太高 | schnell 用 cfg=1.0 |
| `width or height not divisible by 64` | 尺寸没凑 64 | 用 1024×1024 或 640×640 |
| App 生成时卡死 | 生成途中切了模型 | 等当前任务完成再换模型 |
