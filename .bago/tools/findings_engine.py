#!/usr/bin/env python3
"""
findings_engine.py — Motor de hallazgos unificado para BAGO.

Modelo canónico de Finding:
  id, severity, file, line, col, rule, source, message,
  fix_suggestion, autofixable, fix_patch, context_lines

Parsea salida de: flake8, pylint, mypy, pyflakes, bandit, custom-bago,
  checkstyle (Java), dotnet build (C#), rubocop (Ruby), phpcs/phpstan (PHP),
  swiftlint (Swift), ktlint (Kotlin), shellcheck (Shell),
  tflint (Terraform), yamllint (YAML)
Persiste en state/findings/SCAN-{timestamp}.json
"""
import json, os, re, subprocess, sys, datetime, hashlib, xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

BAGO_ROOT    = Path(__file__).parent.parent
# Allow tests to isolate scan output by setting BAGO_STATE_DIR env var
_state_env   = os.environ.get("BAGO_STATE_DIR")
FINDINGS_DIR = Path(_state_env) / "findings" if _state_env else BAGO_ROOT / "state" / "findings"
FINDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Import permission fixer — graceful fallback if not yet available
try:
    sys.path.insert(0, str(Path(__file__).parent))
    from permission_fixer import run_with_permission_fix as _run_cmd
except ImportError:
    def _run_cmd(cmd, *, capture_output=True, text=True, timeout=60,    # type: ignore[misc]
                 cwd=None, env=None, silent=True, **_):
        return subprocess.run(cmd, capture_output=capture_output, text=text,
                              timeout=timeout, cwd=cwd, env=env)

SEVERITIES = ("error", "warning", "info", "hint")


@dataclass
class Finding:
    id:             str
    severity:       str          # error|warning|info|hint
    file:           str
    line:           int
    col:            int
    rule:           str
    source:         str          # flake8|pylint|mypy|bandit|bago
    message:        str
    fix_suggestion: str  = ""
    autofixable:    bool = False
    fix_patch:      str  = ""    # unified diff when autofixable
    context_lines:  list = field(default_factory=list)  # ±2 lines

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Finding":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _make_id(source: str, file: str, line: int, rule: str) -> str:
    key = f"{source}:{file}:{line}:{rule}"
    return "FIND-" + hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()[:8].upper()


def _read_context(filepath: str, line: int, radius: int = 2) -> list:
    try:
        lines = Path(filepath).read_text(errors="replace").splitlines()
        start = max(0, line - 1 - radius)
        end   = min(len(lines), line + radius)
        return [f"{i+1:4d} | {lines[i]}" for i in range(start, end)]
    except Exception:
        return []


# ─── Parsers ────────────────────────────────────────────────────────────────

def parse_flake8(output: str, root: str = "") -> list:
    """
    flake8 --format='%(path)s:%(row)d:%(col)d: %(code)s %(text)s'
    """
    findings = []
    pattern  = re.compile(r"^(.+?):(\d+):(\d+):\s+([A-Z]\d+)\s+(.+)$", re.MULTILINE)
    sev_map  = {"E": "error", "W": "warning", "F": "warning", "C": "info", "N": "hint"}
    autofix_rules = {"E302","E303","E501","W291","W293","W292","E231","E225","E251"}
    fix_hints = {
        "E302": "Añade 2 líneas en blanco antes de la definición",
        "E303": "Reduce a máximo 2 líneas en blanco consecutivas",
        "E501": "Acorta la línea a ≤79 caracteres",
        "W291": "Elimina espacios al final de la línea",
        "W293": "Elimina espacios en blanco en línea vacía",
        "W292": "Añade newline al final del archivo",
        "E231": "Añade espacio después de ','",
        "E225": "Añade espacios alrededor del operador",
        "E251": "Elimina espacios alrededor del '=' en keyword argument",
    }
    for m in pattern.finditer(output):
        filepath, line, col, code, msg = m.groups()
        prefix = code[0]
        sev    = sev_map.get(prefix, "info")
        fid    = _make_id("flake8", filepath, int(line), code)
        fix    = fix_hints.get(code, "")
        findings.append(Finding(
            id=fid, severity=sev, file=filepath,
            line=int(line), col=int(col),
            rule=code, source="flake8", message=msg.strip(),
            fix_suggestion=fix, autofixable=code in autofix_rules,
            context_lines=_read_context(filepath, int(line)),
        ))
    return findings


def parse_pylint(output: str, root: str = "") -> list:
    """
    pylint --output-format=text
    formato: filepath:line:col: CODE (category) message
    """
    findings = []
    # pylint JSON format is more reliable
    try:
        data = json.loads(output)
        sev_map = {"error":"error","warning":"warning","convention":"info",
                   "refactor":"hint","fatal":"error","information":"info"}
        for item in data:
            filepath = item.get("path","")
            line     = item.get("line", 0)
            col      = item.get("column", 0)
            code     = item.get("message-id","")
            msg      = item.get("message","")
            cat      = item.get("type","")
            sev      = sev_map.get(cat, "info")
            fid      = _make_id("pylint", filepath, line, code)
            findings.append(Finding(
                id=fid, severity=sev, file=filepath,
                line=line, col=col, rule=code,
                source="pylint", message=msg,
                context_lines=_read_context(filepath, line),
            ))
    except (json.JSONDecodeError, TypeError):
        # Fallback: text format
        pattern = re.compile(r"^(.+?):(\d+):(\d+):\s+([A-Z]\d+):\s+(.+)$", re.MULTILINE)
        for m in pattern.finditer(output):
            filepath, line, col, code, msg = m.groups()
            fid = _make_id("pylint", filepath, int(line), code)
            findings.append(Finding(
                id=fid, severity="warning", file=filepath,
                line=int(line), col=int(col), rule=code,
                source="pylint", message=msg.strip(),
                context_lines=_read_context(filepath, int(line)),
            ))
    return findings


def parse_mypy(output: str, root: str = "") -> list:
    """
    mypy: filepath:line: error: message  [code]
    """
    findings = []
    pattern  = re.compile(r"^(.+?):(\d+):\s+(error|warning|note):\s+(.+?)(?:\s+\[(.+?)\])?$", re.MULTILINE)
    sev_map  = {"error":"error","warning":"warning","note":"info"}
    for m in pattern.finditer(output):
        filepath, line, level, msg, code = m.groups()
        code = code or "mypy"
        sev  = sev_map.get(level, "info")
        fid  = _make_id("mypy", filepath, int(line), code)
        findings.append(Finding(
            id=fid, severity=sev, file=filepath,
            line=int(line), col=0, rule=code,
            source="mypy", message=msg.strip(),
            context_lines=_read_context(filepath, int(line)),
        ))
    return findings


def parse_bandit(output: str, root: str = "") -> list:
    """Parse bandit JSON output."""
    findings = []
    try:
        data = json.loads(output)
        sev_map = {"HIGH":"error","MEDIUM":"warning","LOW":"info"}
        for issue in data.get("results", []):
            filepath = issue.get("filename","")
            line     = issue.get("line_number", 0)
            code     = issue.get("test_id","")
            msg      = issue.get("issue_text","")
            sev      = sev_map.get(issue.get("issue_severity","LOW"), "info")
            fid      = _make_id("bandit", filepath, line, code)
            findings.append(Finding(
                id=fid, severity=sev, file=filepath,
                line=line, col=0, rule=code,
                source="bandit", message=msg,
                fix_suggestion=issue.get("more_info",""),
                context_lines=_read_context(filepath, line),
            ))
    except (json.JSONDecodeError, TypeError):
        pass
    return findings


def parse_bago_custom(output: str, root: str = "") -> list:
    """
    BAGO custom lint: JSON array of {severity,file,line,rule,message,fix,autofixable}
    """
    findings = []
    try:
        items = json.loads(output)
        for item in items:
            filepath = item.get("file","")
            line     = item.get("line", 0)
            code     = item.get("rule","BAGO-CUSTOM")
            fid      = _make_id("bago", filepath, line, code)
            findings.append(Finding(
                id=fid,
                severity=item.get("severity","info"),
                file=filepath, line=line, col=0, rule=code,
                source="bago",
                message=item.get("message",""),
                fix_suggestion=item.get("fix",""),
                autofixable=item.get("autofixable", False),
                fix_patch=item.get("fix_patch",""),
                context_lines=_read_context(filepath, line),
            ))
    except (json.JSONDecodeError, TypeError):
        pass
    return findings


