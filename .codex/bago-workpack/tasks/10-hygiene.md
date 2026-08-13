# Dead code, legacy, dependencias, CSS y docs

Usa `bago_hygiene_scanner`.

Realiza barridos de:
- componentes/hooks/handlers/endpoints/tipos/CSS no usados;
- mocks, backups, legacy, feature flags antiguas e implementaciones sustituidas;
- dependencias sin uso o duplicadas;
- CSS monolítico, hardcodes y selectors globales;
- documentación que contradiga el código.

Clasifica candidatos como SEGURO_DE_RETIRAR, PROBABLEMENTE_RETIRABLE, REQUIERE_INVESTIGACION o ACTIVO.
No elimines ni actualices nada.
