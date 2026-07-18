// src/features/workspace/highlight.ts
// Resaltado de sintaxis ligero basado en regex por línea. Produce
// una lista de tokens por línea que el editor pinta como <span>s.
// No busca 100% de paridad con Monaco/TextMate, pero ofrece feedback
// visual útil para los lenguajes comunes del workspace.

import type { Language } from './workspaceTypes';

export type TokenKind =
  | 'plain'
  | 'keyword'
  | 'string'
  | 'number'
  | 'comment'
  | 'function'
  | 'type'
  | 'operator'
  | 'punct'
  | 'tag'
  | 'attribute'
  | 'key'
  | 'boolean'
  | 'builtin'
  | 'regex'
  | 'deco'
  | 'heading'
  | 'link'
  | 'code'
  | 'list'
  | 'frontmatter'
  | 'selector'
  | 'property'
  | 'unit'
  | 'variable';

export interface Token {
  kind: TokenKind;
  text: string;
}

interface Rule {
  kind: TokenKind;
  pattern: RegExp;
}

const COMMON_RULES: Rule[] = [
  { kind: 'comment', pattern: /(\/\/[^\n]*|#[^\n]*)/ }
];

const STRING_RULES: Rule[] = [
  { kind: 'string', pattern: /"(?:\\[\s\S]|[^"\\])*"/ },
  { kind: 'string', pattern: /'(?:\\[\s\S]|[^'\\])*'/ },
  { kind: 'string', pattern: /`(?:\\[\s\S]|[^`\\])*`/ },
  { kind: 'string', pattern: /"(?:\\[\s\S]|[^"\\])*$/ },
  { kind: 'string', pattern: /'(?:\\[\s\S]|[^'\\])*$/ }
];

const NUMBER_RULES: Rule[] = [
  { kind: 'number', pattern: /\b\d+(?:\.\d+)?\b/ }
];

const TS_RULES: Rule[] = [
  { kind: 'keyword', pattern: /\b(?:import|export|from|const|let|var|function|return|if|else|for|while|switch|case|break|continue|default|new|class|extends|implements|interface|type|enum|public|private|protected|static|readonly|async|await|yield|throw|try|catch|finally|of|in|void|null|undefined|true|false|this|super|as|is|keyof|infer|namespace|declare|module|get|set)\b/ },
  { kind: 'type', pattern: /\b(?:string|number|boolean|bigint|symbol|any|unknown|never|object|Array|Promise|Record|Partial|Required|Readonly|Pick|Omit|Exclude|Extract|Map|Set|Error|Date|RegExp|HTMLElement|HTMLInputElement)\b/ },
  { kind: 'boolean', pattern: /\b(?:true|false|null|undefined)\b/ },
  { kind: 'function', pattern: /\b[a-zA-Z_$][\w$]*(?=\s*\()/ },
  { kind: 'deco', pattern: /@[a-zA-Z_$][\w$]*/ }
];

const PY_RULES: Rule[] = [
  { kind: 'keyword', pattern: /\b(?:def|class|import|from|as|return|if|elif|else|for|while|try|except|finally|with|yield|lambda|pass|break|continue|raise|global|nonlocal|in|is|not|and|or|None|True|False|async|await)\b/ },
  { kind: 'deco', pattern: /@[a-zA-Z_][\w.]*/ },
  { kind: 'function', pattern: /\b[a-zA-Z_][\w]*(?=\s*\()/ }
];

const MD_RULES: Rule[] = [
  { kind: 'heading', pattern: /^#{1,6}\s+.*$/ },
  { kind: 'code', pattern: /`[^`]*`/ },
  { kind: 'link', pattern: /\[([^\]]+)\]\(([^)]+)\)/ },
  { kind: 'list', pattern: /^\s*[-*+]\s+/ },
  { kind: 'list', pattern: /^\s*\d+\.\s+/ },
  { kind: 'frontmatter', pattern: /^---\s*$/ }
];

const CSS_RULES: Rule[] = [
  { kind: 'comment', pattern: /\/\*[\s\S]*?\*\// },
  { kind: 'selector', pattern: /[.#]?[a-zA-Z_-][\w-]*(?=\s*\{)/ },
  { kind: 'property', pattern: /[a-zA-Z-]+(?=\s*:)/ },
  { kind: 'number', pattern: /-?\d+(?:\.\d+)?(?:px|rem|em|%|vh|vw|s|ms|deg)?/ },
  { kind: 'string', pattern: /"(?:\\[\s\S]|[^"\\])*"/ },
  { kind: 'string', pattern: /'(?:\\[\s\S]|[^'\\])*'/ }
];

const HTML_RULES: Rule[] = [
  { kind: 'comment', pattern: /<!--[\s\S]*?-->/ },
  { kind: 'tag', pattern: /<\/?[a-zA-Z][\w-]*/ },
  { kind: 'attribute', pattern: /\b[a-zA-Z_-][\w-]*(?==)/ },
  { kind: 'string', pattern: /"(?:\\[\s\S]|[^"\\])*"/ },
  { kind: 'string', pattern: /'(?:\\[\s\S]|[^'\\])*'/ }
];

