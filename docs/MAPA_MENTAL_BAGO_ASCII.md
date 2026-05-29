# Mapa Mental BAGO

```text
BAGO
├─ E:\bago_fw  [checkout/runtime]
│  ├─ bago_core/            bootstrap, launcher, installer
│  ├─ .bago/                runtime real
│  │  ├─ tools/             comandos, validadores, smoke, cosecha
│  │  ├─ state/             memoria, sesiones, cambios, evidencias
│  │  ├─ docs/              docs canónicos usados por validación
│  │  ├─ knowledge/         memoria de conocimiento
│  │  └─ pack.json          entrada canónica del pack
│  ├─ install.ps1           instalación Windows
│  ├─ smoke-test.ps1        smoke postinstalación
│  ├─ runtime_contract.json contrato vivo del runtime
│  └─ docs/                 documentación humana
└─ E:\bago_projects\task_manager  [proyecto real visible]
   ├─ task_manager.py
   └─ tasks.json
```

## Frentes

```text
1. Runtime y arranque
   ├─ launcher
   ├─ installer
   ├─ smoke
   └─ validate

2. Estado y memoria
   ├─ global_state.json
   ├─ sessions / changes / evidences
   └─ artefactos generados

3. Cosecha y salud
   ├─ cosecha.py
   ├─ health_score.py
   └─ session history

4. Documentación canónica
   ├─ docs/
   └─ .bago/docs/

5. Proyecto real
   └─ E:\bago_projects\task_manager

6. Instalación
   ├─ install.ps1
   ├─ bago_core/installer.py
   └─ E:\START.bat
```

## Qué está verde

```text
validate_pack  -> GO
smoke          -> pass
health_score   -> 100 green
```

## Qué sigue abierto

```text
1. Elegir el árbol de verdad para seguir
2. Separar código de estado generado
3. Confirmar instalación limpia real
4. Unificar docs canónicos
5. Volver a un proyecto concreto
```
