---
title: Federated Learning (Plant Disease)
type: project-dossier
path: /Users/tejas/Documents/Fedrated Learning
deployed: none
tags: [flower, federated-learning, tensorflow, efficientnet, onnx, non-iid]
---

# Federated Learning — Full Dossier

> Project root: `/Users/tejas/Documents/Fedrated Learning` (note: "Fedrated" misspelled on disk, contains a space — quote in shell). Single git commit (`afd2cd1` — "Federated learning for plant disease detection — code, specs, results, and Claude Code chat transcripts"), built 2026-05-28 → 2026-06-06, frozen for export ~2026-06-11. Not deployed.

## TL;DR

A [[federated-learning]] system built with [[flower]] (flwr 1.30.0) where **2 clients simulate 2 independent farms** training a shared plant-disease classifier ([[efficientnet]] B1, frozen backbone, 2,562-param head) on private, deliberately **non-IID** data — raw images never leave a client; only weights are aggregated by [[fedavg]] / [[fedprox]]. **Headline result: FedProx μ=1.0 on skewed 150:50 non-IID data hit 99.0% global accuracy, beating the centralized baseline (98.8%)**; a balanced-data FedAvg run hit 100% (log-only). Final models exported to [[onnx]] via [[tf2onnx]] and independently re-verified at **98.0%** on fresh images via `demo_results.ipynb` ([[onnxruntime]], no FL stack needed). Strictly **spec-driven**: 12 spec docs in `.claude/specs/`, including a 433-line `flaws.md` ledger — no code written before an approved spec. Same PlantVillage dataset/domain as [[smart-agri]]. Run entirely on a MacBook M1 8GB; Phase 2 (real distributed clients + Raspberry Pi 5 server at marutsut.me) and Phase 3 (packaged client agents) are specced but unbuilt.

## Problem & Purpose (why FL for plant disease)

