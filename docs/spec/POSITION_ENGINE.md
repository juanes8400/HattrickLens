# Motor de posiciones — Manual no Escrito

## Propósito

El motor clasifica la plantilla por posición y orden individual usando las
matrices de aportes del [Manual no Escrito](https://wiki.hattrick.org/wiki/Manual_no_Escrito).
No replica estrellas ni se ajusta contra Hattrick Control: la salida es un
**índice de aporte a sectores** para comparar alternativas tácticas.

## Fuente y alcance

`backend/app/config/positions.yaml` contiene la matriz completa de las 19
posiciones de campo:

- Defensa central y defensa lateral.
- Mediocampo.
- Ataque central y ataque lateral.

Cada celda expresa `habilidad × contribución relativa` del Manual para ese
puesto y su orden. Las posiciones laterales representan el lado propio del
jugador. El optimizador de alineaciones aplica también las penalizaciones por
superpoblación que documenta el Manual para DC, MC y delanteros normales.

## Cálculo

Para cada habilidad relevante se obtiene primero la habilidad efectiva:

```text
habilidad efectiva = habilidad + ln(experiencia) × 4/3 + fidelidad/19
factor de forma   = ((forma - 0,5) / 7) ^ 0,45
factor condición  = ((condición + 6,5) / 14) ^ 0,6
```

El aporte de cada sector es la suma de sus `coeficiente × habilidad efectiva`,
multiplicada por forma y condición. Para comparar puestos, el índice se divide
por la suma de coeficientes declarados en ese puesto: es una normalización
matemática, no una escala ajustada. El campo `rating` de la API mantiene ese
nombre por compatibilidad, pero representa ese aporte medio ponderado y no una
valoración oficial del partido.

## Roles especiales

- **Capitán:** `3 × liderazgo + 2 × experiencia`, criterio recomendado por el
  Manual para mejorar o igualar la experiencia de equipo automática.
- **Lanzador de faltas directas:** pelota parada y experiencia; son las dos
  habilidades que el Manual identifica para TLD. Mientras no publique una
  ponderación entre ambas, se muestra su suma transparente, sin inventar una.

## Reglas de producto

- La interfaz debe llamarlo “aporte” o “índice de aporte”, nunca estrellas.
- Cada recomendación debe mostrar su fuente: **Manual no Escrito**.
- La interfaz no hace los cálculos: solo consume el motor del servidor.
- La matriz se mantiene declarativa en YAML; cambiar un coeficiente exige
  actualizar el Manual o dejar trazada una nueva fuente comunitaria.
