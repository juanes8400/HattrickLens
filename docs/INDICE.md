# Índice del código por funcionalidad

**Generado. No se edita a mano:** `python backend/scripts/indice.py`.

Para qué sirve: para cambiar una pantalla hay que saber primero qué
ficheros la forman, y averiguarlo leyendo el repo cuesta más que el
cambio. Aquí está la cadena entera de cada ruta, sacada de las
importaciones y de los decoradores, no de lo que alguien recuerde.

Cómo se usa: busca tu ruta en la tabla, abre su apartado, y abre sólo
los ficheros que lista. Lo que no esté ahí no hace falta leerlo.

Aviso sobre los documentos vecinos: `05-frontend.md` y
`01-arquitectura.md` describen un Next.js con Celery que nunca se
construyó, y `68-catalogo-vistas.md` y `200-vistas-y-tabs.md` son
planes, no código. Para orientarse, este fichero; ésos, para historia.

## Cómo se calcula

Por **símbolo**, no por fichero, que es lo que lo hace útil:
`useTeam.ts` tiene 60 hooks y `services/api.ts` 66 miembros, así que
contar por fichero ataría cada pantalla a media aplicación. Se mira el
cuerpo del hook que se importó y el cuerpo de la función que atiende
la ruta, y se sigue desde ahí.

Lo que alcanzan 25 de las 28 rutas o más se considera
fontanería compartida y se aparta en «Transversal», al final: si no se
apartara, cada fila traería sesenta ficheros y no serviría de nada.

## Las funcionalidades

`Leer` es el total de líneas de TODO lo que hay que abrir para tocar esa
pantalla: la página, sus componentes, su cliente, su endpoint, su
aplicación y sus motores. Es la cuenta que conviene ver bajar.

| Ruta | Página | Líneas | Leer | Endpoints | Dominio | Tests |
| --- | --- | --: | --: | --- | --: | --: |
| `/connected` | [ConnectedPage.tsx](../frontend/src/pages/ConnectedPage.tsx) | 59 | - | - | 0 | 0 |
| `/welcome` | [WelcomePage.tsx](../frontend/src/pages/WelcomePage.tsx) | 237 | 1585 | auth_chpp | 0 | 0 |
| `/apoyar` | [ApoyarPage.tsx](../frontend/src/pages/ApoyarPage.tsx) | 154 | 9145 | dashboard | 10 | 33 |
| `/setup` | [SetupPage.tsx](../frontend/src/pages/SetupPage.tsx) | 428 | 9686 | auth_chpp, dashboard | 10 | 33 |
| `/dashboard` | [DashboardNuevo.tsx](../frontend/src/pages/DashboardNuevo.tsx) | 876 | 32697 | alertas, alineacion, cup, economy, league, matches, cambios, dashboard | 26 | 94 |
| `/dashboard-anterior` | [DashboardPage.tsx](../frontend/src/pages/DashboardPage.tsx) | 616 | 27630 | alertas, alineacion, league, dashboard | 24 | 88 |
| `/club` | [ClubPage.tsx](../frontend/src/pages/ClubPage.tsx) | 591 | 5579 | club | 4 | 7 |
| `/overview` | [TeamOverviewPage.tsx](../frontend/src/pages/TeamOverviewPage.tsx) | 254 | 5431 | resumen | 5 | 18 |
| `/team` | [TeamPage.tsx](../frontend/src/pages/TeamPage.tsx) | 503 | 4609 | plantilla | 3 | 14 |
| `/skills` | [SkillsPage.tsx](../frontend/src/pages/SkillsPage.tsx) | 1079 | 9403 | resumen, skills | 9 | 27 |
| `/players/:htPlayerId` | [PlayerPage.tsx](../frontend/src/pages/PlayerPage.tsx) | 1533 | 14872 | jugadores, player_balance, precio_comparable, jugadores | 14 | 40 |
| `/positions` | [PositionsPage.tsx](../frontend/src/pages/PositionsPage.tsx) | 349 | 4171 | plantilla | 3 | 14 |
| `/lineup` | [LineupPage.tsx](../frontend/src/pages/LineupPage.tsx) | 825 | 6997 | alineacion, plantilla | 8 | 19 |
| `/training` | [TrainingPage.tsx](../frontend/src/pages/TrainingPage.tsx) | 2064 | 13735 | entrenamiento, jugadores, club | 10 | 33 |
| `/transfers/balance` | [PlayerBalancePage.tsx](../frontend/src/pages/PlayerBalancePage.tsx) | 3245 | 11953 | player_balance, jugadores, plantilla | 8 | 25 |
| `/libro` | [LibroDeVisitasPage.tsx](../frontend/src/pages/LibroDeVisitasPage.tsx) | 136 | 1182 | libro | 0 | 1 |
| `/academy` | [AcademyPage.tsx](../frontend/src/pages/AcademyPage.tsx) | 4020 | 15495 | academy | 12 | 27 |
| `/matches` | [MatchesPage.tsx](../frontend/src/pages/MatchesPage.tsx) | 684 | 5759 | matches | 4 | 12 |
| `/league` | [LeaguePage.tsx](../frontend/src/pages/LeaguePage.tsx) | 1600 | 16895 | league | 13 | 63 |
| `/cup` | [CupPage.tsx](../frontend/src/pages/CupPage.tsx) | 1082 | 16511 | cup, rivals | 16 | 70 |
| `/rivals` | [RivalPickerPage.tsx](../frontend/src/pages/RivalPickerPage.tsx) | 321 | 13968 | cup, league | 10 | 51 |
| `/rivals/:rivalHtTeamId` | [RivalPage.tsx](../frontend/src/pages/RivalPage.tsx) | 1365 | 21328 | rivals, dashboard | 17 | 73 |
| `/economy` | [EconomyPage.tsx](../frontend/src/pages/EconomyPage.tsx) | 1374 | 8780 | economy | 9 | 26 |
| `/arena` | [ArenaPage.tsx](../frontend/src/pages/ArenaPage.tsx) | 510 | 3834 | arena | 3 | 8 |
| `/insights` | [InsightsPage.tsx](../frontend/src/pages/InsightsPage.tsx) | 200 | 20160 | alertas | 19 | 79 |
| `/sync` | [SyncPage.tsx](../frontend/src/pages/SyncPage.tsx) | 202 | 9234 | dashboard | 10 | 33 |
| `/news` | [SyncChangesPage.tsx](../frontend/src/pages/SyncChangesPage.tsx) | 868 | 13189 | player_balance, cambios, partidos, plantilla | 10 | 35 |
| `/transparency` | [TransparencyPage.tsx](../frontend/src/pages/TransparencyPage.tsx) | 980 | 13910 | entrenamiento, modelos, modelos | 14 | 28 |
| `/wiki` | [WikiPage.tsx](../frontend/src/pages/WikiPage.tsx) | 171 | - | - | 0 | 0 |
| `/uso` | [UsagePage.tsx](../frontend/src/pages/UsagePage.tsx) | 1007 | 2813 | uso | 1 | 4 |
| `/autor` | [AutorPage.tsx](../frontend/src/pages/AutorPage.tsx) | 331 | - | - | 0 | 0 |

## Ruta por ruta

### `/connected`

- **Página:** [frontend/src/pages/ConnectedPage.tsx](../frontend/src/pages/ConnectedPage.tsx) (59 líneas)
- **Componentes y hooks suyos (2):**
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
- Sin datos del servidor: esta pantalla no pide nada al backend.

### `/welcome`

- **Página:** [frontend/src/pages/WelcomePage.tsx](../frontend/src/pages/WelcomePage.tsx) (237 líneas)
- **Componentes y hooks suyos (7):**
  - [frontend/src/components/ImagenOpcional.tsx](../frontend/src/components/ImagenOpcional.tsx)
  - [frontend/src/components/SelectorDeIdioma.tsx](../frontend/src/components/SelectorDeIdioma.tsx)
  - [frontend/src/config/apoyo.ts](../frontend/src/config/apoyo.ts)
  - [frontend/src/hooks/useTeam/auth.ts](../frontend/src/hooks/useTeam/auth.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
- **Pide a `api.`:** `connectChpp`, `sessionProfile`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/auth.ts](../frontend/src/services/api/auth.ts)
- **Rutas HTTP:** `/auth/chpp/connect`, `/auth/chpp/session`
- **Endpoints:** [backend/app/api/v1/endpoints/auth_chpp.py](../backend/app/api/v1/endpoints/auth_chpp.py)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas)

### `/apoyar`

- **Página:** [frontend/src/pages/ApoyarPage.tsx](../frontend/src/pages/ApoyarPage.tsx) (154 líneas)
- **Componentes y hooks suyos (8):**
  - [frontend/src/components/ApoyarProyecto.tsx](../frontend/src/components/ApoyarProyecto.tsx)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/config/apoyo.ts](../frontend/src/config/apoyo.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `dashboard`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/dashboard.ts](../frontend/src/services/api/dashboard.ts)
