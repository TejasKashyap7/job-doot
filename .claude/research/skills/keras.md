---
title: Keras
type: skill
verdict: strong
---
## Evidence
- [[smart-agri]] — keras.applications backbones for 8 architecture families; two-phase transfer learning (frozen base → fine-tune) with EarlyStopping [verified-in-notebooks].
- [[federated-learning]] — EfficientNetB1 application with GAP + Dense(2) head, frozen backbone (2,562 trainable params), Adam, custom callbacks (`SaveBestNpz`, `EpochLogger`) [verified-in-code: `phase1/model.py`].

## Resume verdict
Yes — already in LOCKED_SKILL_SET; keep alongside TensorFlow (one line: "TensorFlow/Keras").

## Interview readiness
Can discuss applications API, freezing strategies, callback design, and the F35 lesson (EfficientNet's internal Rescaling layer vs manual /255 — the double-normalization bug story). No caveats.
