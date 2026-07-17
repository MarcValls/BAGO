// src/lib/ResizableHandle.tsx
// Handle visual entre paneles. Cursor col-resize al hover.

interface Props {
  onMouseDown: () => void;
  vertical?: boolean;
  label?: string;
}

export function ResizableHandle(props: Props) {
  return (
    <div
      role="separator"
      aria-orientation={props.vertical ? 'vertical' : 'horizontal'}
      aria-label={props.label || 'Redimensionar'}
      className={`resizable-handle ${props.vertical ? 'is-vertical' : 'is-horizontal'}`}
      onMouseDown={(event) => { event.preventDefault(); props.onMouseDown(); }}
    />
  );
}