- **Stated goal** (`.claude/specs/approach.md:5-6`): "Learn Federated Learning hands-on by training EfficientNet on PlantVillage data across simulated and then real distributed clients. **Goal is understanding, not production accuracy.**" It's an explicitly pedagogical project that nonetheless produced rigorous, verified results.
- **Domain framing** (`README.md:3`): two clients "simulate two independent farms. Each client trains on its own private, imbalanced data and never shares raw images — only model weights." FL fits agriculture because farms hold private imagery, have naturally skewed class distributions (one farm sees mostly blight, another mostly healthy crops), and run constrained edge hardware.
- **Privacy contract is taken seriously**: in the catastrophic-forgetting analysis (flaws.md F28), a replay buffer is rejected specifically because "it breaks the FL privacy contract (server holds raw data)."
- **Why constrained-device design**: flaws.md F30 — "FL exists to train on small devices — phones, old PCs, Pi 5. If a client must full fine-tune a 7.8M parameter model, it is not feasible on those devices." Hence the frozen-backbone, head-only training design.
- **Three-phase plan** (approach.md): Phase 1 (done) = local simulation on Mac localhost; Phase 2 = real distributed clients (friends' laptops/gaming PC) with Raspberry Pi 5 as server over Tailscale, FastAPI dashboard at marutsut.me; Phase 3 = packaged PyInstaller client agents (blocked on flaw F28, catastrophic forgetting). Cross-links: [[smart-agri]] (same PlantVillage data + Pi deployment domain), [[job-doot]] (same Pi + domain infra).

## Architecture (server/client topology, training flow)

**Topology**: 1 Flower server + 2 Flower clients, all as separate Python processes on one Mac in Phase 1 (server binds `0.0.0.0:8080`, clients connect `127.0.0.1:8080` — `phase1/config.py:39-40`). gRPC transport (Flower default).

**Per-round flow**:
1. Server (`phase1/server.py`, custom `FedAvgWithEval` strategy extending `flwr.server.strategy.FedAvg`, lines 56-117) sends global weights to both clients.
2. Each client (`phase1/client.py`, `PlantClient(NumPyClient)`, lines 102-166) trains the 2,562-param head locally for E=5 epochs (batch 32, Adam lr=1e-4) on its private non-IID slice; FedProx adds a proximal penalty against the round-start global weights.
3. Clients return weights + sample counts; server does weighted averaging (FedAvg aggregation).
4. Server evaluates the aggregated global model on a held-out server-side set (50 images/class = 100 images, `config.py:32`), logs "Round N — accuracy: X%", saves `round_NN_global.npz` (deleting the previous round's checkpoint, `server.py:87-92`).
5. After the final round: export to ONNX (opset 13) and delete the last `.npz` (`server.py:48-51, 166-175`).

**Resilience engineering** (non-obvious, see "Model & Training Detail"): per-epoch client checkpointing with resume, server `--from-checkpoint` resume, divergence warning if accuracy drops >5% below best (`config.py:35`), and shell-script orchestration (`run_overnight.sh`, `run_batch2.sh`, `run_resume.sh`) that queues multi-experiment overnight batches with `caffeinate`.

**M1 memory engineering** (`client.py:7-12`): clients force CPU (`tf.config.set_visible_devices([], 'GPU')`) *before* the flwr import (flwr triggers TF runtime init at import time). Rationale in code comment: 3 processes each grabbing ~2GB Metal GPU context → 6GB on an 8GB unified-memory M1 → swap thrashing ("224GB written to disk in one 8-hour run"). The 2,562-param head trains fine on CPU; the server keeps the GPU for brief eval passes.

## Complete Tech Stack

| Tech | Where used | Evidence |
|---|---|---|
| [[flower]] (flwr) 1.30.0 | FL server (`start_server`, `FedAvg` strategy subclass) + `NumPyClient` clients | `requirements.txt`; `phase1/server.py:56-117`; `phase1/client.py:102-166` |
| [[tensorflow]] (tensorflow-macos 2.16.2 + tensorflow-metal 1.2.0) | Model build, training, Metal GPU accel | `requirements.txt`; `phase1/model.py` |
| [[keras]] (via TF) | EfficientNetB1 application, GAP + Dense head, Adam, callbacks | `phase1/model.py:5-24`; `phase1/baseline.py:87-106` |
| [[efficientnet]] B1 (ImageNet weights) | Frozen feature backbone, 240×240 input | `phase1/model.py:5-11`; `phase1/config.py:16` |
| [[fedavg]] | Aggregation strategy (Exp 6, 7); also the aggregation core under FedProx | `phase1/server.py:56-68` |
| [[fedprox]] | Client-side proximal term in custom `@tf.function` train step (μ=0.1 default, μ=1.0 in Exp 8) | `phase1/client.py:70-86`; `phase1/config.py:31` |
| [[tf2onnx]] 1.17.0 + [[onnx]] 1.21.0 | Keras → ONNX export, opset 13 | `phase1/server.py:48-51` |
| [[onnxruntime]] | Standalone inference verification (InferenceSession) | `evaluate_models.py:53-67`; `demo_results.ipynb` cells 2/8 |
| [[numpy]] 1.24.3 (pinned, post-install downgrade) | Weights as ndarray lists, `.npz` checkpoints, partition shuffling | `requirements.txt:6`; `phase1/data_loader.py` |
| [[pillow]] 12.2.0 | Image loading at 240×240 | `phase1/data_loader.py:24` |
| [[matplotlib]] 3.10.9 + [[seaborn]] 0.13.2 | Convergence curves, confusion matrices, `results_plot.png` | `plot_results.py` (192 lines); `evaluate_models.py` |
| [[scikit-learn]] 1.7.2 | ML utilities/metrics | `requirements.txt` |
| [[jupyter]] notebook (programmatically generated) | `demo_results.ipynb` built by `build_notebook.py` (332 lines) | `build_notebook.py`; `demo_results.ipynb` (19 cells) |
| [[grpc]] (Flower transport) | Server↔client weight exchange | flwr internals; discussed in `.claude/specs/fl_concepts.md` (gRPC vs HTTP section) |
| Bash orchestration | Overnight experiment batches, resume workflows | `run_overnight.sh` (130 ln), `run_batch2.sh` (160 ln), `run_resume.sh` (156 ln) |
| [[git]] | Single-commit frozen export incl. chat transcripts | `.git/`, commit `afd2cd1` |
| Conda env `fl`, Python 3.10.16 | Runtime (`/opt/anaconda3/envs/fl/`) | shell scripts line 10; `requirements.txt:1` (README says 3.11 works for repro) |

No `.env` file; no secrets anywhere (hardcoded localhost paths only).

## FL Detail (strategies, client count, rounds, local epochs, non-IID partitioning, aggregation)

**Clients**: exactly 2, hardcoded by class identity — `Tomato_healthy` client and `Tomato_Early_blight` client (`config.py:9-12`, `client.py:33-35`).

**Server strategy** (`server.py`): `FedAvgWithEval(FedAvg)` with `min_fit_clients=2`, `min_evaluate_clients=2`, implicit `fraction_fit=1.0` (both clients every round), `num_rounds=30` default (`config.py:27`, overridable `--rounds`), optional `initial_parameters` from an `.npz` checkpoint (`--from-checkpoint`, `server.py:127-150`). Server-side centralized evaluation each round on 100 held-out images (50/class). Aggregation is standard sample-count-weighted FedAvg.

**Client training** (`client.py`): `LOCAL_EPOCHS=5` (E=1 in Exp 9), `BATCH_SIZE=32`, `LEARNING_RATE=1e-4` Adam, 80/20 local train/val split. Returns weights + len(train) + client id.

**FedProx implementation** — hand-written, not Flower's built-in: a custom `@tf.function` training step (`client.py:70-86`) computes `total_loss = sparse_CE + (MU/2) * ||w_local − w_global||²`, where `w_global` is a snapshot of the round-start global weights (`global_ref`, updated each `fit()` call, `client.py:116-119`). `MU=0.1` default (`config.py:31`); μ=0 reduces it to FedAvg; Exp 8 used **μ=1.0**. FedAvg runs use plain `model.fit`.

**Non-IID partitioning** — explicit **label-skew quantity split**, *not* Dirichlet. From `phase1/data_loader.py:31-46`:

```python
def load_mixed_data(primary_folder, primary_label, secondary_folder, secondary_label,
                    primary_samples, secondary_samples):
    """Load from two class folders and mix them (non-IID imbalanced split)..."""
    X_p, y_p = load_data(primary_folder, primary_samples, primary_label)
    X_s, y_s = load_data(secondary_folder, secondary_samples, secondary_label)
    X = np.concatenate([X_p, X_s]); y = np.concatenate([y_p, y_s])
    idx = np.random.permutation(len(X))
    return X[idx], y[idx]
```

- **Skewed config** (Exp 6/6b/8/9): `PRIMARY_SAMPLES=150`, `SECONDARY_SAMPLES=50` → each client is 75%/25% one class (mirror-imaged between clients), 200 images/client.
- **Balanced variant** (Exp 7): 100:100 per client via `patch_config.py` (a 24-line CLI utility that rewrites `config.py` values so one shell script can run many configs — `run_batch2.sh:91-124`).
- Design history: started as the *pathological* one-class-per-client split (flaws.md F14), which "accidentally created the pathological non-IID case that FL researchers use as a benchmark for failure," then evolved to 90/10, then locked at 150:50.

**Aggregation pathology discovered and documented — bias cancellation** (`fl_concepts.md:154-173`): with one-class-skewed clients, Adam shortcuts to opposite bias vectors on each client (`[+large, −large]` vs `[−large, +large]`); FedAvg averages them to `[0,0]` — "perfect cancellation" — yielding 50% forever. FedProx's proximal "leash" prevents the drift. (Note: the original 50% runs were *also* poisoned by the F35 input bug — see Honesty Flags — but the bias-cancellation mechanism is the documented theory and post-fix Exp 6b/8/9 dynamics are consistent with μ mattering.)

## Model & Training Detail

**Architecture** (`phase1/model.py:5-24`, verified directly):
- `tf.keras.applications.EfficientNetB1(include_top=False, weights="imagenet", input_shape=(240,240,3))`
- `base.trainable = False` — backbone frozen (decision F30)
- Head: `GlobalAveragePooling2D` → `Dense(2, activation="softmax")`
- Compile: Adam lr=1e-4, `sparse_categorical_crossentropy`, accuracy metric
- **Trainable params: 2,562** (1280×2 weights + 2 biases); frozen: 6,575,239 (baseline.py log line 81; spec prose says "7.8M" — that's total incl. non-trainable BN stats, minor doc/code mismatch)
- Input: raw [0,255] float32 — EfficientNet's internal Rescaling/normalization layers handle preprocessing (this is the F35 bug-fix; see Honesty Flags)
- Weight payload per round: ~31MB full-model weights (assumptions.md; Phase 2 plan: send only the ~10KB head)

**Dataset**: PlantVillage (Kaggle), at `data/PlantVillage/` — 15 class folders present (shared dataset with [[smart-agri]]); this project uses only `Tomato_healthy` (1,591 imgs) and `Tomato_Early_blight` (1,000 imgs). Per-experiment usage: 200 imgs/client train pool (80/20 train/val) + 100 server eval images. Centralized baseline pools 400 (320 train / 80 val).

**Centralized baseline** (`phase1/baseline.py`, 154 lines): same frozen-backbone model, same 400 images, 50 epochs, ~6 min on M1. `SaveBestNpz` + `EpochLogger` callbacks. Result: **best val acc 98.75% at epoch 39** (`checkpoints/baseline/results.json`: `best_val_accuracy_pct: 98.75`, `final_val_loss: 0.1474`) — rounded to 98.8% in all docs.

**Checkpoint/resume engineering** (the standout non-obvious work):
- *Client level* (`client.py:110-156`): every local epoch writes `checkpoints/{class}/round_NN/weights.npz` + `epoch.json {"completed_epochs": N}`; on reconnect mid-round, the client resumes from the completed epoch ("[RESUME] Round N from epoch k+1").
- *Server level*: per-round global `.npz` with previous-round deletion; `--from-checkpoint` warm-start. Caveat the author handled: resumed servers restart round numbering at 1, so logs are relabeled/split — `demo_results.ipynb` cell 14 has a dedicated `parse_exp8()` that splits the log at the "RESUMED FROM ROUND 15 CHECKPOINT" marker.
- *Batch level*: `run_resume.sh:50-77` preserves `round_15_global.npz` as `exp8_resume_ckpt.npz`, archives phase-1 server dir to `server_exp8_p1`, clears stale client round dirs, appends a resume marker to the same log, then runs 15 more rounds. State tracked in `checkpoints/RESUME_STATE.md` and `checkpoints/MONITOR_STATE.md` (incl. health heuristics: 3 processes, training client RSS 200-400MB, deadlocked client <50MB).
- This machinery directly produced the headline result: Exp 8 plateaued at 96% for 10+ rounds, was interrupted at round 15, and **broke through to 99% at round 22 after resume** with fresh client optimizer state (results.md:159-177 — "false plateaus are real").

## ONNX Export & Verification

**Export** (`phase1/server.py:48-51`, invoked at 166-175 after final round):
```python
spec = (tf.TensorSpec((None, IMAGE_SIZE, IMAGE_SIZE, 3), tf.float32, name="input"),)
onnx_model, _ = tf2onnx.convert.from_keras(keras_model, input_signature=spec, opset=13)
onnx.save(onnx_model, str(path))
```

**Artifacts** (all ~25MB; timestamps from notebook cell 18):
- `checkpoints/server_fedavg/global_model_fedavg.onnx` (Exp 6, saved 2026-06-03 03:14)
- `checkpoints/server_exp8_p2/global_model_exp8_fedprox_mu1.onnx` (**primary**, Exp 8, saved 2026-06-06 01:54)
- `checkpoints/server/global_model_exp9_fedprox_e1.onnx` (Exp 9, saved 2026-06-06 03:43)
- Plus `.npz` checkpoints: `baseline/best_weights.npz`, `server_fedavg/round_17_global.npz`, `server_exp8_p1/round_15_global.npz`, `exp8_resume_ckpt.npz` (23MB each)

**Verification — two independent paths, neither touching TF/Flower:**
1. `evaluate_models.py` (150 lines): `onnxruntime.InferenceSession` over 100 fresh images (50/class), accuracy + TP/TN/FP/FN confusion matrices.
2. `demo_results.ipynb` (19 cells, generated by `build_notebook.py`): "Every number here is computed live from the model, not copied from training logs" (cell 0). Loads the 3 ONNX models, runs inference on 100 held-out images, renders per-image prediction galleries, confusion matrices, convergence curves parsed from raw server logs, and model-file metadata. Pitched in README as professor-runnable without the FL stack.
3. `fed_proofs/` — screenshot evidence: `1_log.png` (round-by-round Exp 8 server log showing 99%), `2_onnx_editor.png`, `2_onnx_CLI.png` (ONNX file proof), and `results_summary.md` (87-line writeup).

**Independent (live) results** (notebook cells 8/16 outputs): Exp 6 FedAvg **98.0%** (avg conf 69.8%), Exp 8 FedProx μ=1.0 **98.0%** (avg conf 69.5%), Exp 9 **94.0%**, centralized baseline **85.0%** on the independent set. See Honesty Flags for the confidence-number artifact and the baseline's 85%.

## Metrics & Hard Numbers

**Master table** (sources: `README.md:7-14`, `.claude/specs/results.md:223-229`, raw logs in `checkpoints/`, `demo_results.ipynb` cell 16):

| Experiment | Algorithm | Data split | Rounds | Train-eval best | Live ONNX eval | vs baseline | Source log |
|---|---|---|---|---|---|---|---|
| Baseline | Centralized | 400 pooled | 50 epochs | **98.75%** (ep 39) | 85.0% | — | `checkpoints/baseline/results.json` |
| Exp 1-5 | FedAvg/FedProx/centralized | various | — | ~50% / 41.2% | — | **INVALID (F35 bug)** | experiments.md |
| Exp 6 | FedAvg | skewed 150:50 | 30 (17+13 resumed) | 96.0% | 98.0% | −2.8pp | `checkpoints/fedavg_server.log` |
| Exp 6b | FedProx μ=0.1 | skewed 150:50 | 30 | 95.0% | n/a (no ONNX) | −3.8pp | `checkpoints/fedprox_server.log` |
| Exp 7 | FedAvg | balanced 100:100 | 30 | **100.0%** (log only) | n/a (no ONNX) | +1.2pp ⭐ | `checkpoints/exp7_fedavg_balanced_server.log` |
| **Exp 8** | **FedProx μ=1.0** | **skewed 150:50** | **30 (15+15 resumed)** | **99.0%** | **98.0%** | **+0.2pp ⭐⭐** | `checkpoints/exp8_fedprox_mu1_server.log` |
| Exp 9 | FedProx μ=0.1, **E=1** | skewed 150:50 | 50 | 96.0% | 94.0% | −2.8pp | `checkpoints/exp9_fedprox_e1_server.log` |

**Convergence detail (from raw logs):**
- Baseline: ep1 26.2% → ep10 83.7% → ep20 93.8% → ep30 96.2% → ep39 **98.8%** (held to ep50; final loss 0.1474).
- Exp 6 (resumed segment, logged as rounds 1-13): 95.0%/0.1876 → 96.0% by r5, final 96.0%/0.0998.
- Exp 6b: r1 64.0% → r5 88% → r10 90% → r20 93% → r30 95.0%/0.1975.
- Exp 7: r1 50.0% → r5 95% → r9 99% → **r14 100.0%**, held through r30 (loss 0.0908).
- Exp 8: phase 1 — flat 96.0% rounds 1-15 (loss falling 0.2392→0.2510→0.251); resume marker; phase 2 — relabeled r7 (=22 overall) **99.0%**, held to r30, final loss **0.1313** (results.md:149-157: "Best round 22 overall — held through round 30; gap vs centralized **+0.2%** (EXCEEDS baseline)").
- Exp 9 (E=1): r1 50% → r10 76% → r20 88% → r30 92% → r40 94% → r50 96.0%/0.2482 — **~5× slower** than E=5 to the same 96%.

**Key documented findings** (results.md:233-251):
1. Data heterogeneity dominates: balanced FedAvg (100%) > skewed anything.
2. FL exceeded centralized two ways — balanced data (+1.2pp) or strong proximal regularization (+0.2pp).
3. μ is non-monotonic on skewed data: μ=0 → 96%, μ=0.1 → 95%, **μ=1.0 → 99%**.
4. E=1 doesn't help: 49 rounds to match what E=5 reached in ~10.
5. False plateaus are real: Exp 8 sat at 96% with loss still dropping, then jumped to 99% post-resume.

**Other hard numbers**: 2,562 trainable / 6,575,239 frozen params; 240×240×3 input; ~31MB weight transfer/round; 25MB ONNX, 23MB npz; 100-image server eval set; baseline ~6 min on M1; 224GB swap written in one bad 8-hour run (pre-CPU-pinning); divergence alarm threshold 5%; PlantVillage classes used: 1,591 + 1,000 images.

## Spec-Driven Development Evidence

Strongest spec-first evidence among the user's projects. `README.md:22`: ".claude/specs/ — the written specs each piece of code was built from (**spec-first workflow: no code was written without an approved spec**)."

**12 spec files in `.claude/specs/`:**

| File | Lines | Role |
|---|---|---|
| `approach.md` | 166 | High-level design: hardware inventory (Pi 5, M1 Air, friends' PCs, marutsut.me domain), 3 phases, model choice, FL flow diagram |
| `assumptions.md` | 134 | "Single source of truth for all locked decisions" — framework, B1/240px/2,562 params, 150:50 split, E=5/lr=1e-4, checkpoint strategy, "FedProx (μ=0.1) — FedAvg failed on all 3 non-IID experiments (F33)" |
| `phase1_code_spec.md` | 331 | File-by-file architecture; opens: "**No code is written until this document exists. No file is created that is not listed here.**" |
| `flaws.md` | 433 | Flaw ledger F1-F35+; header: "All items here block a code decision. Nothing gets built until each relevant item is resolved and the answer is written into approach.md or assumptions.md." |
| `experiments.md` | 346 | Full experiment matrix with parameters, results, root-cause analyses |
| `results.md` | 259 | Standardized results format, convergence curves, comparison table, key findings |
| `fl_concepts.md` | 377 | Plain-language FL theory: bias cancellation, FedAvg vs FedProx, weights vs gradients, gRPC vs HTTP, catastrophic forgetting |
| `later_concepts.md` | 158 | Concepts understood after use — incl. the full F35 EfficientNet-preprocessing post-mortem and eager vs graph execution |
| `baseline_spec.md` | 46 | Centralized baseline spec |
| `code_story.md` | 98 | Per-file explainer one-pagers + 4 anticipated Q&As (interview prep artifact) |
| `environment_setup.md` | 172 | M1 (tensorflow-macos+metal) / Windows CUDA / Pi 5 setup matrix |
| `phase3_client_agent.md` | 93 | Phase 3 vision (PyInstaller agents, coordination API on Pi, Tailscale); explicitly blocked on F28 |

**Process artifacts beyond specs**: `claude_chats/` — five exported pair-programming transcripts (2026-05-28 theory study session *before any code* → 2026-05-30 1.6MB planning session → 2026-06-06 concepts review), generated by the project's own `export_chats.py`; `checkpoints/RESUME_STATE.md` + `MONITOR_STATE.md` as operational runbooks. README documents the 4-step workflow: theory → spec → experiments → verification, "including wrong turns and debugging."

## Resume Raw Material

1. Built a federated learning system in [[flower]] where 2 simulated farm clients train a shared [[efficientnet]] B1 plant-disease classifier on private non-IID data, exchanging only model weights — never raw images. [verified-in-code]
2. Achieved **99.0% global accuracy with [[fedprox]] (μ=1.0) on skewed 75/25 non-IID splits, exceeding the 98.8% centralized baseline**, on the PlantVillage tomato dataset. [verified-in-code: server log + results.json]
3. Demonstrated that data heterogeneity dominates FL performance: balanced-split [[fedavg]] reached 100% (log-recorded) vs 96% on skewed splits under identical settings. [verified-in-code: exp7 log]
4. Implemented FedProx by hand as a custom `@tf.function` TensorFlow training step adding a proximal term `(μ/2)·||w_local − w_global||²` to client loss, rather than using a library implementation. [verified-in-code: client.py:70-86]
5. Diagnosed and fixed a double-normalization bug (manual /255 colliding with EfficientNet's internal rescaling) that had silently blinded the backbone and pinned 5 experiments at coin-flip accuracy; root-caused via the centralized ablation. [verified-in-code + docs: flaws.md F35]
6. Designed for constrained edge clients by freezing the 6.6M-param backbone and training only a 2,562-parameter head, cutting client compute and enabling CPU-only client training. [verified-in-code: model.py]
7. Engineered crash-safe FL training: per-epoch client checkpoints with mid-round resume, per-round server `.npz` checkpoints with `--from-checkpoint` warm-start, and bash orchestration for unattended overnight multi-experiment batches. [verified-in-code: client.py, server.py, run_resume.sh]
8. Exported final global models to [[onnx]] (tf2onnx, opset 13) and verified them independently with [[onnxruntime]] in a standalone notebook — 98.0% on a fresh 100-image set with zero FL/TF training dependencies. [verified-in-code: notebook outputs]
9. Ran a controlled 6-experiment matrix (centralized baseline, FedAvg/FedProx × skewed/balanced × μ ∈ {0, 0.1, 1.0} × E ∈ {1, 5}) with standardized per-round metrics and a written results spec. [verified-in-code: logs + results.md]
10. Found μ is non-monotonic on skewed data (μ=0 → 96%, μ=0.1 → 95%, μ=1.0 → 99%) and that E=1 aggregation is ~5× slower to converge than E=5. [verified-in-code: logs]
11. Documented the "bias cancellation" failure mode of FedAvg under label skew (clients learn opposite bias vectors that average to zero) and validated FedProx's proximal leash as the fix. [docs-only mechanism; consistent with logs]
12. Resolved M1 unified-memory contention (3 TF processes → 6GB Metal contexts → 224GB swap thrash) by pinning clients to CPU before flwr import while reserving GPU for server eval. [verified-in-code: client.py comment]
13. Practiced strict spec-driven development: 12 specs including a 433-line flaw ledger gating all code ("nothing gets built until each item is resolved"), full experiment/results specs, and exported pair-programming transcripts. [verified-in-code: .claude/specs/]
14. Discovered and exploited the "false plateau" phenomenon: a run flat at 96% for 10+ rounds (loss still falling) broke through to 99% after checkpoint-resume reset client optimizer state. [verified-in-code: exp8 log resume marker]
15. Specced (not yet built) Phase 2/3: real distributed clients over Tailscale with a Raspberry Pi 5 aggregation server and packaged PyInstaller client agents. [docs-only]

## Interview Depth

**FedAvg vs FedProx — when and why**
- Honest framing: FedAvg is weighted parameter averaging; it works well when client distributions are similar or balanced (Exp 7: 100%). Under label skew, each client's local optimum drifts toward its majority class; in the extreme, the Dense head's biases on the two clients become mirror images and average to ~zero (the documented "bias cancellation"). FedProx adds `(μ/2)||w − w_global||²` to local loss — a leash limiting per-round drift, trading local fit for global stability.
- Nuance worth volunteering: **μ was non-monotonic here** — μ=0.1 (95%) actually underperformed FedAvg (96%) on skewed data; only μ=1.0 (99%) won. Small μ buys drift-slowdown cost without enough stabilization benefit. Also: with only the head trainable, the proximal term acts on a 2,562-param space, which is why a large μ stayed tractable.
- Caveat to concede if pressed: 2 clients, binary task, frozen backbone — favorable conditions; with many clients and full fine-tuning, μ tuning is harder and FedProx's benefit varies.

**Non-IID challenges**
- This project used quantity-based **label skew** (75/25 mirrored), not Dirichlet sampling — be ready to explain Dirichlet(α) as the standard generalization and that this 2-client setup is the worst-case end of it.
- Server-side centralized evaluation (100 balanced held-out images) was the referee — without it, each client's local val accuracy looks great while the global model is broken.
- Catastrophic forgetting is the documented open problem for clients-arriving-with-new-classes (flaws.md F28); the spec evaluates persistent clients, EWC, knowledge distillation, and rejects replay buffers on privacy grounds. Good answer to "what breaks at scale?"

**Likely questions + honest answers**
- *"Why only 2 clients?"* — Deliberate Phase 1 scope: isolate the aggregation mechanics on one machine (M1 8GB couldn't host more TF processes anyway). 2 mirrored-skew clients is also the cleanest demonstration of the FedAvg failure mode. Phase 2 spec covers real distributed clients.
- *"Is 99% real?"* — It's the global model's accuracy on a 100-image balanced server-side held-out set, recorded in the raw server log; the exported ONNX model independently scored 98% on a different fresh 100-image set. Small eval set (each image = 1pp), binary task, PlantVillage is a clean dataset — so it's verified-but-easy, not a research claim.
- *"Hardest bug?"* — F35 double normalization. Great story: all FL experiments stuck at 50%, suspected aggregation, but the *centralized* ablation also failed (41%), proving the bug was below the FL layer; traced to EfficientNet's internal Rescaling layer; fix was deleting `/255.0`; baseline immediately hit 98.8%.
- *"Why send full 31MB weights when only 2,562 params train?"* — Known inefficiency, accepted for Phase 1 simplicity; Phase 2 spec sends head-only (~10KB).
- *"How did you handle interrupted training?"* — Per-epoch client checkpoints + server `--from-checkpoint`; the resume actually *improved* the result (false plateau / optimizer-state reset story).
- *"FL round vs epoch?"* — 1 round = E local epochs per client + 1 aggregation + 1 global eval; with E=5 a round ≈ 5 centralized epochs of compute but only 1 communication step; E=1 made communication the bottleneck (50 rounds for 96%).

## Honesty Flags

- **The 99% claim holds in recorded artifacts** — `checkpoints/exp8_fedprox_mu1_server.log` (relabeled round 7 post-resume = round 22 overall), `results.md`, `fed_proofs/1_log.png` all agree; independent ONNX re-eval gives 98.0% on a different image subset (README acknowledges the difference). Safe to state as "99% training-eval / 98% independently verified."
- **Tiny eval sets**: 100 images (50/class) for both server eval and notebook verification — 1 image = 1 percentage point. The 99-vs-98.8 "beats centralized" margin is **+0.2pp on a 100-image set, i.e., well within noise**. Frame as "matched the centralized baseline" under scrutiny, not "beat" it. Exp 7's 100% is log-only (no ONNX saved).
- **Centralized baseline scored only 85.0% on the notebook's independent live-eval set** while FL models scored 98% (notebook cell 16; baseline live number is hardcoded in the print dict with an "on independent eval set" note). Surprising inversion, never explained in the docs — could be eval-set overlap with FL training images, or genuine FedProx regularization benefit. Don't cite "FL generalizes better than centralized" without re-checking this.
- **Notebook confidence numbers are an artifact**: `run_inference` applies softmax (`np.exp(...)`) to the model output, but `model.py`'s Dense layer already has `activation="softmax"` — a **double softmax**. Accuracy (argmax) is unaffected, but the reported "avg confidence ~69%" understates true confidence. Don't quote confidence figures.
- **Binary task, clean dataset**: Tomato healthy vs Early blight on PlantVillage (lab-style images). "Plant disease detection" on a resume should not imply the 15-class problem ([[smart-agri]] covers more classes); this is 2-class.
- **Experiments 1-5 are invalid** (F35 double-normalization bug) — never cite them except as the debugging story. Only Exp 6-9 + baseline count.
- **Exp 6's log only covers the resumed rounds** (logged as 1-13 = real 18-30); the original rounds 1-17 log is the pre-resume `server/` lineage. The 96% figure is consistent across docs but the full curve is stitched.
- **Round numbering after resume restarts at 1** in Flower; all "round 22" style claims rely on manual relabeling (handled in `parse_exp8()` in the notebook — defensible, but know it).
- **B0 vs B1**: `approach.md` says EfficientNet **B0** in its goal line; the locked decision (assumptions.md) and actual code (`model.py`, 240px input) are **B1**. Always say B1. Similarly docs say "7.8M params" frozen; the training log says 6,575,239 non-trainable — say "~6.6M frozen / 2,562 trainable."
- **"Simulated farms"**: both clients ran as processes on one MacBook over localhost. Never imply real distributed deployment — Phase 2 (Pi 5 + Tailscale) is specced, unbuilt. Project is not deployed anywhere.
- Environment mismatch nit: scripts hardcode conda env `fl` with Python 3.10.16; README repro says Python 3.11 — harmless but don't claim a pinned reproducible env beyond `requirements.txt`.
