# Core Prompt Blocks

This directory stores the small prompt fragments loaded dynamically by the core runtime.

## Entry points

- `bc_policy.md`
- `behavior_policy.md`
- `intent_chat.md`
- `intent_execute.md`
- `intent_review.md`
- `intent_work.md`
- `router.md`
- `task_response_contract.md`
- `translation_en_to_es.md`
- `translation_es_to_en.md`
- `workspace_authority.md`
- `workspace_question.md`

## Notes

- These are loaded through `prompt_loader.py`.
- `intent_*.md` files are selected by intent key at runtime.
- They are prompt fragments, not standalone policy documents.