- **Rutas HTTP:** `/teams/:x/dashboard`
- **Endpoints:** [backend/app/api/v1/endpoints/teams/dashboard.py](../backend/app/api/v1/endpoints/teams/dashboard.py)
- **Aplicación:** `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.dashboard` (6 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.minutos_del_partido` (7 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Tests (33):** `tests/test_cache_por_sync.py`, `tests/test_changes_history.py`, `tests/test_closing_the_formula.py`, `tests/test_dashboard_query.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_minutos_del_partido.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_training_engine.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/setup`

- **Página:** [frontend/src/pages/SetupPage.tsx](../frontend/src/pages/SetupPage.tsx) (428 líneas)
- **Componentes y hooks suyos (7):**
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/SyncProgressPanel.tsx](../frontend/src/components/SyncProgressPanel.tsx)
  - [frontend/src/hooks/useTeam/auth.ts](../frontend/src/hooks/useTeam/auth.ts)
  - [frontend/src/hooks/useTeam/dashboard.ts](../frontend/src/hooks/useTeam/dashboard.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
- **Pide a `api.`:** `dashboard`, `sessionProfile`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/auth.ts](../frontend/src/services/api/auth.ts), [frontend/src/services/api/dashboard.ts](../frontend/src/services/api/dashboard.ts)
- **Rutas HTTP:** `/auth/chpp/session`, `/teams/:x/dashboard`
- **Endpoints:** [backend/app/api/v1/endpoints/auth_chpp.py](../backend/app/api/v1/endpoints/auth_chpp.py), [backend/app/api/v1/endpoints/teams/dashboard.py](../backend/app/api/v1/endpoints/teams/dashboard.py)
- **Aplicación:** `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.dashboard` (6 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.minutos_del_partido` (7 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Tests (33):** `tests/test_cache_por_sync.py`, `tests/test_changes_history.py`, `tests/test_closing_the_formula.py`, `tests/test_dashboard_query.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_minutos_del_partido.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_training_engine.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/dashboard`

- **Página:** [frontend/src/pages/DashboardNuevo.tsx](../frontend/src/pages/DashboardNuevo.tsx) (876 líneas)
- **Componentes y hooks suyos (24):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/BarraDePrediccion.tsx](../frontend/src/components/BarraDePrediccion.tsx)
  - [frontend/src/components/FlorDeFuerza.tsx](../frontend/src/components/FlorDeFuerza.tsx)
  - [frontend/src/components/Insights.tsx](../frontend/src/components/Insights.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PitchField.tsx](../frontend/src/components/PitchField.tsx)
  - [frontend/src/components/SplitSelector.tsx](../frontend/src/components/SplitSelector.tsx)
  - [frontend/src/hooks/useFocoDeLista.ts](../frontend/src/hooks/useFocoDeLista.ts)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/alertas.ts](../frontend/src/hooks/useTeam/alertas.ts)
  - [frontend/src/hooks/useTeam/alineacion.ts](../frontend/src/hooks/useTeam/alineacion.ts)
  - [frontend/src/hooks/useTeam/copa.ts](../frontend/src/hooks/useTeam/copa.ts)
  - [frontend/src/hooks/useTeam/dashboard.ts](../frontend/src/hooks/useTeam/dashboard.ts)
  - [frontend/src/hooks/useTeam/economia.ts](../frontend/src/hooks/useTeam/economia.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/liga.ts](../frontend/src/hooks/useTeam/liga.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTeam/partidos.ts](../frontend/src/hooks/useTeam/partidos.ts)
  - [frontend/src/hooks/useTeam/sincronizacion.ts](../frontend/src/hooks/useTeam/sincronizacion.ts)
  - [frontend/src/i18n/glosario.ts](../frontend/src/i18n/glosario.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/pages/DashboardPage.tsx](../frontend/src/pages/DashboardPage.tsx)
  - [frontend/src/utils/alertas.ts](../frontend/src/utils/alertas.ts)
  - [frontend/src/utils/skillLevels.ts](../frontend/src/utils/skillLevels.ts)
