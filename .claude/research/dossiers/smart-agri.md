---
title: Smart Agri / Plant Disease Detection
type: project-dossier
path: /Users/tejas/Documents/Smart Agri
deployed: https://pifive.marutsut.me/docs
tags: [tensorflow, keras, efficientnet, mobilenet, cnn, onnx, fastapi, docker, raspberry-pi-5, cloudflare-tunnel]
status: COMPLETE — merged from spec-analyst + code-analyst reports + live API verification, 2026-06-12
---

# Smart Agriculture / Plant Disease Detection — Full Dossier

> [!note] Source locations (the project is SCATTERED; `/Users/tejas/Documents/Smart Agri` holds docs only)
> - `/Users/tejas/Documents/Smart Agri/` — report.docx, Smart Agriculture_PPT.pdf (98 MB), poster, easyExplanation pdf, flowChart.jpeg. NO CODE.
> - `/Users/tejas/Downloads/Smart-Agri/` — final reports, tutorial video, `models/OneDrive_2026-05-14.zip` (1.4 GB trained models).
> - `/Users/tejas/Downloads/agri-tanzania-documentation/smart_agri_notebooks/` — `retrain_efficientnetb0_fast.ipynb`, `retrain_proper_split.ipynb`, `main.tex` (IEEE paper draft), `STATUS.md` (handoff; full project lived at `~/Documents/projects/agri` on the Pi).
> - `/Users/tejas/Documents/pi-backup/120526/.../04-docker/image-smart_agri.tar` (1.9 GB) + inspect JSON — the deployed Docker image as-shipped.

## TL;DR
A deployment-first plant-disease classifier: 15 PlantVillage classes (pepper/potato/tomato, 20,638 images) served live from a [[raspberry-pi-5]] at pifive.marutsut.me via [[fastapi]] + [[docker]] + [[cloudflare-tunnel]], with **10 caller-selectable [[onnx]] models** on one endpoint. Two narratives exist: the 2024 college project (flagship [[efficientnet]]B0, 99.95% accuracy) and a 2026 IEEE paper draft that systematically benchmarks 8 CNN families on the Pi and shows **MobileNetV3-Small is the true edge winner** (99.95% acc, 1.53M params, 8 ms/image, ~82 MB RAM) — with honest findings on optimizer sensitivity, int8 quantization, and a data-leakage fix via seeded multi-seed retraining.

## Problem & Purpose
Farmers rely on manual leaf inspection; prior high-accuracy models (100M+ params) are undeployable on cheap phones/edge hardware. Goal: lightweight models with top accuracy, deployed free-to-access on commodity hardware. The IEEE paper's framing: "the practical bottleneck is not accuracy but deployability" — compare architectures on parameters/memory/latency, not accuracy alone.

## Architecture
- **Training side:** [[tensorflow]]/[[keras]] (tf.data pipeline: 224×224 RGB, batch 64, shuffle 2048 seeded, AUTOTUNE prefetch/cache; augmentation = RandomFlip-horizontal, RandomRotation 0.1, RandomZoom 0.1, train-only). College training on RTX A6000 (80 GB) / 64 GB RAM workstation; retrains on Kaggle free T4.
- **Serving side:** Keras → [[onnx]] via tf2onnx (input spec `(None,224,224,3)` float32) → ONNX Runtime CPU on Pi 5 → FastAPI (`deployment.fast_dep:app`, uvicorn, port 8000) in a multi-arch (AMD64+ARM64) Docker image → Cloudflare Tunnel (no inbound ports).

## Complete Tech Stack

| Tech | Where used | Evidence |
|------|------------|----------|
| [[tensorflow]] 2.x + [[keras]] | training, keras.applications backbones | retrain notebooks cells 1–8 |
| [[scikit-learn]] | stratified splits, classification_report, confusion matrices | retrain notebooks |
| tf2onnx + [[onnx]] Runtime | export + Pi inference | notebook cell 12; deployed image |
| [[fastapi]] + uvicorn | inference API | Docker inspect: entrypoint `uvicorn deployment.fast_dep:app --host 0.0.0.0 --port 8000` |
| [[docker]] (multi-arch) | image `tejaskashyap07/smart_agri` (1.99 GB, Python 3.9.25 base, restart=always) | `image-smart_agri.tar`, inspect JSON |
| [[cloudflare-tunnel]] | systemd `cloudflared.service`, tunnel "pi5", user tejasnewrasp, RestartSec=5 | pi-backup systemd units; ports-listening.txt |
| [[matplotlib]] + seaborn | training curves, confusion-matrix heatmaps | notebook cell 10 |

## Models & Training Detail

### IEEE paper benchmark (8 families, trained FROM SCRATCH for fair comparison; Adam, batch 64, categorical cross-entropy, 100–300 epoch budgets)

