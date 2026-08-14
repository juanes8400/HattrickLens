# 07 — Algoritmos y Motores Matemáticos

Todos viven en `domain/services/` como funciones puras, parametrizadas por tablas de coeficientes versionadas. Los coeficientes exactos de Hattrick no son públicos: se parte de fuentes generales explícitas —Manual no Escrito, documentación oficial o valores comunitarios con procedencia—. Los datos privados del manager sirven para aplicar y comprobar los modelos, nunca para ajustar regresiones o reestimar sus parámetros.

## 1. Training Engine

### Velocidad de entrenamiento

Se usa la fórmula comunitaria pública de HT-Tools:

```text
K = K_tipo · K_entrenador · K_asistentes · intensidad
    · (1 − resistencia) · exposición

semanas = 16 · (reloj_edad⁻¹(reloj_edad
          + (F(nivel+1) − F(nivel+subnivel))/K) − edad)
```

- `F` es una función por tramos: el costo crece con el nivel.
- `reloj_edad` es la tabla pública 17–34, interpolada por días.
- `K_tipo` distingue cada `TrainingType`, incluidos Pases cortos y largos.
- `exposición` combina minutos/90 y la proporción full/partial de la posición.
- Todos los coeficientes y la fuente están en `training.yaml` y
  `docs/spec/TRAINING_ENGINE.md`.

### Subnivel y fecha estimada del pop

CHPP no publica el subnivel. Lens usa 0,0 salvo que exista un dato general
explícito; no lo infiere con TSI, ratings ni regresiones sobre la cuenta del
manager. Un pop confirmado reinicia el conteo histórico, pero no altera los
coeficientes ni crea una precisión decimal ficticia.

### Training ROI
`training_value_semana = Δvalor_mercado(skills+Δ) - Δvalor(depreciación por edad) - coste_prorrateado(coach, asistentes, salario)`. Comparador de entrenamientos = mismo roster evaluado bajo cada training type a horizonte H, ordenado por NPV.

## 2. Pricing Engine (valor de mercado)

Modelo en dos etapas sobre `transfer_compare_samples` (ventas observadas):

1. **Hedónico base**: `log(price) = β·features + ε` con features: skills principales (con interacciones p.ej. scoring×winger), edad (spline), specialty, forma, experiencia, salario, días a lesión, estacionalidad (semana de la temporada), divisa/liga.
   Implementación: gradient boosting (LightGBM) para no linealidades + modelo lineal interpretable de respaldo (lo que se muestra en "cómo se calculó").
2. **Ajuste local**: k-NN sobre comparables recientes (mismo arquetipo) corrige el sesgo del modelo global → banda min/max = cuantiles de los comparables.

Derivados: **overpriced/underpriced** = precio observado vs predicho (z-score); **fecha/edad óptima de venta** = argmax de `E[price(t)] · descuento(t)` sobre la trayectoria proyectada de skills/edad (el training sube valor, la edad lo baja: máximo típico antes del cliff de edad por posición); **ROI skill trading** = `E[venta] - compra - salarios·semanas - coste training`.

## 3. Ratings y predicción de partidos

### Ratings de sector
A partir de alineación + skills + forma + experiencia + spirit + táctica se estiman ratings por sector con la fórmula comunitaria (pesos por posición/rol y comportamientos individuales). Los `match_team_ratings` reales del propio equipo permiten medir el error y detectar fallos de implementación, pero no ajustar una regresión de residuos ni modificar los coeficientes.

### Probabilidad de victoria (modelo de encuentro)
Hattrick resuelve el partido por posesión y ocasiones; se modela fielmente:

1. `p_posesión = midfield_A^γ / (midfield_A^γ + midfield_B^γ)` (γ≈2.5-3 calibrable).
2. Ocasiones ~ Binomial(n_base≈10, p_posesión) repartidas por sectores (izq/centro/der + set pieces + eventos especiales por specialties).
3. `p_gol(ocasión) = σ(ataque_sector - defensa_sector)` con forma logística calibrada.
4. Convolución → distribución exacta de goles de cada equipo → `p_win/draw/loss`, marcador más probable, **xG = Σ p_gol por ocasión esperada**.

### ELO
Rating por equipo actualizado por partido: `R' = R + K·(S - E)`, `E = 1/(1+10^((R_b-R_a)/400))`, K decae con nº de partidos; ajuste por diferencia de goles (multiplicador log). Sirve de prior para rivales con pocos datos y para el Power Ranking de liga.

### Poisson bivariado (fallback rivales opacos)
Cuando no hay alineación del rival: `goles ~ Poisson(λ)` con `λ = exp(α_ataque_A + δ_defensa_B + home)` estimado por máxima verosimilitud sobre resultados de la serie (Dixon-Coles para corregir empates cortos).

## 4. Simulación de temporada (Monte Carlo)

```
por cada run (default 10.000):
  para cada jornada restante:
    muestrear resultado del modelo de encuentro (o Poisson para partidos ajenos)
    perturbar: forma ~ AR(1), lesiones ~ Poisson(exposición), spirit dinámico
  acumular tabla final con reglas de desempate de HT
salida: distribución de posiciones → p(campeón), p(ascenso directo/playoff), p(descenso), puntos esperados
```

- Implementación NumPy vectorizada (runs en batch); 10k runs de una serie de 8 equipos < 2 s en worker.
- Bayesiano: los parámetros de rivales llevan incertidumbre (posterior del ELO/Poisson) que se propaga muestreando parámetros por run → bandas honestas.
- Actualización semanal: los resultados reales re-estrechan las distribuciones (filtrado secuencial).

## 5. Economía — Forecast 52 semanas

Proyección determinista + bandas estocásticas:

- Ingresos: sponsors (función de fan mood proyectado), taquilla = `asistencia(fan_count, clima~, posición, rival) × precios`, TV/premios por calendario.
- Gastos: salarios proyectados (incluye pops → subida salarial, cumpleaños), staff, intereses, academia, médicos (esperanza de lesiones).
- Eventos discretos del usuario: ventas/compras planificadas, obras de arena (coste + nueva capacidad → nuevo equilibrio de taquilla).
- Salida: cash esperado por semana con p10/p90 (asistencia y resultados muestreados del Monte Carlo deportivo — los dos motores se acoplan).

## 6. Academia

- Potencial estimado por skill revelada/max revelado + curva de revelación (cada entrenamiento juvenil revela información → actualización bayesiana del techo).
- Edad óptima de ascenso: maximizar semanas de entrenamiento senior antes del decaimiento (17 años temprano) vs completar skills juveniles — resuelto por comparación de trayectorias simuladas.

## 7. AI Assistant (arquitectura)

No es un LLM suelto: es **function-calling sobre los motores**. Pipeline: pregunta → intent + entidades (LLM) → llamadas a query services/simuladores (mismos endpoints internos) → respuesta redactada por LLM **solo con los números devueltos** (guardrail: nunca inventar cifras; plantilla de respuesta con fuentes). Preguntas soportadas v1 mapeadas a intents: sell_recommendation, training_recommendation, cash_projection, market_valuation, promotion_eta, signing_gap. Evaluación offline con set dorado de preguntas/respuestas.

## 8. Insights y anomalías

Reglas + estadística sobre snapshots: pop atrasado vs expected (>p90) → alerta de minutos insuficientes; salario/valor fuera de banda → candidato a venta; caída de forma sostenida; asistencia bajo lo esperado → precio de entradas; detección de outliers por z-score robusto (MAD) en series propias. Cada insight enlaza al módulo que lo explica.
