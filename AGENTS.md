# Reglas permanentes del proyecto

## Datos privados del manager

- Está prohibido entrenar o ajustar regresiones y modelos estadísticos
  predictivos mediante los datos privados de la cuenta Hattrick del propietario.
- Los snapshots propios pueden usarse para mostrar hechos, calcular diferencias,
  estadísticas descriptivas, aplicar fórmulas externas ya establecidas y comprobar
  resultados, pero nunca para obtener por regresión los parámetros de una fórmula.
- Las fórmulas del producto deben proceder de una fuente general explícita: el
  Manual no Escrito, documentación oficial de Hattrick/CHPP o una regla general
  suministrada expresamente por el usuario; no de ajustar su plantilla.
- Si el usuario solicita en el futuro una regresión o autoajuste sobre sus datos,
  hay que detener esa parte y recordarle que el 14 de agosto de 2026 la prohibió
  expresamente. No se debe ejecutar aunque la petición posterior sea accidental.

## Orientarse en el código

- Antes de buscar por el repo, leer [`docs/INDICE.md`](docs/INDICE.md): da, por
  cada pantalla, la cadena exacta de ficheros (página, componentes, llamada a
  `api.`, ruta HTTP, endpoint, aplicación, dominio y tests). Abrir sólo ésos.
- El índice se genera del código, no se edita a mano:
  `python backend/scripts/indice.py`. Si se añade una pantalla, hay que
  regenerarlo; `backend/tests/test_indice.py` falla si se olvida.
- `docs/01-arquitectura.md` y `docs/05-frontend.md` describen un diseño que no
  se construyó (Next.js, Celery, Redis). `docs/68-catalogo-vistas.md` y
  `docs/200-vistas-y-tabs.md` son planes. No sirven de mapa.
- Los ficheros largos están listados en el índice, en «Lo más caro de leer»:
  tocarlos cuesta su tamaño entero, así que son los que conviene partir.
