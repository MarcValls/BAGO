import type { PanelId } from '@/contracts/backend';
import { AgentEditorPanel } from '@/features/agents/AgentEditorPanel';
import { InterpreterPanel } from '@/features/interpretation/InterpreterPanel';
import { GitHubAuthPanel } from '@/features/github/GitHubAuthPanel';

interface PanelHostProps {
  activePanel: PanelId | null;
  client?: ReturnType<typeof import('@/api/client').createBagoClient>;
  onClose: () => void;
}

export function PanelHost({ activePanel, client, onClose }: PanelHostProps) {
  if (!activePanel) return null;

  return (
    <div className="panel-host">
      {activePanel === 'agents' && <AgentEditorPanel client={client} onClose={onClose} />}
      {activePanel === 'interpreter' && <InterpreterPanel client={client} onClose={onClose} />}
      {activePanel === 'github-auth' && <GitHubAuthPanel client={client} onClose={onClose} />}
    </div>
  );
}
