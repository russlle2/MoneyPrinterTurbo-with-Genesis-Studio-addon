# ElevenLabs local setup (Genesis Studio)

Your real ElevenLabs credentials must stay on this machine only.

## Where to put secrets

1. **Preferred:** copy `elevenlabs.example.json` to `genesis/config/elevenlabs.json` and fill in your API key and voice ID.
2. **Alternative:** set environment variables (they override the JSON file):
   - `GENESIS_ELEVENLABS_API_KEY`
   - `GENESIS_ELEVENLABS_VOICE_ID`
   - optional: `GENESIS_ELEVENLABS_VOICE_NAME`, `GENESIS_ELEVENLABS_MODEL_ID`, `GENESIS_ELEVENLABS_OUTPUT_FORMAT`

## Git safety

- `genesis/config/elevenlabs.json` is **gitignored** — do not commit it.
- Only `elevenlabs.example.json` (placeholders) belongs in the repo.
- Never paste API keys into Python source, tests, logs, or markdown docs.

## Voice replica

After saving config, Genesis uses your saved `voice_id` automatically when the pipeline calls `generate_narration_from_script()` (no need to pass `voice_id` each time).

## Quick check

```text
python -c "from genesis.integrations.voice_provider import voice_backend_ready; print(voice_backend_ready())"
```

When ready, the first argument is `True`.
