import type { BagoClient } from '@/api/client';
import type { PanelId } from '@/contracts/backend';
import { AgentEditorPanel } from '@/features/agents/AgentEditorPanel';
import { InterpreterPanel } from '@/features/interpretation/InterpreterPanel';
import { GitHubAuthPanel } from '@/features/github/GitHubAuthPanel';
import { ToolsPanel } from '@/features/tools/ToolsPanel';
import { PipelineControlPanel } from '@/features/pipeline/PipelineControlPanel';
import { ExternalCapabilitiesPanel } from '@/modules/capability-anatomy/ExternalCapabilitiesPanel';

interface Props {
  panelId: PanelId;
  client: BagoClient;
  onClose: () => void;
}

export const PANEL_WIDTHS: Record<PanelId, number> = {
  agents: 640,
  interpreter: 620,
  'github-auth': 560,
  capabilities: 560,
  pipeline: 720,
  tools: 520,
};

export function PanelHost({ panelId, client, onClose }: Props) {
  switch (panelId) {
    case 'agents':
      return <AgentEditorPanel client={client} onClose={onClose} />;
    case 'interpreter':
      return <InterpreterPanel client={client} onClose={onClose} />;
    case 'github-auth':
      return <GitHubAuthPanel client={client} onClose={onClose} />;
    case 'tools':
      return <ToolsPanel client={client} onClose={onClose} />;
    case 'pipeline':
      return <PipelineControlPanel client={client} onClose={onClose} onRefreshSnapshot={() => {}} onSetSection={() => {}} />;
    case 'capabilities':
      return <ExternalCapabilitiesPanel client={client} onClose={onClose} />;
    default:
      return null;
  }
}
