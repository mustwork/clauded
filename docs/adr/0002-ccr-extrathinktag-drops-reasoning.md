# ADR 0002: CCR extrathinktag transformer drops reasoning rather than surfacing it as Anthropic thinking blocks

**Status**: Accepted
**Date**: 2026-05-11
**Type**: Lightweight
**Affects**: src/clauded/roles/claude_code_router/
**Supersedes**: none
**Superseded by**: none

## Context

When clauded routes Claude Code traffic through claude-code-router (CCR) to a non-Anthropic provider that emits `<think>...</think>` reasoning blocks in its OpenAI-format chat responses (notably MiniMax M2.x), the reasoning leaks verbatim into `delta.content` and survives the downstream OpenAI→Anthropic SSE conversion. The harness then renders the raw tags as part of the assistant's visible text, polluting the context window.

The clauded provisioner already shipped a custom JavaScript transformer at `/etc/clauded/extra-think-tag.js` (loaded via CCR's top-level `transformers: [{ path }]` array and referenced as `"use": ["extrathinktag"]` from the `minimax` provider block). The transformer strips `<think>...</think>` from both JSON and SSE responses and discards any parallel `delta.reasoning_content` field. This stops the leak but means the reasoning content is dropped entirely — Claude Code never sees it, even as a collapsed thinking block.

A higher-fidelity alternative is technically available. CCR 1.0.73's bundled Anthropic transformer (`transformResponseIn`, the OpenAI→Anthropic SSE converter) has a handler that recognizes a custom `delta.thinking.{content,signature}` shape and emits proper Anthropic `content_block_start` / `thinking_delta` / `signature_delta` / `content_block_stop` frames. This is the same shape that the legacy `musistudio/llms` `extrathinktag` transformer produced before the v1→v2 refactor dropped it. If we rewrote our transformer to emit segmented `delta.thinking` frames instead of stripping, reasoning would round-trip and surface in Claude Code as native thinking blocks.

The rewrite is non-trivial:

- The stripper must return ordered segments (text / thinking / signature) rather than a single concatenated string, so the original interleaving of `text → think → text` within a single OpenAI delta is preserved when fanning out to multiple SSE frames.
- CCR's Anthropic transformer has a sticky `T` flag (thinking-block-opened) that is never reset after `signature_delta`. This means at most one thinking block per stream is supported correctly; a second `<think>` block would fire `thinking_delta` events against `index=-1` and produce malformed Anthropic SSE. Fixing it requires a sentinel-asserted text patch against the bundled `cli.js` analogous to the `useBearer` patch in `tasks/main.yml:46`.
- Signatures on the Anthropic API are server-attestation strings for reasoning verification. For non-Anthropic upstreams we have no real signature; emitting a synthetic timestamp string works for one-way display but means cached or replayed assistant turns cannot be verified by the API.
- Test surface grows from ~8 cases to ~15+: ordered-segment assertions across mixed `text/think/text` deltas, signature-emission assertions, and tests guarding the CCR patch.

## Decision

Ship the strip-and-drop transformer as the long-term behavior. Do not invest in the rewrite that surfaces reasoning as Anthropic thinking blocks.

`src/clauded/roles/claude_code_router/files/extra-think-tag.js` remains as written — `<think>...</think>` content is removed from `delta.content` / `message.content` and any `reasoning_content` field is deleted, with no compensating thinking-block emission.

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| Rewrite transformer to emit `delta.thinking.{content,signature}` segments | Buys reasoning visibility at the cost of ~70 lines of stateful streaming code, a CCR bundle patch to reset the `T` flag, a synthetic-signature scheme with unclear API-cache implications, and roughly doubled test surface. Reasoning visibility is a UX nicety on a non-default routing path; it does not justify the new failure modes (single-block limit on unpatched CCR, malformed SSE on multi-think models, brittle text-patch drift across CCR versions). |
| Patch CCR's Anthropic transformer to read `delta.reasoning_content` directly | OpenAI-standard field would skip the custom-shape detour. But the Anthropic transformer's SSE handler is heavily minified and the patch surface is much larger than the `useBearer` one-liner; every CCR version bump would risk silent no-op. Same UX-vs-fragility tradeoff as above, with more carrying cost. |
| Accept the leak and remove the transformer | Reasoning would render as raw `<think>...</think>` text in the harness, both visually noisy and consuming context budget. Strictly worse than the current behavior. |

## Consequences

**Positive**:
- Stable behavior: stripping is purely defensive and the transformer's surface area is small (one file, well-tested, no CCR coupling beyond `transformResponseOut`).
- No CCR bundle patch beyond the existing `useBearer` flip — fewer text-replace landmines on CCR version bumps.
- Test suite remains compact and stays inside `node -e` subprocess invocations from pytest (no JS test runner pulled in).
- Works uniformly across MiniMax, future providers that emit inline `<think>`, and providers using the structured `reasoning_content` field.

**Negative**:
- Reasoning is not visible to the user. Models that "show their work" via `<think>` blocks effectively become opaque-output models when routed through clauded's CCR layer.
- Token spend for the reasoning is paid on the upstream side and discarded — no caching benefit, no debug visibility.
- Differs from native Anthropic behavior, where extended-thinking models surface reasoning as collapsible thinking blocks in Claude Code's UI. Users may notice this gap when comparing MiniMax-via-CCR to direct Anthropic.

**Accepted Risks**:
- If a future MiniMax (or similar) model emits multi-paragraph chain-of-thought that materially improves answer quality, users won't be able to inspect that reasoning. Acceptable because (a) the answer quality is preserved, (b) upstream provider logs still capture it for diagnostic use, and (c) the CCR routing path is opt-in.

## Evolution Triggers

Reopen this ADR if any of the following hold:

- CCR upstream (or our pin) gains a built-in `extrathinktag`-equivalent transformer with proper thinking-block emission, removing the rewrite cost on our side.
- Multiple users explicitly request reasoning visibility on CCR-routed sessions (signal: GitHub issues, BACKLOG findings, or recurring questions about "where did MiniMax's thinking go").
- A non-MiniMax provider with materially better reasoning emission (e.g. multi-block, structured) becomes the dominant override target and the single-block CCR limitation stops being a blocker.

## References

- Origin: direct via `/base:adr`
- Related ADRs: none
- Related specs: none
- Code: `src/clauded/roles/claude_code_router/files/extra-think-tag.js`, `src/clauded/roles/claude_code_router/tasks/main.yml`
- Tests: `tests/test_ccr_extrathinktag_transformer.py`
- Upstream evidence: `delta.thinking.{content,signature}` handler in CCR 1.0.73 bundled cli.js (the only `thinking_delta` emission site in the bundle); legacy musistudio/llms `extrathinktag.transformer.ts` (removed in v2 refactor).
