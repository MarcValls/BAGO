"""promote_48_to_472.py — merge 4.8 Qwen-skin onto v4.7.2 base.

Base: release v4.7.2 oficial (ya aplicada a AppData/dev/launch).
Add: 4.8 Qwen-skin files (optional layer, does NOT replace base files).

Strategy: copy 4.8-specific files to each target. If a file already
exists in target (from the release), do NOT overwrite — the base wins.
Only NEW files are added.
"""
import shutil
from pathlib import Path

# Files that are 4.8-specific (not in v4.7.2 release)
QWEN_SKIN_FILES = [
    "_safe_print.py",
    "renderer_box.py",
    "renderer_text.py",
    "renderer_tool_box.py",
    "repl_banner.py",
    "repl_chat.py",
    "repl_chat_toolbox.py",
    "repl_hook_on_boot.py",
    "repl_hook_on_boot_diagnostics.py",
    "repl_hook_on_close.py",
    "repl_hook_on_session_end.py",
    "repl_hook_post_input_aliases.py",
    "repl_hook_post_input_transcript.py",
    "repl_hook_pre_prompt.py",
    "repl_layout.py",
    "repl_prompt.py",
    "repl_status.py",
    "repl_wizard_welcome.py",
    "repl_autoload.py",
    "repl_intent.py",
    "repl_memory.py",
    "repl_menu_palette.py",
    "repl_menu_router.py",
    "repl_model_router.py",
    "repl_navigation.py",
    "repl_ollama_cloud.py",
    "repl_plan.py",
    "repl_plan_gate.py",
    "repl_provider_detect.py",
    "repl_resume.py",
    "repl_scaffold.py",
    "repl_scaffold_stacks.py",
    "repl_scaffold_templates.py",
    "repl_schedule.py",
    "repl_search.py",
    "repl_shell_runner.py",
    "repl_subagent.py",
    "repl_text.py",
    "repl_wizard.py",
    "repl_wizard_agent.py",
    "repl_wizard_credential.py",
    "repl_wizard_credential_provider.py",
    "repl_wizard_feedback.py",
    "repl_wizard_load.py",
    "repl_wizard_memory_delete.py",
    "repl_wizard_project.py",
    "repl_wizard_quick.py",
    "repl_wizard_switch.py",
    "repl_wizard_tools.py",
    "repl_file_reader.py",
    "repl_file_writer.py",
    "repl_history.py",
    "repl_cmd_approve.py",
    "repl_cmd_digest.py",
    "repl_cmd_edit.py",
    "repl_cmd_evolve.py",
    "repl_cmd_health.py",
    "repl_cmd_ideas.py",
    "repl_cmd_inventory.py",
    "repl_cmd_memory.py",
    "repl_cmd_model.py",
    "repl_cmd_plan.py",
    "repl_cmd_read.py",
    "repl_cmd_remember.py",
    "repl_cmd_resume.py",
    "repl_cmd_router.py",
    "repl_cmd_scaffold.py",
    "repl_cmd_schedule.py",
    "repl_cmd_search.py",
    "repl_cmd_shell.py",
    "repl_cmd_skip.py",
    "repl_cmd_subagent.py",
    "repl_cmd_write.py",
    "session_context.py",
    "session_provider.py",
    "bago_wait_messages.py",
]

# Files in v4.7.2 release that we PROTECT (do not overwrite)
PROTECTED_FROM_RELEASE = {
    "commands.py",
    "renderer.py",
    "repl.py",
    "repl_inventory.py",
    "repl_menu.py",
    "system_prompt.py",
    "__init__.py",
}

HUERFANA = Path(r"C:\Program Files\BAGO\.bago\chat")
TARGETS = [
    Path(r"C:\Users\AMTEC_Terminal_1º\AppData\Local\BAGO\.bago\chat"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\dev\.bago\chat"),
    Path(r"C:\Users\AMTEC_Terminal_1º\.bago\launch\.bago\chat"),
]

for target in TARGETS:
    name = target.parent.parent.name
    print(f"\n=== {name} ===")
    added = 0
    skipped_protected = 0
    skipped_existing = 0
    for fname in QWEN_SKIN_FILES:
        src = HUERFANA / fname
        dst = target / fname
        if not src.is_file():
            continue
        if dst.is_file():
            # Already in target — skip (preserves release base)
            skipped_existing += 1
            continue
        # Add as new file (won't overwrite)
        shutil.copy2(src, dst)
        added += 1
    # Clean pycache
    pc = target / "__pycache__"
    if pc.is_dir():
        shutil.rmtree(pc)
    print(f"  added {added} new files")
    print(f"  skipped {skipped_existing} already-present")
    print(f"  protected from overwrite: {sorted(PROTECTED_FROM_RELEASE)}")

print("\n=== DONE: 4.8 Qwen-skin merged onto v4.7.2 base ===")
print("Base (release) untouched. 4.8 features available as importable modules.")
print("To enable Qwen-skin: import from repl_wizard_welcome, repl_status, repl_layout in repl.py")
