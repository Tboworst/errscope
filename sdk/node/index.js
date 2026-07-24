'use strict';

const http = require('http');
const https = require('https');

let _endpoint = null;
let _service = 'app';
let _environment = 'production';
let _apiKey = null;

/**
 * Initialize Beacon. Call this once at app startup.
 * Automatically captures uncaught exceptions and unhandled promise rejections.
 *
 * beacon.init({
 *   endpoint: 'http://your-beacon-server:7000/ingest',
 *   service: 'my-app',
 *   environment: 'production',
 *   apiKey: 'your-secret-key',
 * });
 */
function init({ endpoint = 'http://localhost:7000/ingest', service = 'app', environment = 'production', apiKey = null } = {}) {
  _endpoint = endpoint;
  _service = service;
  _environment = environment;
  _apiKey = apiKey;

  // app is already crashing — fire the request then let Node exit normally
  process.on('uncaughtException', (err) => {
    _postTo(_endpoint, _buildPayload(err));
    setTimeout(() => process.exit(1), 250).unref();
  });

  process.on('unhandledRejection', (reason) => {
    const err = reason instanceof Error ? reason : new Error(String(reason));
    setImmediate(() => _postTo(_endpoint, _buildPayload(err)));
  });
}

/**
 * Manually capture a caught exception. Never blocks the caller.
 *
 *   try { ... } catch (err) { beacon.capture(err); }
 */
function capture(err) {
  if (!_endpoint) return;
  const e = err instanceof Error ? err : new Error(String(err));
  setImmediate(() => _postTo(_endpoint, _buildPayload(e)));
}

/**
 * Capture a single LLM call — success or failure.
 *
 *   const t0 = Date.now();
 *   try {
 *     const res = await openai.chat.completions.create({ model: 'gpt-4o', messages });
 *     beacon.captureLlm({
 *       model: 'gpt-4o',
 *       promptHash: hashMessages(messages),
 *       inputTokens: res.usage.prompt_tokens,
 *       outputTokens: res.usage.completion_tokens,
 *       latencyMs: Date.now() - t0,
 *       costUsd: res.usage.prompt_tokens * 0.000005 + res.usage.completion_tokens * 0.000015,
 *       feature: 'document-summarizer',
 *     });
 *   } catch (err) {
 *     beacon.captureLlm({ model: 'gpt-4o', promptHash: hashMessages(messages),
 *                         inputTokens: 0, outputTokens: 0, latencyMs: Date.now() - t0,
 *                         costUsd: 0, feature: 'document-summarizer', error: err });
 *   }
 */
function captureLlm({ model, promptHash, inputTokens = 0, outputTokens = 0, latencyMs = 0, costUsd = 0, feature = null, error = null } = {}) {
  if (!_endpoint) return;
  const llmEndpoint = _endpoint.replace(/\/+$/, '') + '/llm';
  const payload = {
    timestamp: _now(),
    model,
    prompt_hash: String(promptHash ?? ''),
    input_tokens: inputTokens,
    output_tokens: outputTokens,
    latency_ms: latencyMs,
    cost_usd: costUsd,
    feature,
    service: _service,
    environment: _environment,
    error: error != null ? String(error) : null,
  };
  setImmediate(() => _postTo(llmEndpoint, payload));
}

// ── internals ─────────────────────────────────────────────────────────────────

function _now() {
  // strip milliseconds to match the Python SDK format: 2024-01-15T10:23:45Z
  return new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
}

function _buildPayload(err) {
  return {
    timestamp: _now(),
    exception_type: err.constructor?.name ?? 'Error',
    message: err.message,
    stack_trace: _parseStack(err.stack),
    service: _service,
    environment: _environment,
  };
}

function _parseStack(stack) {
  if (!stack) return [];
  return stack
    .split('\n')
    .slice(1)                              // drop the "Error: message" first line
    .map(line => line.trim())
    .filter(line => line.startsWith('at '))
    .map(line => {
      // "at funcName (/path/file.js:10:5)"  or  "at /path/file.js:10:5"
      const withFunc = line.match(/^at (.+?) \((.+):(\d+):\d+\)$/);
      const noFunc   = line.match(/^at ()(.+):(\d+):\d+$/);
      const m = withFunc || noFunc;
      if (!m) return { function: line.slice(3), file: '', line: 0 };
      return { function: m[1] || '<anonymous>', file: m[2], line: parseInt(m[3], 10) };
    });
}

function _postTo(url, payload) {
  if (!url) return;
  try {
    const body = JSON.stringify(payload);
    const u = new URL(url);
    const lib = u.protocol === 'https:' ? https : http;
    const req = lib.request({
      hostname: u.hostname,
      port: u.port || (u.protocol === 'https:' ? 443 : 80),
      path: u.pathname,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(body),
        ...(_apiKey ? { 'X-Api-Key': _apiKey } : {}),
      },
    });
    req.on('error', () => {}); // beacon being down must never surface to the app
    req.write(body);
    req.end();
  } catch (_) {
    // same — silent fail
  }
}

module.exports = { init, capture, captureLlm };