| Model | Accuracy | Loss | Params |
|-------|----------|------|--------|
| MobileNetV3-Small | **99.95%** | 0.0006 | **1.53M** |
| MobileNetV2 | 99.95% | 0.0031 | 2.23M |
| EfficientNet-B0 | 99.95% | **0.0005** | 4.01M |
| DenseNet-169 (k=48) | 99.90% | 0.0030 | 30.50M |
| DenseNet-169 (k=32) | 99.90% | 0.0136 | 14.32M |
| ResNet-101 (Adam) | 99.76% | 0.0100 | 45.20M |
| Inception-v1 | 99.76% | 0.0156 | 12.41M |
| MobileNetV3-Large | 88.35% | 0.7217 | 4.21M |
| VGG-16 (baseline) | 78.70% | 1.2372 | 165.80M |

- **Optimizer-sensitivity finding:** ResNet-101 converges only with Adam; RMSprop and SGD fail (near chance) at the same budget — reported as a reproducibility lesson.
- **VGG-16 honest baseline:** did not converge competitively (78.70%).

### Leakage fix + statistical rigor (retrain notebooks, 2026)
- Original college split was **non-deterministic** (leakage risk, admitted in STATUS.md). Fix: seeded stratified disjoint 80/10/10 (SEED=42), test set never touched in training.
- `retrain_efficientnetb0_fast.ipynb`: ImageNet transfer learning, two-phase — frozen base (Adam 1e-3, 10 epochs, EarlyStopping p=3) → full fine-tune (Adam 1e-5, 25 epochs, p=4).
- `retrain_proper_split.ipynb`: **multi-seed (42, 1337, 2024)** training of MobileNetV3-Small + EfficientNet-B0, mean±std reporting.
- Full-dataset eval (`scripts/eval_winners.py` on all 20,639 images): MobileNetV3-Small **99.67%** — slightly below the 99.95% test-set figure, as expected.

## Dataset Detail
PlantVillage subset, **20,638 images, 15 classes** (Pepper bell: bacterial spot/healthy; Potato: early blight/late blight/healthy; Tomato: 10 classes incl. bacterial spot, early/late blight, leaf mold, septoria, spider mites, target spot, YLCV, mosaic virus, healthy). 224×224 RGB, one-hot labels, 80/10/10 stratified. Known dataset caveat (cited in paper): uniform backgrounds → field-condition generalization gap (Noyan 2022).

## Inference Server

### VERIFIED LIVE 2026-06-12 (curl against https://pifive.marutsut.me/openapi.json — HTTP 200; plain WebFetch got 403 → Cloudflare bot protection in front)
- [[fastapi]] app, OpenAPI 3.1.0; **single endpoint `POST /predict/{model_name}`** — multipart upload, field `file`; description: "…only 15 Plant Village classes from which we can predict".
- `model_name` validated against **10 live models**: `dense169_k64`, `dense169_k32`, `mobilenetv1`, `mobilenetv2`, `mobilenetv3small`, `mobilenetv3large`, `inceptionv1`, `resnet101`, `efficientnetb0`, `vgg16`. `/docs` (Swagger) live.

### VERIFIED LIVE PREDICTIONS (2026-06-12, real bell-pepper-healthy image POSTed from Mac)
- Response: `{"predicted_class": "Pepper__bell___healthy", "confidence": 0.99998}`; all 3 tested models correct (efficientnetb0 0.99998, mobilenetv3small 1.0, vgg16 0.999997).
- End-to-end latency Mac→Tunnel→Pi: cold 1.0–4.7s, warm 0.6–1.0s. The "<150 ms" claim is **on-device inference only** (MobileNetV3-Small 8 ms; VGG-16 720 ms) — keep the distinction straight in interviews.

## Metrics & Hard Numbers (Pi 5: 4-core Cortex-A76, 8 GB)

| Model | Size (MB) | Latency (ms) | int8 MB | int8 ms |
|-------|-----------|--------------|---------|---------|
| MobileNetV3-Small | 6.18 | **8.0** | 1.78 | 30.9 |
| MobileNetV2 | 8.95 | 18.2 | 2.45 | 106.4 |
| MobileNetV1 | 12.87 | 25.7 | 3.33 | 100.5 |
| EfficientNet-B0 | 16.11 | 45.4 | 4.37 | 159.4 |
| MobileNetV3-Large | 16.92 | 21.4 | 4.52 | 86.6 |
| Inception-v1 | 49.67 | 63.5 | 12.58 | 105.3 |
| DenseNet-169 (k=32) | 57.45 | 152.4 | 15.67 | 257.6 |
| DenseNet-169 (k=48) | 122.21 | 285.9 | 32.32 | 529.2 |
| ResNet-101 | 180.86 | 266.9 | 45.56 | 440.7 |
| VGG-16 | 663.19 | 720.4 | 165.92 | 1274.2 |

- Peak RAM: MobileNetV3-Small ~82 MB; EfficientNet-B0 ~111 MB; VGG-16 ~1.3 GB (16×).
- **Int8 paradox:** dynamic int8 = 3.5–4× smaller on disk but *slower* on this ARM ONNX Runtime build (no vectorized int8 kernels) — honest system-limitation finding.
- MobileNetV3-Small vs VGG-16: ~108× smaller, ~90× faster, equal-or-better accuracy.