def parse_eslint(output: str, root: str = "") -> list:
    """
    ESLint --format=json output:
    [{filePath, messages:[{ruleId,severity,message,line,column,fix}]}]
    severity: 1=warning, 2=error
    """
    findings = []
    try:
        data = json.loads(output)
        if not isinstance(data, list):
            return findings
        for file_obj in data:
            filepath = file_obj.get("filePath", "")
            if root and filepath.startswith(root):
                filepath = filepath[len(root):].lstrip("/")
            for msg in file_obj.get("messages", []):
                sev_int = msg.get("severity", 1)
                severity = "error" if sev_int == 2 else "warning"
                rule  = msg.get("ruleId") or "eslint"
                line  = msg.get("line", 0)
                col   = msg.get("column", 0)
                text  = msg.get("message", "")
                has_fix = bool(msg.get("fix"))
                fid   = _make_id("eslint", filepath, line, rule)
                fix_sug = f"eslint --fix puede corregir esta regla ({rule})" if has_fix else ""
                findings.append(Finding(
                    id=fid, severity=severity,
                    file=filepath, line=line, col=col,
                    rule=rule, source="eslint", message=text,
                    fix_suggestion=fix_sug, autofixable=has_fix,
                    context_lines=_read_context(filepath, line),
                ))
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return findings


def parse_ast_js(output: str, root: str = "") -> list:
    """
    Parse JSON output from js_ast_scanner.js — BAGO's AST-based JS/TS linter.

    Each item: {file, line, col, rule, severity, source, message,
                fix_suggestion, autofixable}
    """
    findings = []
    try:
        data = json.loads(output)
        if not isinstance(data, list):
            return findings
        for item in data:
            filepath = item.get("file", "")
            if root and filepath.startswith(root):
                filepath = filepath[len(root):].lstrip("/")
            line = item.get("line", 0)
            rule = item.get("rule", "JS-UNKNOWN")
            fid  = _make_id("bago_ast", filepath, line, rule)
            findings.append(Finding(
                id=fid,
                severity=item.get("severity", "warning"),
                file=filepath,
                line=line,
                col=item.get("col", 0),
                rule=rule,
                source="bago_ast",
                message=item.get("message", ""),
                fix_suggestion=item.get("fix_suggestion", ""),
                autofixable=item.get("autofixable", False),
                context_lines=_read_context(filepath, line),
            ))
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return findings


