import { Icon, type IconName } from '@/shared/Icon';

export type FlowStageState = 'active' | 'next' | 'completed' | 'locked' | 'idle';

export interface FlowStageItem {
  id: string;
  label: string;
  icon: IconName;
  state: FlowStageState;
}

interface Props {
  title: string;
  subtitle?: string;
  stages: FlowStageItem[];
  activeStage: string;
  onStageChange: (stageId: string) => void;
}

export function FlowNav(props: Props) {
  return (
    <aside className="context-flow-nav" aria-label={props.title}>
      <header className="context-flow-nav-header">
        <strong>{props.title}</strong>
        {props.subtitle && <small>{props.subtitle}</small>}
      </header>
      <nav className="context-flow-nav-list">
        {props.stages.map((stage, index) => (
          <button
            key={stage.id}
            type="button"
            className={[
              'context-flow-nav-item',
              stage.id === props.activeStage ? 'is-active' : '',
              stage.state === 'completed' ? 'is-completed' : '',
              stage.state === 'next' ? 'is-next' : '',
              stage.state === 'locked' ? 'is-locked' : ''
            ].filter(Boolean).join(' ')}
            onClick={() => {
              if (stage.state !== 'locked') props.onStageChange(stage.id);
            }}
            disabled={stage.state === 'locked'}
            aria-current={stage.id === props.activeStage ? 'step' : undefined}
          >
            <span className="context-flow-nav-item-label">
              <span className="context-flow-nav-index">{index + 1}</span>
              <span><Icon name={stage.icon} size={12} /> {stage.label}</span>
            </span>
            {stage.state === 'completed' && <Icon name="check" size={11} />}
          </button>
        ))}
      </nav>
    </aside>
  );
}