- **Pide a `api.`:** `archiveInsight`, `changesHistory`, `cup`, `dashboard`, `economy`, `insights`, `league`, `leagueComparison`, `lineup`, `matches`, `sectoresRecientes`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/alertas.ts](../frontend/src/services/api/alertas.ts), [frontend/src/services/api/alineacion.ts](../frontend/src/services/api/alineacion.ts), [frontend/src/services/api/copa.ts](../frontend/src/services/api/copa.ts), [frontend/src/services/api/dashboard.ts](../frontend/src/services/api/dashboard.ts), [frontend/src/services/api/economia.ts](../frontend/src/services/api/economia.ts), [frontend/src/services/api/liga.ts](../frontend/src/services/api/liga.ts), [frontend/src/services/api/partidos.ts](../frontend/src/services/api/partidos.ts), [frontend/src/services/api/sincronizacion.ts](../frontend/src/services/api/sincronizacion.ts)
- **Rutas HTTP:** `/teams/:x/changes/history`, `/teams/:x/cup`, `/teams/:x/dashboard`, `/teams/:x/economy`, `/teams/:x/insights`, `/teams/:x/insights/:x/archive`, `/teams/:x/league`, `/teams/:x/league/comparison`, `/teams/:x/league/sectores-recientes`, `/teams/:x/lineup`, `/teams/:x/matches`
- **Endpoints:** [backend/app/api/v1/endpoints/analysis/alertas.py](../backend/app/api/v1/endpoints/analysis/alertas.py), [backend/app/api/v1/endpoints/analysis/alineacion.py](../backend/app/api/v1/endpoints/analysis/alineacion.py), [backend/app/api/v1/endpoints/cup.py](../backend/app/api/v1/endpoints/cup.py), [backend/app/api/v1/endpoints/economy.py](../backend/app/api/v1/endpoints/economy.py), [backend/app/api/v1/endpoints/league.py](../backend/app/api/v1/endpoints/league.py), [backend/app/api/v1/endpoints/matches.py](../backend/app/api/v1/endpoints/matches.py), [backend/app/api/v1/endpoints/teams/cambios.py](../backend/app/api/v1/endpoints/teams/cambios.py), [backend/app/api/v1/endpoints/teams/dashboard.py](../backend/app/api/v1/endpoints/teams/dashboard.py)
- **Aplicación:** `app.application.commands.sync_team` (7 rutas), `app.application.commands.sync_team.comun` (7 rutas), `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.academy`, `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.arena`, `app.application.queries.changes_history`, `app.application.queries.dashboard` (6 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.flor_de_fuerza`, `app.application.queries.league` (5 rutas), `app.application.queries.matches`, `app.application.queries.nombre_del_torneo` (6 rutas), `app.application.queries.player_balance` (7 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.academy_engine`, `app.domain.engines.arena_engine` (6 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.match_analysis`, `app.domain.engines.minutos_del_partido` (7 rutas), `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.salary_model` (7 rutas), `app.domain.engines.season_simulator` (6 rutas), `app.domain.engines.semilla` (6 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.taquilla`, `app.domain.engines.team_rating_engine`, `app.domain.engines.training_engine` (10 rutas), `app.domain.engines.youth_training_plan` (5 rutas), `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (94):** `tests/test_academy_comparativa.py`, `tests/test_academy_engine.py`, `tests/test_academy_training_plan_contract.py`, `tests/test_alertas_del_reloj.py`, `tests/test_alineacion_para_descubrir.py`, `tests/test_arena_engine.py`, `tests/test_arena_query.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_cantera_por_equipo.py`, `tests/test_changes_history.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_copa_de_esta_temporada.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_flor_de_fuerza.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_habilidades.py`, `tests/test_historial_con_reemplazo.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_insights.py`, `tests/test_insights_endpoint.py`, `tests/test_lados_del_carril.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_analysis.py`, `tests/test_match_parsers.py`, `tests/test_match_type_helpers.py`, `tests/test_metodo_de_resumen.py`, `tests/test_metodo_ocho.py`, `tests/test_middleware_idioma.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_minutos_del_partido.py`, `tests/test_ojeadores.py`, `tests/test_once_del_ultimo_partido.py`, `tests/test_parser_transfersearch.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_plan_de_entrenamiento.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_previous_club_bonus.py`, `tests/test_prioridad_de_entrenamiento.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rival_scouting.py`, `tests/test_rivals_endpoint.py`, `tests/test_salary_model.py`, `tests/test_season_simulator.py`, `tests/test_sede.py`, `tests/test_simulacion_de_venta.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_stint_edit.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_taquilla_del_partido.py`, `tests/test_team_isolation.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_timeseries_modelos_nuevos.py`, `tests/test_token_encryption.py`, `tests/test_training_engine.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ultimo_entrenamiento.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`, `tests/test_youth_parser.py`, `tests/test_youth_skill_score.py`

### `/dashboard-anterior`

- **Página:** [frontend/src/pages/DashboardPage.tsx](../frontend/src/pages/DashboardPage.tsx) (616 líneas)
- **Componentes y hooks suyos (18):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Insights.tsx](../frontend/src/components/Insights.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PitchField.tsx](../frontend/src/components/PitchField.tsx)
  - [frontend/src/components/SplitSelector.tsx](../frontend/src/components/SplitSelector.tsx)
  - [frontend/src/hooks/useFocoDeLista.ts](../frontend/src/hooks/useFocoDeLista.ts)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/alertas.ts](../frontend/src/hooks/useTeam/alertas.ts)
  - [frontend/src/hooks/useTeam/alineacion.ts](../frontend/src/hooks/useTeam/alineacion.ts)
  - [frontend/src/hooks/useTeam/dashboard.ts](../frontend/src/hooks/useTeam/dashboard.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/liga.ts](../frontend/src/hooks/useTeam/liga.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/alertas.ts](../frontend/src/utils/alertas.ts)
- **Pide a `api.`:** `archiveInsight`, `dashboard`, `insights`, `league`, `leagueComparison`, `lineup`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/alertas.ts](../frontend/src/services/api/alertas.ts), [frontend/src/services/api/alineacion.ts](../frontend/src/services/api/alineacion.ts), [frontend/src/services/api/dashboard.ts](../frontend/src/services/api/dashboard.ts), [frontend/src/services/api/liga.ts](../frontend/src/services/api/liga.ts)
- **Rutas HTTP:** `/teams/:x/dashboard`, `/teams/:x/insights`, `/teams/:x/insights/:x/archive`, `/teams/:x/league`, `/teams/:x/league/comparison`, `/teams/:x/lineup`
- **Endpoints:** [backend/app/api/v1/endpoints/analysis/alertas.py](../backend/app/api/v1/endpoints/analysis/alertas.py), [backend/app/api/v1/endpoints/analysis/alineacion.py](../backend/app/api/v1/endpoints/analysis/alineacion.py), [backend/app/api/v1/endpoints/league.py](../backend/app/api/v1/endpoints/league.py), [backend/app/api/v1/endpoints/teams/dashboard.py](../backend/app/api/v1/endpoints/teams/dashboard.py)
- **Aplicación:** `app.application.commands.sync_team` (7 rutas), `app.application.commands.sync_team.comun` (7 rutas), `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.academy`, `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.arena`, `app.application.queries.dashboard` (6 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.flor_de_fuerza`, `app.application.queries.league` (5 rutas), `app.application.queries.nombre_del_torneo` (6 rutas), `app.application.queries.player_balance` (7 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.academy_engine`, `app.domain.engines.arena_engine` (6 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.minutos_del_partido` (7 rutas), `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.salary_model` (7 rutas), `app.domain.engines.season_simulator` (6 rutas), `app.domain.engines.semilla` (6 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.team_rating_engine`, `app.domain.engines.training_engine` (10 rutas), `app.domain.engines.youth_training_plan` (5 rutas), `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (88):** `tests/test_academy_comparativa.py`, `tests/test_academy_engine.py`, `tests/test_academy_training_plan_contract.py`, `tests/test_alertas_del_reloj.py`, `tests/test_alineacion_para_descubrir.py`, `tests/test_arena_engine.py`, `tests/test_arena_query.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_cantera_por_equipo.py`, `tests/test_changes_history.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_flor_de_fuerza.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_historial_con_reemplazo.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_insights.py`, `tests/test_insights_endpoint.py`, `tests/test_lados_del_carril.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_metodo_de_resumen.py`, `tests/test_metodo_ocho.py`, `tests/test_middleware_idioma.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_minutos_del_partido.py`, `tests/test_ojeadores.py`, `tests/test_once_del_ultimo_partido.py`, `tests/test_parser_transfersearch.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_plan_de_entrenamiento.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_previous_club_bonus.py`, `tests/test_prioridad_de_entrenamiento.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rival_scouting.py`, `tests/test_rivals_endpoint.py`, `tests/test_salary_model.py`, `tests/test_season_simulator.py`, `tests/test_sede.py`, `tests/test_simulacion_de_venta.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_stint_edit.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_team_isolation.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_token_encryption.py`, `tests/test_training_engine.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ultimo_entrenamiento.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`, `tests/test_youth_parser.py`, `tests/test_youth_skill_score.py`

### `/club`

- **Página:** [frontend/src/pages/ClubPage.tsx](../frontend/src/pages/ClubPage.tsx) (591 líneas)
- **Componentes y hooks suyos (17):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/DateRangeFilter.tsx](../frontend/src/components/DateRangeFilter.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/SerieConCausas.tsx](../frontend/src/components/SerieConCausas.tsx)
  - [frontend/src/components/StaffRoleCard.tsx](../frontend/src/components/StaffRoleCard.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/club.ts](../frontend/src/hooks/useTeam/club.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/i18n/glosario.ts](../frontend/src/i18n/glosario.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/utils/skillLevels.ts](../frontend/src/utils/skillLevels.ts)
  - [frontend/src/utils/staffEffects.ts](../frontend/src/utils/staffEffects.ts)
  - [frontend/src/utils/ventanaDeGraficas.ts](../frontend/src/utils/ventanaDeGraficas.ts)
- **Pide a `api.`:** `club`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/club.ts](../frontend/src/services/api/club.ts)
- **Rutas HTTP:** `/teams/:x/club`
- **Endpoints:** [backend/app/api/v1/endpoints/teams/club.py](../backend/app/api/v1/endpoints/teams/club.py)
- **Aplicación:** `app.application.queries.club`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.staff_effects`, `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (7):** `tests/test_club_query.py`, `tests/test_economy_engine.py`, `tests/test_player_balance.py`, `tests/test_psicologia.py`, `tests/test_staff_effects.py`, `tests/test_transparencia.py`, `tests/test_weekly.py`

### `/overview`

- **Página:** [frontend/src/pages/TeamOverviewPage.tsx](../frontend/src/pages/TeamOverviewPage.tsx) (254 líneas)
- **Componentes y hooks suyos (9):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTeam/resumen.ts](../frontend/src/hooks/useTeam/resumen.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
- **Pide a `api.`:** `teamOverview`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/resumen.ts](../frontend/src/services/api/resumen.ts)
- **Rutas HTTP:** `/teams/:x/overview`
- **Endpoints:** [backend/app/api/v1/endpoints/analysis/resumen.py](../backend/app/api/v1/endpoints/analysis/resumen.py)
- **Aplicación:** `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.team_overview`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (18):** `tests/test_cache_por_sync.py`, `tests/test_changes_history.py`, `tests/test_economy_engine.py`, `tests/test_formato_numeros.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_player_balance.py`, `tests/test_position_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/team`

- **Página:** [frontend/src/pages/TeamPage.tsx](../frontend/src/pages/TeamPage.tsx) (503 líneas)
- **Componentes y hooks suyos (15):**
  - [frontend/src/components/CountryFlag.tsx](../frontend/src/components/CountryFlag.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PlayerLink.tsx](../frontend/src/components/PlayerLink.tsx)
  - [frontend/src/components/Specialty.tsx](../frontend/src/components/Specialty.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTeam/plantilla.ts](../frontend/src/hooks/useTeam/plantilla.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
- **Pide a `api.`:** `squad`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/plantilla.ts](../frontend/src/services/api/plantilla.ts)
- **Rutas HTTP:** `/teams/:x/squad`
- **Endpoints:** [backend/app/api/v1/endpoints/teams/plantilla.py](../backend/app/api/v1/endpoints/teams/plantilla.py)
- **Aplicación:** `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (14):** `tests/test_changes_history.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_position_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/skills`

- **Página:** [frontend/src/pages/SkillsPage.tsx](../frontend/src/pages/SkillsPage.tsx) (1079 líneas)
- **Componentes y hooks suyos (17):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/CountryFlag.tsx](../frontend/src/components/CountryFlag.tsx)
  - [frontend/src/components/MejorPosicion.tsx](../frontend/src/components/MejorPosicion.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PitchField.tsx](../frontend/src/components/PitchField.tsx)
  - [frontend/src/components/Specialty.tsx](../frontend/src/components/Specialty.tsx)
  - [frontend/src/components/SplitSelector.tsx](../frontend/src/components/SplitSelector.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useTeam/habilidades.ts](../frontend/src/hooks/useTeam/habilidades.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTeam/resumen.ts](../frontend/src/hooks/useTeam/resumen.ts)
  - [frontend/src/i18n/glosario.ts](../frontend/src/i18n/glosario.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
  - [frontend/src/utils/skillLevels.ts](../frontend/src/utils/skillLevels.ts)
- **Pide a `api.`:** `skills`, `teamOverview`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/habilidades.ts](../frontend/src/services/api/habilidades.ts), [frontend/src/services/api/resumen.ts](../frontend/src/services/api/resumen.ts)
- **Rutas HTTP:** `/teams/:x/overview`, `/teams/:x/skills`
- **Endpoints:** [backend/app/api/v1/endpoints/analysis/resumen.py](../backend/app/api/v1/endpoints/analysis/resumen.py), [backend/app/api/v1/endpoints/skills.py](../backend/app/api/v1/endpoints/skills.py)
- **Aplicación:** `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.flor_de_fuerza`, `app.application.queries.habilidades`, `app.application.queries.squad` (20 rutas), `app.application.queries.team_overview`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.team_rating_engine`, `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (27):** `tests/test_alineacion_para_descubrir.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_changes_history.py`, `tests/test_economy_engine.py`, `tests/test_flor_de_fuerza.py`, `tests/test_formato_numeros.py`, `tests/test_habilidades.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_lados_del_carril.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_match_type_helpers.py`, `tests/test_once_del_ultimo_partido.py`, `tests/test_player_balance.py`, `tests/test_position_engine.py`, `tests/test_prediccion_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/players/:htPlayerId`

- **Página:** [frontend/src/pages/PlayerPage.tsx](../frontend/src/pages/PlayerPage.tsx) (1533 líneas)
- **Componentes y hooks suyos (23):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/CountryFlag.tsx](../frontend/src/components/CountryFlag.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/DateRangeFilter.tsx](../frontend/src/components/DateRangeFilter.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PlayerDistributionPanel.tsx](../frontend/src/components/PlayerDistributionPanel.tsx)
  - [frontend/src/components/PrecioPorComparables.tsx](../frontend/src/components/PrecioPorComparables.tsx)
  - [frontend/src/components/Specialty.tsx](../frontend/src/components/Specialty.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/jugadores.ts](../frontend/src/hooks/useTeam/jugadores.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTeam/plantilla.ts](../frontend/src/hooks/useTeam/plantilla.ts)
  - [frontend/src/hooks/useTeam/transferencias.ts](../frontend/src/hooks/useTeam/transferencias.ts)
  - [frontend/src/i18n/glosario.ts](../frontend/src/i18n/glosario.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
  - [frontend/src/utils/skillLevels.ts](../frontend/src/utils/skillLevels.ts)
- **Pide a `api.`:** `confirmCareerStage`, `playerBalance`, `playerDetail`, `precioComparable`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/jugadores.ts](../frontend/src/services/api/jugadores.ts), [frontend/src/services/api/transferencias.ts](../frontend/src/services/api/transferencias.ts)
- **Rutas HTTP:** `/teams/:x/player-balance`, `/teams/:x/players/:x`, `/teams/:x/players/:x/career-stage`, `/teams/:x/players/:x/precio-comparable`
- **Endpoints:** [backend/app/api/v1/endpoints/analysis/jugadores.py](../backend/app/api/v1/endpoints/analysis/jugadores.py), [backend/app/api/v1/endpoints/player_balance.py](../backend/app/api/v1/endpoints/player_balance.py), [backend/app/api/v1/endpoints/precio_comparable.py](../backend/app/api/v1/endpoints/precio_comparable.py), [backend/app/api/v1/endpoints/teams/jugadores.py](../backend/app/api/v1/endpoints/teams/jugadores.py)
- **Aplicación:** `app.application.commands.mercado_comparable`, `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.player_balance` (7 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.precio_comparable`, `app.application.queries.squad` (20 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.career_stage_engine`, `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.mercado_comparable`, `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.pricing_engine`, `app.domain.engines.salary_model` (7 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Tests (40):** `tests/test_busqueda_de_comparables.py`, `tests/test_camel_helper.py`, `tests/test_career_stage_engine.py`, `tests/test_changes_history.py`, `tests/test_closing_the_formula.py`, `tests/test_economy_engine.py`, `tests/test_experience_calibration_api.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_mercado_comparable.py`, `tests/test_mercado_peticiones.py`, `tests/test_mercado_resolucion.py`, `tests/test_paso_del_mercado.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_previous_club_bonus.py`, `tests/test_pricing_engine.py`, `tests/test_salary_model.py`, `tests/test_simulacion_de_venta.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_stint_edit.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_training_engine.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/positions`

- **Página:** [frontend/src/pages/PositionsPage.tsx](../frontend/src/pages/PositionsPage.tsx) (349 líneas)
- **Componentes y hooks suyos (14):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/CountryFlag.tsx](../frontend/src/components/CountryFlag.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PlayerLink.tsx](../frontend/src/components/PlayerLink.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTeam/plantilla.ts](../frontend/src/hooks/useTeam/plantilla.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
- **Pide a `api.`:** `squad`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/plantilla.ts](../frontend/src/services/api/plantilla.ts)
- **Rutas HTTP:** `/teams/:x/squad`
- **Endpoints:** [backend/app/api/v1/endpoints/teams/plantilla.py](../backend/app/api/v1/endpoints/teams/plantilla.py)
- **Aplicación:** `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (14):** `tests/test_changes_history.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_position_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/lineup`

- **Página:** [frontend/src/pages/LineupPage.tsx](../frontend/src/pages/LineupPage.tsx) (825 líneas)
- **Componentes y hooks suyos (16):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/LineupAvailabilityNotice.tsx](../frontend/src/components/LineupAvailabilityNotice.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PitchField.tsx](../frontend/src/components/PitchField.tsx)
  - [frontend/src/components/PlayerLink.tsx](../frontend/src/components/PlayerLink.tsx)
  - [frontend/src/components/SplitSelector.tsx](../frontend/src/components/SplitSelector.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/alineacion.ts](../frontend/src/hooks/useTeam/alineacion.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTeam/plantilla.ts](../frontend/src/hooks/useTeam/plantilla.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/utils/lineupAvailability.ts](../frontend/src/utils/lineupAvailability.ts)
- **Pide a `api.`:** `lineup`, `lineupHindsight`, `squad`, `teamSpiritMultiplier`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/alineacion.ts](../frontend/src/services/api/alineacion.ts), [frontend/src/services/api/plantilla.ts](../frontend/src/services/api/plantilla.ts)
- **Rutas HTTP:** `/teams/:x/lineup`, `/teams/:x/lineup/hindsight`, `/teams/:x/lineup/team-spirit`, `/teams/:x/squad`
- **Endpoints:** [backend/app/api/v1/endpoints/analysis/alineacion.py](../backend/app/api/v1/endpoints/analysis/alineacion.py), [backend/app/api/v1/endpoints/teams/plantilla.py](../backend/app/api/v1/endpoints/teams/plantilla.py)
- **Aplicación:** `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.team_rating_engine`, `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (19):** `tests/test_alineacion_para_descubrir.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_changes_history.py`, `tests/test_formato_numeros.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_lados_del_carril.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_position_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/training`

- **Página:** [frontend/src/pages/TrainingPage.tsx](../frontend/src/pages/TrainingPage.tsx) (2064 líneas)
- **Componentes y hooks suyos (21):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/CountryFlag.tsx](../frontend/src/components/CountryFlag.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PlayerLink.tsx](../frontend/src/components/PlayerLink.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/club.ts](../frontend/src/hooks/useTeam/club.ts)
  - [frontend/src/hooks/useTeam/entrenamiento.ts](../frontend/src/hooks/useTeam/entrenamiento.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/jugadores.ts](../frontend/src/hooks/useTeam/jugadores.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
  - [frontend/src/utils/skillLevels.ts](../frontend/src/utils/skillLevels.ts)
  - [frontend/src/utils/staffEffects.ts](../frontend/src/utils/staffEffects.ts)
- **Pide a `api.`:** `club`, `playerTrainingLevels`, `postMatchTraining`, `trainingDevelopment`, `trainingFormula`, `trainingSquad`, `ultimoEntrenamiento`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/club.ts](../frontend/src/services/api/club.ts), [frontend/src/services/api/entrenamiento.ts](../frontend/src/services/api/entrenamiento.ts), [frontend/src/services/api/jugadores.ts](../frontend/src/services/api/jugadores.ts)
- **Rutas HTTP:** `/teams/:x/club`, `/teams/:x/players/:x/training/levels`, `/teams/:x/training/development`, `/teams/:x/training/formula`, `/teams/:x/training/last`, `/teams/:x/training/post-match`, `/teams/:x/training/squad`
- **Endpoints:** [backend/app/api/v1/endpoints/analysis/entrenamiento.py](../backend/app/api/v1/endpoints/analysis/entrenamiento.py), [backend/app/api/v1/endpoints/analysis/jugadores.py](../backend/app/api/v1/endpoints/analysis/jugadores.py), [backend/app/api/v1/endpoints/teams/club.py](../backend/app/api/v1/endpoints/teams/club.py)
- **Aplicación:** `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.club`, `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.ultimo_entrenamiento`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.minutos_del_partido` (7 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.staff_effects`, `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Tests (33):** `tests/test_changes_history.py`, `tests/test_closing_the_formula.py`, `tests/test_club_query.py`, `tests/test_economy_engine.py`, `tests/test_experience_calibration_api.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_minutos_del_partido.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_psicologia.py`, `tests/test_squad_last_match_recency.py`, `tests/test_staff_effects.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_training_engine.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ultimo_entrenamiento.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/transfers/balance`

- **Página:** [frontend/src/pages/PlayerBalancePage.tsx](../frontend/src/pages/PlayerBalancePage.tsx) (3245 líneas)
- **Componentes y hooks suyos (25):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/colors.ts](../frontend/src/charts/colors.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/BotonDeBorrado.tsx](../frontend/src/components/BotonDeBorrado.tsx)
  - [frontend/src/components/CountryFlag.tsx](../frontend/src/components/CountryFlag.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PlayerLink.tsx](../frontend/src/components/PlayerLink.tsx)
  - [frontend/src/components/Specialty.tsx](../frontend/src/components/Specialty.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/config/flags.ts](../frontend/src/config/flags.ts)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useModal.ts](../frontend/src/hooks/useModal.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTeam/plantilla.ts](../frontend/src/hooks/useTeam/plantilla.ts)
  - [frontend/src/hooks/useTeam/transferencias.ts](../frontend/src/hooks/useTeam/transferencias.ts)
  - [frontend/src/hooks/useTheme.ts](../frontend/src/hooks/useTheme.ts)
  - [frontend/src/i18n/glosario.ts](../frontend/src/i18n/glosario.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
  - [frontend/src/utils/simulacionDeVenta.ts](../frontend/src/utils/simulacionDeVenta.ts)
- **Pide a `api.`:** `deleteTransferAttempt`, `editStint`, `playerBalance`, `setManualPurchasePrice`, `squad`, `transferAttempts`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/comun.ts](../frontend/src/services/api/comun.ts), [frontend/src/services/api/jugadores.ts](../frontend/src/services/api/jugadores.ts), [frontend/src/services/api/plantilla.ts](../frontend/src/services/api/plantilla.ts), [frontend/src/services/api/transferencias.ts](../frontend/src/services/api/transferencias.ts)
- **Rutas HTTP:** `/teams/:x/player-balance`, `/teams/:x/players/:x/purchase-price`, `/teams/:x/squad`, `/teams/:x/stints/:x`, `/teams/:x/transfer-attempts`, `/teams/:x/transfer-attempts/:x`
- **Endpoints:** [backend/app/api/v1/endpoints/player_balance.py](../backend/app/api/v1/endpoints/player_balance.py), [backend/app/api/v1/endpoints/teams/jugadores.py](../backend/app/api/v1/endpoints/teams/jugadores.py), [backend/app/api/v1/endpoints/teams/plantilla.py](../backend/app/api/v1/endpoints/teams/plantilla.py)
- **Aplicación:** `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.player_balance` (7 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.transfer_attempts`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.salary_model` (7 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas), `app.domain.value_objects.skill`
- **Tests (25):** `tests/test_age.py`, `tests/test_camel_helper.py`, `tests/test_changes_history.py`, `tests/test_economy_engine.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_player_balance.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_previous_club_bonus.py`, `tests/test_salary_model.py`, `tests/test_simulacion_de_venta.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stint_edit.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_transfer_attempts.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_arrival.py`, `tests/test_youth_htms.py`

### `/libro`

- **Página:** [frontend/src/pages/LibroDeVisitasPage.tsx](../frontend/src/pages/LibroDeVisitasPage.tsx) (136 líneas)
- **Componentes y hooks suyos (5):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `guestbook`, `signGuestbook`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/libro.ts](../frontend/src/services/api/libro.ts)
- **Rutas HTTP:** `/guestbook`
- **Endpoints:** [backend/app/api/v1/endpoints/libro.py](../backend/app/api/v1/endpoints/libro.py)
- **Tests (1):** `tests/test_team_isolation.py`

