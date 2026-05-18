# 📖 Guía: Cómo Usar BAGO en Tu Propio Proyecto

Después de la demostración exitosa, aquí te muestro cómo **usar BAGO en tus propios proyectos**.

---

## 🚀 Inicio Rápido

### **1. Tienes un proyecto existente**

```bash
# Navega a tu proyecto
cd C:\Mi\Proyecto

# Ejecuta análisis BAGO
powershell -ExecutionPolicy Bypass -File C:\Marc_max_20gb\.bago\bago_interactive_demo.ps1
```

### **2. Quieres crear un proyecto nuevo con BAGO**

```bash
# Crea estructura
mkdir mi-proyecto\src
mkdir mi-proyecto\tests

# Añade tu código
code mi-proyecto\src\app.js

# Ejecuta BAGO
powershell -ExecutionPolicy Bypass -File C:\Marc_max_20gb\.bago\bago_interactive_demo.ps1 -ProjectPath mi-proyecto
```

---

## 🎯 Workflow Típico BAGO

```
1. Escribes código
   ↓
2. Ejecutas BAGO
   ├─ AGENTS analizan
   │  ├─ Security: busca vulnerabilidades
   │  ├─ Logic: busca errores
   │  ├─ Smells: busca anti-patterns
   │  └─ Duplication: busca código repetido
   │
   ├─ ROLES deciden
   │  ├─ REVISOR_SEGURIDAD: "¿Es seguro?"
   │  ├─ REVISOR_PERFORMANCE: "¿Es eficiente?"
   │  └─ MAESTRO_BAGO: "¿Listo para producción?"
   │
   └─ Reporte final
      ├─ Hallazgos por categoría
      ├─ Veredictos de roles
      ├─ Recomendaciones
      └─ Próximos pasos
   ↓
3. Implementas recomendaciones
   ↓
4. Re-ejecutas BAGO
   ↓
5. Código con veredicto revisable para el alcance analizado
```

---

## 📋 Casos de Uso

### **Caso 1: Revisar código antes de PR**

```bash
# Tu código está en src/
# Ejecuta BAGO
powershell -File ..\..\.bago\bago_interactive_demo.ps1 -ProjectPath .

# Lee reporte
# Implementa cambios
# Haz commit + push
```

### **Caso 2: Auditoría de seguridad**

```bash
# REVISOR_SEGURIDAD te dirá:
# - Vulnerabilidades XSS
# - Uso de HTTP sin HTTPS
# - Datos sensibles expuestos
# - Validación missing

# Prioridades automáticas por severity
```

### **Caso 3: Refactoring**

```bash
# AGENTS detectan:
# - Código duplicado (Duplication Finder)
# - Code smells (Code Smell Detector)
# - Variables globales
# - Funciones muy largas

# Recomendaciones automáticas
```

### **Caso 4: Performance**

```bash
# REVISOR_PERFORMANCE te dirá:
# - Duplicación impacta mantenibilidad
# - N+1 queries
# - Memory leaks
# - Loops ineficientes
```

---

## 🛠️ Personalizar BAGO

### **Crear nuevo AGENT**

```bash
# Usa factory
cd .bago\agents
python agent_factory.py create --category "performance"

# Edita agent generado
nano performance.py

# Usa en próximo análisis
```

### **Crear nuevo ROLE**

```bash
# Usa factory
cd .bago\roles
python role_factory.py create --family especialistas --name "ml_validator"

# Edita archivo generado
nano .bago\roles\especialistas\ML_VALIDATOR.md

# BAGO lo consulta automáticamente
```

---

## 📊 Interpretar Reporte BAGO

### **Sección 1: Resumen de Hallazgos**

```
Security issues:   5  ← Número de vulnerabilidades
Logic issues:      2  ← Errores lógicos
Code smells:       3  ← Anti-patterns
Duplications:      1  ← Código repetido
```

**Prioridad:** Security > Logic > Smells > Duplication

### **Sección 2: Veredictos de Roles**

```
REVISOR_SEGURIDAD:    ACCEPTED ✅
REVISOR_PERFORMANCE:  REVIEW NEEDED 🟡
MAESTRO_BAGO:         NOT READY ❌
```

**Interpretación:**
- ✅ ACCEPTED = Cumple criterios
- 🟡 REVIEW = Requiere atención
- ❌ NOT READY = No listo para producción

### **Sección 3: Recomendaciones**

```
1. CRÍTICO: Fix security vulnerabilities
   - XSS vulnerability (innerHTML)
   - Insecure HTTP protocol
   
2. ALTO: Remove duplicate code
   - getLessonContent() vs getLesson()
   
3. MEDIO: Refactor code smells
   - Global variables (currentLesson, lessonData)
```

