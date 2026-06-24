import sys, os
sys.path.insert(0, r'C:\Users\AMTEC_Terminal_1º\BAG4.8')
sys.path.insert(0, r'C:\Users\AMTEC_Terminal_1º\BAG4.8\bago_core')
sys.path.insert(0, r'C:\Users\AMTEC_Terminal_1º\BAG4.8\.bago\chat')
os.chdir(r'C:\Users\AMTEC_Terminal_1º\BAG4.8')

from bago_core.commands.cmd_doctor import cmd_doctor
print('cmd_doctor import OK')

from repl_model_router import Selection, discover_models, ModelEntry
print('repl_model_router import OK')

entries = discover_models()
print(f'discover_models: {len(entries)} models found')
for e in entries:
    print(f'  {e.provider}/{e.model_id} [{e.best_for}] available={e.available}')