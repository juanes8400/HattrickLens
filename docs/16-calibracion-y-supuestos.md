# 16 — Calibración y registro de supuestos

Este documento es la fuente de verdad sobre **de dónde sale cada número** del
sistema. La regla es simple: si un coeficiente no está aquí, no puede usarse en
producción.

Estados posibles:

| Estado | Significado |
|---|---|
| ✅ **Verificado** | Derivado de datos observados con error nulo o despreciable, y reproducible |
| 🔶 **Calibrado** | Ajustado sobre observaciones reales, con error medido |
| ⚠️ **Supuesto** | Valor razonable sin verificar. Prohibido presentarlo como certeza al usuario |
| ❌ **Refutado** | Creímos algo, los datos lo desmintieron. Se documenta para no repetirlo |

---

## 1. Moneda ✅ Verificado

**Hallazgo.** CHPP entrega todos los importes en la moneda base del juego. Cada país
tiene una tasa de conversión. Colombia = 10.

**Método.** Contraste de seis campos independientes entre la respuesta de la API y la
pantalla de Hattrick Control del mismo momento.

| Campo | API | Hattrick Control | Ratio |
|---|---|---|---|
| Cash | 210.341.736 | 21.034.174 | 10,0000 |
| CostsPlayers | 2.324.280 | 232.428 | 10,0000 |
| IncomeSponsors | 1.035.000 | 103.500 | 10,0000 |
| CostsArena | 409.828 | 40.983 | 10,0000 |
| IncomeSpectators | 152.100 | 15.210 | 10,0000 |
| LastWeeksTotal | −52.364.038 | −5.236.404 | 10,0000 |

**Impacto.** Bug real en producción: todas las cifras monetarias se mostraban
infladas ×10. Corregido en `HL-006`. La tasa debe leerse de `worlddetails` por país,
nunca fijarse en código.

---

## 2. Velocidad de entrenamiento · fórmula comunitaria pública

La fórmula lineal anterior quedó **refutada y retirada**. La fórmula vigente es el
modelo público por tramos de HT-Tools, documentado completo en
`docs/spec/TRAINING_ENGINE.md`:

```text
K = K_entrenamiento × K_entrenador × K_asistentes
    × intensidad × (1 − resistencia) × exposición

semanas = 16 × (reloj_edad⁻¹(reloj_edad
          + (F(nivel+1) − F(nivel+subnivel))/K) − edad)
```

**Estado: fuente comunitaria reproducida.** No es una fórmula oficial del servidor.
Su función de habilidad, reloj de edad y coeficientes salen de la implementación
pública de HT-Tools; los valores del club salen del CHPP.

Los datos privados del manager sirven para aplicar la fórmula, mostrar pops y
contrastar errores, nunca para ajustar coeficientes. Por instrucción expresa del
propietario del 14 de agosto de 2026, está prohibido hacer regresiones,
autoaprendizaje o estimación de parámetros con esos datos. Cualquier variante
obtenida de ese modo fue retirada y no debe reintroducirse.

---

## 3. Experiencia ✅ Verificado (pesos) · 🔶 Calibrado (denominador)

**Pesos por tipo de partido.** Reconstruyen la columna "Suma" de 19 jugadores con
error **0,0000**:

| Tipo de partido | Peso |
|---|---|
| Liga | 1,0 ✅ |
| Amistoso internacional | 0,2 ✅ |
| Copa y clasificación | 1,0 ⚠️ (asumido igual a liga, sin observar) |
| Amistoso nacional | 0,1 ⚠️ (asumido, sin observar) |
| Torneos | 0,0 ⚠️ |

**Equivalentes por nivel.** Búsqueda exhaustiva del denominador constante compatible
con las 19 filas simultáneamente: rango **26,01 – 26,66**. Se adopta 26,3.

**Observación pendiente de confirmar.** El coste por nivel parece **plano**: un
jugador con experiencia "clase mundial" progresa al mismo ritmo que uno "pobre". Va
contra la intuición y una sola pantalla no basta para cerrarlo. Marcado para
re-verificar con subidas de experiencia observadas en snapshots propios.

---

## 4. Entrada de estadio ✅ Verificado (un sector)

**Precio del asiento en Tribunas = 19,0 exacto.**

