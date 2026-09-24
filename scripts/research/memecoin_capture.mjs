// Bounded read-only Pump log capture. Node 22+ provides the WebSocket client.
// The output segment uses rocket.raw-capture.v1 and can be replayed by Python.
import { createHash } from 'node:crypto';
import { closeSync, existsSync, fsyncSync, mkdirSync, openSync, writeFileSync, writeSync } from 'node:fs';
import { resolve } from 'node:path';

const PROGRAM = '6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P';
const WS_URL = process.env.SOLANA_WS_URL || 'wss://api.mainnet-beta.solana.com/';
const RPC_URL = process.env.SOLANA_RPC_URL || 'https://api.mainnet-beta.solana.com/';
const args = process.argv.slice(2);
function arg(name) {
  const position = args.indexOf(name);
  if (position < 0 || position + 1 >= args.length) throw Error(`missing ${name}`);
  return args[position + 1];
}
const out = resolve(arg('--out'));
const seconds = Number(arg('--seconds'));
const maxBytes = Number(arg('--max-bytes'));
if (!Number.isInteger(seconds) || seconds < 5 || seconds > 300 ||
    !Number.isInteger(maxBytes) || maxBytes < 1024 || maxBytes > 268435456) {
  throw Error('seconds must be 5..300 and max-bytes 1024..268435456');
}
if (existsSync(out)) throw Error('capture directory already exists');
mkdirSync(out, { recursive: true });
const segment = 'segment-000000000000.jsonl';
const fd = openSync(`${out}/${segment}`, 'wx');
const sha = createHash('sha256');
let bytes = 0;
let frames = 0;
let notifications = 0;
let createLogHints = 0;
let firstSlot = null;
let lastSlot = null;
let ackAt = null;
let endReason = 'unknown';
let settled = false;
let timer;
let ws;
const errors = [];
const pendingTransactions = [];
let createTransactionResponses = 0;
const startedAt = new Date().toISOString();

async function slot() {
  const response = await fetch(RPC_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'getSlot', params: [{ commitment: 'confirmed' }] }),
    signal: AbortSignal.timeout(8000),
  });
  const body = await response.json();
  if (!response.ok || !Number.isInteger(body.result)) throw Error('getSlot unavailable');
  return body.result;
}

async function endAnchor() {
  const response = await fetch(RPC_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ jsonrpc: '2.0', id: 2, method: 'getSignaturesForAddress',
      params: [PROGRAM, { limit: 1, commitment: 'confirmed' }] }),
    signal: AbortSignal.timeout(8000),
  });
  const body = await response.json();
  if (!response.ok || !Array.isArray(body.result) || !body.result[0]?.signature) {
    throw Error('signature anchor unavailable');
  }
  return body.result[0];
}

function append(raw, receivedAt) {
  const data = Buffer.from(raw);
  const record = {
    schema: 'rocket.raw-capture.v1',
    received_at: receivedAt,
    available_at: receivedAt,
    event_id: createHash('sha256').update(data).digest('hex'),
    raw_base64: data.toString('base64'),
  };
  const line = Buffer.from(`${JSON.stringify(record)}\n`);
  if (bytes + line.length > maxBytes) throw Error('CAPTURE_DISK_BOUND');
  writeSync(fd, line);
  fsyncSync(fd);
  sha.update(line);
  bytes += line.length;
  frames++;
}

async function fetchCreateTransaction(signature) {
  for (let attempt = 1; attempt <= 2; attempt++) {
    const requestedAt = new Date().toISOString();
    try {
      const response = await fetch(RPC_URL, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ jsonrpc: '2.0', id: 3, method: 'getTransaction',
          params: [signature, { encoding: 'jsonParsed', commitment: 'confirmed',
            maxSupportedTransactionVersion: 0 }] }),
        signal: AbortSignal.timeout(4000),
      });
      const body = await response.json();
      const receivedAt = new Date().toISOString();
      append(JSON.stringify({ source: 'rpc:getTransaction', signature, attempt,
        requested_at: requestedAt, response: body }), receivedAt);
      if (response.ok && body.result) {
        createTransactionResponses++;
        return;
      }
    } catch (error) {
      errors.push(`create_tx_${signature.slice(0, 8)}_${attempt}_${error.name || 'error'}`);
    }
    if (attempt === 1) await new Promise((resolveDelay) => setTimeout(resolveDelay, 500));
  }
}

