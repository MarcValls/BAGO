# Knowledge Topics · BAGO

Este directorio (`\.bago\knowledge\topics\`) contiene el conocimiento estructurado del framework: contratos, protocolos, guías y lecciones aprendidas.

## Topics registrados

| Topic | Propósito | Tipo |
|-------|-----------|------|
| `engine-contract.md` | Contrato del motor de BAGO (runtime, refresh-engine, perfiles) | Contrato técnico |
| `image-generation.md` | Guía de generación de imágenes | Guía de uso |
| `index.md` | Índice y mapa de topics | Índice |
| `knowledge-curation.md` | Protocolo de curación del knowledge | Protocolo |
| `learned-lessons.md` | Lecciones aprendidas del proyecto | Lección |
| `project-patterns.md` | Patrones recurrentes en proyectos BAGO | Patrón |
| `publication-contract.md` | Contrato de publicación (perfiles with/without knowledge) | Contrato técnico |
| `release-gates.md` | Puertas de liberación de versiones | Protocolo |
| `sync-protocol.md` | Protocolo de sincronización con `MarcValls/bago-knowledge` | Protocolo |
| `transposition.md` | Guía de transposición musical (módulo music) | Guía de dominio |

## Curación

1. Todo topic debe ser markdown válido.
2. Los topics de tipo **contrato técnico** deben estar alineados con el canon (`core/canon/CONTRATOS/`).
3. Los **protocolos** deben tener pasos numerados y criterio de cierre.
4. Las **lecciones** deben incluir: contexto, decisión, consecuencia, recomendación.
5. El índice (`index.md`) se regenera con `bago knowledge sync`.

## Regla

Los topics son **fuente de verdad para el runtime** cuando `knowledge/` está montado. Si hay discrepancia entre un topic y el canon, gana el canon; el topic se marca para revisión.
