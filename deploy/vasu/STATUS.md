# Vasu setup — status (Vasu's Claude keeps this current; Tejas's Claude reads it)

_Last updated: 2026-11-21 by Vasu's Claude. WSL base stack installed; next gate is `claude /login` (human), then the Claude-LLM swap._

| Checkpoint | State | Notes |
|---|---|---|
| 0 — read handoff + repo | ✅ | |
| 2 — WSL, Docker, Chrome, venv, Claude CLI | ✅ (login pending) | Ubuntu 24.04, systemd+cron+linger, Docker 29.10, Chrome 158, Py3.11 venv (`playwright`+`python_ghost_cursor` import OK), Claude CLI 2.1.330. **`claude /login` not yet run (human step).** |
| 3 — .env + Google OAuth + fetch cookie | 🔧 | Groq/Telegram **dropped** (see below). Still need Google OAuth + fetch cookie. |
| 4 — backend up, user `vasu` (admin), jobs scored | ⬜ | depends on Claude-LLM swap (scoring + tailoring now need Claude) |
| 5 — applier: one slot works, service running | ⬜ | Phase A dummy. Applier kept as-is (it already uses Claude). |
| 5b — LinkedIn-only daily counter (spec first) | ⬜ | §1 |
| 6 — dashboard + widget over Tailscale | ⬜ | |
| 7 — auto-deploy cron | ⬜ | |

## Architecture change on Vasu's instance (he decided this)
- **No Groq, no Telegram, no Ollama.** All LLM work (tailoring, critic/improver, scoring, email classify) routes through Vasu's **Claude subscription** instead — same as the applier already does. Spec: `.claude/specs/claude-llm/approach.md`.
  - Chosen bridge: a **host HTTP shim** (`tools/claude_shim.py`, systemd --user) that runs `claude -p`, reached from the backend container at `host.docker.internal` — reusing the exact pattern Ollama used.
  - Telegram push dropped; the dashboard `/needs-you` + bell remain the Q&A channel.
- **Apply engine unchanged** — Tejas's `applier/` (ghost-cursor + Haiku) kept.
- Deviation from Pi: Docker **CE inside WSL** (not Docker Desktop), so setup is scriptable.

## Blocked
1. **git push denied** — cached credential is `KartikBlu` (403). Needs Vasu's GitHub account as collaborator (Q2). All work committed locally meanwhile.
2. **`claude /login`** — interactive; must be run by Vasu in WSL before the LLM swap can be tested.

## Questions for Tejas
**Q1 — WSL mandatory? → RESOLVED.** Going WSL2 for parity (Vasu's call). Docker CE in WSL instead of Docker Desktop.
**Q2 — push access:** add Vasu's GitHub account as collaborator, or fork+PR? (Currently blocked.)
**Q3 — account model:** Vasu's real LinkedIn/Naukri/Indeed sessions from a prior session are **parked**, unused. Proceeding with your dummy fetch account + separate apply account. Confirm you're creating the fetch account.
**Q4 — roles/locations:** set scraper to AI/GenAI + ML/NLP; Delhi NCR/Gurugram + remote-India + remote-global (spec-first)? Replaces Gurgaon/Delhi/Noida/Pune/Remote.
**Q5 — LinkedIn volume:** §1 says 15/day. Vasu's own target was ~5–10/day. Confirm 15 or lower.
**Q6 — NEW — heads up on the Claude-LLM swap:** on Vasu's instance, Groq/Ollama are replaced by his Claude subscription via a host shim (above). Old `groq_client.py`/`local_llm_client.py` are left in place (unused) so your merges don't conflict. If you change those modules, note it here so we re-point the facade.

## Answers from Tejas
