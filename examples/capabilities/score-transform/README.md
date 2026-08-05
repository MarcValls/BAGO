# Analizar y transformar partitura

Capability Package local para BAGO. Acepta PDF, imagen, MusicXML, XML o MXL.

- PDF e imagen: reconocimiento OMR real mediante Audiveris.
- MusicXML/MXL: normalización, validación estructural y análisis armónico por compás.
- Transposición: modifica las alturas de las notas por semitonos.
- Separación de voces: genera un MusicXML por valor de `voice`.
- Operación completa: ejecuta conversión, análisis, transposición opcional y separación.

Requiere confirmar `filesystem.read`, `filesystem.write` y `process`. La salida
se guarda junto al archivo original o en la carpeta configurada. Los errores del
motor no se ocultan: producen una ejecución fallida con receipt.