const SH_RULES: Rule[] = [
  { kind: 'keyword', pattern: /\b(?:if|then|else|elif|fi|for|while|do|done|case|esac|in|function|return|exit|export|local|read|echo|cd|ls|rm|cp|mv|mkdir|set|unset|declare|trap|shift)\b/ },
  { kind: 'variable', pattern: /\$\{?[\w@:?!\-*]+\}?/ }
];

const JSON_RULES: Rule[] = [
  { kind: 'key', pattern: /"[\w-]+"(?=\s*:)/ },
  { kind: 'string', pattern: /"(?:\\[\s\S]|[^"\\])*"/ },
  { kind: 'number', pattern: /-?\d+(?:\.\d+)?/ },
  { kind: 'boolean', pattern: /\b(?:true|false|null)\b/ }
];

const YAML_RULES: Rule[] = [
  { kind: 'key', pattern: /^[\s-]*[\w-]+(?=\s*:)/ },
  { kind: 'string', pattern: /"(?:\\[\s\S]|[^"\\])*"/ },
  { kind: 'string', pattern: /'(?:\\[\s\S]|[^'\\])*'/ },
  { kind: 'number', pattern: /-?\d+(?:\.\d+)?/ },
  { kind: 'boolean', pattern: /\b(?:true|false|null|yes|no|on|off)\b/i },
  { kind: 'comment', pattern: /#.*/ }
];

const TOML_RULES: Rule[] = [
  { kind: 'key', pattern: /^[\s[]*[#\w.-]+(?=\s*=)/ },
  { kind: 'string', pattern: /"(?:\\[\s\S]|[^"\\])*"/ },
  { kind: 'string', pattern: /'(?:\\[\s\S]|[^'\\])*'/ },
  { kind: 'number', pattern: /-?\d+(?:\.\d+)?/ },
  { kind: 'boolean', pattern: /\b(?:true|false)\b/ },
  { kind: 'comment', pattern: /#.*/ }
];

function rulesFor(language: Language): Rule[] {
  switch (language) {
    case 'typescript':
    case 'tsx':
    case 'javascript':
    case 'jsx':
      return [...STRING_RULES, ...TS_RULES, ...COMMON_RULES, ...NUMBER_RULES];
    case 'python':
      return [...STRING_RULES, ...PY_RULES, ...COMMON_RULES, ...NUMBER_RULES];
    case 'json':
      return JSON_RULES;
    case 'markdown':
      return MD_RULES;
    case 'css':
      return CSS_RULES;
    case 'html':
      return HTML_RULES;
    case 'shell':
      return [...STRING_RULES, ...SH_RULES, ...COMMON_RULES, ...NUMBER_RULES];
    case 'yaml':
      return YAML_RULES;
    case 'toml':
      return TOML_RULES;
    case 'dotenv':
      return [...COMMON_RULES, ...NUMBER_RULES];
    case 'text':
    case 'unknown':
    default:
      return [];
  }
}

function tokenizeLine(line: string, rules: Rule[]): Token[] {
  if (!rules.length) return [{ kind: 'plain', text: line }];
  // Construimos un patrón global con alternativas.
  const alternation = rules.map((rule) => `(${rule.pattern.source})`).join('|');
  const re = new RegExp(alternation, 'g');
  const tokens: Token[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = re.exec(line)) !== null) {
    if (match.index > lastIndex) {
      tokens.push({ kind: 'plain', text: line.slice(lastIndex, match.index) });
    }
    // El primer grupo que coincida determina el kind.
    const groupIndex = match.findIndex((g, idx) => idx > 0 && g !== undefined);
    const ruleIndex = groupIndex - 1;
    const rule = rules[ruleIndex] || rules[0];
    tokens.push({ kind: rule.kind, text: match[0] });
    lastIndex = match.index + match[0].length;
    if (match[0].length === 0) re.lastIndex += 1; // safety
  }
  if (lastIndex < line.length) {
    tokens.push({ kind: 'plain', text: line.slice(lastIndex) });
  }
  return tokens;
}

export function tokenizeContent(content: string, language: Language): Token[][] {
  const rules = rulesFor(language);
  const lines = content.split(/\r?\n/);
  return lines.map((line) => tokenizeLine(line, rules));
}
