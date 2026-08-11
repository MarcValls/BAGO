import type { AgentConfig, AgentUpdateRequest } from '@/contracts/backend';

export type { AgentConfig, AgentUpdateRequest };

export interface AgentEditorState {
  agent: AgentConfig | null;
  loading: boolean;
  saving: boolean;
  testing: boolean;
  error: string | null;
  savedMessage: string | null;
  testOutput: string | null;
  isDirty: boolean;
}
