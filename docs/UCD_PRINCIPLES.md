# Diseño Centrado en el Usuario — cómo se aplica en HT Lens

Los principios y dónde se ven en la app (`HT-Lens.html`).

1. **Tarea antes que dato.** Cada pantalla empieza por la decisión, no por la
   tabla. Inicio abre con "Qué hacer esta semana" (a quién vender, quién sube);
   Mercado con la recomendación de venta; Entrenamiento con la próxima subida.
   El dato está debajo para justificar, no encima para abrumar.

2. **Reconocer en vez de recordar.** Buscador global de jugador en la barra
   superior (no hay que recordar en qué pestaña estaba). Habilidades con su
   nombre oficial del juego ("clase mundial", "excelente"), no solo el número.

3. **Control del usuario.** Todo lo que se puede ordenar se ordena; los filtros
   (competición, tipo de ingreso, periodo) son visibles; el plan de
   entrenamiento es un simulador editable, no un número fijo.

4. **Visibilidad del estado y honestidad.** Donde falta sincronizar un fichero,
   la pantalla dice qué falta y qué mostrará — nunca inventa. Lo incierto se
   marca (muestra corta, valor estimado, correspondencia provisional).

5. **Consistencia.** Un mismo componente (tarjeta, KPI, tabla, barra) en toda la
   app; los colores significan siempre lo mismo (verde bien, ámbar atención,
   rojo riesgo).

6. **Prevención del error.** El motor de posiciones no deja que un jugador sin
   habilidades supere a uno bueno; la suma de ayudantes se topa en 10; la
   demanda censurada se declara en vez de fingir precisión.

7. **Navegación reversible y enlazada.** Todo nombre lleva a la ficha; la ficha
   vuelve a la plantilla. Nunca un callejón sin salida.

8. **Accesibilidad.** Foco visible al tabular, filas activables con Enter,
   `aria-label` en la navegación, contraste alto en modo oscuro, ningún texto
   por debajo de 11px.

9. **Carga cognitiva mínima.** Máximo lo esencial por vista; el detalle se
   revela al pulsar (progressive disclosure). Sin adornos que no informen.
