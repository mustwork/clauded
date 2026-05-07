# claude-code-router (CCR)

clauded can run a per-session [claude-code-router](https://github.com/musistudio/claude-code-router) inside the VM that lets the `claude` client reach Ollama models on the host, curated third-party OpenAI-compatible providers, and the Anthropic API through a single local endpoint. CCR replaces the previous LiteLLM-based proxy (see `docs/litellm-issues-for-maintainers.md` on the `litellm-proxy-archive` branch for why we moved).

## What it does

When the feature is enabled, every `clauded`-launched `claude-code` session:

1. Starts a CCR process on `127.0.0.1:3456` (loopback-only) via the `clauded-ccr-with` wrapper script.
2. Sets `ANTHROPIC_BASE_URL=http://127.0.0.1:3456` so the Claude client routes through the proxy.
3. Forwards the user's OAuth token (subscription) or `ANTHROPIC_API_KEY` to the proxy via the process environment so the Anthropic passthrough provider can authenticate.

The proxy is **per-session** — it starts when you run `clauded` and exits when you leave the session. There is no systemd service.

## Configuration

Add to `.clauded.yaml`:

```yaml
vm:
  claude_code_router:
    enabled: true
```

To enable curated providers and per-model overrides:

```yaml
vm:
  claude_code_router:
    enabled: true
    providers:
      - groq
      - minimax
    overrides:
      haiku: ollama/qwen3:latest          # local Ollama model (auto-discovered)
      sonnet: groq/llama-3.3-70b-versatile
      opus: minimax/MiniMax-M2.7
  # Forward your provider API keys into the VM (the wrapper sets them in the
  # CCR process environment; CCR resolves them via ${VAR} interpolation in
  # config.json — never written to disk).
  forward_env:
    - GROQ_API_KEY
    - MINIMAX_API_KEY
```

Or use the interactive wizard — the CCR prompt appears after harness selection when `claude-code` is your harness.

## Curated providers

| Provider | OpenAI-compatible endpoint | Required env var |
|---|---|---|
| MiniMax | `https://api.minimax.io/v1/chat/completions` | `MINIMAX_API_KEY` |
| Groq | `https://api.groq.com/openai/v1/chat/completions` | `GROQ_API_KEY` |
| Together AI | `https://api.together.xyz/v1/chat/completions` | `TOGETHER_API_KEY` |

Anthropic passthrough is always active — `claude-*` model names that aren't intercepted by an override are forwarded to `api.anthropic.com` with `${ANTHROPIC_API_KEY}` from the proxy environment. Ollama models are auto-discovered at provision time from `host.lima.internal:11434`.

API keys must be exported on the host shell before running `clauded` and listed in `vm.forward_env`.

## Override syntax

Each `overrides.<key>` value uses `<provider>/<model>` syntax. The provider must match a configured CCR Provider name (`anthropic`, `ollama`, `groq`, `minimax`, `together`). Examples:

- `ollama/qwen3:latest` → routes to the auto-discovered Ollama provider on the host
- `groq/llama-3.3-70b-versatile` → routes to Groq (requires `GROQ_API_KEY` forwarded)
- `minimax/MiniMax-M2.7` → routes to MiniMax (requires `MINIMAX_API_KEY` forwarded)
- `anthropic/claude-haiku-4-5` → explicit Anthropic passthrough (rare; passthrough is the default)

## Routing semantics

CCR's built-in router has only one model-name pattern match (`background` for any model containing both "claude" and "haiku"). To support per-model routing for sonnet and opus, the role generates a small custom router at `/etc/clauded/ccr-router.js` that pattern-matches Anthropic model names against the configured overrides:

1. Override matches → route to the configured `<provider>,<model>`.
2. No override but model starts with `claude-` → forward to the `anthropic` provider with the original model name preserved.
3. Anything else → fall back to CCR's built-in routing (`Router.default`, `think`, `longContext`, etc.).

The custom router is written from `vm.claude_code_router.overrides` at provision time and re-rendered on `clauded --reprovision`.

## Limitations

- **Anthropic provider's `models[]` is a fixed list.** The role enumerates current Claude generations (haiku/sonnet/opus 4-5/4-6/4-7, 3-5/3-7 dated variants). New model names that aren't in the list will fail at the proxy with `provider not found`. Edit the role's generated config or extend `models[]` if you need a model not on the list.
- **Tool use with Ollama is model-dependent.** qwen2.5-coder, qwen3-coder, and llama3.1 generally work; gpt-oss models are known broken (musistudio/claude-code-router#790). Test with your specific Ollama model before relying on it for agentic flows.
- **Sonnet/opus name-based overrides go through `CUSTOM_ROUTER_PATH`.** CCR's built-in router doesn't pattern-match those names; clauded's small JS router handles them.

## Version pin

The role pins CCR to **1.0.73** (last 1.x release, 2025-12-18). v2.0.0 (2026-01-04) is a major refactor with active regressions on Ollama routing as of 2026-05 (musistudio/claude-code-router#1379, #1166). Bump `ccr_version` in `roles/claude_code_router/defaults/main.yml` only after verifying the haiku→Ollama tool-use smoke test still works against the newer release.

## Manual smoke test

```sh
# Host: ensure Ollama is running with at least one tool-capable model
ollama pull qwen2.5-coder:7b
ollama list

# Enable in .clauded.yaml, then reprovision:
clauded --reprovision

# Launch a session; the wrapper starts CCR automatically:
clauded
# In the claude-code TUI, ask: "list all files in this directory"
# A successful response means the haiku→Ollama tool round-trip worked.
```

If the proxy fails to start, check `/tmp/clauded-ccr.log` and `~/.claude-code-router/logs/`.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `clauded-ccr-with: claude-code-router did not become healthy within 60s` | Port 3456 in use, npm install failed, or config rejected | `ss -tlnp`; check `/tmp/clauded-ccr.log`; reprovision |
| Provider models missing from CCR config | API key not forwarded or not set on host | Add the key to `vm.forward_env` and `export` it before running `clauded` |
| Ollama models missing | Host Ollama was not running at provision time | Re-provision with `ollama serve` running |
| `provider 'undefined' not found` | The model name in `req.body.model` doesn't match any configured Provider | Add the model to the relevant Provider's `models[]` in the role, or use an explicit `provider,model` override |
