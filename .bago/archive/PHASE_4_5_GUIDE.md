# BAGO Phase 4-5: Complete Implementation Guide

## Overview

**Phase 4**: CLI for Agents & Code Quality Orchestrator  
**Phase 5**: Role Integration & Governance Workflow  

This guide demonstrates the fully working BAGO system with:
- ✅ 4 built-in AGENTS (security, logic, smells, duplication)
- ✅ Code Quality Orchestrator (parallel execution)
- ✅ Role-based Governance (security, performance, maestro)
- ✅ Interactive CLI & Management Commands
- ✅ Custom Agent Registration

---

## Quick Start

### 1. Analyze Code Quality

```powershell
cd C:\Marc_max_20gb

# Analyze a project
powershell -ExecutionPolicy Bypass -File .bago\code_quality_orchestrator.ps1 -TargetPath "your-project\src\file.js"

# Or use BAGO CLI
powershell -ExecutionPolicy Bypass -File .bago\bago.ps1 -Command analyze -Target "your-project"
```

### 2. Start Interactive Menu

```powershell
# Open interactive CLI
powershell -ExecutionPolicy Bypass -File .bago\cli.ps1

# Or via bago command
powershell -ExecutionPolicy Bypass -File .bago\bago.ps1 -Command cli
```

### 3. Manage Agents

```powershell
# List all agents
powershell -ExecutionPolicy Bypass -File .bago\bago.ps1 -Command list-agents

# Create new agent
powershell -ExecutionPolicy Bypass -File .bago\bago.ps1 -Command new-agent `
  -NewAgent "performance_checker" -Category "performance"

# Remove agent
powershell -ExecutionPolicy Bypass -File .bago\bago.ps1 -Command remove-agent -RemoveAgent "performance_checker"
```

---

## Architecture

### Workflow: AGENTS → ROLES → VERDICTS

```
User Input (code path)
    ↓
Code Quality Orchestrator
    ├─ Agent: Security Analyzer
    │  └─ Detects: XSS, credentials, HTTP insecurity
    ├─ Agent: Logic Checker
    │  └─ Detects: TODOs, inconsistencies
    ├─ Agent: Smell Detector
    │  └─ Detects: Global variables, code smells
    └─ Agent: Duplication Finder
       └─ Detects: Duplicated code patterns
    ↓
Role Orchestrator (Governance)
    ├─ Role: REVISOR_SEGURIDAD
    │  └─ Reviews security findings → verdict
    ├─ Role: REVISOR_PERFORMANCE
    │  └─ Reviews performance findings → verdict
    └─ Role: MAESTRO_BAGO
       └─ Synthesizes all verdicts → final status
    ↓
Final Output
    ├─ Findings by severity (CRITICAL, HIGH, MEDIUM, LOW)
    ├─ Role verdicts
    └─ Production readiness: READY | CONDITIONAL | NOT_READY
```

---

## Components

### 1. Code Quality Orchestrator (`code_quality_orchestrator.ps1`)

**Purpose**: Executes all AGENTS in sequence and aggregates findings.

**Features**:
- Detects 4 categories of issues
- Groups findings by severity
- Provides line numbers and fixes

**Usage**:
```powershell
& .bago\code_quality_orchestrator.ps1 -TargetPath "file.js"
```

**Output**:
```
BAGO Code Quality Orchestrator
Launching specialized agents...
  OK: security_analyzer (findings: 2)
  OK: logic_checker (findings: 5)
  OK: smell_detector (findings: 0)
  OK: duplication_finder (findings: 5)

Synthesis of Findings
Total issues: 4
  CRITICAL: 0
  HIGH: 5
  MEDIUM: 5
  LOW: 2
```

### 2. Role Orchestrator (`role_orchestrator.ps1`)

**Purpose**: Consults governance roles with agent findings.

**Roles**:
- **REVISOR_SEGURIDAD**: Validates security
- **REVISOR_PERFORMANCE**: Evaluates performance
- **MAESTRO_BAGO**: Synthesizes verdicts

**Verdicts**: `READY`, `CONDITIONAL`, `NOT_READY`

**Example Output**:
```
BAGO Role Orchestrator - Governance Review

Consulting ROLE: REVISOR_SEGURIDAD
  Status: CONDITIONAL
  Reason: High severity issues must be addressed before production

MAESTRO_BAGO Synthesis
Final Verdict: CONDITIONAL
Recommendations:
  • Security: Fix XSS vulnerability
  • Performance: Reduce code duplication
