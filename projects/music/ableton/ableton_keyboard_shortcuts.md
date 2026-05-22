# Ableton Live 11 — Atajos de Teclado (Keyboard Shortcuts)

## NAVEGACIÓN DE VISTAS
| Acción | Atajo |
|--------|-------|
| Alternar Session / Arrangement View | `Tab` |
| Mostrar/ocultar Browser | `Ctrl+Alt+B` |
| Mostrar/ocultar Device View (chain) | `Ctrl+Alt+D` (o doble-click en track name en Arrangement) |
| Mostrar/ocultar sección I/O (E/S) | `Ctrl+Alt+I` |
| Mostrar/ocultar Sends | `Ctrl+Alt+E` |
| Mostrar/ocultar Returns | — |
| Abrir Preferencias | `Ctrl+,` |
| Pantalla completa | `F11` |

## TRANSPORT / REPRODUCCIÓN
| Acción | Atajo |
|--------|-------|
| Play / Stop | `Espacio` |
| Continuar desde cursor | `Shift+Espacio` |
| Grabar | `F9` |
| Volver al inicio | `Home` o `Ctrl+Home` |
| Activar/desactivar metrónomo | `Ctrl+Click en botón metro` |
| Loop ON/OFF | `Ctrl+L` |

## TRACKS
| Acción | Atajo |
|--------|-------|
| Nueva pista MIDI | `Ctrl+Shift+T` |
| Nueva pista Audio | `Ctrl+T` |
| Nueva pista de retorno | `Ctrl+Alt+T` |
| Renombrar pista seleccionada | `Ctrl+R` o `F2` |
| Duplicar pista | `Ctrl+D` |
| Eliminar pista | `Backspace` o `Delete` |
| Silenciar pista (Mute) | `0` |
| Solo pista | `S` (con pista seleccionada) |
| Activar grabación en pista | `Ctrl+Click en botón ARM` |

## BROWSER
| Acción | Atajo |
|--------|-------|
| Abrir búsqueda | `Ctrl+F` |
| Cargar ítem seleccionado en pista activa | `Enter` |
| Navegar resultados | `↑ ↓` |
| Preescucha (preview) | `Alt+Enter` |
| Cerrar búsqueda / Escape | `Escape` |

## CLIPS (ARRANGEMENT VIEW)
| Acción | Atajo |
|--------|-------|
| Crear clip MIDI vacío | `Ctrl+Shift+M` (en pista MIDI) |
| Duplicar clip | `Ctrl+D` |
| Cortar clip | `Ctrl+E` (split) |
| Consolidar clips | `Ctrl+J` |
| Zoom in/out timeline | `+` / `-` |
| Seleccionar todo | `Ctrl+A` |

## DISPOSITIVOS (DEVICES)
| Acción | Atajo |
|--------|-------|
| Ver cadena de dispositivos del track | Click en nombre de instrumento (panel inferior) |
| Activar/desactivar dispositivo | Click en LED del dispositivo |
| Eliminar dispositivo | Seleccionar + `Delete` |
| Mover foco al siguiente control | `Tab` (dentro del plugin) |

## MIDI / MAPEO
| Acción | Atajo |
|--------|-------|
| Modo MIDI Map | `Ctrl+M` |
| Modo Key Map | `Ctrl+K` |
| Salir de modo mapeo | `Escape` o mismo atajo |

## I/O — CONFIGURAR MIDI FROM SIN MOUSE
La única forma 100% sin mouse es editar el .als directamente:
1. Guardar el set: `Ctrl+S`
2. Cerrar Ableton: `Alt+F4`
3. Editar el XML del .als (gzip → descomprimir → modificar `<MidiInputRoutings>`)
4. Reabrir Ableton y el set

### Alternativa con teclado (dentro de Ableton):
1. `Ctrl+Alt+I` → mostrar sección I/O
2. `Tab` repetido hasta llegar al dropdown "MIDI From"
3. `↑ ↓` para navegar opciones del dropdown
4. `Enter` para confirmar

## CONFIGURAR KOMPLETE KONTROL S49 (PROCEDIMIENTO)
### En Preferencias (Ctrl+,) → pestaña MIDI:
- Buscar "Komplete Kontrol DAW" en la lista de dispositivos MIDI In
- Activar columna **Track** → ✓ (para recibir notas)
- Activar columna **Remote** → ✓ (para control remoto)
- También activar en MIDI Out si se quiere feedback al teclado

### En el track MIDI de Ableton:
- **MIDI From**: `Komplete Kontrol DAW - 4` (puerto específico DAW)
- **Channel**: `All Channels` o canal 1
- **Monitor**: `Auto` (suena cuando el track está armado)
- **ARM** (botón naranja): activar para tocar en tiempo real

### Nota importante:
El puerto correcto del S49 es `Komplete Kontrol DAW - 4`, NO `Komplete Kontrol MIDI` ni `Komplete Kontrol - 4`. El puerto DAW es el que sincroniza tempo y permite control avanzado.

## GOTCHAS APRENDIDOS
- `Tab` en Arrangement View cambia a Session View (y viceversa), no navega controles
- El dropdown "MIDI From" requiere mouse o navegación Tab extensa
- `Ctrl+Alt+I` = toggle I/O section (puede fallar si Ableton no tiene foco — verificar con click previo)
- Click en área vacía de un track MIDI en Arrangement CREA un clip nuevo — mejor clickar en el HEADER del track (franja izquierda muy estrecha ~65px)
- Para seleccionar track sin crear clip: clickar en la franja gris estrecha del header, NO en la zona de clips
- Doble-click en clip MIDI abre el piano roll (clip editor), no el device chain
- Para ver Device Chain: clickar en el nombre del instrumento en el panel inferior

## FLUJO RECOMENDADO PARA BAGO (sin mouse para MIDI routing)
```
1. Ctrl+S → guardar set actual como .als
2. Cerrar Ableton (Alt+F4)
3. Leer .als (gzip → GZipStream → XML)
4. Localizar nodo <MidiTrack> correcto (por nombre)
5. Modificar <DeviceChain><MidiInputRoutings><RoutedMidiInput>
   - <Name Value="Komplete Kontrol DAW - 4"/>
   - <ExternalInputTarget Value="..."/>
6. Volver a comprimir como gzip
7. Abrir Ableton con el set modificado
```
Este flujo es el más fiable para BAGO — evita dependencia de coordenadas de pantalla.
