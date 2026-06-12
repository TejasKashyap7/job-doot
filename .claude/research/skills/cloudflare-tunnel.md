---
title: Cloudflare Tunnel
type: skill
verdict: strong
---
## Evidence
- [[smart-agri]] — systemd `cloudflared.service` (tunnel "pi5", RestartSec=5) exposing pifive.marutsut.me with no inbound ports; verified live.
- [[ekantik]] — ekantik.marutsut.me through the same tunnel; plus a custom upload bridge (bridge.marutsut.me) streaming 64 KB-chunked tar.gz through the tunnel to sync a 684 MB vector DB without SSH [verified-in-code].
- [[job-doot]] — planned jobs.marutsut.me ingress (DEPLOY.md runbook: ingress rule, `tunnel route dns`, TLS at edge, plain HTTP origin).

## Resume verdict
Yes — already in LOCKED_SKILL_SET; keep it. Phrase as "zero-port-forwarding public exposure of home-server ML services via Cloudflare Tunnel (systemd, multi-subdomain ingress)".

## Interview readiness
Can explain the tunnel model (outbound-only connector, TLS at edge), multi-service ingress on one Pi, and the DIY deployment bridge built on top. Caveat: lens.marutsut.me currently 403 with no tunnel config in that repo.
