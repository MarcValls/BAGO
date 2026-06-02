# BAGO Support Matrix

BAGO is Windows-first today. Other operating systems are not stable until their install, CLI, API, UI, Ollama, and packaging gates pass.

| Surface | Windows | macOS | Linux |
|---|---|---|---|
| Install scripts | Supported | Experimental | Experimental |
| CLI | Supported | Experimental | Experimental |
| Session persistence | Supported | Experimental | Experimental |
| Provider switch | Supported | Experimental | Experimental |
| Ollama local | Supported when Ollama is installed | Experimental | Experimental |
| Local API | Supported | Experimental | Experimental |
| React UI | Optional, buildable with Node/npm | Experimental | Experimental |
| Packaging | Supported via Windows release flow | Planned | Planned |
| Uninstall/rollback | Supported | Planned | Planned |

## Windows Gate

```powershell
python test_security_release.py
python test_e2e.py
python bago_core\cli.py validate
python bago_core\cli.py evidence --test
python bago_core\cli.py llm list
python bago_core\cli.py llm start --provider ollama-local --model llama3.2:3b --dry-run
```

## Non-Windows Rule

Do not mark macOS or Linux as supported until the same gate passes on that platform and the install/uninstall behavior is documented.
