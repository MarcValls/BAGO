import { describe, expect, it, vi } from 'vitest';
import type { BagoClient } from '../src/api/client';
import {
  CONTEXT_BANK_MANUAL_FILE,
  CONTEXT_PACKS_FILE,
  CONTEXT_PROPOSALS_FILE,
  CONTEXT_RECEIPTS_FILE,
  CONTEXT_SOURCE_DIRECTORIES_FILE,
  CONTEXT_TREE_FILE,
  loadContextBankManual,
  loadContextPacks,
  loadContextPatchRequests,
  loadContextReceipts,
  loadContextTree,
  loadSourceDirectories
} from '../src/features/context-tree/contextTreeApi';

function clientWithRead(readFile: ReturnType<typeof vi.fn>): BagoClient {
  return { readFile } as unknown as BagoClient;
}

describe('optional context storage', () => {
  it('loads all absent initial files through the optional-read contract', async () => {
    const readFile = vi.fn().mockResolvedValue({ ok: true, exists: false, content: '' });
    const client = clientWithRead(readFile);

    await expect(Promise.all([
      loadContextPacks(client),
      loadContextPatchRequests(client),
      loadContextTree(client),
      loadContextReceipts(client),
      loadSourceDirectories(client),
      loadContextBankManual(client)
    ])).resolves.toEqual([[], [], null, [], [], []]);

    for (const path of [
      CONTEXT_PACKS_FILE,
      CONTEXT_PROPOSALS_FILE,
      CONTEXT_TREE_FILE,
      CONTEXT_RECEIPTS_FILE,
      CONTEXT_SOURCE_DIRECTORIES_FILE,
      CONTEXT_BANK_MANUAL_FILE
    ]) {
      expect(readFile).toHaveBeenCalledWith(path, { optional: true });
    }
  });

  it('does not hide genuine read failures', async () => {
    const client = clientWithRead(vi.fn().mockRejectedValue(new Error('HTTP 500 Internal Server Error')));

    await expect(loadContextTree(client)).rejects.toThrow('HTTP 500 Internal Server Error');
  });
});