let startSlot = null;
try { startSlot = await slot(); } catch { errors.push('start_slot_unavailable'); }

const finished = new Promise((resolveFinish) => {
  function finish(reason) {
    if (settled) return;
    settled = true;
    endReason = reason;
    clearTimeout(timer);
    if (ws && ws.readyState === WebSocket.OPEN) ws.close();
    resolveFinish();
  }
  ws = new WebSocket(WS_URL);
  ws.addEventListener('open', () => {
    ws.send(JSON.stringify({
      jsonrpc: '2.0', id: 1, method: 'logsSubscribe',
      params: [{ mentions: [PROGRAM] }, { commitment: 'confirmed' }],
    }));
  });
  ws.addEventListener('message', (event) => {
    const receivedAt = new Date().toISOString();
    const raw = String(event.data);
    try {
      append(raw, receivedAt);
      const message = JSON.parse(raw);
      if (message.id === 1) {
        if (!Number.isInteger(message.result)) throw Error('SUBSCRIPTION_REJECTED');
        ackAt = receivedAt;
        timer = setTimeout(() => finish('duration_elapsed'), seconds * 1000);
      } else if (message.method === 'logsNotification') {
        notifications++;
        const observed = message.params?.result;
        const value = observed?.value;
        if (!Number.isInteger(observed?.context?.slot) || typeof value?.signature !== 'string') {
          throw Error('INVALID_NOTIFICATION');
        }
        const current = observed.context.slot;
        firstSlot = firstSlot === null ? current : Math.min(firstSlot, current);
        lastSlot = lastSlot === null ? current : Math.max(lastSlot, current);
        if (value.err === null && Array.isArray(value.logs) &&
            value.logs.some((line) => /Instruction: Create(?:V2)?$/.test(line))) {
          createLogHints++;
          pendingTransactions.push(fetchCreateTransaction(value.signature));
        }
      }
    } catch (error) {
      errors.push(String(error.message || error));
      finish('frame_or_disk_error');
    }
  });
  ws.addEventListener('error', () => { errors.push('websocket_error'); finish('websocket_error'); });
  ws.addEventListener('close', () => { if (!settled) finish('connection_closed'); });
  setTimeout(() => { if (!ackAt) finish('subscription_timeout'); }, 12000);
});

await finished;
const endedAt = new Date().toISOString();
await Promise.allSettled(pendingTransactions);
let endSlot = null;
try { endSlot = await slot(); } catch { errors.push('end_slot_unavailable'); }
let endIndexAnchor = null;
try { endIndexAnchor = await endAnchor(); } catch { errors.push('end_index_anchor_unavailable'); }
fsyncSync(fd);
closeSync(fd);
const manifest = {
  schema: 'rocket.memecoin.capture-session.v1',
  program_id: PROGRAM,
  commitment: 'confirmed',
  endpoint_host: new URL(WS_URL).host,
  started_at: startedAt,
  subscription_ack_at: ackAt,
  ended_at: endedAt,
  start_slot: startSlot,
  end_slot: endSlot,
  end_index_anchor: endIndexAnchor,
  first_notification_slot: firstSlot,
  last_notification_slot: lastSlot,
  requested_seconds: seconds,
  max_bytes: maxBytes,
  segment,
  segment_sha256: sha.digest('hex'),
  frames,
  notifications,
  create_log_hints: createLogHints,
  create_transaction_responses: createTransactionResponses,
  end_reason: endReason,
  errors,
  // The websocket session alone cannot establish independent chain coverage.
  coverage_status: 'UNVERIFIED',
};
writeFileSync(`${out}/capture-manifest.json`, `${JSON.stringify(manifest, null, 2)}\n`, { flag: 'wx' });
console.log(JSON.stringify(manifest));
if (endReason !== 'duration_elapsed') process.exitCode = 1;
