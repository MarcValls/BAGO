import type { ReactNode } from 'react';

interface Props {
  title: ReactNode;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}

export function FlowStageScreen(props: Props) {
  return (
    <section className={`context-flow-screen ${props.className || ''}`.trim()}>
      <header className="context-flow-screen-header">
        <h3>{props.title}</h3>
        {props.subtitle && <p>{props.subtitle}</p>}
      </header>
      <div className="context-flow-screen-body">{props.children}</div>
    </section>
  );
}
