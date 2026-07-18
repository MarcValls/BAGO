import type { ReactNode } from 'react';
import { FlowNav, type FlowStageItem } from './FlowNav';

interface Props {
  title: string;
  subtitle?: string;
  stages: FlowStageItem[];
  activeStage: string;
  onStageChange: (stageId: string) => void;
  children: ReactNode;
}

export function FlowShell(props: Props) {
  return (
    <div className="context-flow-shell">
      <FlowNav
        title={props.title}
        subtitle={props.subtitle}
        stages={props.stages}
        activeStage={props.activeStage}
        onStageChange={props.onStageChange}
      />
      <div className="context-flow-stage">
        {props.children}
      </div>
    </div>
  );
}
