# BAGO — Reglas de UI / Menús

Estas reglas se aplican **siempre** al crear o modificar cualquier menú o
diálogo en BAGO. El código fuente canónico está en
`.bago/tools/bago/ui.py` (cabecera del módulo).

---

## REGLA 1 — Widget correcto para cada tipo de interacción

| Tipo de interacción | Función a usar |
|---|---|
| Una opción de N (radio) | `_menu_pick()` |
| Opciones ON/OFF + acciones mixtas | `_toggle_menu()` |
| Varias de N (checkbox) | `_menu_multiselect()` |
| Confirmación Sí / No | `_menu_confirm()` |
| Entrada de texto libre | `_menu_input()` |
| Botones de acción directa | `_menu_action()` |

---

## REGLA 2 — Cuándo usar botones explícitos

| Widget | Botones | Motivo |
|---|---|---|
| `_menu_pick` | ❌ No | Elegir ítem = acción inmediata |
| `_menu_multiselect` | ✅ Aceptar / Cancelar | El usuario marca N ítems; necesita confirmación |
| `_menu_confirm` | ✅ Sí / No | Decisión binaria irreversible; ambas opciones igual de visibles |
| `_toggle_menu` | ❌ No | Los toggles se confirman al salir con Esc o eligiendo una acción |
| `_menu_input` | ✅ OK / Cancel | Entrada de texto libre; necesita confirmación |

> En `_menu_pick` y `_toggle_menu` no hay botones porque la interacción
> es suficientemente explícita con Enter / Esc.

---

## REGLA 3 — Un único camino de salida

Nunca duplicar la salida poniendo un ítem `__exit__` / `__cancel__` en la
lista **y** un botón Cancelar al mismo tiempo. Un solo mecanismo: `Esc` / `C-c`.

---

## REGLA 4 — Esc siempre = atrás / sin ejecutar

Todo widget vincula `"escape"` y `"c-c"` (con `eager=True`) al handler de
cancelación que **cierra sin ejecutar ninguna acción**.

> **Aclaración vs R5**: en `_toggle_menu`, Esc devuelve el estado actual de
> los toggles pero la decisión de aplicarlos o descartarlos es **del llamador**.
> La convención BAGO es: **Esc = descartar cambios**. El llamador no aplica
> `result["toggles"]` si `result["action"] is None`.

---

## REGLA 5 — Opciones booleanas (ON/OFF) usan `_toggle_menu`

Nunca usar `_menu_pick` para valores booleanos.

**Vocabulario diferenciado** (evita ambigüedad con R2/R6):

| Término | Significado |
|---|---|
| **elegir** | Seleccionar un ítem de acción → cierra el menú |
| **conmutar** | Cambiar el estado ON/OFF de un toggle → NO cierra |

| Tecla | Sobre toggle | Sobre ítem acción |
|---|---|---|
| `Space` | Conmuta ON⟷OFF (no cierra) | — |
| `Enter` | Conmuta ON⟷OFF (no cierra) | Elige → cierra, devuelve acción |
| `Esc` | — | Cierra sin elegir ninguna acción |

> Esc devuelve `result["action"] = None`. El llamador **descarta** los
> cambios de toggles cuando `action is None` (ver R4).

---

## REGLA 6 — Sin bucles implícitos en el widget

**Elegir** una acción cierra el menú. **Conmutar** un toggle no cierra
(solo actualiza el estado visual en sitio — no es un "loop", es edición
in-place).

Si el llamador necesita volver al menú después de ejecutar una sub-acción
(por ejemplo, `/config` → nivel de confirmación → volver a config), lo
controla con un `while True` explícito. El widget no hace loops internos.

---

## REGLA 7 — Hint de teclas siempre visible al pie

Todo menú muestra al pie la línea de ayuda:

```
Arriba/Abajo navegar   [teclas específicas del widget]   Esc volver
```

Implementado como `Label(..., style="class:label")` dentro del `Frame`.

---

*Última actualización: sesión BAGO — toggle-switch-widget*
