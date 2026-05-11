"""Behavior tests for the custom CCR `extrathinktag` transformer.

The transformer at `roles/claude_code_router/files/extra-think-tag.js`
strips `<think>...</think>` reasoning blocks from OpenAI-format chat
responses so they don't leak into the Claude Code harness context when
routing through claude-code-router. CCR 1.0.73's built-in registry has no
equivalent transformer (the legacy musistudio/llms `extrathinktag` was
dropped during the v1→v2 refactor), so this is a clauded-shipped module.

Tests exercise the module by spawning `node` against a small driver that
constructs synthetic Web Fetch `Response` objects (JSON and SSE), runs
them through `transformResponseOut`, and prints the result back. We
verify:

  - JSON responses have <think>...</think> stripped from message.content
  - SSE delta.content is stripped with state preserved across chunks
  - SSE delta.reasoning_content is dropped
  - A `<think>` tag split across two SSE frames is still stripped cleanly
  - Streams without any `<think>` content are passed through unchanged

Skipped if `node` is not on PATH (Node 18+ is required for the global
Response / ReadableStream / TextDecoder APIs used by the transformer).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSFORMER = (
    REPO_ROOT / "src/clauded/roles/claude_code_router/files/extra-think-tag.js"
)

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node not on PATH — required to exercise the JS transformer",
)


def _run_driver(*, content_type: str, body: str) -> tuple[str, str]:
    """Run `transformResponseOut` over a synthetic Response. Returns
    (resulting_content_type, resulting_body_text)."""
    driver = textwrap.dedent(
        f"""
        'use strict';
        const Transformer = require({json.dumps(str(TRANSFORMER))});
        const t = new Transformer();
        const upstream = new Response(
          {json.dumps(body)},
          {{ status: 200, headers: {{ 'Content-Type': {json.dumps(content_type)} }} }}
        );
        (async () => {{
          const out = await t.transformResponseOut(upstream);
          const text = await out.text();
          process.stdout.write(JSON.stringify({{
            contentType: out.headers.get('Content-Type') || '',
            body: text,
          }}));
        }})().catch((e) => {{
          process.stderr.write(String(e && e.stack || e));
          process.exit(1);
        }});
        """
    )
    proc = subprocess.run(
        ["node", "-e", driver],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    payload = json.loads(proc.stdout)
    return payload["contentType"], payload["body"]


def _sse(*deltas: dict) -> str:
    """Build a synthetic OpenAI-format SSE body from a sequence of delta
    objects. Each delta becomes one `data: { ... }` frame; the stream
    terminates with `data: [DONE]`."""
    lines: list[str] = []
    for delta in deltas:
        frame = {"choices": [{"index": 0, "delta": delta}]}
        lines.append("data: " + json.dumps(frame))
        lines.append("")
    lines.append("data: [DONE]")
    lines.append("")
    return "\n".join(lines)


def _parse_sse(body: str) -> list[dict]:
    """Extract delta objects from data: frames; ignores [DONE] sentinel."""
    out: list[dict] = []
    for line in body.split("\n"):
        if not line.startswith("data:"):
            continue
        payload = line[len("data:") :].strip()
        if not payload or payload == "[DONE]":
            continue
        frame = json.loads(payload)
        for c in frame.get("choices", []):
            out.append(c.get("delta", {}))
    return out


def test_json_strips_think_tag() -> None:
    body = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "<think>internal reasoning</think>Final answer.",
                        "reasoning_content": "extra reasoning field",
                    }
                }
            ]
        }
    )
    ctype, out = _run_driver(content_type="application/json", body=body)
    parsed = json.loads(out)
    msg = parsed["choices"][0]["message"]
    assert msg["content"] == "Final answer."
    assert "reasoning_content" not in msg


def test_sse_strips_think_in_single_delta() -> None:
    body = _sse(
        {"content": "<think>plotting</think>Hello, world!"},
        {"content": ""},
    )
    _, out = _run_driver(content_type="text/event-stream", body=body)
    contents = [d.get("content", "") for d in _parse_sse(out)]
    assert "".join(contents) == "Hello, world!"
    assert "<think>" not in out
    assert "plotting" not in out


def test_sse_strips_think_split_across_deltas() -> None:
    body = _sse(
        {"content": "<thi"},
        {"content": "nk>secret rea"},
        {"content": "soning</thi"},
        {"content": "nk>Visible content."},
    )
    _, out = _run_driver(content_type="text/event-stream", body=body)
    contents = [d.get("content", "") for d in _parse_sse(out)]
    assert "".join(contents) == "Visible content."
    assert "secret" not in out
    assert "<think" not in out


def test_sse_drops_reasoning_content_field() -> None:
    body = _sse(
        {"reasoning_content": "should not survive", "content": "kept"},
    )
    _, out = _run_driver(content_type="text/event-stream", body=body)
    deltas = _parse_sse(out)
    assert all("reasoning_content" not in d for d in deltas)
    assert "should not survive" not in out
    assert "kept" in out


def test_sse_passthrough_without_think_tag() -> None:
    body = _sse(
        {"role": "assistant", "content": ""},
        {"content": "Hello"},
        {"content": ", world!"},
        {"finish_reason": "stop"},
    )
    _, out = _run_driver(content_type="text/event-stream", body=body)
    contents = [d.get("content", "") for d in _parse_sse(out)]
    assert "".join(contents) == "Hello, world!"


def test_sse_unterminated_think_is_dropped() -> None:
    # Model crashes mid-reasoning — no closing tag. The opened think block
    # contents must not appear in the output; the stream ends cleanly.
    body = _sse(
        {"content": "<think>partial reasoning"},
        {"content": " continues..."},
    )
    _, out = _run_driver(content_type="text/event-stream", body=body)
    contents = [d.get("content", "") for d in _parse_sse(out)]
    assert "partial reasoning" not in out
    assert "continues" not in out
    assert "".join(contents) == ""


def test_non_stream_non_json_passthrough() -> None:
    # Unknown content type: pass through untouched.
    body = "raw text body"
    ctype, out = _run_driver(content_type="text/plain", body=body)
    assert ctype.startswith("text/plain")
    assert out == body


def test_transformer_exposes_correct_name() -> None:
    # CCR's dynamic loader requires `instance.name` to register the
    # transformer under the key referenced from `transformer.use`. Verify
    # the constructed instance reports the expected name.
    driver = textwrap.dedent(
        f"""
        const Transformer = require({json.dumps(str(TRANSFORMER))});
        process.stdout.write(new Transformer().name);
        """
    )
    proc = subprocess.run(
        ["node", "-e", driver],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert proc.stdout == "extrathinktag"
