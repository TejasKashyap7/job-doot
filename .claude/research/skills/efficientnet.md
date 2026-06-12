---
title: EfficientNet
type: skill
verdict: strong
---
## Evidence
- [[smart-agri]] — EfficientNet-B0: 99.95% accuracy, lowest loss (0.0005) in the 8-family benchmark; 4.01M params (ONNX-counted), 45.4 ms / ~111 MB RAM on Pi 5; served live [verified-in-paper + live].
- [[federated-learning]] — EfficientNet-B1 (ImageNet, frozen backbone, 240×240) as the FL classifier; F35 internal-preprocessing bug diagnosed and fixed [verified-in-code].

## Resume verdict
Yes — resume-worthy as the named architecture in both flagship ML projects. Cite 4.01M params (not the PPT's 5.3M); say B1 for the FL project (not B0).

## Interview readiness
Can discuss compound scaling at a working level, B0 vs MobileNetV3 efficiency trade-offs, and the internal Rescaling/normalization gotcha from first-hand debugging. Caveat: the honest smart-agri headline is MobileNetV3-Small as the edge winner — EffB0 is the accuracy/loss leader.