### `/academy`

- **Página:** [frontend/src/pages/AcademyPage.tsx](../frontend/src/pages/AcademyPage.tsx) (4020 líneas)
- **Componentes y hooks suyos (19):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/CountryFlag.tsx](../frontend/src/components/CountryFlag.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/Specialty.tsx](../frontend/src/components/Specialty.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useAsentado.ts](../frontend/src/hooks/useAsentado.ts)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/usePersistido.ts](../frontend/src/hooks/usePersistido.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/juveniles.ts](../frontend/src/hooks/useTeam/juveniles.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
  - [frontend/src/utils/chiCuadrado.ts](../frontend/src/utils/chiCuadrado.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
  - [frontend/src/utils/skillLevels.ts](../frontend/src/utils/skillLevels.ts)
- **Pide a `api.`:** `academy`, `academyComparativa`, `academyScouts`, `academyScoutsLedger`, `academySkillScores`, `academyTrainingPlan`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/juveniles.ts](../frontend/src/services/api/juveniles.ts)
- **Rutas HTTP:** `/teams/:x/academy`, `/teams/:x/academy/comparativa`, `/teams/:x/academy/scouts`, `/teams/:x/academy/scouts-ledger`, `/teams/:x/academy/skill-scores`, `/teams/:x/academy/training-plan`
- **Endpoints:** [backend/app/api/v1/endpoints/academy.py](../backend/app/api/v1/endpoints/academy.py)
- **Aplicación:** `app.application.queries.academy`, `app.application.queries.ojeadores`, `app.application.queries.player_balance` (7 rutas), `app.application.queries.team_overview`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.academy_engine`, `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.salary_model` (7 rutas), `app.domain.engines.youth_skill_score`, `app.domain.engines.youth_training_plan` (5 rutas), `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas)
- **Tests (27):** `tests/test_academy_comparativa.py`, `tests/test_academy_engine.py`, `tests/test_academy_training_plan_contract.py`, `tests/test_alineacion_para_descubrir.py`, `tests/test_banquillo_no_se_rinde.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_economy_engine.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineas_de_entrenamiento.py`, `tests/test_metodo_ocho.py`, `tests/test_middleware_idioma.py`, `tests/test_plan_de_entrenamiento.py`, `tests/test_player_balance.py`, `tests/test_post_match_training.py`, `tests/test_previous_club_bonus.py`, `tests/test_prioridad_de_entrenamiento.py`, `tests/test_rellena_banquillo.py`, `tests/test_salary_model.py`, `tests/test_simulacion_de_venta.py`, `tests/test_stint_edit.py`, `tests/test_transparencia.py`, `tests/test_ultimo_entrenamiento.py`, `tests/test_weekly.py`, `tests/test_youth_skill_score.py`

