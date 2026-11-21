# Spec: route all backend LLM calls through Claude (replace Groq + Ollama)

**Status:** proposed, 2026-11-21 (Vasu's instance only — NOT for Tejas's Pi).
**Why:** Vasu is not using Groq (paid API) or Ollama (local model). All LLM work
on his instance goes through his **Claude subscription** instead. The apply agent
already does this (`claude -p --model haiku`); this extends the same idea to the
backend's tailoring, critic/improver, scoring, and email classification.

## What changes

Both existing providers expose the **same interface** and say so in their own
docstrings:
- `backend/services/groq_client.py` — `chat_json(system, user, **kw) -> dict`, `chat_text(...) -> str` (tailoring, critic/improver, email classify)
- `backend/services/local_llm_client.py` — identical two functions (scoring)

So we add ONE drop-in with the same signature and repoint callers:

- **New:** `backend/services/claude_client.py` — `chat_json` / `chat_text` that
  call Claude and return the same types. `chat_json` must still return a parsed
  `dict` (enforce JSON: instruct "reply with only a JSON object", then
  `json.loads`, with a salvage/retry like the others).
- **Callers:** change imports from `groq_client` / `local_llm_client` →
  `claude_client`. Keep the old files in place (unused) so Tejas's merges don't
  conflict on deletions; a single switch point is cleaner — see below.
- Optional: a tiny `llm.py` facade that re-exports the chosen provider, so
  callers import `services.llm` and we flip providers in one line. Preferred over
  editing every caller.

## The container problem and the chosen solution

The backend runs in **Docker**; the `claude` CLI and its subscription auth live
on the **WSL host** (`~/.claude`). Three ways to bridge:

1. Install `claude` in the backend image + mount `~/.claude` into the container.
2. **Host HTTP shim (CHOSEN):** a tiny host service (`tools/claude_shim.py`,
   systemd --user) that accepts `{system, user, json, model}` and runs
   `claude -p`, returning the text. The container reaches it at
   `http://host.docker.internal:<port>` — the **exact pattern Ollama already
   used** (`local_llm_client` → `host.docker.internal:11434`), so compose and the
   mental model barely change.
3. Anthropic API with an API key — rejected: that's pay-per-token, not the
   subscription Vasu wants.

**Chosen: option 2.** One auth location (host), nothing Claude-specific baked
into the image, and it slots into the existing `host.docker.internal` wiring.

### Shim contract
- `POST /chat` `{system, user, json: bool, model: "haiku"|"sonnet", max_tokens}`
  → `{text}`. On `json:true` the shim asks Claude for a bare JSON object.
- Runs `claude -p --model <model>` with the prompt on stdin; `--output-format`
  text. Serialized/low-concurrency (one subscription); a small queue + timeout.
- Env: `CLAUDE_SHIM_URL` (container → `http://host.docker.internal:8099`),
  `CLAUDE_DEFAULT_MODEL=haiku`.

## Model policy (cost control — one subscription, shared)
- **haiku** for high-volume/cheap calls: scoring, email classification.
- **sonnet** for quality-sensitive: tailoring critic/improver.
- Scoring runs in batches (`SCORE_BATCH`, every `SCORE_INTERVAL_MIN`) — keep
  batches small and serialize so a scoring pass can't starve the applier, which
  shares the same subscription.

## Risks / tradeoffs (flag to Vasu + Tejas)
- **Quota & latency:** every tailor/score/classify now spends Claude quota and is
  slower than Groq/Ollama. Mitigate with haiku + small batches; revisit limits
  after a day of real load.
- **Serialization:** the applier and the shim share one login; heavy backend
  scoring could slow applies. Keep scoring batches modest; applier has priority.
- **Divergence from Tejas's Pi:** this is Vasu-only. Record in STATUS.md so his
  auto-deploy/merges account for it. Old provider files stay for mergeability.

## Checkpoints
1. `tools/claude_shim.py` answers `curl host:PORT/chat` with a JSON round-trip.
2. `claude_client.chat_json` returns a dict end-to-end through the shim.
3. One real tailoring pass and one scoring pass complete with no Groq/Ollama.
