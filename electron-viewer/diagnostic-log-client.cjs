const http = require('http');

function createDiagnosticLogClient({ baseUrl = 'http://127.0.0.1:8080' } = {}) {
  const pending = [];
  let flushing = null;

  function post(record) {
    return new Promise((resolve, reject) => {
      const body = Buffer.from(JSON.stringify({ source: 'electron-viewer', ...record }));
      const request = http.request(new URL('/desktop/viewer-log', baseUrl), {
        method: 'POST',
        headers: { 'content-type': 'application/json', 'content-length': body.length }
      }, (response) => {
        response.resume();
        if (response.statusCode === 200) resolve();
        else reject(new Error(`desktop log API returned ${response.statusCode}`));
      });
      request.setTimeout(1500, () => request.destroy(new Error('desktop log API timed out')));
      request.on('error', reject);
      request.end(body);
    });
  }

  async function flush() {
    if (flushing) return flushing;
    flushing = (async () => {
      while (pending.length) {
        try {
          await post(pending[0]);
          pending.shift();
        } catch {
          return;
        }
      }
    })();
    try { await flushing; } finally { flushing = null; }
  }

  function append(kind, message) {
    if (!['boot', 'request'].includes(kind) || typeof message !== 'string') return;
    if (pending.length >= 500) pending.shift();
    pending.push({ kind, message: message.slice(0, 2048) });
    void flush();
  }

  return { append, flush };
}

module.exports = { createDiagnosticLogClient };