### `/matches`

- **Página:** [frontend/src/pages/MatchesPage.tsx](../frontend/src/pages/MatchesPage.tsx) (684 líneas)
- **Componentes y hooks suyos (15):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/MatchSectorMap.tsx](../frontend/src/components/MatchSectorMap.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTeam/partidos.ts](../frontend/src/hooks/useTeam/partidos.ts)
  - [frontend/src/i18n/glosario.ts](../frontend/src/i18n/glosario.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
- **Pide a `api.`:** `matchDetail`, `matches`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/partidos.ts](../frontend/src/services/api/partidos.ts)
- **Rutas HTTP:** `/teams/:x/matches`, `/teams/:x/matches/:x`
- **Endpoints:** [backend/app/api/v1/endpoints/matches.py](../backend/app/api/v1/endpoints/matches.py)
- **Aplicación:** `app.application.queries.matches`, `app.application.queries.nombre_del_torneo` (6 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.match_analysis`, `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (12):** `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_economy_engine.py`, `tests/test_formato_numeros.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_match_analysis.py`, `tests/test_match_parsers.py`, `tests/test_match_type_helpers.py`, `tests/test_player_balance.py`, `tests/test_prediccion_engine.py`, `tests/test_transparencia.py`, `tests/test_weekly.py`

### `/league`

- **Página:** [frontend/src/pages/LeaguePage.tsx](../frontend/src/pages/LeaguePage.tsx) (1600 líneas)
- **Componentes y hooks suyos (21):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/BarraDePrediccion.tsx](../frontend/src/components/BarraDePrediccion.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PitchField.tsx](../frontend/src/components/PitchField.tsx)
  - [frontend/src/components/PitchZoneMethodSelector.tsx](../frontend/src/components/PitchZoneMethodSelector.tsx)
  - [frontend/src/components/SplitSelector.tsx](../frontend/src/components/SplitSelector.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/components/TsiHistogramPanel.tsx](../frontend/src/components/TsiHistogramPanel.tsx)
  - [frontend/src/components/pitchZoneMethods.ts](../frontend/src/components/pitchZoneMethods.ts)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/liga.ts](../frontend/src/hooks/useTeam/liga.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTheme.ts](../frontend/src/hooks/useTheme.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/pages/SimularJornada.tsx](../frontend/src/pages/SimularJornada.tsx)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
