# Tree audit full prioritized

Generated with:

```powershell
python scripts\tree_state_audit.py --root . --format json --workspace-only --scan-all --max-results 100000 --output backend/docs/audit/tree-state-audit.full.json
python scripts\tree_bug_audit.py --root . --format json --scan-all --max-results 100000 --output backend/docs/audit/tree-bug-audit.full.json
python scripts\tree_truth_audit.py --root . --format json --scan-all --max-results 100000 --output backend/docs/audit/tree-truth-audit.full.json
```

- Total findings: 0
- Severity counts: {}

| Severity | File | Line | Category | Pattern | Source | Message |
|---|---|---:|---|---|---|---|