**Orden:** Por impacto y urgencia

### **Sección 4: Próximos Pasos**

```
1. Fix vulnerabilities
2. Complete TODOs
3. Run tests
4. Re-execute BAGO
```

**Accionable:** Pasos claros, orden específico

---

## 🔄 Ciclo de Mejora

### **Iteración 1: Análisis Inicial**

```
BAGO → 5 issues → Priority 1,2,3
```

### **Iteración 2: Fijar Prioridad 1 (Critical)**

```
Implementa fix → BAGO → 3 issues remaining
```

### **Iteración 3: Fijar Prioridad 2 (High)**

```
Implementa fix → BAGO → 1 issue remaining
```

### **Iteración 4: Fijar Prioridad 3 (Medium)**

```
Implementa fix → BAGO → 0 issues → READY FOR PRODUCTION ✅
```

---

## 💡 Tips y Buenas Prácticas

### **Usa BAGO frecuentemente**
- Después de cada feature
- Antes de cada PR
- Después de refactoring

### **Personaliza ROLES**
- Añade ROLES específicos de tu equipo
- Define criterios propios
- Automatiza decisiones

### **Integra en CI/CD**
```yaml
# GitHub Actions / GitLab CI
- name: Run BAGO Analysis
  run: powershell -File .bago/bago_interactive_demo.ps1
  
- name: Check Results
  if: bago_verdict == 'NOT_READY'
  run: exit 1  # Bloquea PR si no está listo
```

### **Documenta problemas comunes**
Crea guía sobre cómo BAGO detecta:
- Security issues específicas
- Anti-patterns en tu codebase
- Performance bottlenecks

---

## ❓ Preguntas Frecuentes

### **P: ¿Qué sucede si BAGO dice "NOT READY"?**
R: El código tiene problemas de seguridad o rendimiento. Implementa recomendaciones y re-ejecuta.

### **P: ¿Puedo ignorar los warnings de BAGO?**
R: Técnicamente sí, pero es arriesgado. BAGO encontró problemas reales que impactarán.

### **P: ¿Qué pasa si no tengo Python?**
R: Usa `bago_interactive_demo.ps1` (PowerShell). Funciona en Windows sin dependencias.

### **P: ¿Cómo creo un AGENT personalizado?**
R: `python .bago\agents\agent_factory.py create --category "mi-dominio"`

### **P: ¿Puedo desactivar ciertos AGENTS?**
R: Sí, edita `manifest.json` y marca como `"status": "disabled"`

---

## 🎓 Ejemplos Reales

### **Ejemplo 1: Bug de Seguridad**

Antes:
```javascript
innerHTML = userInput;  // Vulnerable to XSS
```

BAGO detecta:
```
🔒 Security Analyzer: XSS vulnerability
   → Use textContent or DOMPurify
```

Después:
```javascript
textContent = userInput;  // Safe
```

### **Ejemplo 2: Código Duplicado**

Antes:
```javascript
function getData() { ... }
function fetchData() { ... }  // Same logic!
```

BAGO detecta:
```
🔍 Duplication Finder: Duplicate functions
   → Consolidate into single implementation
```

Después:
```javascript
function getData() { ... }  // One function
```

### **Ejemplo 3: Performance**

Antes:
```javascript
for (let i = 0; i < data.length; i++) {
  for (let j = 0; j < data[i].items.length; j++) {
    // O(n²) complexity
  }
}
```

BAGO detecta:
```
⚡ Performance: O(n²) complexity
   → Use flat() or flatMap()
```

Después:
```javascript
const flattened = data.flatMap(d => d.items);
// O(n) complexity
```

---

## 🚀 Próximos Pasos

1. ✅ Entiendo cómo funciona BAGO
2. ✅ Ejecuté la demo exitosamente
3. → **Ahora ejecuta en tu proyecto**

```bash
# Reemplaza con tu ruta
powershell -ExecutionPolicy Bypass `
  -File C:\Marc_max_20gb\.bago\bago_interactive_demo.ps1 `
  -ProjectPath "C:\Tu\Proyecto"
```

4. → Implementa recomendaciones
5. → Re-ejecuta BAGO
6. → Código con veredicto revisable para el alcance analizado

---

## 📞 Soporte

- **Factory AGENTS:** `.bago/agents/agent_factory.py --help`
- **Factory ROLES:** `.bago/roles/role_factory.py --help`
- **Docs:** `.bago/docs/` (ROLE_ARCHITECTURE.md, AGENT_ARCHITECTURE.md)
- **Examples:** Ver `typing-course/` en este repo

---

**Happy analyzing! 🎉**

BAGO es tu especialista en código. Úsalo en cada proyecto.

---

Version: 1.0  
BAGO: 2.5-stable