- **Pide a `api.`:** `league`, `leagueComparison`, `leagueTeamOfWeek`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/liga.ts](../frontend/src/services/api/liga.ts)
- **Rutas HTTP:** `/teams/:x/league`, `/teams/:x/league/comparison`, `/teams/:x/league/team-of-the-week`
- **Endpoints:** [backend/app/api/v1/endpoints/league.py](../backend/app/api/v1/endpoints/league.py)
- **Aplicación:** `app.application.commands.sync_team` (7 rutas), `app.application.commands.sync_team.comun` (7 rutas), `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.flor_de_fuerza`, `app.application.queries.league` (5 rutas), `app.application.queries.nombre_del_torneo` (6 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.season_simulator` (6 rutas), `app.domain.engines.semilla` (6 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.team_of_the_week`, `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (63):** `tests/test_alertas_del_reloj.py`, `tests/test_alineacion_para_descubrir.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_cantera_por_equipo.py`, `tests/test_changes_history.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_flor_de_fuerza.py`, `tests/test_formato_numeros.py`, `tests/test_historial_con_reemplazo.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_insights_endpoint.py`, `tests/test_lados_del_carril.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_match_type_helpers.py`, `tests/test_metodo_de_resumen.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_minutos_del_partido.py`, `tests/test_ojeadores.py`, `tests/test_once_del_ultimo_partido.py`, `tests/test_parser_transfersearch.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_player_balance.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rival_scouting.py`, `tests/test_rivals_endpoint.py`, `tests/test_season_simulator.py`, `tests/test_sede.py`, `tests/test_squad_last_match_recency.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_team_isolation.py`, `tests/test_team_of_the_week.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_token_encryption.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`, `tests/test_youth_parser.py`

### `/cup`

- **Página:** [frontend/src/pages/CupPage.tsx](../frontend/src/pages/CupPage.tsx) (1082 líneas)
- **Componentes y hooks suyos (16):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/BarraDePrediccion.tsx](../frontend/src/components/BarraDePrediccion.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PitchZoneMethodSelector.tsx](../frontend/src/components/PitchZoneMethodSelector.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/components/pitchZoneMethods.ts](../frontend/src/components/pitchZoneMethods.ts)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/copa.ts](../frontend/src/hooks/useTeam/copa.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTeam/rivales.ts](../frontend/src/hooks/useTeam/rivales.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
- **Pide a `api.`:** `cup`, `rivalScouting`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/copa.ts](../frontend/src/services/api/copa.ts), [frontend/src/services/api/rivales.ts](../frontend/src/services/api/rivales.ts)
- **Rutas HTTP:** `/teams/:x/cup`, `/teams/:x/rivals/:x/scouting`
- **Endpoints:** [backend/app/api/v1/endpoints/cup.py](../backend/app/api/v1/endpoints/cup.py), [backend/app/api/v1/endpoints/rivals.py](../backend/app/api/v1/endpoints/rivals.py)
- **Aplicación:** `app.application.commands.partidos_de_rivales`, `app.application.commands.sync_team` (7 rutas), `app.application.commands.sync_team.comun` (7 rutas), `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.arena_engine` (6 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.match_analysis`, `app.domain.engines.next_match_analysis`, `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.taquilla`, `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (70):** `tests/test_alertas_del_reloj.py`, `tests/test_alineacion_para_descubrir.py`, `tests/test_arena_engine.py`, `tests/test_arena_query.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_cantera_por_equipo.py`, `tests/test_changes_history.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_copa_de_esta_temporada.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_economy_engine.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_insights_endpoint.py`, `tests/test_lados_del_carril.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_match_analysis.py`, `tests/test_match_type_helpers.py`, `tests/test_mercado_resolucion.py`, `tests/test_metodo_de_resumen.py`, `tests/test_middleware_idioma.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_minutos_del_partido.py`, `tests/test_next_match_analysis.py`, `tests/test_ojeadores.py`, `tests/test_parser_transfersearch.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_partidos_de_rivales.py`, `tests/test_player_balance.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rival_scouting.py`, `tests/test_rivals_endpoint.py`, `tests/test_rivals_most_recent.py`, `tests/test_sede.py`, `tests/test_squad_last_match_recency.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_taquilla_del_partido.py`, `tests/test_team_isolation.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_token_encryption.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`, `tests/test_youth_parser.py`

### `/rivals`

- **Página:** [frontend/src/pages/RivalPickerPage.tsx](../frontend/src/pages/RivalPickerPage.tsx) (321 líneas)
- **Componentes y hooks suyos (11):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/copa.ts](../frontend/src/hooks/useTeam/copa.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/liga.ts](../frontend/src/hooks/useTeam/liga.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
- **Pide a `api.`:** `cup`, `league`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/copa.ts](../frontend/src/services/api/copa.ts), [frontend/src/services/api/liga.ts](../frontend/src/services/api/liga.ts)
- **Rutas HTTP:** `/teams/:x/cup`, `/teams/:x/league`
- **Endpoints:** [backend/app/api/v1/endpoints/cup.py](../backend/app/api/v1/endpoints/cup.py), [backend/app/api/v1/endpoints/league.py](../backend/app/api/v1/endpoints/league.py)
- **Aplicación:** `app.application.commands.sync_team` (7 rutas), `app.application.commands.sync_team.comun` (7 rutas), `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.league` (5 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines.arena_engine` (6 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.match_analysis`, `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.season_simulator` (6 rutas), `app.domain.engines.semilla` (6 rutas), `app.domain.engines.taquilla`, `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (51):** `tests/test_alertas_del_reloj.py`, `tests/test_arena_engine.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_cantera_por_equipo.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_copa_de_esta_temporada.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_economy_engine.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_historial_con_reemplazo.py`, `tests/test_insights_endpoint.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_match_analysis.py`, `tests/test_match_type_helpers.py`, `tests/test_metodo_de_resumen.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_minutos_del_partido.py`, `tests/test_ojeadores.py`, `tests/test_once_del_ultimo_partido.py`, `tests/test_parser_transfersearch.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_player_balance.py`, `tests/test_player_history.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rivals_endpoint.py`, `tests/test_season_simulator.py`, `tests/test_sede.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_taquilla_del_partido.py`, `tests/test_team_overview.py`, `tests/test_token_encryption.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_transparencia.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_parser.py`

### `/rivals/:rivalHtTeamId`

- **Página:** [frontend/src/pages/RivalPage.tsx](../frontend/src/pages/RivalPage.tsx) (1365 líneas)
- **Componentes y hooks suyos (17):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/BarraDePrediccion.tsx](../frontend/src/components/BarraDePrediccion.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PitchZoneMethodSelector.tsx](../frontend/src/components/PitchZoneMethodSelector.tsx)
  - [frontend/src/components/TsiHistogramPanel.tsx](../frontend/src/components/TsiHistogramPanel.tsx)
  - [frontend/src/components/pitchZoneMethods.ts](../frontend/src/components/pitchZoneMethods.ts)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/dashboard.ts](../frontend/src/hooks/useTeam/dashboard.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTeam/rivales.ts](../frontend/src/hooks/useTeam/rivales.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
- **Pide a `api.`:** `dashboard`, `rivalScouting`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/dashboard.ts](../frontend/src/services/api/dashboard.ts), [frontend/src/services/api/rivales.ts](../frontend/src/services/api/rivales.ts)
- **Rutas HTTP:** `/teams/:x/dashboard`, `/teams/:x/rivals/:x/scouting`
- **Endpoints:** [backend/app/api/v1/endpoints/rivals.py](../backend/app/api/v1/endpoints/rivals.py), [backend/app/api/v1/endpoints/teams/dashboard.py](../backend/app/api/v1/endpoints/teams/dashboard.py)
- **Aplicación:** `app.application.commands.partidos_de_rivales`, `app.application.commands.sync_team` (7 rutas), `app.application.commands.sync_team.comun` (7 rutas), `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.dashboard` (6 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.minutos_del_partido` (7 rutas), `app.domain.engines.next_match_analysis`, `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (73):** `tests/test_alertas_del_reloj.py`, `tests/test_alineacion_para_descubrir.py`, `tests/test_arena_query.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_cantera_por_equipo.py`, `tests/test_changes_history.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_insights_endpoint.py`, `tests/test_lados_del_carril.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_mercado_resolucion.py`, `tests/test_middleware_idioma.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_minutos_del_partido.py`, `tests/test_next_match_analysis.py`, `tests/test_ojeadores.py`, `tests/test_parser_transfersearch.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_partidos_de_rivales.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rival_scouting.py`, `tests/test_rivals_endpoint.py`, `tests/test_rivals_most_recent.py`, `tests/test_sede.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_team_isolation.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_token_encryption.py`, `tests/test_training_engine.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`, `tests/test_youth_parser.py`

### `/economy`

- **Página:** [frontend/src/pages/EconomyPage.tsx](../frontend/src/pages/EconomyPage.tsx) (1374 líneas)
- **Componentes y hooks suyos (13):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/DateRangeFilter.tsx](../frontend/src/components/DateRangeFilter.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/economia.ts](../frontend/src/hooks/useTeam/economia.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `economy`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/economia.ts](../frontend/src/services/api/economia.ts)
- **Rutas HTTP:** `/teams/:x/economy`
- **Endpoints:** [backend/app/api/v1/endpoints/economy.py](../backend/app/api/v1/endpoints/economy.py)
- **Aplicación:** `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.semilla` (6 rutas), `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (26):** `tests/test_alineacion_para_descubrir.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_changes_history.py`, `tests/test_dashboard_query.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_lados_del_carril.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_middleware_idioma.py`, `tests/test_player_balance.py`, `tests/test_position_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_timeseries_modelos_nuevos.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/arena`

- **Página:** [frontend/src/pages/ArenaPage.tsx](../frontend/src/pages/ArenaPage.tsx) (510 líneas)
- **Componentes y hooks suyos (12):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/colors.ts](../frontend/src/charts/colors.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/estadio.ts](../frontend/src/hooks/useTeam/estadio.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTheme.ts](../frontend/src/hooks/useTheme.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `arena`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/estadio.ts](../frontend/src/services/api/estadio.ts)
- **Rutas HTTP:** `/teams/:x/arena`
- **Endpoints:** [backend/app/api/v1/endpoints/arena.py](../backend/app/api/v1/endpoints/arena.py)
- **Aplicación:** `app.application.queries.arena`, `app.application.queries.nombre_del_torneo` (6 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines.arena_engine` (6 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (8):** `tests/test_arena_engine.py`, `tests/test_arena_query.py`, `tests/test_camel_helper.py`, `tests/test_economy_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_prediccion_engine.py`, `tests/test_transparencia.py`, `tests/test_weekly.py`

### `/insights`

- **Página:** [frontend/src/pages/InsightsPage.tsx](../frontend/src/pages/InsightsPage.tsx) (200 líneas)
- **Componentes y hooks suyos (9):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Insights.tsx](../frontend/src/components/Insights.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/hooks/useFocoDeLista.ts](../frontend/src/hooks/useFocoDeLista.ts)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/alertas.ts](../frontend/src/hooks/useTeam/alertas.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
- **Pide a `api.`:** `archiveInsight`, `archivedInsights`, `insights`, `restoreInsight`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/alertas.ts](../frontend/src/services/api/alertas.ts)
- **Rutas HTTP:** `/teams/:x/insights`, `/teams/:x/insights/:x/archive`, `/teams/:x/insights/archived`
- **Endpoints:** [backend/app/api/v1/endpoints/analysis/alertas.py](../backend/app/api/v1/endpoints/analysis/alertas.py)
- **Aplicación:** `app.application.commands.sync_team` (7 rutas), `app.application.commands.sync_team.comun` (7 rutas), `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.academy`, `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.arena`, `app.application.queries.economy` (8 rutas), `app.application.queries.league` (5 rutas), `app.application.queries.nombre_del_torneo` (6 rutas), `app.application.queries.player_balance` (7 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.academy_engine`, `app.domain.engines.arena_engine` (6 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.salary_model` (7 rutas), `app.domain.engines.season_simulator` (6 rutas), `app.domain.engines.semilla` (6 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.engines.youth_training_plan` (5 rutas), `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (79):** `tests/test_academy_comparativa.py`, `tests/test_academy_engine.py`, `tests/test_academy_training_plan_contract.py`, `tests/test_alertas_del_reloj.py`, `tests/test_alineacion_para_descubrir.py`, `tests/test_arena_engine.py`, `tests/test_arena_query.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_cantera_por_equipo.py`, `tests/test_changes_history.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_historial_con_reemplazo.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_insights.py`, `tests/test_insights_endpoint.py`, `tests/test_lados_del_carril.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_match_type_helpers.py`, `tests/test_metodo_de_resumen.py`, `tests/test_metodo_ocho.py`, `tests/test_middleware_idioma.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_minutos_del_partido.py`, `tests/test_ojeadores.py`, `tests/test_once_del_ultimo_partido.py`, `tests/test_parser_transfersearch.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_plan_de_entrenamiento.py`, `tests/test_player_balance.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_previous_club_bonus.py`, `tests/test_prioridad_de_entrenamiento.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rivals_endpoint.py`, `tests/test_salary_model.py`, `tests/test_season_simulator.py`, `tests/test_sede.py`, `tests/test_simulacion_de_venta.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stint_edit.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_token_encryption.py`, `tests/test_training_engine.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_transparencia.py`, `tests/test_ultimo_entrenamiento.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`, `tests/test_youth_parser.py`, `tests/test_youth_skill_score.py`

### `/sync`

- **Página:** [frontend/src/pages/SyncPage.tsx](../frontend/src/pages/SyncPage.tsx) (202 líneas)
- **Componentes y hooks suyos (9):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/SyncProgressPanel.tsx](../frontend/src/components/SyncProgressPanel.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/dashboard.ts](../frontend/src/hooks/useTeam/dashboard.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `dashboard`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/dashboard.ts](../frontend/src/services/api/dashboard.ts)
- **Rutas HTTP:** `/teams/:x/dashboard`
- **Endpoints:** [backend/app/api/v1/endpoints/teams/dashboard.py](../backend/app/api/v1/endpoints/teams/dashboard.py)
- **Aplicación:** `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.dashboard` (6 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.minutos_del_partido` (7 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Tests (33):** `tests/test_cache_por_sync.py`, `tests/test_changes_history.py`, `tests/test_closing_the_formula.py`, `tests/test_dashboard_query.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_minutos_del_partido.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_training_engine.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/news`

- **Página:** [frontend/src/pages/SyncChangesPage.tsx](../frontend/src/pages/SyncChangesPage.tsx) (868 líneas)
- **Componentes y hooks suyos (20):**
  - [frontend/src/components/AvisoDelBarrido.tsx](../frontend/src/components/AvisoDelBarrido.tsx)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/BotonDeBorrado.tsx](../frontend/src/components/BotonDeBorrado.tsx)
  - [frontend/src/components/GroupedPlayerChanges.tsx](../frontend/src/components/GroupedPlayerChanges.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/ParteDelPartido.tsx](../frontend/src/components/ParteDelPartido.tsx)
  - [frontend/src/components/PlayerLink.tsx](../frontend/src/components/PlayerLink.tsx)
  - [frontend/src/components/SyncChangesFeed.tsx](../frontend/src/components/SyncChangesFeed.tsx)
  - [frontend/src/components/SyncComparisonReport.tsx](../frontend/src/components/SyncComparisonReport.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/components/YouthChanges.tsx](../frontend/src/components/YouthChanges.tsx)
  - [frontend/src/config/flags.ts](../frontend/src/config/flags.ts)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/hooks/useTeam/partidos.ts](../frontend/src/hooks/useTeam/partidos.ts)
  - [frontend/src/hooks/useTeam/plantilla.ts](../frontend/src/hooks/useTeam/plantilla.ts)
  - [frontend/src/hooks/useTeam/sincronizacion.ts](../frontend/src/hooks/useTeam/sincronizacion.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `changesHistory`, `deleteTransferAttempt`, `lastMatchReport`, `setTimesSeen`, `squad`, `syncChanges`, `transferAttempts`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/partidos.ts](../frontend/src/services/api/partidos.ts), [frontend/src/services/api/plantilla.ts](../frontend/src/services/api/plantilla.ts), [frontend/src/services/api/sincronizacion.ts](../frontend/src/services/api/sincronizacion.ts), [frontend/src/services/api/transferencias.ts](../frontend/src/services/api/transferencias.ts)
- **Rutas HTTP:** `/teams/:x/changes/history`, `/teams/:x/last-match-report`, `/teams/:x/squad`, `/teams/:x/sync/changes`, `/teams/:x/transfer-attempts`, `/teams/:x/transfer-attempts/:x`
- **Endpoints:** [backend/app/api/v1/endpoints/player_balance.py](../backend/app/api/v1/endpoints/player_balance.py), [backend/app/api/v1/endpoints/teams/cambios.py](../backend/app/api/v1/endpoints/teams/cambios.py), [backend/app/api/v1/endpoints/teams/partidos.py](../backend/app/api/v1/endpoints/teams/partidos.py), [backend/app/api/v1/endpoints/teams/plantilla.py](../backend/app/api/v1/endpoints/teams/plantilla.py)
- **Aplicación:** `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.changes_history`, `app.application.queries.parte_del_partido`, `app.application.queries.player_balance` (7 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.sync_comparison`, `app.application.queries.transfer_attempts`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.salary_model` (7 rutas), `app.domain.engines.sync_diff`, `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas), `app.domain.value_objects.skill`
- **Tests (35):** `tests/test_age.py`, `tests/test_cache_por_sync.py`, `tests/test_cambios_academia_profundo.py`, `tests/test_cambios_del_ultimo_sync.py`, `tests/test_cambios_juveniles.py`, `tests/test_camel_helper.py`, `tests/test_changes_history.py`, `tests/test_economy_engine.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_middleware_idioma.py`, `tests/test_player_balance.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_previous_club_bonus.py`, `tests/test_salary_model.py`, `tests/test_salida_de_un_juvenil.py`, `tests/test_simulacion_de_venta.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stint_edit.py`, `tests/test_sync_comparison.py`, `tests/test_sync_diff.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_transfer_attempts.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_arrival.py`, `tests/test_youth_htms.py`

### `/transparency`

- **Página:** [frontend/src/pages/TransparencyPage.tsx](../frontend/src/pages/TransparencyPage.tsx) (980 líneas)
- **Componentes y hooks suyos (10):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useTeam/entrenamiento.ts](../frontend/src/hooks/useTeam/entrenamiento.ts)
  - [frontend/src/hooks/useTeam/index.ts](../frontend/src/hooks/useTeam/index.ts)
  - [frontend/src/hooks/useTeam/jugadores.ts](../frontend/src/hooks/useTeam/jugadores.ts)
  - [frontend/src/hooks/useTeam/modelos.ts](../frontend/src/hooks/useTeam/modelos.ts)
  - [frontend/src/hooks/useTeam/nucleo.ts](../frontend/src/hooks/useTeam/nucleo.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `calculos`, `experienceModel`, `loyaltyModel`, `positionModel`, `trainingFormula`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/entrenamiento.ts](../frontend/src/services/api/entrenamiento.ts), [frontend/src/services/api/jugadores.ts](../frontend/src/services/api/jugadores.ts), [frontend/src/services/api/modelos.ts](../frontend/src/services/api/modelos.ts)
