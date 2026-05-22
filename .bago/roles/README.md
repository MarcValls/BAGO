# 🎭 ROLES FACTORY — Sistema de Roles Especializados BAGO

## ¿Qué hay aquí?

Este directorio contiene el **Sistema de Fábrica de Roles** de BAGO — equivalente a `agent_factory.py` pero para governance.

### Archivos principales:

| Archivo | Propósito |
|---------|-----------|
| **role_factory.py** | Factory para crear, validar y listar roles |
| **ROLE_TEMPLATE.md** | Plantilla universal de estructura de rol |
| **manifest.json** | Registro centralizado de todos los roles |
| **ROLE_ARCHITECTURE.md** (en docs/) | Documentación completa de arquitectura |

### Directorio de roles por familia:

```
.bago/roles/
├── gobierno/              ← Gobierno de BAGO (maestro, orquestador)
├── especialistas/         ← Especialistas por dominio (seguridad, UX, etc)
├── supervision/           ← Supervisión y cumplimiento (vacío)
└── produccion/            ← Operaciones y despliegue (vacío)
```

---

## 🚀 Uso Rápido

### 1. Crear un rol nuevo

```bash
cd .bago/roles
python role_factory.py create --family especialistas --name performance_auditor
```

Esto genera:
- `.bago/roles/especialistas/PERFORMANCE_AUDITOR.md` (archivo vacío con estructura)
- Entrada en `manifest.json`

### 2. Editar el rol

```bash
nano .bago/roles/especialistas/PERFORMANCE_AUDITOR.md
```

Rellenar usando las secciones de `ROLE_TEMPLATE.md`:
- Identidad
- Propósito
- Alcance
- Límites
- Entradas
- Salidas
- Activación
- No Activación
- Dependencias
- Criterio de Éxito

### 3. Validar el rol

```bash
python role_factory.py validate .bago/roles/especialistas/PERFORMANCE_AUDITOR.md
```

### 4. Listar todos los roles

```bash
python role_factory.py list                    # Todos
python role_factory.py list --family gobierno  # Solo gobierno
```

---

## 📋 Estructura de un Rol

Cada rol es un **documento MD** con estructura estándar:

```markdown
# {NOMBRE}

## Identidad
- id: role_{familia}_{nombre}
- family: {gobierno|especialistas|supervision|produccion}
- version: 2.5-stable

## Propósito
{Una frase clara}

## Alcance
- Responsabilidad 1
- Responsabilidad 2

## Límites
- Explícitamente qué NO hace

[... más secciones ...]
```

Ver **ROLE_TEMPLATE.md** para estructura completa.

---

## 🏭 Cómo Funciona la Factory

### `role_factory.py` proporciona:

```
✓ create    — Genera nuevo rol con estructura
✓ validate  — Verifica que cumple estructura
✓ list      — Muestra roles registrados
✓ families  — Describe familias disponibles
```

### Manifest.json

Registro automático de roles:

```json
{
  "roles": {
    "role_government_maestro_bago": {
      "family": "gobierno",
      "name": "maestro_bago",
      "file": "gobierno/MAESTRO_BAGO.md",
      "created": "...",
      "status": "active"
    },
    ...
  }
}
```

---

## 🎓 Familias de Roles

### GOVERNMENT (Gobierno)
Deciden, orquestan, gobiernan proceso.

**Roles existentes:**
- MAESTRO_BAGO — Interfaz principal con usuario
- ORQUESTADOR_CENTRAL — Coordina especialistas

### SPECIALIST (Especialistas)
Análisis profundo en dominio específico.

**Roles existentes:**
- REVISOR_SEGURIDAD — Audita seguridad
- REVISOR_PERFORMANCE — Analiza rendimiento
- REVISOR_UX — Valida UX
- INTEGRADOR_REPO — Gestiona integraciones

### SUPERVISION (Supervisión)
Verificación de calidad y cumplimiento.

**Roles existentes:** (ninguno, crear según necesidades)

### PRODUCTION (Producción)
Operaciones y despliegue.

**Roles existentes:** (ninguno, crear según necesidades)

---

## 🔗 Diferencia: Agents vs Roles

| Aspecto | Agents | Roles |
|---------|--------|-------|
| **Qué hacen** | Analizan código | Gobiernan proceso |
| **Cómo actúan** | subprocess + JSON | Documentos MD + lógica BAGO |
| **Cuándo** | Al revisar artefactos | En cualquier punto del ciclo |
| **Coordinación** | Paralelo (ThreadPoolExecutor) | Secuencial/gobernanza |
| **Output** | Hallazgos técnicos | Decisiones, veredictos |
| **Ejemplo** | security_analyzer.py | MAESTRO_BAGO.md |

---

## 📚 Documentación

| Documento | Contenido |
|-----------|-----------|
| **ROLE_TEMPLATE.md** | Plantilla completa + ejemplos |
| **ROLE_ARCHITECTURE.md** | Arquitectura, workflow, integración |
| **manifest.json** | Registro de roles actuales |

---

## ✅ Checklist para Crear Rol

- [ ] Usar `role_factory.py create --family X --name Y`
- [ ] Editar `.bago/roles/{family}/{NAME}.md`
- [ ] Rellenar todas las secciones de ROLE_TEMPLATE.md
- [ ] Validar con `role_factory.py validate`
- [ ] Verificar que aparece en `role_factory.py list`
- [ ] Leer ROLE_ARCHITECTURE.md para integración

---

## 🎬 Caso de Uso: Crear Especialista en Compliance

```bash
# 1. Factory crea estructura
python role_factory.py create --family especialistas --name compliance_auditor

# 2. Editar el archivo
nano .bago/roles/especialistas/COMPLIANCE_AUDITOR.md

# Llenar:
# - Propósito: Auditar GDPR, HIPAA, etc.
# - Alcance: Privacidad, consentimiento, datos sensibles
# - Activación: Cuando se toquen datos personales
# - Salidas: Reporte de cumplimiento

# 3. Validar
python role_factory.py validate .bago/roles/especialistas/COMPLIANCE_AUDITOR.md

# ✅ Rol listo. BAGO puede usarlo en siguiente ciclo.
```

---

## 🔴 Troubleshooting

### `python: command not found`
Python no está en PATH. Usa `python3` o instala Python.

### `Archivo ya existe`
Cambia el nombre del rol: `python role_factory.py create --family X --name Y_v2`

### `Falta sección` en validación
Verifica que incluiste todas las secciones de ROLE_TEMPLATE.md.

---

## 📞 Soporte

- Ver **ROLE_TEMPLATE.md** para estructura
- Ver **ROLE_ARCHITECTURE.md** para conceptos
- Revisar roles existentes como ejemplo (ej. `REVISOR_SEGURIDAD.md`)

---

**Version:** 1.0  
**Status:** Active  
**BAGO Version:** 2.5-stable