```

### 3. BAGO CLI (`bago.ps1`)

**Purpose**: Main command-line interface for system management.

**Commands**:
```
bago help                    Show help
bago analyze <path>          Analyze code quality
bago list-agents             Show all agents
bago new-agent <name>        Create custom agent
bago remove-agent <name>     Delete agent
bago list-roles              Show all roles
bago cli                     Start interactive menu
```

### 4. Interactive CLI (`cli.ps1`)

**Purpose**: User-friendly menu for BAGO operations.

**Options**:
- [1] Analyze code with BAGO
- [2] List available AGENTS
- [3] List available ROLES
- [4] Run demo again
- [5] Read quick guide
- [6] Change project
- [0] Exit

---

## Built-in AGENTS

### Security Analyzer
- **Detects**: XSS vulnerabilities, hardcoded credentials, HTTP insecurity
- **Severity**: HIGH, CRITICAL, MEDIUM

### Logic Checker
- **Detects**: TODO markers, incomplete validations
- **Severity**: LOW

### Smell Detector
- **Detects**: Global variables, complex code patterns
- **Severity**: MEDIUM

### Duplication Finder
- **Detects**: Duplicated code blocks
- **Severity**: LOW

---

## Built-in ROLES

Located in: `.bago/roles/`

### Gobierno (Government)
- **MAESTRO_BAGO**: User interface & synthesis
- **ORQUESTADOR_CENTRAL**: Central orchestration

### Especialistas (Specialists)
- Security reviewers
- Performance evaluators
- UX validators

### Supervision
- Quality assurance
- Compliance checking

---

## Demo Project

The typing-course project demonstrates BAGO detection:

**File**: `typing-course/src/lesson.js`

**Issues Detected**:
1. **XSS_VULNERABILITY** (HIGH) - innerHTML usage
2. **HTTP_INSECURITY** (MEDIUM) - Unencrypted HTTP
3. **TODO_MARKER** (LOW) - Incomplete features
4. **DUPLICATED_CODE** (LOW) - Code duplication

**Test**:
```powershell
cd C:\Marc_max_20gb
powershell -ExecutionPolicy Bypass -File .bago\code_quality_orchestrator.ps1 -TargetPath typing-course\src\lesson.js
```

---

## Custom Agents

### Create a New Agent

```powershell
powershell -ExecutionPolicy Bypass -File .bago\bago.ps1 `
  -Command new-agent `
  -NewAgent "my_analyzer" `
  -Category "custom"
```

### Register in Manifest

Agents are auto-registered in: `.bago\manifests\custom_agents.json`

### Implement Logic

Create: `.bago\agents\my_analyzer.ps1`

Example structure:
```powershell
function Analyze-MyAgent {
    param([string]$FilePath)
    
    $findings = @()
    $content = Get-Content $FilePath -Raw
    
    # Your detection logic
    if ($content -match 'pattern') {
        $findings += @{
            type = "ISSUE_TYPE"
            severity = "HIGH"
            message = "Issue description"
            suggestion = "How to fix"
            source = "my_analyzer"
        }
    }
    
    return $findings
}
```

---

## Integration Points

### With CI/CD

The orchestrator output can be piped to:
- GitHub Actions workflows
- GitLab CI
- Jenkins pipelines
- Any JSON-aware tool

### With IDEs

- VS Code extensions (read findings JSON)
- WebStorm integration (consume exit codes)
- ESLint parsers (custom formatter)

### With Repositories

Run before commits:
```powershell
# Pre-commit hook
powershell .bago\code_quality_orchestrator.ps1 -TargetPath "staged-files"
```

---

## Severity Levels

| Level | Meaning | Action |
|-------|---------|--------|
| CRITICAL | Must fix before merge | Blocks production |
| HIGH | Should fix before merge | Conditional readiness |
| MEDIUM | Nice to have | Advisory |
| LOW | Educational | Suggestions |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (findings processed) |
| 1 | Error (missing file, etc) |
| 2 | CRITICAL issues found (blocking) |

---

## File Structure

```
.bago/
├── code_quality_orchestrator.ps1      # Main AGENT executor
├── role_orchestrator.ps1              # ROLE governance
├── bago.ps1                          # CLI interface
├── cli.ps1                           # Interactive menu
├── agents/
│   ├── security_analyzer.py
│   ├── logic_checker.py
│   ├── smell_detector.py
│   ├── duplication_finder.py
│   └── [custom agents...]
├── roles/
│   ├── gobierno/
│   │   ├── MAESTRO_BAGO.md
│   │   └── ORQUESTADOR_CENTRAL.md
│   ├── especialistas/
│   └── supervision/
└── manifests/
    └── custom_agents.json            # Registry of custom agents
```

---

## Troubleshooting

### "File not found" error
- Ensure target path exists
- Use absolute paths for consistency

### No findings detected
- Check file format (.js, .ts, .jsx, .tsx)
- Verify file contains analyzable code

### Roles not consulted
- Ensure `.bago\role_orchestrator.ps1` exists
- Check role definitions in `.bago\roles/`

### Custom agent not loaded
- Check manifest: `.bago\manifests\custom_agents.json`
- Verify agent file syntax

---

## Next Steps

### Phase 6: CI/CD Integration
- GitHub Actions workflows
- GitLab CI integration
- Pre-commit hooks

### Phase 7: Advanced Features
- Machine learning-based rule learning
- Custom rule DSL
- Team violation trends
- Performance benchmarking

### Phase 8: Enterprise Features
- Multi-project analysis
- Team dashboards
- Policy enforcement
- Audit trails

---

## Key Principles

1. **BAGO = Leader, not doer**
   - Orchestrates specialists
   - Does not analyze directly
   
2. **AGENTS = Specialists**
   - Each does ONE thing well
   - Parallel execution
   - Persistent & reusable

3. **ROLES = Governance**
   - Consult agents' findings
   - Provide verdicts
   - Enforce policy

4. **Factory Pattern**
   - Dynamic agent creation
   - Template-based generation
   - Manifest-driven registry

---

## Support

For issues or questions:
- Check `.bago/docs/` for detailed guides
- Review role definitions in `.bago/roles/`
- Test with typing-course demo first
- Run `bago help` for command reference

---

**Version**: Phase 4-5 Complete  
**Status**: Production Ready (with conditional findings)  
**Last Updated**: 2026-04-28
