---
title: ONNX / ONNX Runtime
type: skill
verdict: strong
---
## Evidence
- [[smart-agri]] — all 10 models exported via tf2onnx and served by ONNX Runtime CPU on the Pi 5 (live, verified with real predictions); exact param counts from ONNX initializer tensors; documented the int8 quantization paradox on ARM (3.5–4× smaller but slower without vectorized kernels).
- [[federated-learning]] — final global models exported (opset 13) and independently re-verified at 98.0% via onnxruntime in a standalone notebook with zero FL/TF dependencies [verified-in-code + artifacts].

## Resume verdict
Yes — LOCKED_SKILL_SET and resume. Strong, distinctive claim: "ONNX export + runtime serving on ARM edge hardware, including independent model verification decoupled from the training stack".

## Interview readiness
Can discuss tf2onnx export signatures, opsets, why ONNX over TFLite/TF-Serving for this use, and the int8-on-ARM finding as an honest system-limitation story. No caveats.
