from __future__ import annotations
import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import json, re, subprocess, sys, xml.etree.ElementTree as ET
from pathlib import Path

_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from _findings_model import Finding, _make_id, _read_context
from _findings_model import _run_cmd

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
