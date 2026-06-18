# BAGO External Audit Parallel Bootstrap

This audit bundle intentionally excludes local model weights and caches.

To test BAGO in parallel while auditing the ZIP:

1. Install Ollama if it is not already available.
2. Pull one local model outside the bundle:

```powershell
ollama pull llama3.2:3b
```

3. Confirm the model is available:

```powershell
ollama list
```

4. Start BAGO against the local provider:

```powershell
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
```

5. Keep the model cache outside this ZIP. Do not add `.ollama`, model weights, checkpoints, or other local artifacts to the bundle.

Suggested parallel audit checks:

- `python bago_core\cli.py project analyze --root <repo>`
- `python scripts\verify_release_463.py`
- `python scripts\package_audit_bundle.py --test`
