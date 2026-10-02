# Arquitectura visual

## Mapa mental interactivo

Abre [`bago_mind_map.html`](bago_mind_map.html) en un navegador moderno. Es un
documento autónomo y funciona sin servicios externos.

La fuente estructurada de nodos y detalles es
[`bago_mind_map.data.json`](bago_mind_map.data.json). Después de editarla,
actualiza el HTML derivado con:

```powershell
python scripts/update_bago_mind_map.py
```

Comprueba que el HTML coincide con los datos con:

```powershell
python scripts/update_bago_mind_map.py --check
```

El generador valida la estructura de los datos y comprueba que las reglas de
superposición mantienen por encima la rama seleccionada y el nodo enfocado.
Los nodos con `+` tienen hijos: selecciónalos para abrirlos. La búsqueda recorre
también los niveles anidados y muestra la ruta hasta cada coincidencia.
El mapa comunica contexto; para el estado operativo vigente prevalecen los
contratos y recibos del repositorio.