**Método.** En el partido de liga contra etbenianos1 tres sectores se agotaron y solo
Tribunas quedó a medias, de modo que la diferencia entre ingresos reales e ingresos a
estadio lleno aísla ese sector sin ambigüedad:

```
(630.527 − 535.090) / (10.808 − 5.785) = 19,0000
comprobación entera: 5.023 × 19 = 95.437 ✓
```

**Pendiente.** Los precios de Grada General, Preferentes y Palcos requieren un
partido donde esos sectores **no** se llenen. Valores actuales marcados ⚠️ en
`arena_engine.TICKET_PRICES`, con el conjunto verificado declarado explícitamente en
`TICKET_PRICES_VERIFIED`.

---

## 5. Exposición al entrenamiento juvenil ✅ Verificado (leído de la interfaz)

Pesos que HC expone directamente en su panel "Valoración del entrenamiento":

| Factor | Peso |
|---|---|
| Entrenamiento principal | 1,0 |
| Entrenamiento secundario | **0,667 (⅔)** |
| Posición principal | 1,0 |
| Posición secundaria | 0,5 |
| Partido oficial | 1,0 |
| Amistoso | 0,5 |

Adoptados como valores iniciales del factor de exposición del motor de entrenamiento,
aplicable tanto a juveniles como al primer equipo.

> **Corregido el 2026-08-26.** Esta tabla decía `0,8` para el entrenamiento
> secundario y llevaba el sello «✅ Verificado», pero el valor bueno es **⅔
> (0,667)**, confirmado por el usuario. La diferencia no era cosmética: hasta
> 13 puntos por habilidad. El código (`youth_training_plan.SECUNDARIO_NORMAL`)
> siempre usó ⅔ y era el que estaba en lo cierto; lo que fallaba era este
> documento, que es peor —un número equivocado con sello de verificado se cree
> más que uno sin sello—.
>
> **Resuelto el 2026-08-28.** El **133,3 %** aplica cuando se repite exactamente
> el mismo entrenamiento: el hueco secundario normal vale `2/3` y la repetición
> lo castiga a la mitad, de modo que `100 % + (66,7 % × 50 %) = 133,3 %`.
> Entrenamientos distintos conservan el `2/3` del hueco secundario aunque
> ambos puedan producir la misma habilidad. Ejemplos: `Lateral + Individual`
> no es repetición aunque Individual sortee Lateral; `Pases + Pases` sí lo es.

---

## 6. Tipos de entrenamiento 🔶 Uno verificado, resto supuesto

**✅ Verificado: `TrainingType = 10` es "Pases (defensas y centrocampistas)"**.
Es el valor que publica la tabla paramétrica CHPP. `TrainingType = 7` es el
entrenamiento de Pases general; el 10 restringe la exposición a defensas y
centrocampistas.

**❌ Refutado.** El sistema mostraba el 10 como "Porteros". El error llegó hasta la
interfaz y generó análisis equivocados que se comunicaron al usuario.

**⚠️ Resto de la tabla.** Los demás identificadores están rellenados con el mapeo más
probable y marcados como no verificados. Cada uno se confirma contrastando el XML de
un equipo con lo que muestra la interfaz de Hattrick.

---

## 7. Modelo de predicción de liga 🔶 Calibrado · ⚠️ con limitaciones

**Modelo.** Poisson con fuerzas de ataque y defensa encogidas hacia la media de la
liga (μ = 1,35 goles/partido) con un prior equivalente a 6 partidos, ventaja de campo
1,15, y simulación Monte Carlo de 10.000 temporadas.

**❌ Refutado durante el desarrollo.** La primera versión tomó dos partidos de las
semanas 82-14 y 82-15 como si fueran las jornadas 1 y 2 de la temporada 83. Eran de
la **temporada anterior**. El error nació de inferir la temporada a partir de fechas
en lugar de leerla de `worlddetails`. Corregido en `HL-007`.

**Limitaciones vigentes.** El prior usa goles de la temporada pasada, cuando las
plantillas cambian en verano — un equipo que acaba de reforzarse está infravalorado
por el modelo. Se corrige a medida que entran resultados de la temporada en curso.

---

## 8. Series temporales 🔶 Metodología verificada

