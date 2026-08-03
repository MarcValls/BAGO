TASK RESPONSE CONTRACT
Return ONLY a JSON object. No markdown, no code fences, no prose.
Required keys:
intent, objective, facts, assumptions, files_required, symbols_required, evidence, risks, proposed_changes, validation_actions, missing_information, confidence
Types:
intent: string
objective: string
facts: array
assumptions: array
files_required: array
symbols_required: array
evidence: array
risks: array
proposed_changes: array
validation_actions: array
missing_information: array
confidence: number between 0 and 1
Rules:
- Do not invent files, symbols, commands, or evidence.
- Use missing_information when evidence is insufficient.
- Keep proposed_changes minimal.
- If validation is pending, say so explicitly in validation_actions.
- If you cannot comply, return a JSON object with the same keys and confidence 0.
