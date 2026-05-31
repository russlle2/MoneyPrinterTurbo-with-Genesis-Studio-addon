# Local LLM Setup (Genesis Studio)

Genesis Studio supports local language model servers as the creative brain for
script generation.  When a local model is configured and reachable, it replaces
the built-in Viral Spine template engine.  When the model is offline, disabled,
or returns unrecognised output, Genesis automatically falls back to the
deterministic template engine — the workflow never crashes.

## Privacy

- `genesis/config/local_llm.json` is **gitignored** — never committed.
- `genesis/config/local_llm.example.json` is safe to commit (placeholder values only).
- This phase does **not** call any paid hosted APIs.
- Use professional naming in configs: "private local model", "custom local model", or "creative model".

## Quick Setup

1. Copy `local_llm.example.json` → `local_llm.json`
2. Set `"enabled": true`
3. Choose your backend and set `endpoint_url` and `model`
4. Run a quick check:

```bash
python -c "
from genesis.integrations.local_llm_provider import local_llm_ready
print(local_llm_ready())
"
```

---

## Backend Examples

### 1. Ollama

```json
{
  "enabled": true,
  "backend": "ollama",
  "endpoint_url": "http://localhost:11434/api/generate",
  "model": "llama3.1",
  "timeout_seconds": 120,
  "max_tokens": 1200,
  "temperature": 0.7
}
```

Start Ollama: `ollama serve` then `ollama pull llama3.1`

---

### 2. LM Studio (local server)

```json
{
  "enabled": true,
  "backend": "lmstudio",
  "endpoint_url": "http://localhost:1234/v1/chat/completions",
  "model": "local-model",
  "timeout_seconds": 120,
  "max_tokens": 1200,
  "temperature": 0.7
}
```

In LM Studio: Load a model → Server tab → Start server on port 1234.

---

### 3. llama.cpp server

```json
{
  "enabled": true,
  "backend": "llama_cpp_server",
  "endpoint_url": "http://localhost:8080/completion",
  "model": "local-llama",
  "timeout_seconds": 180,
  "max_tokens": 1200
}
```

Start: `./server -m your-model.gguf --port 8080`

---

### 4. text-generation-webui

```json
{
  "enabled": true,
  "backend": "text_generation_webui",
  "endpoint_url": "http://localhost:5000/api/v1/generate",
  "model": "local-model",
  "timeout_seconds": 120,
  "max_tokens": 1200
}
```

Start with `--api` flag enabled.

---

### 5. Custom HTTP endpoint

```json
{
  "enabled": true,
  "backend": "custom_http",
  "endpoint_url": "http://localhost:8000/generate",
  "model": "custom-local",
  "timeout_seconds": 120,
  "max_tokens": 1200,
  "temperature": 0.7
}
```

The custom endpoint should accept a POST with JSON body and return one of the
supported response shapes (Ollama / OpenAI-compatible / TGWUI / `{"text": "..."}`).

---

## Environment variable overrides

All settings can be overridden without editing the JSON file:

```bash
GENESIS_LOCAL_LLM_ENABLED=true
GENESIS_LOCAL_LLM_BACKEND=ollama
GENESIS_LOCAL_LLM_ENDPOINT_URL=http://localhost:11434/api/generate
GENESIS_LOCAL_LLM_MODEL=llama3.1
GENESIS_LOCAL_LLM_TIMEOUT_SECONDS=120
GENESIS_LOCAL_LLM_MAX_TOKENS=1200
GENESIS_LOCAL_LLM_TEMPERATURE=0.7
GENESIS_LOCAL_LLM_DEBUG_PROMPTS=false
```

## Fallback behaviour

| Situation | Outcome |
|-----------|---------|
| `enabled: false` | Template fallback used. Workflow completes normally. |
| Model server unreachable | Template fallback used. `fallback_reason` recorded in `ScriptPackage`. |
| Model returns invalid JSON | Template fallback used. |
| Model output partially parseable | Best-effort merge with template fallback for missing fields. |

The `script_source` field in `script_package.json` tells you which path was used:
- `"local_llm"` — your private local model generated the script
- `"template_fallback"` — deterministic Viral Spine engine was used
