'use strict';

// extra-think-tag.js — CCR custom transformer.
//
// Strips <think>...</think> reasoning blocks emitted by some upstream
// models (notably MiniMax M2.x) from OpenAI-format chat responses so they
// never reach the Anthropic-formatted client stream and pollute the
// Claude Code harness context window.
//
// Context: CCR 1.0.73's built-in transformer registry has no equivalent.
// The legacy `extrathinktag` transformer from musistudio/llms was dropped
// during the v1→v2 refactor; configs that reference it by name are
// silently filtered out when the lookup misses (the unknown-name guard is
// `.filter(s => typeof s < "u")`). Without this module, MiniMax M2.x
// `<think>` content lands verbatim in `delta.content` and survives the
// downstream OpenAI→Anthropic SSE conversion.
//
// Wiring: loaded via the top-level `transformers: [{ path }]` array in
// CCR config.json. Provider configs that need stripping reference it as
// `"transformer": { "use": ["extrathinktag"] }`. The pipeline in
// claude-code-router (function m0) iterates the provider's `use` array
// in reverse and applies each `transformResponseOut` before the Anthropic
// transformer's `transformResponseIn` converts OpenAI SSE → Anthropic SSE,
// so this module operates on OpenAI-format frames.
//
// Behavior:
//   - JSON responses (application/json): regex-strip `<think>...</think>`
//     from each `choices[].message.content`. Deletes a parallel
//     `reasoning_content` field if present.
//   - SSE responses (text/event-stream): line-buffered FSM that parses
//     `data: { ... }` payloads, mutates each `delta.content` through a
//     stateful stripper that tolerates tags split across SSE frames, and
//     drops `delta.reasoning_content` unconditionally.
//
// Reasoning text is dropped rather than re-emitted as Anthropic
// `thinking_delta` blocks. A round-trip is technically available — CCR's
// bundled Anthropic transformer recognises a custom
// `delta.thinking.{content,signature}` shape and converts it into proper
// Anthropic SSE thinking frames — but the rewrite carries non-trivial
// cost (ordered-segment streaming, a CCR bundle patch to lift the
// single-thinking-block-per-stream limit, synthetic signatures, larger
// test surface) for what amounts to a UX nicety on a non-default routing
// path. See docs/adr/0002-ccr-extrathinktag-drops-reasoning.md for the
// full tradeoff and the conditions that would trigger a re-evaluation.

const OPEN_TAG = '<think>';
const CLOSE_TAG = '</think>';

// Longest suffix of `s` starting at `from` that could be a prefix of
// `target`. Used to defer emitting a tail that might complete into a tag
// once the next chunk arrives.
function tailPrefixOf(s, from, target) {
  const maxLen = Math.min(s.length - from, target.length - 1);
  for (let len = maxLen; len > 0; len--) {
    const tail = s.slice(s.length - len);
    if (target.startsWith(tail)) return s.length - len;
  }
  return -1;
}

// Per-stream state machine. The model's reasoning may straddle multiple
// delta.content chunks; state is preserved across feed() calls.
function makeStripper() {
  let mode = 'SEARCHING'; // 'SEARCHING' | 'THINKING'
  let partial = '';

  return {
    feed(chunk) {
      const s = partial + (chunk || '');
      partial = '';
      let out = '';
      let i = 0;
      while (i < s.length) {
        if (mode === 'SEARCHING') {
          const idx = s.indexOf(OPEN_TAG, i);
          if (idx < 0) {
            const tail = tailPrefixOf(s, i, OPEN_TAG);
            if (tail >= 0) {
              out += s.slice(i, tail);
              partial = s.slice(tail);
            } else {
              out += s.slice(i);
            }
            i = s.length;
          } else {
            out += s.slice(i, idx);
            i = idx + OPEN_TAG.length;
            mode = 'THINKING';
          }
        } else {
          const idx = s.indexOf(CLOSE_TAG, i);
          if (idx < 0) {
            const tail = tailPrefixOf(s, i, CLOSE_TAG);
            if (tail >= 0) partial = s.slice(tail);
            i = s.length;
          } else {
            i = idx + CLOSE_TAG.length;
            mode = 'SEARCHING';
          }
        }
      }
      return out;
    },
    // End-of-stream flush. If we ended outside a <think> block, surface any
    // partial open-tag tail — it was real text that just happened to look
    // like the start of a tag. If we ended mid-<think>, drop the
    // unterminated remainder.
    flush() {
      const tail = mode === 'SEARCHING' ? partial : '';
      partial = '';
      return tail;
    },
  };
}

