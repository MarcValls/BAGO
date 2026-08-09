import { afterEach, describe, expect, it, vi } from 'vitest';
import { createBagoClient } from '../src/api/client';

describe('BagoClient response parsing', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('replaces raw JSON parser failures with a stable backend error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<!doctype html><title>Vite</title>', {
      status: 200,
      headers: { 'Content-Type': 'text/html' }
    })));

    const request = createBagoClient('', '').sendChat('hola');

    await expect(request).rejects.toMatchObject({
      name: 'BagoHttpError',
      status: 200,
      message: 'La API de BAGO devolvió una respuesta no JSON. Comprueba la URL del backend.'
    });
  });

  it('keeps valid JSON responses unchanged', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true, response: 'hola' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    })));

    await expect(createBagoClient('', '').sendChat('hola')).resolves.toEqual({
      ok: true,
      response: 'hola'
    });
  });

  it('preserves attempted provider and model on backend chat failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: false,
      error: 'El modelo agotó el tiempo',
      provider: 'ollama-local',
      model: 'granite3.2:8b'
    }), {
      status: 504,
      headers: { 'Content-Type': 'application/json' }
    })));

    await expect(createBagoClient('', '').sendChat('hola')).rejects.toMatchObject({
      name: 'BagoHttpError',
      status: 504,
      message: 'El modelo agotó el tiempo',
      provider: 'ollama-local',
      model: 'granite3.2:8b'
    });
  });

  it('marks context helper calls as internal', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true, response: '{}' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    }));
    vi.stubGlobal('fetch', fetchMock);

    await createBagoClient('', '').sendInternalChat('revisa contexto');

    const body = JSON.parse(String((fetchMock.mock.calls[0]?.[1] as RequestInit).body));
    expect(body).toMatchObject({ message: 'revisa contexto', internal: true, surface: 'context-internal' });
  });

  it('keeps streamed text and final receipt metadata together', async () => {
    const encoder = new TextEncoder();
    const body = new ReadableStream({
      start(controller) {
        controller.enqueue(encoder.encode('data: {"chunk":"Hola "}\n\ndata: {"chunk":"mundo"}\n\n'));
        controller.enqueue(encoder.encode('data: {"done":true,"response_state":"done","context_receipt":{"id":"r1"}}\n\n'));
        controller.close();
      }
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, { status: 200 })));

    const chunks: string[] = [];
    const result = await createBagoClient('', '').streamChat('hola', (chunk) => chunks.push(chunk));

    expect(chunks.join('')).toBe('Hola mundo');
    expect(result).toMatchObject({ response: 'Hola mundo', response_state: 'done', context_receipt: { id: 'r1' } });
  });

  it('marks optional file reads explicitly in the request URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: true,
      exists: false,
      content: ''
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(createBagoClient('', '').readFile('.bago/context/context-tree.json', { optional: true })).resolves.toMatchObject({
      ok: true,
      exists: false
    });
    expect(fetchMock).toHaveBeenCalledWith(
      '/files/read/.bago%2Fcontext%2Fcontext-tree.json?optional=1',
      expect.objectContaining({ method: 'GET' })
    );
  });

  it('uses the canonical BAGO token header for provider operations', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: 'idle' }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' }
    }));
    vi.stubGlobal('fetch', fetchMock);

    await createBagoClient('http://127.0.0.1:8080', 'session-token').getAutoConfigStatus();

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const headers = new Headers(init.headers);
    expect(headers.get('X-Bago-Token')).toBe('session-token');
    expect(headers.get('Authorization')).toBeNull();
  });

  it('attempts the modern bootstrap only once before the legacy fallback', async () => {
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      const status = url === '/api/v1/ui/bootstrap' ? 404 : 200;
      return Promise.resolve(new Response(JSON.stringify({}), {
        status,
        headers: { 'Content-Type': 'application/json' }
      }));
    });
    vi.stubGlobal('fetch', fetchMock);

    await createBagoClient('', '').bootstrap();

    expect(fetchMock.mock.calls.filter(([url]) => url === '/api/v1/ui/bootstrap')).toHaveLength(1);
  });

  it('applies a verified release through the dedicated endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true, status: 'applying' }), {
      status: 202,
      headers: { 'Content-Type': 'application/json' }
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(createBagoClient('', '').applyReleaseUpdate()).resolves.toMatchObject({ status: 'applying' });
    expect(fetchMock).toHaveBeenCalledWith('/release/apply', expect.objectContaining({
      method: 'POST',
      body: '{}'
    }));
  });
});
