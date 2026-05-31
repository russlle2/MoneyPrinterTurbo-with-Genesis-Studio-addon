# ComfyUI Setup Guide for Genesis Forge

Setting up ComfyUI unlocks **real AI video generation** in Genesis Forge:
- Text to video via **CogVideoX-5B** (full motion, not just animated images)
- Image to video via **AnimateDiff-Lightning** (real motion from your photos)

Your hardware (RTX 5090, 24GB VRAM) handles all of this comfortably.

---

## Step 1 — Download ComfyUI (Windows Portable)

1. Go to: https://github.com/comfyanonymous/ComfyUI/releases
2. Download the latest **ComfyUI_windows_portable_nvidia.7z**
3. Extract it anywhere, e.g. `C:\ComfyUI\`

---

## Step 2 — First Launch

1. Open the extracted folder
2. Double-click **`run_nvidia_gpu.bat`**
3. Wait for it to finish installing — a browser tab opens at `http://localhost:8188`
4. If it opened, ComfyUI is working. Close the browser tab (keep the terminal running).

---

## Step 3 — Install the Video Helper Node

ComfyUI needs a custom node to handle video output:

1. In ComfyUI's browser interface, go to **Manager** (top menu) → **Install Custom Nodes**
2. Search for: `ComfyUI-VideoHelperSuite`
3. Click Install → Restart ComfyUI when prompted

Alternatively via command line (in the ComfyUI folder):
```
cd custom_nodes
git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite
cd ..
```

---

## Step 4 — Download CogVideoX-5B (Text to Video)

CogVideoX-5B is ~20GB and produces 6-second 480p clips. Fits in 24GB VRAM.

**Option A — Using ComfyUI Manager:**
1. In ComfyUI browser → Manager → **Model Manager**
2. Search "CogVideoX-5B" → Download

**Option B — Manual download:**
1. Go to: https://huggingface.co/THUDM/CogVideoX-5B
2. Download model files to: `C:\ComfyUI\models\CogVideoX\`

---

## Step 5 — Download AnimateDiff-Lightning (Image to Video)

AnimateDiff-Lightning produces smooth motion from still images.

1. Go to: https://huggingface.co/ByteDance/AnimateDiff-Lightning
2. Download `animatediff_lightning_8step_diffusers.safetensors`
3. Place it in: `C:\ComfyUI\models\animatediff_models\`

Also needed — a base SD 1.5 checkpoint (if you don't have one):
1. Download `v1-5-pruned-emaonly.safetensors` from Hugging Face
2. Place it in: `C:\ComfyUI\models\checkpoints\`

---

## Step 6 — Run ComfyUI before using Genesis Forge

Every time you want real AI video generation:

1. Open `C:\ComfyUI\run_nvidia_gpu.bat`
2. Wait until you see: `"To see the GUI go to: http://127.0.0.1:8188"`
3. Genesis Forge automatically detects ComfyUI and switches to real AI video

You'll see the status badge in Genesis Forge change from:
> ComfyUI offline — using Pollinations FLUX + animation

to:
> ComfyUI connected — real AI video enabled

---

## What works without ComfyUI

Even without ComfyUI, Genesis Forge generates real videos using:
- **Pollinations.ai** (free, internet-based) — generates high-quality FLUX images for each scene
- **Ken Burns / zoom / pan animations** — smooth motion on every image
- **Full MP4 output** with transitions and fades

The result looks great. ComfyUI just makes the motion more organic and fluid.

---

## Troubleshooting

**ComfyUI won't start:**
- Make sure you ran `run_nvidia_gpu.bat`, not `run_cpu.bat`
- Check that port 8188 isn't used by another app: `netstat -an | findstr 8188`

**Out of VRAM error:**
- Close other GPU apps (games, LM Studio, etc.) before generating video
- CogVideoX-5B needs ~18GB VRAM for generation

**Genesis Forge still shows "offline":**
- ComfyUI must be running *before* you click Generate
- Refresh the Genesis Forge page after starting ComfyUI
