import type { ExplorerNode } from './workspaceTypes';
import { getFilePresentation } from './fileTypePresentation';
import { Icon } from '@/shared/Icon';

interface Props {
  node: ExplorerNode;
  size?: number;
}

export function FileTypeIcon({ node, size = 16 }: Props) {
  const presentation = getFilePresentation(node.name, node.kind === 'directory');

  return (
    <Icon
      name={presentation.iconName as Parameters<typeof Icon>[0]['name']}
      size={size}
      style={{ color: presentation.colorToken }}
      aria-label={presentation.label}
    />
  );
}
