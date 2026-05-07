# Configurable Router Host Overrides

## Summary

Allow `.clauded.yaml` to override the upstream URLs that the `claude_code_router` role bakes into the generated CCR config. Today the Ollama host and every curated provider's endpoint URL are hardcoded inside the role and reachable only by editing role files. This blocks legitimate workflows: remote/non-Lima Ollama, regional provider endpoints, on-prem proxies, and air-gapped routing.

The feature must keep the existing zero-configuration default working unchanged — users who don't override anything continue to get the current behavior — while letting users who need different upstreams declare them in their config without forking the role.

## Background

The `vm.claude_code_router` block currently surfaces three things: `enabled`, `providers` (curated whitelist), and per-model `overrides` (string `<provider>/<model>` syntax). The actual upstream URL each provider name resolves to is fixed in the role:

- **Ollama**: `http://host.lima.internal:11434` (Lima magic hostname for the Mac host)
- **MiniMax**: `https://api.minimax.io/v1/chat/completions`
- **Groq**: `https://api.groq.com/openai/v1/chat/completions`
- **Together AI**: `https://api.together.xyz/v1/chat/completions`

These defaults serve the common case (developer on a Mac with Ollama on the same machine, using each provider's public OpenAI-compatible endpoint). They break for:

- Users running Ollama on a different machine on the LAN, on a remote server, or behind a tunnel.
- Users in regions where a provider exposes a different endpoint (e.g., MiniMax has both China and international URLs).
- Teams routing all outbound traffic through a corporate proxy that proxies provider APIs at internal URLs.
- Air-gapped or self-hosted deployments that mirror provider APIs behind their own gateway.

The gap was flagged earlier and not carried over into the CCR pivot. This epic addresses it.

## Problem Statement

Users cannot override the upstream URL for any router-managed provider without editing files inside the `roles/claude_code_router/` directory. Such edits don't survive package upgrades and don't persist across `.clauded.yaml`-driven setups, defeating the goal of a declarative project config.

## Requirements

### R1 — Ollama host override

`.clauded.yaml` MUST accept an optional URL that replaces the role's default Ollama upstream. When unset, the existing default applies.

The override MUST:

- Be a valid HTTP(S) URL.
- Be used both for the provision-time model probe (so auto-discovery hits the configured host) and the runtime `Provider.api_base_url` rendered into CCR's config.
- Default to the Lima magic-hostname URL when absent, identical to today's behavior.

### R2 — Per-curated-provider URL override

`.clauded.yaml` MUST accept optional URL overrides for each curated provider name (`minimax`, `groq`, `together`, plus any future curated additions). When unset for a given provider, the role's compiled default applies.

A user MUST be able to override one provider's URL without affecting any other, and without enumerating every provider.

### R3 — Validation

The configuration loader MUST raise `ConfigValidationError` at load time for:

- Non-string URL values.
- Empty-string URL values.
- URLs that don't begin with `http://` or `https://` (a sanity check; the loader is not a full URL validator).
- URL keys for unknown curated providers (drift-detector against the whitelist).

Validation runs at config-load time, not at provision time — surfaces typos immediately on `clauded` invocation rather than after VM boot.

### R4 — Wizard non-handling

The wizard MUST NOT prompt for these URLs. They are an advanced-use override; the curated UX goes through `providers:` and `overrides:`. Users who need URL overrides edit `.clauded.yaml` directly.

`clauded --edit` MUST round-trip URL overrides through the wizard untouched: if the YAML had them set on entry, they are preserved on save.

### R5 — YAML round-trip and schema visibility

Setting a URL override and saving via `Config.save()` MUST emit the override to YAML in a stable, documented location under `vm.claude_code_router`.

The schema location MUST be documented in `docs/claude-code-router.md` with a worked example for at least Ollama and one curated provider.

### R6 — Anthropic upstream is out of scope

The Anthropic passthrough URL (`https://api.anthropic.com/v1/messages`) is NOT part of this override surface. Routing claude-code to a non-Anthropic Anthropic-API-compatible upstream is a different concern (proxy chaining, custom auth) and is deliberately excluded from this epic.

## Schema sketch

The exact key naming is a design decision left to implementation, but the schema MUST cluster the URL overrides under `vm.claude_code_router` so the existing block remains the single source of truth for proxy configuration. One viable shape:

```yaml
vm:
  claude_code_router:
    enabled: true
    providers:
      - minimax
    overrides:
      haiku: ollama/qwen3:latest
      sonnet: minimax/MiniMax-M2.7
    hosts:
      ollama:   http://10.0.0.5:11434          # remote Ollama on LAN
      minimax:  https://api.minimax.io/v1/chat/completions
      groq:     https://corporate-proxy.example/groq/openai/v1/chat/completions
  forward_env:
    - MINIMAX_API_KEY
    - GROQ_API_KEY
```

A flatter alternative (e.g., `ollama_host:` at top level + per-provider keys) is acceptable if implementation surfaces a clear validation story for unknown keys. The key requirement is that overrides are namespaced — they cannot collide with other `vm.claude_code_router` fields.

## Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-001 | A `.clauded.yaml` with the new Ollama host override loads without error and the rendered `~/.claude-code-router/config.json` reflects the override (both probe target and `api_base_url`). |
| AC-002 | A `.clauded.yaml` with one curated provider's URL overridden loads cleanly; other providers retain their defaults. |
| AC-003 | A `.clauded.yaml` *without* any host override loads identically to a current config (round-trip preserves emptiness; defaults kick in at the role). |
| AC-004 | A non-string URL value (number, list, null) raises `ConfigValidationError` naming the offending key. |
| AC-005 | A URL value not prefixed with `http://` or `https://` raises `ConfigValidationError` naming the offending key. |
| AC-006 | A URL override under an unknown curated provider name raises `ConfigValidationError` listing the accepted names. |
| AC-007 | `Config.save()` round-trip preserves all set URL overrides verbatim. |
| AC-008 | `clauded --edit` over a YAML with URL overrides preserves them through the wizard's non-interactive merge path. |
| AC-009 | The wizard does NOT prompt for URL overrides on either initial run or `--edit`. |
| AC-010 | `docs/claude-code-router.md` documents the new schema with at least one Ollama and one curated-provider example. |
| AC-011 | A CHANGELOG `[Unreleased]` entry under `### Added` describes the new keys with sensible-default semantics. |
| AC-012 | The Ollama probe (the role task that pre-fetches the model list) targets the configured override URL when set. |
| AC-013 | When the configured Ollama host is unreachable, provisioning continues with an empty Ollama models list and emits the existing "host Ollama unreachable" warning — same fallback as today. |

## Out of Scope

- **Per-`overrides` `api_base` overrides.** Setting a custom URL for a *single model override* (e.g., `overrides.haiku.api_base`) is a more invasive schema change and a separate feature.
- **Custom transformers per provider.** CCR supports `transformer: { use: [...] }` per Provider; surfacing that via YAML is a separate epic.
- **Custom curated-provider definitions.** Letting users add a brand-new provider (`{name, api_base_url, api_key, models}`) entirely from YAML is a separate epic.
- **Anthropic upstream override** (R6).
- **Host-side network plumbing.** The pre-existing `epic-ollama-host-proxy/` epic addresses guest-localhost forwarding from a different angle and is independent.

## Non-functional Considerations

- **No API keys in any override.** URL overrides are non-secret; `api_key:` continues to come from the proxy process environment via CCR's `${VAR}` interpolation. The boundary rule "no API key values written to any file" is preserved.
- **Backward compatibility.** Existing `.clauded.yaml` files without any URL overrides MUST behave identically to the current implementation. No silent migration of LiteLLM-era keys (those are already dead schema).
- **Failure modes are visible.** Misconfigured URLs surface either at config load (typos, scheme issues) or at runtime via the existing role warning ("host Ollama unreachable") and CCR's own logs. No new silent-failure modes are introduced.

## Open Questions

1. **Schema shape**: nested `hosts:` block vs. flat `ollama_host:` + per-provider keys vs. extending each provider entry to be an object. Pick one during implementation; the differences are mostly ergonomic.
2. **Curated provider URL drift**: if upstream provider URLs change (regional remappings, new versions), the role's hardcoded defaults can go stale. Should the override mechanism *also* be the recommended way to pin a known-good URL, or do we keep the defaults as "best effort, user overrides if broken"? Answer affects how prominent we make this in user-facing docs.
3. **Deprecation of role-default URLs**: long-term, should curated provider URLs always be overridable per project, with the role only carrying a "last-known-good" hint? Probably yes, but out of scope for this epic.
