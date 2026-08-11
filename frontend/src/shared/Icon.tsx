import type { ReactElement, SVGProps } from 'react';

export type IconName =
  | 'home' | 'chat' | 'workspace' | 'graph' | 'pipeline' | 'evidence'
  | 'context' | 'system' | 'search' | 'actions' | 'plus' | 'inspector'
  | 'focus' | 'review' | 'refresh' | 'menu' | 'close' | 'send'
  | 'attach' | 'history' | 'command' | 'chevron' | 'chevronDown' | 'chevronUp' | 'zoomIn' | 'zoomOut'
  | 'center' | 'filter' | 'layout' | 'retry' | 'stop' | 'compare'
  | 'copy' | 'check' | 'warning' | 'server' | 'model' | 'link'
  | 'file' | 'folder' | 'session' | 'prompt' | 'artifact' | 'node'
  | 'trace' | 'live' | 'more' | 'arrowLeft' | 'arrowRight' | 'expand'
  | 'chatOff' | 'chatSplit' | 'chatFull' | 'sparkle' | 'cog' | 'shield' | 'settings' | 'tools'
  | 'lock' | 'intent' | 'risk' | 'claim' | 'decision' | 'pack' | 'stale'
  | 'conflict' | 'proposed' | 'canon' | 'target' | 'tree' | 'bank' | 'tray'
  | 'inbox' | 'rule' | 'verified' | 'dot' | 'collapse' | 'alert' | 'flag' | 'brace' | 'spark'
  | 'agent' | 'interpret';

interface Props extends SVGProps<SVGSVGElement> {
  name: IconName;
  size?: number;
}

