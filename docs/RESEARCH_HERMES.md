# RESEARCH — P-HERMES Feasibility (LLM/Reasoning Layer)

**Author:** RESEARCHER (researcher-and-ideator-mtumwxna) · **Date:** 2026-09-10
**Task:** Determine whether TRINETRA's P-HERMES phase builds a live chat layer or an honest-unavailable layer. READ-ONLY — no repo edits, no suite runs, nothing executed against :8000 beyond an accidental root GET noted below.

---

## 1. ENDPOINT AVAILABILITY — probe results (measured today)

**VERDICT: A LIVE LLM ENDPOINT EXISTS — the local OmniRoute gateway at `http://127.0.0.1:20128/v1` (OpenAI-compatible), serving chat completions RIGHT NOW.** P-HERMES should build the live chat layer with the honest-unavailable fallback design (both are required anyway — laptops reboot).

### Exact probe log

| Probe | Result | Time |
|---|---|---|
| `GET 127.0.0.1:20128/v1/models` (auth Bearer) | **HTTP 200**, 3,319 model IDs listed | 5.64s |
| `POST /v1/chat/completions` model `oc/deepseek-v4-flash-free` | **HTTP 400** — "Upstream request failed: Model is unavailable" (model-level failure; gateway itself fine) | 12.79s |
| `POST /v1/chat/completions` model `auto/glm` | **HTTP 200 — content `PING_OK`**, routed to `z-ai/glm-5.1`, clean usage stats (19 prompt / 16 completion tokens, incl. 13 reasoning tokens) | within the 90s window (exact ms not captured — output was truncated; the failed-probe timing above brackets the gateway round-trip class: ~10-13s) |
| Port scan 11434 (ollama) / 1234 (LM Studio) / 8080 / 8081 / 3000 | **connection refused** — no local model servers | instant |
| `pgrep ollama/lmstudio/llama-server` | **none running** | — |
| Port 5000 | 403 — macOS ControlCenter (AirPlay), not an LLM | 10ms |
| Port 8000 | 200, Python listener (8.5ms) — a running FastAPI app; NOT probed further per discipline; not an LLM endpoint | 8.5ms |
| Listener audit (`lsof`) | Only inference-adjacent listener = `node *:20128` (the gateway) + 20131/20132 (same stack) | — |

### Key facts for the integrator

- **Gateway is OpenAI-compatible** (`/v1/models`, `/v1/chat/completions`, Bearer auth) — integration is a plain HTTP POST, no SDK needed.
- **`httpx 0.28.1` is ALREADY in the Trinetra venv** — zero new dependencies for the proxy. (Verified in pip list during stage-1.)
- **Model choice:** `auto/*` routes let the gateway pick a live upstream. `auto/glm` verified working today. Alternates visible in catalog: `auto/best-fast`, `auto/cheap`, `auto/best-free`, 3,000+ explicit IDs. One specific free model (`oc/deepseek-v4-flash-free`) was dead upstream — **do not hardcode one model ID; use an auto route or make the model configurable**.
- **Latency class:** seconds, not milliseconds (5.6s for a models list; ~10-13s round-trips). The response may include `reasoning`/`reasoning_details` fields (GLM reasoning models) — parse `choices[0].message.content`, ignore the rest.
- **Failure modes to handle** (from OmniRoute ops docs): HTTP 503 `chat_admission_busy` (concurrent load), `{"code":"model_cooldown"}` with `reset_seconds` (upstream creds cooling), per-model 400 "Model is unavailable" (pick another model / auto route). All must surface honestly in the UI, never trigger canned responses.
- **Stage-1's "offline" note was about the Nous web-search TOOL, not this gateway** — the gateway was up all along; I re-tested per orders and it answers.

### Trinetra/.env

Contains exactly one key: `GOOGLE_MAPS_API_KEY` (name only, per orders — value not read). No LLM keys configured today → P-HERMES adds `HERMES_BASE_URL`, `HERMES_API_KEY`, `HERMES_MODEL` (values from the working gateway config above).

