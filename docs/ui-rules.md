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

## REGLA 2 — Botones OK/Cancelar SOLO en multi-select

Los botones "Aceptar"/"Cancelar" solo aparecen en `_menu_multiselect`,
donde el usuario puede marcar varias opciones y necesita confirmación
explícita.

En **single-select** (`_menu_pick`): seleccionar el ítem = aceptar.
**Sin botones.**

---

## REGLA 3 — Un único camino de salida

Nunca duplicar la salida poniendo un ítem `__exit__` / `__cancel__` en la
lista **y** un botón Cancelar al mismo tiempo. Un solo mecanismo: `Esc` / `C-c`.

---

## REGLA 4 — Esc siempre = atrás / cancelar

Todo widget vincula `"escape"` y `"c-c"` (con `eager=True`) al handler de
cancelación que sale **sin ejecutar ni guardar nada**.

---

## REGLA 5 — Opciones booleanas (ON/OFF) usan `_toggle_menu`

Nunca usar `_menu_pick` para valores booleanos.

| Tecla | Comportamiento |
|---|---|
| `Space` / `Enter` sobre toggle | Conmuta ON⟷OFF **en sitio**, sin cerrar |
| `Enter` sobre ítem acción | Cierra y devuelve `{"action": key, "toggles": {...}}` |
| `Esc` | Cierra devolviendo estado actual de todos los toggles |

---

## REGLA 6 — Sin bucles implícitos en el widget

Seleccionar una opción cierra el menú. Si el llamador necesita un bucle
(por ejemplo, `/config` con sub-menús encadenados), lo controla él con un
`while True` explícito. El widget no hace loops internos.

---

## REGLA 7 — Hint de teclas siempre visible al pie

Todo menú muestra al pie la línea de ayuda:

```
Arriba/Abajo navegar   [teclas específicas del widget]   Esc volver
```

Implementado como `Label(..., style="class:label")` dentro del `Frame`.

---

*Última actualización: sesión BAGO — toggle-switch-widget*