const paths: Record<IconName, ReactElement> = {
  home: <><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/><path d="M9 21v-7h6v7"/></>,
  chat: <><path d="M21 12a8 8 0 0 1-8 8H6l-3 2 1-5a8 8 0 1 1 17-5Z"/><path d="M8 12h.01M12 12h.01M16 12h.01"/></>,
  workspace: <><path d="M3 7h6l2 2h10v11H3Z"/><path d="M3 7V4h7l2 3"/></>,
  graph: <><circle cx="6" cy="6" r="2.5"/><circle cx="18" cy="6" r="2.5"/><circle cx="12" cy="18" r="2.5"/><path d="m8.2 7.3 2.6 7.4M15.8 7.3l-2.6 7.4M8.5 6h7"/></>,
  pipeline: <><path d="M4 5h6v5H4zM14 14h6v5h-6z"/><path d="M10 7.5h3a3 3 0 0 1 3 3V14M8 10v4a3 3 0 0 0 3 3h3"/></>,
  evidence: <><path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4M9 12l2 2 4-5"/></>,
  context: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2M4.5 17.5l3-2M19.5 17.5l-3-2"/></>,
  system: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 9h10M7 13h5M7 17h8"/></>,
  search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></>,
  actions: <><path d="M4 7h10M4 17h16M14 7l2-2m-2 2 2 2M10 17l-2-2m2 2-2 2"/></>,
  plus: <><path d="M12 5v14M5 12h14"/></>,
  inspector: <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M15 4v16M7 8h4M7 12h4M7 16h4"/></>,
  focus: <><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></>,
  review: <><path d="M3 5h18v14H3z"/><path d="M7 9h10M7 13h7"/></>,
  refresh: <><path d="M20 7v5h-5"/><path d="M19 12a7 7 0 1 0-2 5"/></>,
  menu: <><path d="M4 7h16M4 12h16M4 17h16"/></>,
  close: <><path d="m6 6 12 12M18 6 6 18"/></>,
  send: <><path d="m3 11 18-8-8 18-2-8z"/><path d="m11 13 10-10"/></>,
  attach: <><path d="m8 12 6-6a4 4 0 0 1 6 6l-8 8a6 6 0 0 1-8-8l8-8"/></>,
  history: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
  command: <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M12 15h5"/></>,
  chevron: <path d="m9 6 6 6-6 6"/>,
  zoomIn: <><circle cx="10" cy="10" r="6"/><path d="m15 15 5 5M10 7v6M7 10h6"/></>,
  zoomOut: <><circle cx="10" cy="10" r="6"/><path d="m15 15 5 5M7 10h6"/></>,
  center: <><circle cx="12" cy="12" r="4"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4"/></>,
  filter: <><path d="M3 5h18l-7 8v6l-4 2v-8z"/></>,
  layout: <><rect x="3" y="4" width="8" height="7"/><rect x="13" y="4" width="8" height="4"/><rect x="13" y="10" width="8" height="10"/><rect x="3" y="13" width="8" height="7"/></>,
  retry: <><path d="M20 7v5h-5"/><path d="M19 12a7 7 0 1 0-2 5"/></>,
  stop: <rect x="6" y="6" width="12" height="12" rx="1"/>,
  compare: <><path d="M8 4 4 8l4 4M4 8h12M16 20l4-4-4-4M20 16H8"/></>,
  copy: <><rect x="8" y="8" width="11" height="11" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/></>,
  check: <path d="m5 12 4 4L19 6"/>,
  warning: <><path d="M12 3 2.5 20h19z"/><path d="M12 9v4M12 17h.01"/></>,
  server: <><rect x="3" y="4" width="18" height="6" rx="2"/><rect x="3" y="14" width="18" height="6" rx="2"/><path d="M7 7h.01M7 17h.01M11 7h6M11 17h6"/></>,
  model: <><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/></>,
  link: <><path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1 1"/><path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1-1"/></>,
  file: <><path d="M6 3h9l3 3v15H6z"/><path d="M15 3v4h4"/></>,
  folder: <path d="M3 6h7l2 2h9v11H3z"/>,
  session: <><circle cx="9" cy="9" r="3"/><path d="M3 20c0-4 2-6 6-6s6 2 6 6M16 7h5M18.5 4.5v5"/></>,
  prompt: <><path d="M4 4h16v12H8l-4 4z"/><path d="M8 8h8M8 12h5"/></>,
  artifact: <><path d="M4 7 12 3l8 4-8 4z"/><path d="m4 12 8 4 8-4M4 17l8 4 8-4"/></>,
  node: <><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/><path d="M10 7h4a3 3 0 0 1 3 3v4"/></>,
  trace: <><path d="M4 17 9 7l4 8 3-6 4 8"/></>,
  live: <><circle cx="12" cy="12" r="2"/><path d="M7 7a7 7 0 0 0 0 10M17 7a7 7 0 0 1 0 10M4 4a11 11 0 0 0 0 16M20 4a11 11 0 0 1 0 16"/></>,
  more: <><circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/></>,
  arrowLeft: <><path d="m15 18-6-6 6-6"/></>,
  arrowRight: <><path d="m9 18 6-6-6-6"/></>,
  expand: <><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></>,
  chatOff: <><path d="M21 12a8 8 0 0 1-8 8H6l-3 2 1-5a8 8 0 0 1 2-5"/><path d="m3 3 18 18"/></>,
  chatSplit: <><rect x="3" y="4" width="11" height="16" rx="1.5"/><rect x="16" y="4" width="5" height="16" rx="1.5"/><path d="M7 9h3M7 12h3"/></>,
  chatFull: <><rect x="3" y="5" width="18" height="14" rx="1.5"/><path d="M8 10h.01M12 10h.01M8 14h5"/></>,
  sparkle: <><path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.5 5.5l2.8 2.8M15.7 15.7l2.8 2.8M5.5 18.5l2.8-2.8M15.7 8.3l2.8-2.8"/><circle cx="12" cy="12" r="2"/></>,
  cog: <><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/></>,
  shield: <><path d="M12 2 4 5v7c0 4.5 3.5 8.5 8 10 4.5-1.5 8-5.5 8-10V5z"/><path d="m9 12 2 2 4-4"/></>,
  // Iconos del ContextTreeModule: estado de nodo, riesgo, paquete, claim, etc.
  // Mantener stroke coherente con el resto del catálogo.
  lock: <><rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/><path d="M12 15v2"/></>,
  intent: <><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.5 5.5l2 2M16.5 16.5l2 2M18.5 5.5l-2 2M7.5 16.5l-2 2"/><circle cx="12" cy="12" r="3"/></>,
  risk: <><path d="M12 3 2.5 20h19z"/><path d="M12 9v4M12 17h.01"/></>,
  claim: <><path d="M6 3h9l3 3v15H6z"/><path d="M9 12l2 2 4-5"/></>,
  decision: <><path d="M5 12l4 4 10-10"/><path d="M5 19h14"/></>,
  pack: <><rect x="3" y="6" width="18" height="14" rx="2"/><path d="M3 10h18M8 6V3h8v3"/></>,
  stale: <><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l3 2"/></>,
  conflict: <><path d="M4 4l16 16M20 4 4 20"/></>,
  proposed: <><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 4l16 16M4 20 20 4"/></>,
  canon: <><path d="M5 11h14v9H5z"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></>,
  target: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><circle cx="12" cy="12" r="1"/></>,
  tree: <><rect x="3" y="3" width="6" height="6" rx="1"/><rect x="9" y="15" width="6" height="6" rx="1"/><rect x="15" y="9" width="6" height="6" rx="1"/><path d="M9 6h6a3 3 0 0 1 3 3v3M9 18h0M12 18v-6"/></>,
  bank: <><rect x="3" y="9" width="18" height="11" rx="2"/><path d="M3 9l3-6h12l3 6M7 13h.01M11 13h.01M15 13h.01M7 17h.01M11 17h.01M15 17h.01"/></>,
  tray: <><path d="M3 13l3-9h12l3 9M3 13h6l1 2h4l1-2h6M3 13v5a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-5"/></>,
  inbox: <><path d="M3 14h6l1 2h4l1-2h6"/><path d="M5 14V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v9"/></>,
  rule: <><path d="M5 3h14v4H5zM5 17h14v4H5z"/><path d="M12 7v10"/></>,
  verified: <><path d="M12 2 4 5v7c0 4.5 3.5 8.5 8 10 4.5-1.5 8-5.5 8-10V5z"/><path d="m9 12 2 2 4-4"/></>,
  dot: <circle cx="12" cy="12" r="3" />,
  collapse: <><path d="M5 5l14 14M19 5L5 19"/><path d="M5 12h14"/></>,
  alert: <><path d="M12 3 2 21h20Z"/><path d="M12 9v6M12 18h.01"/></>,
  flag: <><path d="M5 21V4h11l-2 4 2 4H5"/></>,
  brace: <><path d="M9 4H5v4a2 2 0 0 1-2 2 2 2 0 0 1 2 2v4h4M15 4h4v4a2 2 0 0 0 2 2 2 2 0 0 0-2 2v4h-4"/></>,
  spark: <><path d="M12 3v6M12 15v6M3 12h6M15 12h6M6 6l3 3M15 15l3 3M6 18l3-3M15 9l3-3"/></>,
  // Agent: persona/bust with gear — represents configurable AI agent
  agent: <><circle cx="12" cy="8" r="4"/><path d="M6 20v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2"/><path d="M12 2v2M12 14v2M2 12h2M20 12h2"/></>,
  // Interpret: radar/signal wave — represents text interpretation
  interpret: <><circle cx="12" cy="12" r="2"/><path d="M12 5a7 7 0 0 1 7 7M12 5a7 7 0 0 0-7 7M5 12a7 7 0 0 0 7 7M19 12a7 7 0 0 1-7 7M12 19v3M12 2v3"/></>,
  settings: <><path d="M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1Z"/></>,
  tools: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 9h8M8 13h6M8 17h10"/></>,
  chevronDown: <><path d="m6 9 6 6 6-6"/></>,
  chevronUp: <><path d="m18 15-6-6-6 6"/></>
};

export function Icon({ name, size = 18, ...props }: Props) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
