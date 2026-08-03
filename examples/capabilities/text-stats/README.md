# Capability Package de ejemplo

Comprime `capability.json` y `run.py` en la raíz de un ZIP. Impórtalo desde
`Grafo > Capacidades > Externas`, confirma la confianza, actívalo y ejecútalo.

El runner recibe JSON por stdin y devuelve JSON por stdout. BAGO valida el
manifest, exige confirmación y conserva un receipt por ejecución.
