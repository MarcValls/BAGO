# SIMULACIÓN: Inicio BAGO en PC nuevo (Windows)
# ==============================================

# 1. Insertas el pendrive. Windows le asigna, por ejemplo, letra F:
# 2. Abres PowerShell o CMD
# 3. Navegas al pendrive:

F:
cd F:\bago_fw

# 4. Si la letra cambió, ejecutas (SOLO si da error de ruta):
powershell -ExecutionPolicy Bypass -File .\make-portable.ps1

# 5. Inicias BAGO:
.\bago.cmd status

# 6. O directamente el chat:
.\bago.cmd launch

# Resultado esperado: Banner ASCII + "Fuente de verdad: F:\bago_fw\.bago (INSTALADO)"
# No importa que sea F:, G:, H:... make-portable.ps1 lo detecta automáticamente.
