import type { ReactNode } from 'react';

interface Props {
  title?: ReactNode;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}

export function FlowStageScreen(props: Props) {
  // FIX v0.2.1: el header (título + subtítulo) era decorativo. Los
  // 5 stages (Sources, Structure, Pack, Compile, Destination) ya
  // tienen headers semánticos en el árbol de contexto padre. Se
  // elimina el header de este wrapper para evitar duplicación.
  return (
    <section className={`context-flow-screen ${props.className || ''}`.trim()}>
      <div className="context-flow-screen-body">{props.children}</div>
    </section>
  );
}
