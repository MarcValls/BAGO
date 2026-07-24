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
});