def run_js_ast_scan(target: str) -> list:
    """Run js_ast_scanner.js on target and return Finding list.

    Requires node + acorn + acorn-walk.
    Returns empty list (never raises) if node or scanner unavailable.
    """
    import shutil
    import subprocess as sp

    scanner = Path(__file__).parent / "js_ast_scanner.js"
    if not scanner.exists():
        return []
    node = shutil.which("node")
    if not node:
        return []
    try:
        result = sp.run(
            [node, str(scanner), target, "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode in (0, 1):  # 1 = errors found, still valid output
            return parse_ast_js(result.stdout, root=target)
    except Exception:  # noqa: BAGO-W002
        pass
    return []


    """
    ESLint --format=json output:
    [{filePath, messages:[{ruleId,severity,message,line,column,fix}]}]
    severity: 1=warning, 2=error
    """
    findings = []
    try:
        data = json.loads(output)
        if not isinstance(data, list):
            return findings
        for file_obj in data:
            filepath = file_obj.get("filePath", "")
            if root and filepath.startswith(root):
                filepath = filepath[len(root):].lstrip("/")
            for msg in file_obj.get("messages", []):
                sev_int = msg.get("severity", 1)
                severity = "error" if sev_int == 2 else "warning"
                rule  = msg.get("ruleId") or "eslint"
                line  = msg.get("line", 0)
                col   = msg.get("column", 0)
                text  = msg.get("message", "")
                has_fix = bool(msg.get("fix"))
                fid   = _make_id("eslint", filepath, line, rule)
                fix_sug = f"eslint --fix puede corregir esta regla ({rule})" if has_fix else ""
                findings.append(Finding(
                    id=fid, severity=severity,
                    file=filepath, line=line, col=col,
                    rule=rule, source="eslint", message=text,
                    fix_suggestion=fix_sug, autofixable=has_fix,
                    context_lines=_read_context(filepath, line),
                ))
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return findings


def parse_golangci(output: str, root: str = "") -> list:
    """
    golangci-lint --out-format=json output:
    {"Issues":[{FromLinter,Text,Pos:{Filename,Line,Column}}]}
    """
    findings = []
    try:
        data = json.loads(output)
        issues = data.get("Issues") or []
        for issue in issues:
            pos      = issue.get("Pos", {})
            filepath = pos.get("Filename", "")
            if root and filepath.startswith(root):
                filepath = filepath[len(root):].lstrip("/")
            line   = pos.get("Line", 0)
            col    = pos.get("Column", 0)
            linter = issue.get("FromLinter", "golangci")
            text   = issue.get("Text", "")
            # Map linter name to severity
            severity = "error" if linter in ("errcheck", "govet", "staticcheck") else "warning"
            fid = _make_id("golangci", filepath, line, linter)
            fix_sug = issue.get("Replacement", {}).get("NewLines", "")
            has_fix = bool(fix_sug)
            findings.append(Finding(
                id=fid, severity=severity,
                file=filepath, line=line, col=col,
                rule=linter, source="golangci", message=text,
                fix_suggestion="\n".join(fix_sug) if isinstance(fix_sug, list) else str(fix_sug),
                autofixable=has_fix,
                context_lines=_read_context(filepath, line),
            ))
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return findings


def parse_clippy(output: str, root: str = "") -> list:
    """
    cargo clippy --message-format=json (stream of JSON objects, one per line).
    Each line: {"reason":"compiler-message","message":{...}}
    """
    findings = []
    for raw_line in output.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        try:
            obj = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if obj.get("reason") != "compiler-message":
            continue
        msg = obj.get("message", {})
        level = msg.get("level", "warning")
        severity = "error" if level == "error" else "warning"
        code_obj = msg.get("code") or {}
        rule = code_obj.get("code") or "clippy"
        spans = msg.get("spans", [])
        if not spans:
            continue
        span = spans[0]
        filepath = span.get("file_name", "")
        if root and filepath.startswith(root):
            filepath = filepath[len(root):].lstrip("/")
        line = span.get("line_start", 0)
        col  = span.get("column_start", 0)
        text = msg.get("rendered") or msg.get("message", "")
        has_fix = bool(msg.get("suggested_replacement"))
        fix_sug = msg.get("suggested_replacement", "")
        fid = _make_id("clippy", filepath, line, rule)
        findings.append(Finding(
            id=fid, severity=severity,
            file=filepath, line=line, col=col,
            rule=rule, source="clippy", message=text.split("\n")[0],
            fix_suggestion=fix_sug, autofixable=has_fix,
            context_lines=_read_context(filepath, line),
        ))
    return findings


def parse_checkstyle(output: str, root: str = "") -> list:
    """
    Checkstyle XML output (default format):
    <checkstyle><file name="..."><error line="..." column="..." severity="..." message="..." source="..."/></file></checkstyle>
    """
    findings = []
    try:
        root_el = ET.fromstring(output.strip())
        sev_map = {"error": "error", "warning": "warning", "info": "info", "ignore": "hint"}
        for file_el in root_el.findall("file"):
            filepath = file_el.get("name", "")
            if root and filepath.startswith(root):
                filepath = filepath[len(root):].lstrip("/")
            for error_el in file_el.findall("error"):
                line = int(error_el.get("line", 0))
                col  = int(error_el.get("column", 0))
                sev  = sev_map.get(error_el.get("severity", "warning"), "warning")
                msg  = error_el.get("message", "")
                src  = error_el.get("source", "checkstyle")
                rule = src.split(".")[-1] if "." in src else src
                fid  = _make_id("checkstyle", filepath, line, rule)
                findings.append(Finding(
                    id=fid, severity=sev,
                    file=filepath, line=line, col=col,
                    rule=rule, source="checkstyle", message=msg,
                    context_lines=_read_context(filepath, line),
                ))
    except Exception:
        pass
    return findings


def parse_dotnet_build(output: str, root: str = "") -> list:
    """
    dotnet build / dotnet format MSBuild diagnostic output:
    filepath(line,col): error|warning CODE: message [project]
    """
    findings = []
    pattern = re.compile(
        r"^\s*(.+?)\((\d+),(\d+)\):\s+(error|warning)\s+(CS\w+):\s+(.+?)(?:\s+\[.+?\])?\s*$",
        re.MULTILINE,
    )
    sev_map = {"error": "error", "warning": "warning"}
    for m in pattern.finditer(output):
        filepath, line, col, level, code, msg = m.groups()
        filepath = filepath.strip()
        if root and filepath.startswith(root):
            filepath = filepath[len(root):].lstrip("/")
        sev = sev_map.get(level, "warning")
        fid = _make_id("dotnet", filepath, int(line), code)
        findings.append(Finding(
            id=fid, severity=sev,
            file=filepath, line=int(line), col=int(col),
            rule=code, source="dotnet", message=msg.strip(),
            context_lines=_read_context(filepath, int(line)),
        ))
    return findings


def parse_rubocop(output: str, root: str = "") -> list:
    """
    RuboCop --format=json output:
    {"files":[{"path":"...","offenses":[{"severity":"...","message":"...","cop_name":"...",
      "correctable":true,"location":{"line":N,"column":N}}]}]}
    """
    findings = []
    try:
        data = json.loads(output)
        sev_map = {
            "fatal": "error", "error": "error", "warning": "warning",
            "convention": "info", "refactor": "hint", "info": "info",
        }
        for file_obj in data.get("files", []):
            filepath = file_obj.get("path", "")
            if root and filepath.startswith(root):
                filepath = filepath[len(root):].lstrip("/")
            for offense in file_obj.get("offenses", []):
                sev         = sev_map.get(offense.get("severity", "warning"), "warning")
                msg         = offense.get("message", "")
                rule        = offense.get("cop_name", "rubocop")
                loc         = offense.get("location", {})
                line        = loc.get("line", 0)
                col         = loc.get("column", 0)
                correctable = bool(offense.get("correctable", False))
                fid         = _make_id("rubocop", filepath, line, rule)
                fix_sug = "rubocop --autocorrect puede corregir esta ofensa" if correctable else ""
                findings.append(Finding(
                    id=fid, severity=sev,
                    file=filepath, line=line, col=col,
                    rule=rule, source="rubocop", message=msg,
                    fix_suggestion=fix_sug, autofixable=correctable,
                    context_lines=_read_context(filepath, line),
                ))
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return findings


def parse_phpcs(output: str, root: str = "") -> list:
    """
    PHP_CodeSniffer --report=json output:
    {"files":{"path":{"errors":N,"warnings":N,"messages":[
      {"message":"...","source":"...","severity":N,"type":"ERROR"|"WARNING","line":N,"column":N}
    ]}}}
    """
    findings = []
    try:
        data = json.loads(output)
        for filepath, file_data in data.get("files", {}).items():
            fp = filepath
            if root and fp.startswith(root):
                fp = fp[len(root):].lstrip("/")
            for msg in file_data.get("messages", []):
                sev_str = msg.get("type", "WARNING").upper()
                sev  = "error" if sev_str == "ERROR" else "warning"
                text = msg.get("message", "")
                src  = msg.get("source", "phpcs")
                rule = src.split(".")[-1] if "." in src else src
                line = msg.get("line", 0)
                col  = msg.get("column", 0)
                fid  = _make_id("phpcs", fp, line, rule)
                findings.append(Finding(
                    id=fid, severity=sev,
                    file=fp, line=line, col=col,
                    rule=rule, source="phpcs", message=text,
                    context_lines=_read_context(fp, line),
                ))
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return findings


def parse_phpstan(output: str, root: str = "") -> list:
    """
    PHPStan --error-format=json output:
    {"totals":{...},"files":{"path":{"errors":N,"messages":[{"message":"...","line":N}]}},"errors":[]}
    """
    findings = []
    try:
        data = json.loads(output)
        for filepath, file_data in data.get("files", {}).items():
            fp = filepath
            if root and fp.startswith(root):
                fp = fp[len(root):].lstrip("/")
            for msg in file_data.get("messages", []):
                text = msg.get("message", "")
                line = msg.get("line", 0)
                fid  = _make_id("phpstan", fp, line, "phpstan")
                findings.append(Finding(
                    id=fid, severity="error",
                    file=fp, line=line, col=0,
                    rule="phpstan", source="phpstan", message=text,
                    context_lines=_read_context(fp, line),
                ))
        for err in data.get("errors", []):
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            fid = _make_id("phpstan", "", 0, "phpstan-global")
            findings.append(Finding(
                id=fid, severity="error",
                file="", line=0, col=0,
                rule="phpstan-global", source="phpstan", message=msg,
            ))
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return findings


def parse_swiftlint(output: str, root: str = "") -> list:
    """
    SwiftLint --reporter=json output:
    [{"file":"...","line":N,"character":N,"severity":"Warning"|"Error",
      "reason":"...","rule_id":"...","type":"..."}]
    """
    findings = []
    try:
        data = json.loads(output)
        if not isinstance(data, list):
            return findings
        sev_map = {"Error": "error", "Warning": "warning",
                   "error": "error", "warning": "warning"}
        for item in data:
            filepath = item.get("file", "")
            if root and filepath.startswith(root):
                filepath = filepath[len(root):].lstrip("/")
            line = item.get("line", 0)
            col  = item.get("character", 0)
            sev  = sev_map.get(item.get("severity", "Warning"), "warning")
            msg  = item.get("reason", "")
            rule = item.get("rule_id", "swiftlint")
            fid  = _make_id("swiftlint", filepath, line, rule)
            findings.append(Finding(
                id=fid, severity=sev,
                file=filepath, line=line, col=col,
                rule=rule, source="swiftlint", message=msg,
                context_lines=_read_context(filepath, line),
            ))
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return findings


def parse_ktlint(output: str, root: str = "") -> list:
    """
    ktlint --reporter=json output:
    [{"file":"...","errors":[{"line":N,"column":N,"message":"...","rule":"..."}]}]
    """
    findings = []
    try:
        data = json.loads(output)
        if not isinstance(data, list):
            return findings
        for file_obj in data:
            filepath = file_obj.get("file", "")
            if root and filepath.startswith(root):
                filepath = filepath[len(root):].lstrip("/")
            for error in file_obj.get("errors", []):
                line = error.get("line", 0)
                col  = error.get("column", 0)
                msg  = error.get("message", "")
                rule = error.get("rule", "ktlint")
                fid  = _make_id("ktlint", filepath, line, rule)
                findings.append(Finding(
                    id=fid, severity="warning",
                    file=filepath, line=line, col=col,
                    rule=rule, source="ktlint", message=msg,
                    context_lines=_read_context(filepath, line),
                ))
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return findings


def parse_shellcheck(output: str, root: str = "") -> list:
    """
    ShellCheck --format=json output:
    [{"file":"...","line":N,"column":N,"level":"error"|"warning"|"info"|"style",
      "code":N,"message":"...","fix":null|{...}}]
    """
    findings = []
    try:
        data = json.loads(output)
        if not isinstance(data, list):
            return findings
        sev_map = {"error": "error", "warning": "warning",
                   "info": "info", "style": "hint"}
        for item in data:
            filepath = item.get("file", "")
            if root and filepath.startswith(root):
                filepath = filepath[len(root):].lstrip("/")
            line    = item.get("line", 0)
            col     = item.get("column", 0)
            sev     = sev_map.get(item.get("level", "warning"), "warning")
            msg     = item.get("message", "")
            code    = f"SC{item.get('code', 0)}"
            has_fix = item.get("fix") is not None
            fid     = _make_id("shellcheck", filepath, line, code)
            fix_sug = f"shellcheck --apply-fix puede corregir {code}" if has_fix else ""
            findings.append(Finding(
                id=fid, severity=sev,
                file=filepath, line=line, col=col,
                rule=code, source="shellcheck", message=msg,
                fix_suggestion=fix_sug, autofixable=has_fix,
                context_lines=_read_context(filepath, line),
            ))
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return findings


def parse_tflint(output: str, root: str = "") -> list:
    """
    tflint --format=json output:
    {"issues":[{"rule":{"name":"...","severity":"error"|"warning"|"notice"},
      "message":"...","range":{"filename":"...","start":{"line":N,"column":N}}}],"errors":[]}
    """
    findings = []
    try:
        data = json.loads(output)
        sev_map = {"error": "error", "warning": "warning", "notice": "info"}
        for issue in data.get("issues", []):
            rule_obj  = issue.get("rule", {})
            rule_name = rule_obj.get("name", "tflint")
            sev       = sev_map.get(rule_obj.get("severity", "warning"), "warning")
            msg       = issue.get("message", "")
            rng       = issue.get("range", {})
            filepath  = rng.get("filename", "")
            if root and filepath.startswith(root):
                filepath = filepath[len(root):].lstrip("/")
            start = rng.get("start", {})
            line  = start.get("line", 0)
            col   = start.get("column", 0)
            fid   = _make_id("tflint", filepath, line, rule_name)
            findings.append(Finding(
                id=fid, severity=sev,
                file=filepath, line=line, col=col,
                rule=rule_name, source="tflint", message=msg,
                context_lines=_read_context(filepath, line),
            ))
        for err in data.get("errors", []):
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            fid = _make_id("tflint", "", 0, "tflint-error")
            findings.append(Finding(
                id=fid, severity="error",
                file="", line=0, col=0,
                rule="tflint-error", source="tflint", message=msg,
            ))
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return findings


def parse_yamllint(output: str, root: str = "") -> list:
    """
    yamllint -f parsable output:
    filepath:line:col: [error|warning] message (rule-name)
    Example: ./config.yml:3:3: [warning] wrong indentation: expected 4 but found 2 (indentation)
             ./config.yml:7:1: [error] too many blank lines (2 > 1) (empty-lines)
    The rule name is always the last parenthesised token at end of line.
    Using a non-greedy message group and [^)]+ for the rule avoids mis-matching
    embedded parentheses in the message body.
    """
    findings = []
    pattern = re.compile(
        # filepath        line   col   level              message (non-greedy)  rule (no parens inside)
        r"^(.+?):(\d+):(\d+):\s+\[(error|warning)\]\s+(.+?)\s+\(([^)]+)\)\s*$",
        re.MULTILINE,
    )
    sev_map = {"error": "error", "warning": "warning"}
    for m in pattern.finditer(output):
        filepath, line, col, level, msg, rule = m.groups()
        filepath = filepath.strip()
        if root and filepath.startswith(root):
            filepath = filepath[len(root):].lstrip("/")
        sev = sev_map.get(level, "warning")
        fid = _make_id("yamllint", filepath, int(line), rule)
        findings.append(Finding(
            id=fid, severity=sev,
            file=filepath, line=int(line), col=int(col),
            rule=rule, source="yamllint", message=msg.strip(),
            context_lines=_read_context(filepath, int(line)),
        ))
    return findings


def parse_sarif(output: str, root: str = "", strict: bool = False) -> list:
    """Parse SARIF 2.1.0 JSON output (e.g. from CodeQL or other SARIF-compliant tools).

    Maps:
      result.ruleId              -> Finding.rule
      result.message.text        -> Finding.message
      location.physicalLocation  -> file/line/col
      result.level               -> severity (error→error, warning→warning, note→info, none→hint)
      tool.driver.name (lowercased) -> source (e.g. "codeql")

    strict=False keeps ingestion non-fatal for optional inputs and returns []
    on invalid payloads.

    Raises:
        ValueError: If strict=True and the SARIF payload is invalid.
    """
    findings = []
    sev_map = {"error": "error", "warning": "warning", "note": "info", "none": "hint"}
    try:
        data = json.loads(output)
        if not isinstance(data, dict):
            raise TypeError("SARIF payload must be a JSON object")
        runs = data.get("runs")
        if not isinstance(runs, list):
            raise KeyError("runs")
        for run in runs:
            if not isinstance(run, dict):
                raise TypeError("SARIF run must be an object")
            tool_name = (
                run.get("tool", {}).get("driver", {}).get("name", "sarif")
            ).lower()
            results = run.get("results", [])
            if not isinstance(results, list):
                raise TypeError("SARIF results must be a list")
            for result in results:
                if not isinstance(result, dict):
                    raise TypeError("SARIF result must be an object")
                rule  = result.get("ruleId") or "sarif-rule"
                message = result.get("message", {})
                if not isinstance(message, dict):
                    raise TypeError("SARIF message must be an object")
                msg   = message.get("text", "")
                level = result.get("level", "warning")
                sev   = sev_map.get(level, "warning")

                locations = result.get("locations", [])
                if not isinstance(locations, list):
                    raise TypeError("SARIF locations must be a list")
                if locations:
                    location = locations[0]
                    if not isinstance(location, dict):
                        raise TypeError("SARIF location must be an object")
                    phys = location.get("physicalLocation", {})
                    if not isinstance(phys, dict):
                        raise TypeError("SARIF physicalLocation must be an object")
                    artifact = phys.get("artifactLocation", {})
                    if not isinstance(artifact, dict):
                        raise TypeError("SARIF artifactLocation must be an object")
                    filepath = artifact.get("uri", "")
                    if filepath.startswith("file://"):
                        filepath = filepath[7:]
                    if root and filepath.startswith(root):
                        filepath = filepath[len(root):].lstrip("/")
                    region = phys.get("region", {})
                    if not isinstance(region, dict):
                        raise TypeError("SARIF region must be an object")
                    line   = region.get("startLine", 0)
                    col    = region.get("startColumn", 0)
                else:
                    filepath = ""
                    line     = 0
                    col      = 0

                fid = _make_id(tool_name, filepath, line, rule)
                findings.append(Finding(
                    id=fid, severity=sev,
                    file=filepath, line=line, col=col,
                    rule=rule, source=tool_name, message=msg,
                    context_lines=_read_context(filepath, line) if filepath else [],
                ))
    except (json.JSONDecodeError, TypeError, KeyError) as exc:
        if strict:
            raise ValueError(f"Invalid SARIF input: {exc}") from exc
        # Best-effort mode keeps optional ingestion non-fatal, but callers that
        # must fail closed can opt into strict=True.
        return []
    return findings


# ─── Runner ─────────────────────────────────────────────────────────────────

def run_linter(cmd: list, parser_fn, cwd: str = ".") -> tuple:
    """Run a linter command and parse its output. Returns (findings, error_msg).

    Uses permission_fixer to auto-fix chmod/pip-user/npm-prefix errors and retry.
    """
    try:
        r = _run_cmd(cmd, capture_output=True, text=True, timeout=60, cwd=cwd, silent=True)
        output   = r.stdout + r.stderr
        findings = parser_fn(output)
        return findings, None
    except FileNotFoundError:
        return [], f"linter not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return [], f"timeout: {cmd[0]}"
    except Exception as e:
        return [], str(e)


def run_bago_lint(target_dir: str) -> list:
    """
    BAGO's own lint: checks Python files for known issues.
    Returns list of Finding objects (no external dependency).

    Rules:
      BAGO-W001  datetime.utcnow — deprecated since Python 3.12
      BAGO-I001  raise SystemExit(1) without user-visible message
      BAGO-E001  bare except: clause — catches SystemExit/KeyboardInterrupt
      BAGO-W002  eval() or exec() — security risk # noqa: BAGO-W002
      BAGO-W003  os.system() — should use subprocess  # noqa: BAGO-W003
      BAGO-W004  hardcoded absolute user path (/Users/, /home/, C:\\) — not portable
      BAGO-I002  TODO/FIXME/HACK comments — technical debt markers
    """
    findings = []
    target = Path(target_dir)
    _bare_except_re  = re.compile(r'^\s*except\s*:', re.MULTILINE)
    _eval_exec_re    = re.compile(r'\b(eval|exec)\s*\(')
    _os_system_re    = re.compile(r'\bos\.system\s*\(')
    _hardpath_re     = re.compile(r'["\'](?:/Users/\w+|/home/\w+|C:\\\\Users\\\\)[^"\']*["\']')
    _todo_re         = re.compile(r'#.*\b(TODO|FIXME|HACK|XXX)\b', re.IGNORECASE)  # noqa: BAGO-I002
    _noqa_re         = re.compile(r'#\s*noqa(?::\s*([\w,\s-]+))?')

    for pyfile in sorted(target.rglob("*.py")):
        try:
            src   = pyfile.read_text(errors="replace")
            lines = src.splitlines()
            rel   = str(pyfile)
            is_test = "test" in pyfile.name.lower()
            for i, line in enumerate(lines, 1):
                # Check for # noqa suppression (flake8-compatible)
                noqa_m = _noqa_re.search(line)
                if noqa_m:
                    noqa_codes = {c.strip() for c in noqa_m.group(1).split(",")} if noqa_m.group(1) else set()
                    if not noqa_codes:  # bare # noqa → suppress all
                        continue
                    _noqa_all = noqa_codes  # used per-rule below
                else:
                    _noqa_all = set()

                def _suppressed(rule: str) -> bool:
                    return bool(_noqa_all and (rule in _noqa_all or "BAGO" in _noqa_all))

                # BAGO-W001: deprecated utcnow()
                if not _suppressed("BAGO-W001") and ("datetime.utcnow()" in line or ".utcnow()" in line):  # noqa: BAGO-W001
                    fid = _make_id("bago", rel, i, "BAGO-W001")
                    findings.append(Finding(
                        id=fid, severity="warning", file=rel, line=i, col=0,
                        rule="BAGO-W001", source="bago",
                        message="datetime.utcnow() deprecated — use datetime.now(timezone.utc)",  # noqa: BAGO-W001
                        fix_suggestion="Usa datetime.datetime.now(datetime.timezone.utc)",
                        autofixable=True,
                        fix_patch=_make_utcnow_patch(rel, i, line),
                        context_lines=_read_context(rel, i),
                    ))
                # BAGO-I001: bare sys.exit(1) without message (skip comments and raise SystemExit)
                _stripped_i001 = line.lstrip()
                if (not _suppressed("BAGO-I001") and not _stripped_i001.startswith('#')
                        and re.search(r'\bsys\.exit\(\d+\)\s*$', line) and not is_test):
                    fid = _make_id("bago", rel, i, "BAGO-I001")
                    findings.append(Finding(
                        id=fid, severity="info", file=rel, line=i, col=0,
                        rule="BAGO-I001", source="bago",
                        message="raise SystemExit(1) sin mensaje de error claro para el usuario",
                        fix_suggestion="Añade print(mensaje) antes de raise SystemExit(1)",
                        autofixable=False,
                        context_lines=_read_context(rel, i),
                    ))
                # BAGO-E001: bare except:
                if not _suppressed("BAGO-E001") and _bare_except_re.match(line):
                    fid = _make_id("bago", rel, i, "BAGO-E001")
                    findings.append(Finding(
                        id=fid, severity="error", file=rel, line=i, col=0,
                        rule="BAGO-E001", source="bago",
                        message="bare except: captura SystemExit y KeyboardInterrupt",
                        fix_suggestion="Usa 'except Exception:' para capturar solo errores de aplicación",
                        autofixable=True,
                        fix_patch=_make_bare_except_patch(rel, i, line),
                        context_lines=_read_context(rel, i),
                    ))
                # BAGO-W002: eval() or exec() — skip test files # noqa: BAGO-W002
                if not _suppressed("BAGO-W002") and not is_test and _eval_exec_re.search(line):
                    kw = "eval" if "eval(" in line else "exec" # noqa: BAGO-W002
                    fid = _make_id("bago", rel, i, "BAGO-W002")
                    findings.append(Finding(
                        id=fid, severity="warning", file=rel, line=i, col=0,
                        rule="BAGO-W002", source="bago",
                        message=f"{kw}() es un riesgo de seguridad — evitar en producción",
                        fix_suggestion=f"Reemplaza {kw}() por lógica explícita o ast.literal_eval()",
                        autofixable=False,
                        context_lines=_read_context(rel, i),
                    ))
                # BAGO-W003: os.system() — skip test and ci_generator  # noqa: BAGO-W003
                if not _suppressed("BAGO-W003") and not is_test and _os_system_re.search(line):
                    fid = _make_id("bago", rel, i, "BAGO-W003")
                    findings.append(Finding(
                        id=fid, severity="warning", file=rel, line=i, col=0,
                        rule="BAGO-W003", source="bago",
                        message="os.system() no captura salida ni maneja errores",  # noqa: BAGO-W003
                        fix_suggestion="Usa subprocess.run() con capture_output=True",
                        autofixable=False,
                        context_lines=_read_context(rel, i),
                    ))
                # BAGO-W004: hardcoded absolute user paths
                if not _suppressed("BAGO-W004") and not is_test and _hardpath_re.search(line):
                    m4 = _hardpath_re.search(line)
                    found_path = m4.group(0).strip("'\"") if m4 else ""
                    fid = _make_id("bago", rel, i, "BAGO-W004")
                    findings.append(Finding(
                        id=fid, severity="warning", file=rel, line=i, col=0,
                        rule="BAGO-W004", source="bago",
                        message=f"Path absoluto hardcoded: '{found_path}' — no portable",
                        fix_suggestion="Usa Path.home() / os.path.expanduser('~') o variables de entorno",
                        autofixable=False,
                        context_lines=_read_context(rel, i),
                    ))
                # BAGO-I002: TODO/FIXME/HACK  # noqa: BAGO-I002
                if not _suppressed("BAGO-I002") and _todo_re.search(line):
                    m = _todo_re.search(line)
                    kw = m.group(1).upper() if m else "TODO"
                    fid = _make_id("bago", rel, i, "BAGO-I002")
                    findings.append(Finding(
                        id=fid, severity="info", file=rel, line=i, col=0,
                        rule="BAGO-I002", source="bago",
                        message=f"{kw}: deuda técnica pendiente",
                        fix_suggestion="Resuelve o registra en bago debt",
                        autofixable=False,
                        context_lines=_read_context(rel, i),
                    ))
        except Exception:
            pass
    return findings


def _make_bare_except_patch(filepath: str, lineno: int, line: str) -> str:
    """Generate a unified diff patch for bare except → except Exception."""
    new = line.replace("except:", "except Exception:", 1)
    if new == line:
        return ""
    return (
        f"--- a/{filepath}\n+++ b/{filepath}\n"
        f"@@ -{lineno},1 +{lineno},1 @@\n"
        f"-{line}\n+{new}\n"
    )


def _make_utcnow_patch(filepath: str, lineno: int, line: str) -> str:
    """Generate a unified diff patch for utcnow replacement."""
    old = line
    new = re.sub(
        r'datetime\.datetime\.utcnow\(\)',
        'datetime.datetime.now(datetime.timezone.utc)',
        re.sub(r'datetime\.utcnow\(\)',
               'datetime.datetime.now(datetime.timezone.utc)', line)
    )
    if old == new:
        return ""
    return (
        f"--- a/{filepath}\n+++ b/{filepath}\n"
        f"@@ -{lineno},1 +{lineno},1 @@\n"
        f"-{old}\n+{new}\n"
    )


def diff_findings(before: list, after: list) -> dict:
    """Compare two lists of Finding objects.

    Identity key: (file, line, rule) — robust across re-scans.
    Returns dict with keys:
      'new'        — findings in after but not in before
      'fixed'      — findings in before but not in after
      'persistent' — findings in both runs
    """
    def _key(f: "Finding") -> tuple:
        return (f.file, f.line, f.rule)

    before_keys = {_key(f): f for f in before}
    after_keys  = {_key(f): f for f in after}

    new_keys        = set(after_keys) - set(before_keys)
    fixed_keys      = set(before_keys) - set(after_keys)
    persistent_keys = set(before_keys) & set(after_keys)

    return {
        "new":        [after_keys[k] for k in sorted(new_keys)],
        "fixed":      [before_keys[k] for k in sorted(fixed_keys)],
        "persistent": [after_keys[k] for k in sorted(persistent_keys)],
    }


# ─── Storage ─────────────────────────────────────────────────────────────────

class FindingsDB:
    def __init__(self, scan_id: str | None = None):
        if scan_id is None:
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
            scan_id = f"SCAN-{ts}"
        self.scan_id  = scan_id
        self.path     = FINDINGS_DIR / f"{scan_id}.json"
        self.findings: list = []
        self.meta:     dict = {
            "scan_id":    scan_id,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "sources":    [],
            "target":     "",
        }

    def add(self, findings: list):
        self.findings.extend(findings)

    def save(self):
        # Deduplicate by id
        seen  = set()
        dedup = []
        for f in self.findings:
            if f.id not in seen:
                seen.add(f.id)
                dedup.append(f)
        self.findings = dedup

        data = {
            "meta":     self.meta,
            "summary":  self._summary(),
            "findings": [f.to_dict() for f in self.findings],
        }
        self.path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return self.path

    def _summary(self) -> dict:
        by_sev = {s: 0 for s in SEVERITIES}
        by_src: dict = {}
        by_file: dict = {}
        for f in self.findings:
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
            by_src[f.source]   = by_src.get(f.source, 0) + 1
            by_file[f.file]    = by_file.get(f.file, 0) + 1
        autofixable = sum(1 for f in self.findings if f.autofixable)
        return {
            "total":      len(self.findings),
            "autofixable": autofixable,
            "by_severity": by_sev,
            "by_source":   by_src,
            "top_files":   sorted(by_file.items(), key=lambda x: -x[1])[:10],
        }

    @classmethod
    def load(cls, scan_id: str) -> "FindingsDB":
        db = cls(scan_id)
        if db.path.exists():
            data = json.loads(db.path.read_text())
            db.meta     = data.get("meta", {})
            db.findings = [Finding.from_dict(f) for f in data.get("findings", [])]
        return db

    @classmethod
    def latest(cls) -> "FindingsDB | None":
        scans = sorted(FINDINGS_DIR.glob("SCAN-*.json"))
        if not scans:
            return None
        scan_id = scans[-1].stem
        return cls.load(scan_id)


# ─── Tests ───────────────────────────────────────────────────────────────────

def run_tests():
    print("Ejecutando tests de findings_engine.py...")
    errors = 0
    def ok(n): print(f"  OK: {n}")
    def fail(n, m):
        nonlocal errors; errors += 1; print(f"  FAIL: {n} — {m}")

    # T1: parse_flake8
    sample_flake8 = ".bago/tools/test.py:10:1: E302 expected 2 blank lines, found 1\n.bago/tools/test.py:20:5: W291 trailing whitespace\n"
    fs = parse_flake8(sample_flake8)
    if len(fs) == 2 and fs[0].rule == "E302" and fs[0].severity == "error":
        ok("engine:parse_flake8")
    else:
        fail("engine:parse_flake8", str([(f.rule,f.severity) for f in fs]))

    # T2: parse_mypy
    sample_mypy = '.bago/tools/x.py:5: error: Incompatible return value type  [return-value]\n.bago/tools/x.py:8: note: hint here\n'
    fs2 = parse_mypy(sample_mypy)
    if len(fs2) == 2 and fs2[0].severity == "error" and fs2[1].severity == "info":
        ok("engine:parse_mypy")
    else:
        fail("engine:parse_mypy", str([(f.severity,f.rule) for f in fs2]))

    # T3: Finding autofixable flag
    f = Finding(id="X",severity="warning",file="a.py",line=1,col=0,
                rule="E302",source="flake8",message="test",autofixable=True)
    if f.autofixable:
        ok("engine:autofixable_flag")
    else:
        fail("engine:autofixable_flag", str(f))

    # T4: FindingsDB save/load roundtrip
    import tempfile, shutil
    tmp = Path(tempfile.mkdtemp())
    orig_dir = FindingsDB.__init__.__globals__["FINDINGS_DIR"]
    # Monkeypatch via module-level
    import importlib.util
    spec = importlib.util.spec_from_file_location("fe", Path(__file__))
    m    = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.FINDINGS_DIR = tmp
    db = m.FindingsDB("SCAN-TEST")
    db.add([m.Finding(id="F1",severity="error",file="a.py",line=1,col=0,
                      rule="E001",source="flake8",message="test")])
    db.save()
    db2 = m.FindingsDB.load("SCAN-TEST")
    if len(db2.findings) == 1 and db2.findings[0].id == "F1":
        ok("engine:db_roundtrip")
    else:
        fail("engine:db_roundtrip", str(db2.findings))
    shutil.rmtree(tmp)

    # T5: run_bago_lint detects utcnow
    import tempfile as tf
    tmp2 = Path(tf.mkdtemp())
    py_file = tmp2 / "sample.py"
    py_file.write_text("import datetime\nts = datetime.datetime.utcnow()\nprint(ts)\n")  # noqa: BAGO-W001
    findings = run_bago_lint(str(tmp2))
    utcnow_f = [f for f in findings if f.rule == "BAGO-W001"]
    if utcnow_f:
        ok("engine:bago_lint_utcnow")
    else:
        fail("engine:bago_lint_utcnow", str(findings))
    shutil.rmtree(tmp2)

    # T6: _make_utcnow_patch generates valid diff
    patch = _make_utcnow_patch("a.py", 5, "    ts = datetime.datetime.utcnow()")  # noqa: BAGO-W001
    if "BAGO-W001" not in patch and "datetime.timezone.utc" in patch and "@@ -5" in patch:
        ok("engine:utcnow_patch")
    else:
        fail("engine:utcnow_patch", repr(patch[:100]))

    # T7: parse_bandit JSON
    bandit_json = json.dumps({"results":[
        {"filename":"a.py","line_number":3,"test_id":"B101",
         "issue_text":"assert used","issue_severity":"LOW","more_info":""}
    ]})
    fb = parse_bandit(bandit_json)
    if len(fb)==1 and fb[0].source=="bandit" and fb[0].rule=="B101":
        ok("engine:parse_bandit")
    else:
        fail("engine:parse_bandit", str(fb))

    # T8a: bago_lint new rules (BAGO-E001, BAGO-W002, BAGO-W003, BAGO-I002)
    tmp3 = Path(tf.mkdtemp())
    py3 = tmp3 / "mixed.py"
    py3.write_text(
        "import os\n"
        "try:\n"
        "    pass\n"
        "except:  # BAGO-E001\n"
        "    pass\n"
        "result = eval('1+1')  # BAGO-W002\n" # noqa: BAGO-W002
        "os.system('ls')  # BAGO-W003\n"  # noqa: BAGO-W003
        "# TODO: fix this  # BAGO-I002\n"  # noqa: BAGO-I002
    )
    f3 = run_bago_lint(str(tmp3))
    rules3 = {f.rule for f in f3}
    if "BAGO-E001" in rules3 and "BAGO-W002" in rules3 and "BAGO-W003" in rules3 and "BAGO-I002" in rules3:
        ok("engine:bago_lint_new_rules")
    else:
        fail("engine:bago_lint_new_rules", f"found rules: {rules3}")
    # Verify bare_except patch
    patch_e = _make_bare_except_patch("b.py", 4, "    except:")
    if "except Exception:" in patch_e and "@@ -4" in patch_e:
        ok("engine:bare_except_patch")
    else:
        fail("engine:bare_except_patch", repr(patch_e[:80]))
    # T8b: BAGO-W004 hardcoded paths
    tmp4 = Path(tf.mkdtemp())
    py4 = tmp4 / "paths_config.py"
    py4.write_text("DATA_DIR = '/Users/john/data/file.txt'\n") # noqa: BAGO-W004
    f4 = run_bago_lint(str(tmp4))
    rules4 = {f.rule for f in f4}
    if "BAGO-W004" in rules4:
        ok("engine:bago_lint_w004")
    else:
        fail("engine:bago_lint_w004", f"found rules: {rules4}")
    shutil.rmtree(tmp4)
    shutil.rmtree(tmp3)

    # T8c: # noqa suppression
    tmp5 = Path(tf.mkdtemp())
    py5 = tmp5 / "noqa_sample.py"
    py5.write_text(
        "import os\n"
        "os.system('ls')  # noqa: BAGO-W003\n"
        "x = eval('1+1')\n"  # W002 NOT suppressed # noqa: BAGO-W002
    )
    f5 = run_bago_lint(str(tmp5))
    rules5 = {f.rule for f in f5}
    w003_suppressed = "BAGO-W003" not in rules5
    w002_present    = "BAGO-W002" in rules5
    if w003_suppressed and w002_present:
        ok("engine:noqa_suppression")
    else:
        fail("engine:noqa_suppression", f"rules: {rules5}, expected W003 gone + W002 present")
    shutil.rmtree(tmp5)

    # T8d: diff_findings
    f_before = [
        Finding("id1", "warning", "a.py", 10, 0, "BAGO-W001", "bago_lint", "old utcnow"),
        Finding("id2", "error",   "a.py", 20, 0, "BAGO-E001", "bago_lint", "bare except", autofixable=True),
    ]
    f_after = [
        Finding("id1", "warning", "a.py", 10, 0, "BAGO-W001", "bago_lint", "old utcnow"),
        Finding("id3", "warning", "a.py", 30, 0, "BAGO-W004", "bago_lint", "hardcoded path"),
    ]
    diff = diff_findings(f_before, f_after)
    ok_diff = (
        len(diff["new"]) == 1 and diff["new"][0].rule == "BAGO-W004" and
        len(diff["fixed"]) == 1 and diff["fixed"][0].rule == "BAGO-E001" and
        len(diff["persistent"]) == 1 and diff["persistent"][0].rule == "BAGO-W001"
    )
    if ok_diff:
        ok("engine:diff_findings")
    else:
        fail("engine:diff_findings", str(diff))

    total = 12; passed = total - errors
    print(f"\n  {passed}/{total} tests pasaron")
    if errors: raise SystemExit(1)

    # ── Extended tests for new parsers ─────────────────────────────────────
    errors2 = 0
    print("\nTests de parsers multi-lenguaje...")

    # T8: parse_eslint
    eslint_json = json.dumps([{
        "filePath": "/repo/src/app.js",
        "messages": [
            {"ruleId": "no-unused-vars", "severity": 2, "message": "'x' is defined but never used.", "line": 5, "column": 7, "fix": {"range": [0,1],"text":""}},
            {"ruleId": "semi", "severity": 1, "message": "Missing semicolon.", "line": 10, "column": 20},
        ]
    }])
    fe_list = parse_eslint(eslint_json)
    if (len(fe_list) == 2 and fe_list[0].rule == "no-unused-vars"
            and fe_list[0].severity == "error" and fe_list[0].autofixable
            and fe_list[1].severity == "warning"):
        print("  OK: engine:parse_eslint")
    else:
        errors2 += 1; print(f"  FAIL: engine:parse_eslint — {[(f.rule,f.severity,f.autofixable) for f in fe_list]}")

    # T9: parse_golangci
    gc_json = json.dumps({"Issues": [
        {"FromLinter": "errcheck", "Text": "Error return value of x not checked.",
         "Pos": {"Filename": "main.go", "Line": 15, "Column": 3}},
        {"FromLinter": "golint", "Text": "exported function Foo should have comment",
         "Pos": {"Filename": "foo.go", "Line": 7, "Column": 1}},
    ]})
    gc_list = parse_golangci(gc_json)
    if (len(gc_list) == 2 and gc_list[0].source == "golangci"
            and gc_list[0].severity == "error" and gc_list[1].severity == "warning"):
        print("  OK: engine:parse_golangci")
    else:
        errors2 += 1; print(f"  FAIL: engine:parse_golangci — {[(f.rule,f.severity) for f in gc_list]}")

    # T10: parse_clippy
    clippy_line = json.dumps({
        "reason": "compiler-message",
        "message": {
            "level": "warning",
            "code": {"code": "clippy::needless_return"},
            "message": "needless return",
            "rendered": "warning: needless return",
            "spans": [{"file_name": "src/lib.rs", "line_start": 42, "column_start": 5}],
        }
    })
    cl_list = parse_clippy(clippy_line)
    if (cl_list and cl_list[0].rule == "clippy::needless_return"
            and cl_list[0].source == "clippy"):
        print("  OK: engine:parse_clippy")
    else:
        errors2 += 1; print(f"  FAIL: engine:parse_clippy — {cl_list}")

    total2 = 3; passed2 = total2 - errors2
    print(f"\n  {passed2}/{total2} tests de parsers multi-lenguaje pasaron")
    if errors2: raise SystemExit(1)

    # ── Tests for Phase 1-3 parsers ───────────────────────────────────────
    errors3 = 0
    print("\nTests de parsers Fase 1-3...")

    # T11: parse_checkstyle (Java)
    cs_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<checkstyle version="10.0">'
        '<file name="/repo/src/Main.java">'
        '<error line="5" column="1" severity="error" message="Missing a Javadoc comment." source="com.puppycrawl.tools.checkstyle.checks.javadoc.MissingJavadocMethodCheck"/>'
        '<error line="12" column="3" severity="warning" message="Line is too long (110 > 100)." source="com.puppycrawl.tools.checkstyle.checks.sizes.LineLengthCheck"/>'
        '</file>'
        '</checkstyle>'
    )
    cs_list = parse_checkstyle(cs_xml)
    if (len(cs_list) == 2 and cs_list[0].source == "checkstyle"
            and cs_list[0].severity == "error" and cs_list[1].severity == "warning"
            and cs_list[0].rule == "MissingJavadocMethodCheck"):
        print("  OK: engine:parse_checkstyle")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_checkstyle — {[(f.rule, f.severity) for f in cs_list]}")

    # T12: parse_dotnet_build (C#)
    dotnet_out = (
        "Build FAILED.\n"
        "  /repo/Src/Program.cs(10,5): error CS0103: The name 'foo' does not exist [App.csproj]\n"
        "  /repo/Src/Program.cs(15,1): warning CS0219: Variable 'x' assigned but never used [App.csproj]\n"
    )
    dn_list = parse_dotnet_build(dotnet_out)
    if (len(dn_list) == 2 and dn_list[0].rule == "CS0103" and dn_list[0].severity == "error"
            and dn_list[1].rule == "CS0219" and dn_list[1].severity == "warning"):
        print("  OK: engine:parse_dotnet_build")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_dotnet_build — {[(f.rule, f.severity) for f in dn_list]}")

    # T13: parse_rubocop (Ruby)
    rubocop_json = json.dumps({"files": [{"path": "/repo/lib/app.rb", "offenses": [
        {"severity": "convention", "message": "Line is too long. [110/100]",
         "cop_name": "Layout/LineLength", "correctable": False,
         "location": {"line": 5, "column": 101}},
        {"severity": "error", "message": "Use snake_case for method names.",
         "cop_name": "Naming/MethodName", "correctable": True,
         "location": {"line": 12, "column": 7}},
    ]}], "summary": {"offense_count": 2}})
    rb_list = parse_rubocop(rubocop_json)
    if (len(rb_list) == 2 and rb_list[0].source == "rubocop"
            and rb_list[0].severity == "info" and rb_list[1].severity == "error"
            and rb_list[1].autofixable):
        print("  OK: engine:parse_rubocop")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_rubocop — {[(f.severity, f.autofixable) for f in rb_list]}")

    # T14: parse_phpcs (PHP)
    phpcs_json = json.dumps({"files": {"/repo/src/App.php": {"errors": 1, "warnings": 1, "messages": [
        {"message": "Missing function doc comment", "source": "PEAR.Commenting.FunctionComment.Missing",
         "severity": 5, "type": "ERROR", "line": 8, "column": 1},
        {"message": "Line exceeds 120 characters", "source": "Generic.Files.LineLength.TooLong",
         "severity": 5, "type": "WARNING", "line": 20, "column": 121},
    ]}}})
    pc_list = parse_phpcs(phpcs_json)
    if (len(pc_list) == 2 and pc_list[0].source == "phpcs"
            and pc_list[0].severity == "error" and pc_list[1].severity == "warning"):
        print("  OK: engine:parse_phpcs")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_phpcs — {[(f.severity, f.rule) for f in pc_list]}")

    # T15: parse_phpstan (PHP)
    phpstan_json = json.dumps({"totals": {"errors": 1, "file_errors": 1},
                               "files": {"/repo/src/Foo.php": {"errors": 1, "messages": [
                                   {"message": "Call to undefined method Bar::baz()", "line": 14, "ignorable": True}
                               ]}}, "errors": []})
    ps_list = parse_phpstan(phpstan_json)
    if (len(ps_list) == 1 and ps_list[0].source == "phpstan"
            and ps_list[0].severity == "error" and ps_list[0].line == 14):
        print("  OK: engine:parse_phpstan")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_phpstan — {ps_list}")

    # T16: parse_swiftlint (Swift)
    sl_json = json.dumps([
        {"file": "/repo/Sources/App.swift", "line": 7, "character": 5,
         "severity": "Error", "reason": "Force cast is not allowed.", "rule_id": "force_cast", "type": "Force Cast"},
        {"file": "/repo/Sources/App.swift", "line": 22, "character": 1,
         "severity": "Warning", "reason": "Line should be 120 characters or less.", "rule_id": "line_length", "type": "Line Length"},
    ])
    sw_list = parse_swiftlint(sl_json)
    if (len(sw_list) == 2 and sw_list[0].source == "swiftlint"
            and sw_list[0].severity == "error" and sw_list[1].severity == "warning"
            and sw_list[0].rule == "force_cast"):
        print("  OK: engine:parse_swiftlint")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_swiftlint — {[(f.severity, f.rule) for f in sw_list]}")

    # T17: parse_ktlint (Kotlin)
    kt_json = json.dumps([{"file": "/repo/src/main/kotlin/App.kt", "errors": [
        {"line": 3, "column": 1, "message": "Unnecessary semicolon", "rule": "no-semi"},
        {"line": 10, "column": 5, "message": "Missing newline after '{'", "rule": "brace-style"},
    ]}])
    kt_list = parse_ktlint(kt_json)
    if (len(kt_list) == 2 and kt_list[0].source == "ktlint"
            and kt_list[0].rule == "no-semi" and kt_list[1].rule == "brace-style"):
        print("  OK: engine:parse_ktlint")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_ktlint — {[(f.rule,) for f in kt_list]}")

    # T18: parse_shellcheck (Shell)
    sc_json = json.dumps([
        {"file": "deploy.sh", "line": 5, "column": 3, "level": "error",
         "code": 2086, "message": "Double quote to prevent globbing and word splitting.", "fix": {"replacements": []}},
        {"file": "deploy.sh", "line": 12, "column": 1, "level": "warning",
         "code": 2034, "message": "foo appears unused.", "fix": None},
    ])
    sh_list = parse_shellcheck(sc_json)
    if (len(sh_list) == 2 and sh_list[0].source == "shellcheck"
            and sh_list[0].severity == "error" and sh_list[0].rule == "SC2086"
            and sh_list[0].autofixable and not sh_list[1].autofixable):
        print("  OK: engine:parse_shellcheck")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_shellcheck — {[(f.rule, f.severity, f.autofixable) for f in sh_list]}")

    # T19: parse_tflint (Terraform)
    tf_json = json.dumps({"issues": [
        {"rule": {"name": "terraform_deprecated_interpolation", "severity": "warning"},
         "message": "Interpolation-only expressions are deprecated.",
         "range": {"filename": "main.tf", "start": {"line": 8, "column": 3}}},
        {"rule": {"name": "aws_instance_invalid_type", "severity": "error"},
         "message": "\"t1.micro\" is an invalid value as instance_type.",
         "range": {"filename": "main.tf", "start": {"line": 15, "column": 5}}},
    ], "errors": []})
    tfl_list = parse_tflint(tf_json)
    if (len(tfl_list) == 2 and tfl_list[0].source == "tflint"
            and tfl_list[0].severity == "warning" and tfl_list[1].severity == "error"):
        print("  OK: engine:parse_tflint")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_tflint — {[(f.severity,) for f in tfl_list]}")

    # T20: parse_yamllint (YAML)
    yl_out = (
        "./config.yml:3:3: [warning] wrong indentation: expected 4 but found 2 (indentation)\n"
        "./config.yml:7:1: [error] too many blank lines (2 > 1) (empty-lines)\n"
    )
    yl_list = parse_yamllint(yl_out)
    if (len(yl_list) == 2 and yl_list[0].source == "yamllint"
            and yl_list[0].severity == "warning" and yl_list[0].rule == "indentation"
            and yl_list[1].severity == "error" and yl_list[1].rule == "empty-lines"):
        print("  OK: engine:parse_yamllint")
    else:
        errors3 += 1; print(f"  FAIL: engine:parse_yamllint — {[(f.severity, f.rule) for f in yl_list]}")

    total3 = 10; passed3 = total3 - errors3
    print(f"\n  {passed3}/{total3} tests de parsers Fase 1-3 pasaron")
    if errors3: raise SystemExit(1)

    # ── Tests SARIF/CodeQL ────────────────────────────────────────────────
    errors4 = 0
    print("\nTests de parse_sarif...")

    def _sarif(results, tool="CodeQL"):
        return json.dumps({"version": "2.1.0", "runs": [
            {"tool": {"driver": {"name": tool}}, "results": results}
        ]})

    def _loc_result(rule, msg, level, filepath, line, col=0):
        return {"ruleId": rule, "message": {"text": msg}, "level": level,
                "locations": [{"physicalLocation": {
                    "artifactLocation": {"uri": filepath},
                    "region": {"startLine": line, "startColumn": col},
                }}]}

    # T21: SARIF vacío → []
    if parse_sarif(_sarif([])) == []:
        print("  OK: engine:parse_sarif_empty")
    else:
        errors4 += 1; print("  FAIL: engine:parse_sarif_empty")

    # T22: CodeQL error con file/line → Finding(source="codeql")
    sarif22 = _sarif([_loc_result("py/sql-injection", "SQL injection", "error", "app/db.py", 42, 5)])
    fs22 = parse_sarif(sarif22)
    if (len(fs22) == 1 and fs22[0].source == "codeql" and fs22[0].rule == "py/sql-injection"
            and fs22[0].file == "app/db.py" and fs22[0].line == 42 and fs22[0].severity == "error"):
        print("  OK: engine:parse_sarif_codeql_finding")
    else:
        errors4 += 1; print(f"  FAIL: engine:parse_sarif_codeql_finding — {fs22}")

    # T23: SARIF sin location → finding global, no crash
    sarif23 = _sarif([{"ruleId": "py/global", "message": {"text": "global"}, "level": "warning", "locations": []}])
    fs23 = parse_sarif(sarif23)
    if len(fs23) == 1 and fs23[0].file == "" and fs23[0].line == 0:
        print("  OK: engine:parse_sarif_no_location")
    else:
        errors4 += 1; print(f"  FAIL: engine:parse_sarif_no_location — {fs23}")

    # T24: severity mapping (error→error, warning→warning, note→info, none→hint)
    sev_cases = [("error","error"),("warning","warning"),("note","info"),("none","hint")]
    sev_ok = all(
        parse_sarif(_sarif([_loc_result(f"r-{sl}", "m", sl, "f.py", 1)]))[0].severity == es
        for sl, es in sev_cases
    )
    if sev_ok:
        print("  OK: engine:parse_sarif_severity_mapping")
    else:
        errors4 += 1; print("  FAIL: engine:parse_sarif_severity_mapping")

    # T25: ID estable para misma ubicación/regla
    r25 = _loc_result("py/injection", "msg", "error", "x.py", 10)
    id_a = parse_sarif(_sarif([r25]))[0].id
    id_b = parse_sarif(_sarif([r25]))[0].id
    if id_a == id_b and id_a.startswith("FIND-"):
        print("  OK: engine:parse_sarif_stable_id")
    else:
        errors4 += 1; print(f"  FAIL: engine:parse_sarif_stable_id — {id_a} vs {id_b}")

    # T26: strict=True hace observable un SARIF inválido
    try:
        parse_sarif("{}", strict=True)
        errors4 += 1; print("  FAIL: engine:parse_sarif_strict_invalid")
    except ValueError:
        print("  OK: engine:parse_sarif_strict_invalid")

    total4 = 6; passed4 = total4 - errors4
    print(f"\n  {passed4}/{total4} tests SARIF pasaron")
    if errors4: raise SystemExit(1)


if __name__ == "__main__":
    if "--test" in sys.argv:
        run_tests()
    else:
        print("findings_engine.py — importable module. Usa scan.py o 'bago scan'.")