- **Rutas HTTP:** `/teams/:x/experience/calibration`, `/teams/:x/loyalty/model`, `/teams/:x/training/formula`, `/teams/calculos`, `/teams/positions/model`
- **Endpoints:** [backend/app/api/v1/endpoints/analysis/entrenamiento.py](../backend/app/api/v1/endpoints/analysis/entrenamiento.py), [backend/app/api/v1/endpoints/analysis/modelos.py](../backend/app/api/v1/endpoints/analysis/modelos.py), [backend/app/api/v1/endpoints/teams/modelos.py](../backend/app/api/v1/endpoints/teams/modelos.py)
- **Aplicación:** `app.application.dto.dashboard` (20 rutas), `app.application.dto.squad` (20 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.squad` (20 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.transparencia`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (23 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.experience_engine`, `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.metodo_ocho`, `app.domain.engines.position_engine` (21 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.season_simulator` (6 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.engines.youth_skill_score`, `app.domain.engines.youth_training_plan` (5 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Tests (28):** `tests/test_changes_history.py`, `tests/test_closing_the_formula.py`, `tests/test_economy_engine.py`, `tests/test_experience_calibration_api.py`, `tests/test_experience_engine.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_prediccion_engine.py`, `tests/test_proximo_partido_liga.py`, `tests/test_season_simulator.py`, `tests/test_sede.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stats.py`, `tests/test_tacticas.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_training_engine.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/wiki`

- **Página:** [frontend/src/pages/WikiPage.tsx](../frontend/src/pages/WikiPage.tsx) (171 líneas)
- **Componentes y hooks suyos (3):**
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/pages/wiki/contenido.ts](../frontend/src/pages/wiki/contenido.ts)
- Sin datos del servidor: esta pantalla no pide nada al backend.

### `/uso`

- **Página:** [frontend/src/pages/UsagePage.tsx](../frontend/src/pages/UsagePage.tsx) (1007 líneas)
- **Componentes y hooks suyos (7):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/usePersistido.ts](../frontend/src/hooks/usePersistido.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `usage`, `usageLog`
- **Donde se escriben esas llamadas:** [frontend/src/services/api/uso.ts](../frontend/src/services/api/uso.ts)
- **Rutas HTTP:** `/usage`, `/usage/log`
- **Endpoints:** [backend/app/api/v1/endpoints/uso.py](../backend/app/api/v1/endpoints/uso.py)
- **Dominio:** `app.domain.engines` (23 rutas)
- **Tests (4):** `tests/test_uso_endpoint.py`, `tests/test_uso_por_pais.py`, `tests/test_uso_por_usuario.py`, `tests/test_uso_registro.py`

### `/autor`

- **Página:** [frontend/src/pages/AutorPage.tsx](../frontend/src/pages/AutorPage.tsx) (331 líneas)
- **Componentes y hooks suyos (7):**
  - [frontend/src/components/ApoyarProyecto.tsx](../frontend/src/components/ApoyarProyecto.tsx)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/ImagenOpcional.tsx](../frontend/src/components/ImagenOpcional.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/config/apoyo.ts](../frontend/src/config/apoyo.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- Sin datos del servidor: esta pantalla no pide nada al backend.

## Transversal

Lo que alcanzan 25 de 28 rutas o más. Tocar aquí es tocar
toda la aplicación, así que conviene mirar antes qué rutas dependen de
ello, y correr los tests generales enteros.

- `app.api.deps`
- `app.application.queries.weekly`
- `app.core.config`
- `app.infrastructure.db`
- `app.infrastructure.db.session`
- `app.infrastructure.security.jwt`

**Tests que cubren esa parte compartida (71):** correrlos al tocarla.

## Qué conviene partir

`coste` es las líneas por el número de pantallas que abren el fichero:
lo que cuesta de verdad no es lo grande que sea, sino lo grande por lo
a menudo que hay que leerlo. Un fichero enorme que sólo lee una
pantalla no estorba; uno mediano que leen veintiséis, sí.

| Coste | Líneas | Pantallas | Fichero |
| --: | --: | --: | --- |
| 14375 | 575 | 25 | [backend/app/domain/value_objects/ht_constants.py](../backend/app/domain/value_objects/ht_constants.py) |
| 12677 | 1811 | 7 | [backend/app/infrastructure/chpp/parsers/__init__.py](../backend/app/infrastructure/chpp/parsers/__init__.py) |
| 12368 | 1546 | 8 | [backend/app/application/queries/economy.py](../backend/app/application/queries/economy.py) |
| 11313 | 419 | 27 | [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx) |
| 11040 | 552 | 20 | [backend/app/application/queries/squad.py](../backend/app/application/queries/squad.py) |
| 10881 | 1209 | 9 | [backend/app/domain/engines/prediccion.py](../backend/app/domain/engines/prediccion.py) |
| 8981 | 1283 | 7 | [backend/app/application/queries/player_balance.py](../backend/app/application/queries/player_balance.py) |
| 7344 | 816 | 9 | [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts) |
| 6531 | 311 | 21 | [backend/app/domain/engines/economy_engine.py](../backend/app/domain/engines/economy_engine.py) |
| 6377 | 911 | 7 | [backend/app/application/queries/post_match_training.py](../backend/app/application/queries/post_match_training.py) |
| 6321 | 903 | 7 | [backend/app/application/queries/training_squad.py](../backend/app/application/queries/training_squad.py) |
| 6272 | 224 | 28 | [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts) |
| 6155 | 1231 | 5 | [backend/app/application/queries/league.py](../backend/app/application/queries/league.py) |
| 5649 | 269 | 21 | [backend/app/domain/engines/position_engine.py](../backend/app/domain/engines/position_engine.py) |
| 5375 | 215 | 25 | [backend/app/application/queries/weekly.py](../backend/app/application/queries/weekly.py) |
| 5292 | 588 | 9 | [backend/app/application/queries/player_history.py](../backend/app/application/queries/player_history.py) |
| 4873 | 443 | 11 | [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx) |
| 4830 | 483 | 10 | [backend/app/domain/engines/training_engine.py](../backend/app/domain/engines/training_engine.py) |
| 4627 | 661 | 7 | [backend/app/application/commands/sync_team/comun.py](../backend/app/application/commands/sync_team/comun.py) |
| 4613 | 659 | 7 | [backend/app/domain/engines/rival_scouting.py](../backend/app/domain/engines/rival_scouting.py) |
