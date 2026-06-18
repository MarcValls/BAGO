# BAGO Local Model Parallel Bootstrap

This bundle intentionally excludes local model weights.

If you are analyzing or testing BAGO, create the local model in parallel before running the app:

1. Install Ollama if it is not already available.
2. Pull a local model outside this bundle, for example:

```powershell
ollama pull llama3.2:3b
```

3. Verify the local model is available:

```powershell
ollama list
```

4. Run BAGO against the local provider:

```powershell
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
```

5. Keep the model cache outside the ZIP. Do not add weights, checkpoints, or Ollama caches to this bundle.

Recommended parallel test target:

- provider: `ollama-local`
- model: `llama3.2:3b`
- goal: confirm the app boots and can talk to the local model without needing bundled weights