---

## 2. RECOMMENDED INTEGRATION SHAPE (endpoint exists — build this)

**Backend (new `backend/services/hermes.py` + inline routes in `main.py`, C7 pattern):**

1. `POST /api/hermes/ask` — body `{question: str, event_id?: str, session_id?: str}`.
   - Context builder assembles the §4 contract from the DAO (reuses `generate_event_summary` / `generate_session_summary` internals — do not duplicate their queries).
   - One `httpx.post` to `{HERMES_BASE_URL}/chat/completions` with the §5 system prompt + context as a JSON block + operator question. Timeout **60s** (gateway round-trip class is 10-13s; leave headroom), connect-timeout 5s, ONE silent retry on connect-error only.
   - Response: `{answer, model, elapsed_ms, grounded_event_id?}` — or an honest error shape (§3).
   - Single-shot, not streaming, for MVP: the operator's question is a Q&A turn, latency is 5-15s, and the SSE hub stays untouched. Streaming is a stretch goal that can reuse the existing hub if desired — not required for honesty or function.
2. `GET /api/hermes/status` — cheap health: `GET {HERMES_BASE_URL}/models` with Bearer, 10s timeout; **cache the result 60s** so the frontend poll doesn't hammer a seconds-latency gateway. Returns `{connected, model, gateway, checked_at}`.
3. Config: `[hermes]` block in `default.toml` (`enabled=false` default, `base_url`, `model = "auto/glm"`, `timeout_s = 60`, `max_context_events = 5`) — parsed in `config.py` like REID; keys via `.env`, never in the toml. The API key NEVER reaches the frontend — the proxy is the only holder.
4. Discipline: the LLM may ONLY verbalize the context dict (the m8 Hermes rule, M8_CROSS_CAMERA_CONTRACT.md:143-148). It never generates event facts; the deterministic EventSummary stays the operator's explanation layer.

**Frontend:**
- The existing amber pill (`App.tsx:115-121` "HERMES — NOT CONNECTED") becomes dynamic: green "HERMES — CONNECTED" when `/api/hermes/status` says so, amber otherwise. Clicking opens the Hermes panel.
- Panel: question box + answer area + the event-context chip selector (which event am I asking about). Disabled with visible reason ("Hermes not connected") when status is down. NO placeholder chatter.

---

## 3. HONEST-UNAVAILABLE PATH (mandatory companion — gateway will be down sometimes)

The mandate forbids fake chatbots — canned string responses are NOT acceptable. Exactly:

