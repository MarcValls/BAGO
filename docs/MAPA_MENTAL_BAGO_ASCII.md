# Mapa Mental BAGO

```text
BAGO
Ã¢â€Å“Ã¢â€â‚¬ E:\bago_fw  [checkout/runtime]
Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ bago_core/            bootstrap, launcher, installer
Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ .bago/                runtime real
Ã¢â€â€š  Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ tools/             comandos, validadores, smoke, cosecha
Ã¢â€â€š  Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ state/             memoria, sesiones, cambios, evidencias
Ã¢â€â€š  Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ docs/              docs canÃƒÂ³nicos usados por validaciÃƒÂ³n
Ã¢â€â€š  Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ knowledge/         memoria de conocimiento
Ã¢â€â€š  Ã¢â€â€š  Ã¢â€â€Ã¢â€â‚¬ pack.json          entrada canÃƒÂ³nica del pack
Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ install.ps1           instalaciÃƒÂ³n Windows
Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ smoke-test.ps1        smoke postinstalaciÃƒÂ³n
Ã¢â€â€š  Ã¢â€Å“Ã¢â€â‚¬ runtime_contract.json contrato vivo del runtime
Ã¢â€â€š  Ã¢â€â€Ã¢â€â‚¬ docs/                 documentaciÃƒÂ³n humana
Ã¢â€â€Ã¢â€â‚¬ E:\bago_projects\task_manager  [proyecto real visible]
   Ã¢â€Å“Ã¢â€â‚¬ task_manager.py
   Ã¢â€â€Ã¢â€â‚¬ tasks.json
```

## Frentes

```text
1. Runtime y arranque
   Ã¢â€Å“Ã¢â€â‚¬ launcher
   Ã¢â€Å“Ã¢â€â‚¬ installer
   Ã¢â€Å“Ã¢â€â‚¬ smoke
   Ã¢â€â€Ã¢â€â‚¬ validate

2. Estado y memoria
   Ã¢â€Å“Ã¢â€â‚¬ global_state.json
   Ã¢â€Å“Ã¢â€â‚¬ sessions / changes / evidences
   Ã¢â€â€Ã¢â€â‚¬ artefactos generados

3. Cosecha y salud
   Ã¢â€Å“Ã¢â€â‚¬ cosecha.py
   Ã¢â€Å“Ã¢â€â‚¬ health_score.py
   Ã¢â€â€Ã¢â€â‚¬ session history

4. DocumentaciÃƒÂ³n canÃƒÂ³nica
   Ã¢â€Å“Ã¢â€â‚¬ docs/
   Ã¢â€â€Ã¢â€â‚¬ .bago/docs/

5. Proyecto real
   Ã¢â€â€Ã¢â€â‚¬ E:\bago_projects\task_manager

6. InstalaciÃƒÂ³n
   Ã¢â€Å“Ã¢â€â‚¬ install.ps1
   Ã¢â€Å“Ã¢â€â‚¬ bago_core/installer.py
   Ã¢â€â€Ã¢â€â‚¬ E:\START.bat
```

## QuÃƒÂ© estÃƒÂ¡ verde

```text
validate_pack  -> GO
smoke          -> pass
health_score   -> 100 green
```

## QuÃƒÂ© sigue abierto

```text
1. Elegir el ÃƒÂ¡rbol de verdad para seguir
2. Separar cÃƒÂ³digo de estado generado
3. Confirmar instalaciÃƒÂ³n limpia real
4. Unificar docs canÃƒÂ³nicos
5. Volver a un proyecto concreto
```
