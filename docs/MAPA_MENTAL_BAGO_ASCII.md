# Mapa Mental BAGO

```text
BAGO
â”œâ”€ E:\bago_fw  [checkout/runtime]
â”‚  â”œâ”€ bago_core/            bootstrap, launcher, installer
â”‚  â”œâ”€ .bago/                runtime real
â”‚  â”‚  â”œâ”€ tools/             comandos, validadores, smoke, cosecha
â”‚  â”‚  â”œâ”€ state/             memoria, sesiones, cambios, evidencias
â”‚  â”‚  â”œâ”€ docs/              docs canÃ³nicos usados por validaciÃ³n
â”‚  â”‚  â”œâ”€ knowledge/         memoria de conocimiento
â”‚  â”‚  â””â”€ pack.json          entrada canÃ³nica del pack
â”‚  â”œâ”€ install.ps1           instalaciÃ³n Windows
â”‚  â”œâ”€ smoke-test.ps1        smoke postinstalaciÃ³n
â”‚  â”œâ”€ runtime_contract.json contrato vivo del runtime
â”‚  â””â”€ docs/                 documentaciÃ³n humana
â””â”€ E:\bago_projects\task_manager  [proyecto real visible]
   â”œâ”€ task_manager.py
   â””â”€ tasks.json
```

## Frentes

```text
1. Runtime y arranque
   â”œâ”€ launcher
   â”œâ”€ installer
   â”œâ”€ smoke
   â””â”€ validate

2. Estado y memoria
   â”œâ”€ global_state.json
   â”œâ”€ sessions / changes / evidences
   â””â”€ artefactos generados

3. Cosecha y salud
   â”œâ”€ cosecha.py
   â”œâ”€ health_score.py
   â””â”€ session history

4. DocumentaciÃ³n canÃ³nica
   â”œâ”€ docs/
   â””â”€ .bago/docs/

5. Proyecto real
   â””â”€ E:\bago_projects\task_manager

6. InstalaciÃ³n
   â”œâ”€ install.ps1
   â”œâ”€ bago_core/installer.py
   â””â”€ E:\START.bat
```

## QuÃ© estÃ¡ verde

```text
validate_pack  -> GO
smoke          -> pass
health_score   -> 100 green
```

## QuÃ© sigue abierto

```text
1. Elegir el Ã¡rbol de verdad para seguir
2. Separar cÃ³digo de estado generado
3. Confirmar instalaciÃ³n limpia real
4. Unificar docs canÃ³nicos
5. Volver a un proyecto concreto
```
