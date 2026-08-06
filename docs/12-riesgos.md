# 12 — Riesgos y Mitigaciones

| # | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| 1 | **CHPP rechaza la app o restringe funciones** (es aprobación manual, caso a caso) | Media | Crítico | Aplicar temprano (fin de F1) con alcance conservador (solo lectura, user-initiated); diseñar features "allowed" primero; contacto proactivo en la conferencia CHPP; plan B: import manual de XML |
| 2 | **Prohibición de sync automático** limita la propuesta "siempre fresco" | Alta | Alto | UX construida alrededor del SyncButton (1 clic al entrar); solicitar excepción de statistics app; valor del producto no depende de frescura sino de análisis del histórico |
| 3 | **HT cambia XMLs sin aviso** | Media | Alto | Parsers tolerantes (campos desconocidos = warning), fixtures de contrato, archivado de XML crudos, feature flags para desactivar módulos rotos sin caída global |
| 4 | **Coeficientes del juego desconocidos/cambiantes** (HT ajusta motor) | Media | Alto | Coeficientes en DB versionados, recalibración continua contra datos observados, mostrar intervalos (nunca certezas), suite de backtesting detecta drift |
| 5 | **Crecimiento del histórico** degrada queries | Alta (a largo plazo) | Medio | Diseño particionado desde día 1, diffing que evita filas redundantes, read models; plan doc 13 |
| 6 | Rate limits CHPP / bloqueo del consumer key | Baja | Crítico | Presupuesto global conservador, backoff, monitorización de errores CHPP con alerta, cache de XML |
| 7 | Fuga de tokens CHPP | Baja | Crítico | Cifrado en reposo, sin logs, acceso solo workers, rotación de clave maestra, respuesta a incidentes documentada |
| 8 | Dependencia de 1-2 desarrolladores | Alta | Medio | Monorepo documentado, ADRs, CI estricta, cero conocimiento tribal (todo en docs/) |
| 9 | Estimaciones del filtro de sub-skills percibidas como "erróneas" | Media | Medio | UX de incertidumbre (bandas, estado "calibrando"), explicabilidad ("cómo se calculó"), feedback loop de usuarios |
| 10 | Costes de LLM del AI Assistant | Media | Bajo | Cache de intents frecuentes, modelo pequeño para parsing, límites por plan, respuestas basadas en motores (pocos tokens) |
| 11 | Competencia (Hattrick Control u otros) reacciona | Media | Bajo | Ventaja: histórico propio + motores calibrados + UX moderna; ciclo de release corto |
| 12 | GDPR / privacidad | Baja | Alto | Minimización de datos, derecho al olvido implementado, DPA con proveedores, datos en UE |

**Riesgo aceptado**: no se soportará scraping ni funciones fuera de las reglas CHPP aunque las pida la comunidad — el consumer key es el activo existencial del producto.