## Deployment & Infra
Docker image `tejaskashyap07/smart_agri` (1.99 GB, Python 3.9.25, port 8000, restart=always, bridge network) on Pi 5; cloudflared systemd service (tunnel `pi5`, LimitNOFILE 65536); ports snapshot shows 8000 (docker-proxy) + 8001/8002 (other uvicorns) + cloudflared UDP listeners. Public URL https://pifive.marutsut.me/docs.

## Spec-Driven Development Evidence
STATUS.md is a session-handoff doc (done / todo / how-to-recover via tmux); PROJECT_CONTEXT.md referenced as canonical handoff; IEEE `main.tex` in IEEEtran format with figures pre-generated (`paper/figures/` accuracy-vs-params, latency-vs-params, confusion matrices); `.claude/` present. The 2026 retrain work is explicitly structured as: criticize own earlier methodology → fix split → multi-seed → full-dataset eval → paper.

## Resume Raw Material
1. Deployed a live multi-model plant-disease inference API on a [[raspberry-pi-5]] — 10 ONNX models behind one FastAPI endpoint, Docker multi-arch, Cloudflare Tunnel, public Swagger UI [verified-live]
2. Benchmarked 8 CNN families (VGG-16 → MobileNetV3) trained from scratch under one pipeline on 20,638 PlantVillage images / 15 classes [verified-in-paper+notebooks]
3. Identified the edge-efficiency frontier: MobileNetV3-Small at 99.95% accuracy with 1.53M params, 8 ms/image and ~82 MB RAM on Pi 5 — ~108× smaller and ~90× faster than the VGG-16 baseline at equal-or-better accuracy [verified-in-paper]
4. EfficientNet-B0: 99.95% accuracy, lowest loss (0.0005), AUC ≈ 1.0 [verified; cite 4.01M ONNX-counted params, not the PPT's 5.3M]
5. Exported all models to [[onnx]] (tf2onnx) and measured exact parameter counts from ONNX initializer tensors [verified-in-code]
6. Found and reported the int8 quantization paradox on ARM: 3.5–4× size reduction but slower inference without vectorized int8 kernels [verified-in-paper]
7. Diagnosed and fixed a data-leakage risk in the original pipeline: seeded stratified 80/10/10 split + multi-seed (42/1337/2024) retraining with mean±std reporting [verified-in-notebooks]
8. Demonstrated optimizer sensitivity at depth: ResNet-101 converges with Adam, fails with RMSprop/SGD at equal budget [verified-in-paper]
9. Authored an IEEE-format paper draft: "Lightweight Plant Disease Detection for Edge Deployment: A Comparative Study of CNN Architectures with ONNX Inference on a Raspberry Pi" [verified-on-disk]
10. End-to-end ownership: dataset prep → training (A6000 + Kaggle T4) → ONNX export → containerization → home-server deployment → live verification [verified]

## Interview Depth
- **Why ONNX instead of TF-Serving/TFLite?** Portability + stable CPU runtime on ARM64; exact param counting; one runtime for 10 models.
- **Why is int8 slower on your Pi?** Runtime build lacks optimized int8 kernels — quantization saves storage, not latency, unless the runtime has vectorized int8 ops (XNNPACK/TensorRT).
- **Is 99.95% believable?** On held-out PlantVillage test set, yes — but uniform backgrounds mean field generalization is untested; the original split had leakage risk, which the seeded multi-seed retrain addresses (full-dataset 99.67% for MNv3-Small).
- **Why does MobileNetV3-Large underperform (88.35%) when Small hits 99.95%?** Good probe question — likely training-budget/regularization interaction; be ready to discuss honestly.
- **Latency claims:** 8 ms (on-device, MNv3-Small) vs ~0.6–1.0 s end-to-end through the tunnel — never conflate.

## Honesty Flags
1. **"6 DL models + 4 custom CNNs" (old resume claim) is NOT what the evidence shows** — the artifacts show 8 standard architecture families / 10 deployed ONNX models. No "custom CNN architectures" found in notebooks or the live API. Drop or rephrase that claim.
2. **Param-count discrepancy:** PPT says EfficientNetB0 = 5.3M; ONNX count = 4.01M. Use 4.01M.
3. **92.5% precision / 89.8% recall (memory/old resume) conflicts with paper's 99.95/99.95** — the old numbers may come from a different evaluation; prefer the paper's table, or verify before quoting.
4. **99.95% is test-set on lab-style images;** full-dataset eval gives 99.67% (MNv3-Small); field-condition performance unknown (paper admits via Noyan 2022 citation).
5. **College narrative vs IEEE narrative differ** (flagship-EffB0 vs MNv3-Small-wins). The IEEE version is the defensible one.
6. **Code is not in `Documents/Smart Agri`** — that folder is docs-only; canonical code lived on the Pi (`~/Documents/projects/agri`), with notebooks + paper in Downloads. Consolidation recommended before sharing a repo link.
7. tensorflow-macos/-metal (M1 GPU) appears in memory/known-context but the verified training ran on RTX A6000 + Kaggle T4 — only claim Apple-silicon training if Tejas confirms it happened.