**Escalera de modelos:** naive y drift (≥2 puntos), suavizado exponencial simple
(≥4), Holt con tendencia amortiguada (≥6), Holt-Winters aditivo estacional (≥32,
dos temporadas de 16 semanas).

**Selección.** Backtesting de origen móvil sobre el histórico propio; gana el modelo
con menor error absoluto medio. No hay preferencia del autor.

**Validación.** Sobre una serie sintética con estructura conocida (déficit
estructural, taquilla cada dos semanas, premios en la semana 16), el selector eligió
modelos simples hasta las 32 semanas y cambió a Holt-Winters con 48, reduciendo el
error de 147.864 a 26.630. La estacionalidad se detectó sola, sin programarla.

**Bandas.** p10/p90 a partir de los residuos observados un paso adelante, escalados
con √h. Es una aproximación declarada: si el modelo ha fallado históricamente, las
bandas serán anchas, que es el comportamiento correcto.

---

## 9. Posiciones — Manual no Escrito · **HL-020**

**Fuente operativa.** Las 19 posiciones y órdenes individuales se calculan con
las matrices del [Manual no Escrito](https://wiki.hattrick.org/wiki/Manual_no_Escrito).
No se ajustan a estrellas ni a la pantalla de otra aplicación.

**Modelo.** Para cada sector, el motor suma `habilidad efectiva × contribución
relativa` y después aplica los factores publicados para forma y condición.
La habilidad efectiva añade `ln(experiencia) × 4/3` y el bono de fidelidad.
El resultado que ordena la pantalla se llama **índice de aporte**: es el aporte
medio ponderado a defensa, medio y ataque desde esa orden. Se divide por el
total de coeficientes del propio puesto para compararlo con otras posiciones
sin inventar una escala.

**Cobertura.** Portero, defensas centrales y laterales, mediocampistas,
extremos y delanteros —normales y sus tres órdenes— están declarados en
`app/config/positions.yaml`. El optimizador usa las penalizaciones por
superpoblación del mismo Manual para DC, MC y delanteros normales.

**Regla de honestidad.** El Manual no Escrito es investigación comunitaria y no
un reglamento oficial. La interfaz nombra la fuente, muestra sus factores y no
presenta el índice como una estrella oficial de partido.

---

## 10. Capacidades de la API CHPP

| Capacidad | Estado | Nota |
|---|---|---|
| OAuth 1.0a con HMAC-SHA1 | ✅ Verificado | Flujo completo probado de extremo a extremo |
| `players`, `teamdetails`, `training`, `economy` | ✅ Verificado | Parsers con fixtures reales |
| `matches`, `matchesarchive`, `matchdetails` | ✅ Verificado | Estructura explorada |
| `transfersteam`, `transfersplayer`, `playerdetails` | ✅ Verificado | Responden correctamente |
| Plantilla de equipos ajenos | ✅ Verificado (técnicamente) | **Restringido por reglas**: solo estado actual, nunca histórico |
| `leaguefixtures` | ⚠️ Devuelve vacío | Probado con varias versiones y parámetros; posiblemente por inicio de temporada |
| `transfersearch` | 🔶 Existe, firma incompleta | Acepta `minAge`/`maxAge`, rechaza `ageMin`; faltan obligatorios sin documentar |
| Scope `place_bid` | ✅ Documentado | Aparece en las librerías CHPP establecidas. **Corrige una afirmación previa errónea de que las pujas automáticas estaban prohibidas** |

---

## 11. Deuda de verificación

Lista viva de lo que hay que confirmar antes de que estos números lleguen a un
usuario que no sea nosotros:

1. Tabla completa de tipos de entrenamiento (12 de 13 sin verificar).
2. Precios de entrada de tres de los cuatro sectores del estadio.
3. Pesos de experiencia de copa, clasificación y amistoso nacional.
4. Si el coste por nivel de experiencia es realmente plano.
5. Firma completa de `transfersearch`.
6. Por qué `leaguefixtures` devuelve vacío.
7. Factores de entrenador, asistentes e intensidad, aislados.
8. Costes reales de construcción y mantenimiento por asiento.

Las tres primeras y la quinta se resuelven con la documentación oficial que se
obtiene al ser aprobado como CHPP. Las demás, acumulando snapshots propios.