1. **Context builder is built and testable regardless of gateway state** — it is pure DAO reads (deterministic, unit-testable without any network). This is the bulk of P-HERMES engineering and it happens either way.
2. `POST /api/hermes/ask` when gateway is unreachable/timeout/cooldown: return **503** with `{error: "hermes_unavailable", reason: "timeout"|"gateway_down"|"model_cooldown", retry_after_s?: int}`. NEVER a canned answer. The panel renders the reason + a retry affordance, and keeps showing the deterministic EventSummary.
3. Error taxonomy surfaced verbatim: `timeout` (60s elapsed), `gateway_down` (connect refused), `model_cooldown` (503 body's `reset_seconds`), `busy` (`chat_admission_busy`), `bad_model` (400 model unavailable → status page suggests switching `HERMES_MODEL` to an auto route).
4. UI states: CONNECTED / NOT CONNECTED (amber, existing pill) / BUSY (during in-flight ask). The NOT CONNECTED rail already exists and remains correct when the gateway is down — the demo works offline with deterministic summaries, and Hermes is a bonus when the floor's gateway is up.

---

## 4. CONTEXT CONTRACT (minimal schema — every field traces to a DB row)

Per-event context the builder assembles (types from the verified events/tracks/evidence schema):

```jsonc
{
  "question": "str",
  "event": {                       // events table row
    "id": "str", "type": "str", "severity": "str",
    "confidence": "float|null", "ts": "str", "video_ts": "float|null",
    "is_night": "bool", "direction": "str|null", "status": "str"
  },
  "tracks": [                      // tracks table rows for event.track_ids
    { "track_id": "int", "class_name": "str", "first_seen": "str",
      "last_seen": "str", "frames_seen": "int", "max_conf": "float",
      "trajectory": "[{x,y,t}]|null" }   // normalized, ≤60 pts, post-migration-3
  ],
  "zone": { "id": "str", "name": "str", "kind": "str", "zone_type": "str" },  // or null
  "source": { "id": "str", "label": "str", "type": "str", "lat": "float|null", "lng": "float|null" },
  "evidence": [ { "kind": "str", "path": "str", "exists": "bool" } ],
  "metadata": { ... },             // raw event metadata: heuristic score breakdowns,
                                   // reid global_person_id + identity_cameras, ocr fields
  "session_summary": { ... }        // generate_session_summary dict, only when session_id given
}
```

Rules: absent → field omitted or `"Not available"` (existing summary discipline); nothing computed beyond existing DAO reads; snapshot pixels are NOT sent (no multimodal dependency — the LLM reasons over structured records only).

---

## 5. SYSTEM PROMPT SKELETON (≤300 words)

```
You are Hermes, the reasoning assistant embedded in TRINETRA, a
video-analytics console. You receive machine-verified structured
context about surveillance events and an operator's question.

RULES:
1. Ground every claim in the provided context. Never invent facts,
   names, identities, plate numbers, times, or locations.
2. Tag every statement: [OBSERVED] = directly stated in context;
   [DERIVED] = computed by you from context; [INFERRED] = your
   hypothesis — mark it with hedged language ("may", "possibly").
3. Re-ID results are "possible matches" with similarity scores.
   NEVER claim "same person" or any identity. Face data is
   detection-only; no identity records exist in this system.
4. Heuristic events (SUSPECTED_*, crowd counts, OCR_UNCERTAIN)
   are probabilistic detector output, not ground truth. Never
   express certainty based on them.
5. ANPR reads with confidence < 0.80 are uncertain. Never repair
   or complete a plate string.
6. If the context does not answer the question, say exactly what
   is missing and what data would be needed. Refusal is correct
   behavior, not failure.
7. Answer briefly, in plain language. Reference context fields by
   name where useful (track #4, zone "North", severity HIGH).
8. You have no access to video pixels — only structured records.
   Do not describe visual details absent from the context.
9. Never claim you watched the video, ran detection, or have
   capabilities beyond reading this context.
```

(~200 words.)

---

## 6. RISKS / NOTES

- **Gateway is a floor machine service** — not guaranteed up at demo time. The §3 honest-unavailable path is therefore not optional; it ships in the same phase.
- **Model routing volatility**: one probed free model was dead upstream. Use `auto/*` routes (verified `auto/glm` works) and keep `HERMES_MODEL` configurable.
- **Rate limits**: this floor is rate-limited; the backend proxy must not poll aggressively (60s status cache; ask is operator-triggered, low volume).
- **Reasoning-model response shape**: `choices[0].message.content` is the answer; `reasoning`/`reasoning_details` fields may be present — ignore them.
- **No multimodal**: evidence snapshots stay server-side; the LLM sees structured records only (also keeps context payloads small).

## 7. VERDICT

**P-HERMES builds the LIVE chat layer** — endpoint verified working (PING_OK through `auto/glm` → `z-ai/glm-5.1`), zero new deps (httpx 0.28.1 in venv), OpenAI-compatible API — **with the §3 honest-unavailable fallback as a mandatory companion**, because the gateway is a laptop service that will be down at some demos. Canned responses remain forbidden; the deterministic EventSummary stays the always-available explanation layer.
