# 11 — Roadmap, Sprints y Backlog

Sprints de 2 semanas. Equipo asumido: 2 devs full-stack (ajustar linealmente).

## Fase 1 — MVP (Sprints 1-6, ~3 meses)

**Entregable: un manager conecta CHPP, sincroniza y obtiene dashboard + plantilla + jugador + training básico + economía básica.**

| Sprint | Entregables |
|---|---|
| S1 | Monorepo, CI, compose, esqueleto hexagonal, auth (registro/login/JWT), modelo de datos núcleo + migraciones |
| S2 | OAuth CHPP completo, cifrado de tokens, multi-equipo, CHPP fake server para tests |
| S3 | Motor de sync v1 (teamdetails, players, training, economy), diffing + snapshots, SSE de progreso |
| S4 | Dashboard (widgets fijos v1), shell UI (sidebar, dark mode, ⌘K básico), plantilla virtualizada |
| S5 | Ficha de jugador (overview, evolución, timeline), matches sync + vista de partido básica |
| S6 | Training v1 (velocidad, expected pops), economía v1 (breakdown + forecast simple), onboarding pulido, **beta cerrada + solicitud CHPP oficial** |

Gate de salida: 20 usuarios beta, sync <60 s, p95 API <400 ms, aprobación CHPP en trámite.

## Fase 2 — Analytics (Sprints 7-11)

| Sprint | Entregables |
|---|---|
| S7 | Pricing engine v1 (hedónico + comparables), valuador de mercado, valoración en ficha |
| S8 | Training simulator what-if completo, training ROI, comparador de entrenamientos |
| S9 | Forecast económico 52 semanas con supuestos editables, Sankey, simulador económico |
| S10 | Academia completa (proyección, ranking, edad óptima de ascenso) |
| S11 | Widgets configurables drag&drop, favoritos, atajos, insights/alertas v1, exports CSV |

## Fase 3 — Predicciones (Sprints 12-15)

| Sprint | Entregables |
|---|---|
| S12 | Rating engine + calibración con partidos propios; ELO de liga; power ranking |
| S13 | Modelo de encuentro (posesión→ocasiones→goles), win prob, xG; analizador de partido completo |
| S14 | Monte Carlo de temporada (p ascenso/descenso/campeón), heatmap de posiciones, backtesting |
| S15 | Skill trader, market trends, over/underpriced roster; benchmark vs división/país |

## Fase 4 — AI (Sprints 16-18)

| Sprint | Entregables |
|---|---|
| S16 | AI Assistant: intents core (vender, entrenar, cash), function-calling sobre motores, guardrails |
| S17 | Respuestas con gráficos embebidos + "cómo se calculó"; insights proactivos v2 (anomalías) |
| S18 | Recomendador de fichajes (gap analysis de plantilla), evaluación offline del assistant |

## Fase 5 — Escalabilidad y monetización (Sprints 19-22)

| Sprint | Entregables |
|---|---|
| S19 | Billing (Stripe), planes free/pro, límites por plan, colas priorizadas |
| S20 | Optimización de volumen (doc 13): particiones automatizadas, read replicas si aplica, presupuesto de performance |
| S21 | GraphQL, API pública para terceros (keys), PWA móvil |
| S22 | Comparativas avanzadas premium, análisis colaborativo (compartir informes), hardening + auditoría de seguridad externa |

## Backlog priorizado (extracto MoSCoW)

**Must (F1)**: HU-01 conectar CHPP · HU-02 sync manual con progreso · HU-03 dashboard fuerza/finanzas/lesiones · HU-04 plantilla filtrable · HU-05 ficha jugador con histórico · HU-06 training speed + pops · HU-07 economía semanal · HU-08 multi-equipo · HU-09 dark mode/responsive.

**Should (F2)**: HU-10 valuación de jugador · HU-11 simulador training · HU-12 forecast 52 sem · HU-13 academia proyección · HU-14 widgets configurables · HU-15 alertas.

**Could (F3-F4)**: HU-16 win prob y xG · HU-17 Monte Carlo temporada · HU-18 skill trader · HU-19 AI assistant · HU-20 benchmark mundial.

**Won't (por CHPP)**: tracking de jugadores rivales, pujas automáticas, cualquier automatización de acciones en HT.

### Historias de usuario tipo (formato)
> **HU-06** — Como entrenador, quiero ver cuántas semanas faltan para el próximo pop de cada jugador entrenado, para decidir si mantengo el entrenamiento.
> Criterios: dado un roster sincronizado con ≥2 semanas de histórico, la tabla de training muestra ETA con intervalo p10-p90; si faltan datos muestra estado "calibrando" con explicación; recalcula tras cada sync.

## Definition of Done
Código tipado y testeado (cobertura del módulo ≥80%), migraciones reversibles, telemetría añadida, documentación de módulo actualizada, revisado en PR, desplegado en staging con smoke verde.