function stripFromJson(body) {
  if (!body || !Array.isArray(body.choices)) return;
  for (const choice of body.choices) {
    const msg = choice && choice.message;
    if (!msg) continue;
    if (typeof msg.content === 'string') {
      msg.content = msg.content.replace(/<think>[\s\S]*?<\/think>\s*/g, '');
    }
    if ('reasoning_content' in msg) delete msg.reasoning_content;
  }
}

class ExtraThinkTagTransformer {
  constructor(options) {
    this.options = options || {};
    this.name = 'extrathinktag';
  }

  async transformResponseOut(response) {
    const headers = response.headers;
    const contentType =
      (headers && typeof headers.get === 'function' && headers.get('Content-Type')) || '';

    if (contentType.includes('application/json')) {
      let body;
      try {
        body = await response.json();
      } catch {
        return response;
      }
      stripFromJson(body);
      return new Response(JSON.stringify(body), {
        status: response.status,
        statusText: response.statusText,
        headers,
      });
    }

    if (contentType.includes('stream') && response.body) {
      const decoder = new TextDecoder();
      const encoder = new TextEncoder();
      const reader = response.body.getReader();
      const stripper = makeStripper();
      let lineBuffer = '';

      const transformLine = (line) => {
        // SSE lines: `data: { ... }`, `data: [DONE]`, `event:`, `id:`,
        // `retry:`, or empty separators. Only `data:` JSON payloads are
        // mutated; everything else passes through unmodified.
        if (!line.startsWith('data:')) return line;
        const payload = line.slice(5).trimStart();
        if (payload === '[DONE]' || payload === '') return line;
        let obj;
        try {
          obj = JSON.parse(payload);
        } catch {
          return line;
        }
        const choices = (obj && obj.choices) || [];
        for (const c of choices) {
          const delta = c && c.delta;
          if (!delta) continue;
          if (typeof delta.content === 'string') {
            delta.content = stripper.feed(delta.content);
          }
          if ('reasoning_content' in delta) delete delta.reasoning_content;
        }
        return 'data: ' + JSON.stringify(obj);
      };

      const stream = new ReadableStream({
        async start(controller) {
          const writeOut = (text) => {
            if (text) controller.enqueue(encoder.encode(text));
          };
          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) {
                if (lineBuffer) {
                  writeOut(transformLine(lineBuffer) + '\n');
                  lineBuffer = '';
                }
                // Trailing stripper tail isn't naturally attached to any
                // data: line. Drop it; the next response will re-establish.
                stripper.flush();
                break;
              }
              lineBuffer += decoder.decode(value, { stream: true });
              let nlIdx;
              while ((nlIdx = lineBuffer.indexOf('\n')) >= 0) {
                const line = lineBuffer.slice(0, nlIdx);
                lineBuffer = lineBuffer.slice(nlIdx + 1);
                writeOut(transformLine(line) + '\n');
              }
            }
          } catch (e) {
            controller.error(e);
            return;
          } finally {
            try {
              reader.releaseLock();
            } catch {}
            controller.close();
          }
        },
      });

      return new Response(stream, {
        status: response.status,
        statusText: response.statusText,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          Connection: 'keep-alive',
        },
      });
    }

    return response;
  }
}

module.exports = ExtraThinkTagTransformer;
