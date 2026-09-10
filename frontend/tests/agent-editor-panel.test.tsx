// @vitest-environment happy-dom
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { createBagoClient } from '../src/api/client';
import { AgentEditorPanel } from '../src/features/agents/AgentEditorPanel';
import type { AgentConfig } from '../src/contracts/backend';

const createdAgent: AgentConfig = {
  id: 'agent-1',
  name: 'Analista de evidencia',
  systemPrompt: 'Actua como analista de evidencia BAGO.',
  provider: 'openai',
  model: 'gpt-4o-mini',
  temperature: 0.7,
  maxTokens: 4096,
  enabled: true,
  revision: 1,
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
};

function setupClient() {
  const client = createBagoClient('', '');
  vi.spyOn(client, 'listAgents').mockResolvedValue({ ok: true, agents: [] });
  vi.spyOn(client, 'getSubagentsCatalogue').mockResolvedValue({ source: 'test', agents: [] });
  vi.spyOn(client, 'getProviders').mockResolvedValue({
    providers: [
      {
        id: 'openai',
        name: 'openai',
        description: 'OpenAI Platform',
        configured: true,
        enabled: true,
        state: 'confirmed',
        has_secret: true,
        usable: false,
        healthy: false,
        models: ['gpt-4o-mini'],
      },
      {
        id: 'ollama-local',
        name: 'ollama-local',
        description: 'Ollama local',
        configured: true,
        enabled: true,
        state: 'confirmed',
        runtime_kind: 'local',
        has_secret: false,
        usable: false,
        healthy: false,
        models: ['llama3.2'],
      },
    ],
  });
  vi.spyOn(client, 'getModels').mockImplementation(async (provider) => ({
    ok: true,
    provider,
    models: provider === 'openai' ? ['gpt-4o-mini', 'gpt-4.1'] : ['llama3.2'],
  }));
  vi.spyOn(client, 'getActiveProviderModels').mockResolvedValue({ ok: true, active_models: [] });
  vi.spyOn(client, 'sendInternalChat').mockResolvedValue({
    ok: true,
    response: JSON.stringify({
      name: 'Analista de evidencia',
      systemPrompt: 'Actua como analista de evidencia BAGO.',
    }),
  });
  vi.spyOn(client, 'createAgent').mockResolvedValue(createdAgent);
  return client;
}

describe('AgentEditorPanel', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('requires an AI-generated draft before POST and limits model selection to usable provider models', async () => {
    const client = setupClient();
    render(<AgentEditorPanel client={client} onClose={vi.fn()} />);

    await waitFor(() => expect(screen.getByText(/proveedores usables/i)).toBeInTheDocument());
    expect(screen.queryByRole('option', { name: /ollama local/i })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/objetivo del agente/i), {
      target: { value: 'Auditar evidencia de cambios frontend' },
    });
    fireEvent.click(screen.getByRole('button', { name: /generar borrador con ia/i }));

    await screen.findByRole('heading', { name: /revisar borrador generado/i });
    expect(client.createAgent).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Proveedor')).toHaveValue('openai');
    expect(screen.getByLabelText('Modelo')).toHaveValue('openai/gpt-4o-mini');
    expect(screen.getByRole('option', { name: 'gpt-4.1' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: 'llama3.2' })).not.toBeInTheDocument();

    const createButton = screen.getByRole('button', { name: /^crear agente$/i });
    fireEvent.submit(createButton.closest('form') as HTMLFormElement);

    await waitFor(() => expect(client.createAgent).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Analista de evidencia',
      systemPrompt: 'Actua como analista de evidencia BAGO.',
      provider: 'openai',
      model: 'gpt-4o-mini',
    })));
  });

  it('preserves an existing engine when saving a renamed agent before providers load', async () => {
    const client = setupClient();
    vi.mocked(client.listAgents).mockResolvedValue({ ok: true, agents: [createdAgent] });
    vi.mocked(client.getProviders).mockReturnValue(new Promise<never>(() => {}));
    vi.spyOn(client, 'updateAgent').mockResolvedValue({ ...createdAgent, name: 'Analista actualizado' });

    render(<AgentEditorPanel client={client} onClose={vi.fn()} />);

    fireEvent.click(await screen.findByText(createdAgent.name));
    fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'Analista actualizado' } });
    fireEvent.submit(screen.getByRole('button', { name: /^guardar$/i }).closest('form') as HTMLFormElement);

    await waitFor(() => expect(client.updateAgent).toHaveBeenCalledWith(createdAgent.id, expect.objectContaining({
      name: 'Analista actualizado',
      provider: createdAgent.provider,
      model: createdAgent.model,
    })));
  });

  it('surfaces invalid AI draft responses without creating an agent', async () => {
    const client = setupClient();
    vi.mocked(client.sendInternalChat).mockResolvedValue({ ok: true, response: 'No JSON' });

    render(<AgentEditorPanel client={client} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText(/proveedores usables/i)).toBeInTheDocument());

    fireEvent.click(screen.getByRole('button', { name: /generar borrador con ia/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/borrador valido|borrador válido/i);
    expect(client.createAgent).not.toHaveBeenCalled();
  });
});
