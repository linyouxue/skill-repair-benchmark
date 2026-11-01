// Observe native DSH fetch calls without changing their body or response.
// Persist only image counts, request order and HTTP status; never credentials.
import fs from 'node:fs';

if (process.env.JPG_DSH_IMAGE_AUDIT) {
  const original = globalThis.fetch;
  let sequence = 0;
  const emit = value => fs.appendFileSync(process.env.JPG_DSH_IMAGE_AUDIT,
    JSON.stringify({ time: new Date().toISOString(), pid: process.pid, ...value }) + '\n', {mode: 0o600});
  globalThis.fetch = async function(input, init) {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
    if (!String(url).startsWith('https://llmapi.paratera.com/')) return original.call(this, input, init);
    let body = init?.body;
    if (body === undefined && input instanceof Request) body = await input.clone().text();
    let value;
    try { value = JSON.parse(typeof body === 'string' ? body : Buffer.from(body ?? '').toString()); } catch {}
    const images = [];
    for (const message of value?.messages ?? []) {
      for (const block of Array.isArray(message.content) ? message.content : []) {
        if (block.type === 'image_url' || block.type === 'image') images.push(block);
      }
    }
    const id = ++sequence;
    const counts = {request: id, image_blocks: images.length,
      read_image_calls_in_history: (value?.messages ?? []).flatMap(m => m.tool_calls ?? [])
        .filter(t => t.function?.name === 'read_image').length,
      inline_image_blocks: images.filter(b => String(b.image_url?.url ?? b.source?.data ?? '').startsWith('data:image/') || b.source?.type === 'base64').length};
    emit({phase: 'request', model: value?.model, ...counts});
    try {
      const response = await original.call(this, input, init);
      emit({phase: 'response', status: response.status, ...counts});
      return response;
    } catch (error) { emit({phase: 'transport-error', error_type: error.name, ...counts}); throw error; }
  };
}
