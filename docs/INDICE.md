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

| Ruta | Página | Líneas | Endpoints | Dominio | Tests |
| --- | --- | --: | --- | --: | --: |
| `/connected` | [ConnectedPage.tsx](../frontend/src/pages/ConnectedPage.tsx) | 59 | - | 0 | 0 |
| `/welcome` | [WelcomePage.tsx](../frontend/src/pages/WelcomePage.tsx) | 237 | auth_chpp | 0 | 0 |
| `/apoyar` | [ApoyarPage.tsx](../frontend/src/pages/ApoyarPage.tsx) | 154 | teams | 9 | 32 |
| `/setup` | [SetupPage.tsx](../frontend/src/pages/SetupPage.tsx) | 428 | auth_chpp, teams | 9 | 32 |
| `/dashboard` | [DashboardNuevo.tsx](../frontend/src/pages/DashboardNuevo.tsx) | 876 | analysis, cup, economy, league, matches, teams | 25 | 90 |
| `/dashboard-anterior` | [DashboardPage.tsx](../frontend/src/pages/DashboardPage.tsx) | 616 | analysis, league, teams | 23 | 84 |
| `/club` | [ClubPage.tsx](../frontend/src/pages/ClubPage.tsx) | 591 | teams | 4 | 7 |
| `/overview` | [TeamOverviewPage.tsx](../frontend/src/pages/TeamOverviewPage.tsx) | 254 | analysis | 5 | 18 |
| `/team` | [TeamPage.tsx](../frontend/src/pages/TeamPage.tsx) | 503 | teams | 3 | 14 |
| `/skills` | [SkillsPage.tsx](../frontend/src/pages/SkillsPage.tsx) | 1079 | analysis, skills | 9 | 27 |
| `/players/:htPlayerId` | [PlayerPage.tsx](../frontend/src/pages/PlayerPage.tsx) | 1475 | analysis, player_balance, teams | 13 | 33 |
| `/positions` | [PositionsPage.tsx](../frontend/src/pages/PositionsPage.tsx) | 349 | teams | 3 | 14 |
| `/lineup` | [LineupPage.tsx](../frontend/src/pages/LineupPage.tsx) | 825 | analysis, teams | 8 | 19 |
| `/training` | [TrainingPage.tsx](../frontend/src/pages/TrainingPage.tsx) | 1912 | analysis, teams | 9 | 32 |
| `/transfers/balance` | [PlayerBalancePage.tsx](../frontend/src/pages/PlayerBalancePage.tsx) | 2963 | player_balance, teams | 6 | 11 |
| `/libro` | [LibroDeVisitasPage.tsx](../frontend/src/pages/LibroDeVisitasPage.tsx) | 136 | libro | 0 | 1 |
| `/academy` | [AcademyPage.tsx](../frontend/src/pages/AcademyPage.tsx) | 4006 | academy | 12 | 24 |
| `/matches` | [MatchesPage.tsx](../frontend/src/pages/MatchesPage.tsx) | 684 | matches | 4 | 12 |
| `/league` | [LeaguePage.tsx](../frontend/src/pages/LeaguePage.tsx) | 1600 | league | 13 | 60 |
| `/cup` | [CupPage.tsx](../frontend/src/pages/CupPage.tsx) | 1082 | cup, rivals | 16 | 66 |
| `/rivals` | [RivalPickerPage.tsx](../frontend/src/pages/RivalPickerPage.tsx) | 321 | cup, league | 10 | 48 |
| `/rivals/:rivalHtTeamId` | [RivalPage.tsx](../frontend/src/pages/RivalPage.tsx) | 1365 | rivals, teams | 16 | 69 |
| `/economy` | [EconomyPage.tsx](../frontend/src/pages/EconomyPage.tsx) | 1374 | economy | 9 | 26 |
| `/arena` | [ArenaPage.tsx](../frontend/src/pages/ArenaPage.tsx) | 510 | arena | 3 | 8 |
| `/insights` | [InsightsPage.tsx](../frontend/src/pages/InsightsPage.tsx) | 200 | analysis | 19 | 74 |
| `/sync` | [SyncPage.tsx](../frontend/src/pages/SyncPage.tsx) | 202 | teams | 9 | 32 |
| `/news` | [SyncChangesPage.tsx](../frontend/src/pages/SyncChangesPage.tsx) | 868 | player_balance, teams | 10 | 32 |
| `/transparency` | [TransparencyPage.tsx](../frontend/src/pages/TransparencyPage.tsx) | 980 | analysis, teams | 14 | 28 |
| `/wiki` | [WikiPage.tsx](../frontend/src/pages/WikiPage.tsx) | 171 | - | 0 | 0 |
| `/uso` | [UsagePage.tsx](../frontend/src/pages/UsagePage.tsx) | 1007 | uso | 1 | 4 |
| `/autor` | [AutorPage.tsx](../frontend/src/pages/AutorPage.tsx) | 331 | - | 0 | 0 |

## Ruta por ruta

### `/connected`

- **Página:** [frontend/src/pages/ConnectedPage.tsx](../frontend/src/pages/ConnectedPage.tsx) (59 líneas)
- **Componentes y hooks suyos (1):**
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
- Sin datos del servidor: esta pantalla no pide nada al backend.

### `/welcome`

- **Página:** [frontend/src/pages/WelcomePage.tsx](../frontend/src/pages/WelcomePage.tsx) (237 líneas)
- **Componentes y hooks suyos (5):**
  - [frontend/src/components/ImagenOpcional.tsx](../frontend/src/components/ImagenOpcional.tsx)
  - [frontend/src/components/SelectorDeIdioma.tsx](../frontend/src/components/SelectorDeIdioma.tsx)
  - [frontend/src/config/apoyo.ts](../frontend/src/config/apoyo.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
- **Pide a `api.`:** `connectChpp`, `sessionProfile`
- **Rutas HTTP:** `/auth/chpp/connect`, `/auth/chpp/session`
- **Endpoints:** `backend/app/api/v1/endpoints/auth_chpp.py`
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas)

### `/apoyar`

- **Página:** [frontend/src/pages/ApoyarPage.tsx](../frontend/src/pages/ApoyarPage.tsx) (154 líneas)
- **Componentes y hooks suyos (7):**
  - [frontend/src/components/ApoyarProyecto.tsx](../frontend/src/components/ApoyarProyecto.tsx)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/config/apoyo.ts](../frontend/src/config/apoyo.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `dashboard`
- **Rutas HTTP:** `/teams/:x/dashboard`
- **Endpoints:** `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.dashboard` (6 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Tests (32):** `tests/test_cache_por_sync.py`, `tests/test_changes_history.py`, `tests/test_closing_the_formula.py`, `tests/test_dashboard_query.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_training_engine.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/setup`

- **Página:** [frontend/src/pages/SetupPage.tsx](../frontend/src/pages/SetupPage.tsx) (428 líneas)
- **Componentes y hooks suyos (4):**
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/SyncProgressPanel.tsx](../frontend/src/components/SyncProgressPanel.tsx)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
- **Pide a `api.`:** `dashboard`, `sessionProfile`
- **Rutas HTTP:** `/auth/chpp/session`, `/teams/:x/dashboard`
- **Endpoints:** `backend/app/api/v1/endpoints/auth_chpp.py`, `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.dashboard` (6 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Tests (32):** `tests/test_cache_por_sync.py`, `tests/test_changes_history.py`, `tests/test_closing_the_formula.py`, `tests/test_dashboard_query.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_training_engine.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/dashboard`

- **Página:** [frontend/src/pages/DashboardNuevo.tsx](../frontend/src/pages/DashboardNuevo.tsx) (876 líneas)
- **Componentes y hooks suyos (15):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/BarraDePrediccion.tsx](../frontend/src/components/BarraDePrediccion.tsx)
  - [frontend/src/components/FlorDeFuerza.tsx](../frontend/src/components/FlorDeFuerza.tsx)
  - [frontend/src/components/Insights.tsx](../frontend/src/components/Insights.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PitchField.tsx](../frontend/src/components/PitchField.tsx)
  - [frontend/src/components/SplitSelector.tsx](../frontend/src/components/SplitSelector.tsx)
  - [frontend/src/hooks/useFocoDeLista.ts](../frontend/src/hooks/useFocoDeLista.ts)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/glosario.ts](../frontend/src/i18n/glosario.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/pages/DashboardPage.tsx](../frontend/src/pages/DashboardPage.tsx)
  - [frontend/src/utils/alertas.ts](../frontend/src/utils/alertas.ts)
  - [frontend/src/utils/skillLevels.ts](../frontend/src/utils/skillLevels.ts)
- **Pide a `api.`:** `archiveInsight`, `changesHistory`, `cup`, `dashboard`, `economy`, `insights`, `league`, `leagueComparison`, `lineup`, `matches`, `sectoresRecientes`
- **Rutas HTTP:** `/teams/:x/changes/history`, `/teams/:x/cup`, `/teams/:x/dashboard`, `/teams/:x/economy`, `/teams/:x/insights`, `/teams/:x/insights/:x/archive`, `/teams/:x/league`, `/teams/:x/league/comparison`, `/teams/:x/league/sectores-recientes`, `/teams/:x/lineup`, `/teams/:x/matches`
- **Endpoints:** `backend/app/api/v1/endpoints/analysis.py`, `backend/app/api/v1/endpoints/cup.py`, `backend/app/api/v1/endpoints/economy.py`, `backend/app/api/v1/endpoints/league.py`, `backend/app/api/v1/endpoints/matches.py`, `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.commands.sync_team` (7 rutas), `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.academy`, `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.arena`, `app.application.queries.changes_history`, `app.application.queries.dashboard` (6 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.flor_de_fuerza`, `app.application.queries.league` (5 rutas), `app.application.queries.matches`, `app.application.queries.nombre_del_torneo` (6 rutas), `app.application.queries.player_balance` (7 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.academy_engine`, `app.domain.engines.arena_engine` (6 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.match_analysis`, `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.salary_model` (7 rutas), `app.domain.engines.season_simulator` (6 rutas), `app.domain.engines.semilla` (6 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.taquilla`, `app.domain.engines.team_rating_engine`, `app.domain.engines.training_engine` (10 rutas), `app.domain.engines.youth_training_plan` (5 rutas), `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (90):** `tests/test_academy_comparativa.py`, `tests/test_academy_engine.py`, `tests/test_academy_training_plan_contract.py`, `tests/test_alineacion_para_descubrir.py`, `tests/test_arena_engine.py`, `tests/test_arena_query.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_cantera_por_equipo.py`, `tests/test_changes_history.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_copa_de_esta_temporada.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_flor_de_fuerza.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_habilidades.py`, `tests/test_historial_con_reemplazo.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_insights.py`, `tests/test_insights_endpoint.py`, `tests/test_lados_del_carril.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_analysis.py`, `tests/test_match_parsers.py`, `tests/test_match_type_helpers.py`, `tests/test_metodo_de_resumen.py`, `tests/test_metodo_ocho.py`, `tests/test_middleware_idioma.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_ojeadores.py`, `tests/test_once_del_ultimo_partido.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_plan_de_entrenamiento.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_previous_club_bonus.py`, `tests/test_prioridad_de_entrenamiento.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rival_scouting.py`, `tests/test_rivals_endpoint.py`, `tests/test_salary_model.py`, `tests/test_season_simulator.py`, `tests/test_sede.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_stint_edit.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_taquilla_del_partido.py`, `tests/test_team_isolation.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_timeseries_modelos_nuevos.py`, `tests/test_token_encryption.py`, `tests/test_training_engine.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ultimo_entrenamiento.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`, `tests/test_youth_parser.py`, `tests/test_youth_skill_score.py`

### `/dashboard-anterior`

- **Página:** [frontend/src/pages/DashboardPage.tsx](../frontend/src/pages/DashboardPage.tsx) (616 líneas)
- **Componentes y hooks suyos (13):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Insights.tsx](../frontend/src/components/Insights.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PitchField.tsx](../frontend/src/components/PitchField.tsx)
  - [frontend/src/components/SplitSelector.tsx](../frontend/src/components/SplitSelector.tsx)
  - [frontend/src/hooks/useFocoDeLista.ts](../frontend/src/hooks/useFocoDeLista.ts)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/alertas.ts](../frontend/src/utils/alertas.ts)
- **Pide a `api.`:** `archiveInsight`, `dashboard`, `insights`, `league`, `leagueComparison`, `lineup`
- **Rutas HTTP:** `/teams/:x/dashboard`, `/teams/:x/insights`, `/teams/:x/insights/:x/archive`, `/teams/:x/league`, `/teams/:x/league/comparison`, `/teams/:x/lineup`
- **Endpoints:** `backend/app/api/v1/endpoints/analysis.py`, `backend/app/api/v1/endpoints/league.py`, `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.commands.sync_team` (7 rutas), `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.academy`, `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.arena`, `app.application.queries.dashboard` (6 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.flor_de_fuerza`, `app.application.queries.league` (5 rutas), `app.application.queries.nombre_del_torneo` (6 rutas), `app.application.queries.player_balance` (7 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.academy_engine`, `app.domain.engines.arena_engine` (6 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.salary_model` (7 rutas), `app.domain.engines.season_simulator` (6 rutas), `app.domain.engines.semilla` (6 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.team_rating_engine`, `app.domain.engines.training_engine` (10 rutas), `app.domain.engines.youth_training_plan` (5 rutas), `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (84):** `tests/test_academy_comparativa.py`, `tests/test_academy_engine.py`, `tests/test_academy_training_plan_contract.py`, `tests/test_alineacion_para_descubrir.py`, `tests/test_arena_engine.py`, `tests/test_arena_query.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_cantera_por_equipo.py`, `tests/test_changes_history.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_flor_de_fuerza.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_historial_con_reemplazo.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_insights.py`, `tests/test_insights_endpoint.py`, `tests/test_lados_del_carril.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_metodo_de_resumen.py`, `tests/test_metodo_ocho.py`, `tests/test_middleware_idioma.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_ojeadores.py`, `tests/test_once_del_ultimo_partido.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_plan_de_entrenamiento.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_previous_club_bonus.py`, `tests/test_prioridad_de_entrenamiento.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rival_scouting.py`, `tests/test_rivals_endpoint.py`, `tests/test_salary_model.py`, `tests/test_season_simulator.py`, `tests/test_sede.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_stint_edit.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_team_isolation.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_token_encryption.py`, `tests/test_training_engine.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ultimo_entrenamiento.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`, `tests/test_youth_parser.py`, `tests/test_youth_skill_score.py`

### `/club`

- **Página:** [frontend/src/pages/ClubPage.tsx](../frontend/src/pages/ClubPage.tsx) (591 líneas)
- **Componentes y hooks suyos (15):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/DateRangeFilter.tsx](../frontend/src/components/DateRangeFilter.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/SerieConCausas.tsx](../frontend/src/components/SerieConCausas.tsx)
  - [frontend/src/components/StaffRoleCard.tsx](../frontend/src/components/StaffRoleCard.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/glosario.ts](../frontend/src/i18n/glosario.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/utils/skillLevels.ts](../frontend/src/utils/skillLevels.ts)
  - [frontend/src/utils/staffEffects.ts](../frontend/src/utils/staffEffects.ts)
  - [frontend/src/utils/ventanaDeGraficas.ts](../frontend/src/utils/ventanaDeGraficas.ts)
- **Pide a `api.`:** `club`
- **Rutas HTTP:** `/teams/:x/club`
- **Endpoints:** `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.queries.club`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.staff_effects`, `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (7):** `tests/test_club_query.py`, `tests/test_economy_engine.py`, `tests/test_player_balance.py`, `tests/test_psicologia.py`, `tests/test_staff_effects.py`, `tests/test_transparencia.py`, `tests/test_weekly.py`

### `/overview`

- **Página:** [frontend/src/pages/TeamOverviewPage.tsx](../frontend/src/pages/TeamOverviewPage.tsx) (254 líneas)
- **Componentes y hooks suyos (7):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
- **Pide a `api.`:** `teamOverview`
- **Rutas HTTP:** `/teams/:x/overview`
- **Endpoints:** `backend/app/api/v1/endpoints/analysis.py`
- **Aplicación:** `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.team_overview`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (18):** `tests/test_cache_por_sync.py`, `tests/test_changes_history.py`, `tests/test_economy_engine.py`, `tests/test_formato_numeros.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_player_balance.py`, `tests/test_position_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/team`

- **Página:** [frontend/src/pages/TeamPage.tsx](../frontend/src/pages/TeamPage.tsx) (503 líneas)
- **Componentes y hooks suyos (13):**
  - [frontend/src/components/CountryFlag.tsx](../frontend/src/components/CountryFlag.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PlayerLink.tsx](../frontend/src/components/PlayerLink.tsx)
  - [frontend/src/components/Specialty.tsx](../frontend/src/components/Specialty.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
- **Pide a `api.`:** `squad`
- **Rutas HTTP:** `/teams/:x/squad`
- **Endpoints:** `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (14):** `tests/test_changes_history.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_position_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/skills`

- **Página:** [frontend/src/pages/SkillsPage.tsx](../frontend/src/pages/SkillsPage.tsx) (1079 líneas)
- **Componentes y hooks suyos (14):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/CountryFlag.tsx](../frontend/src/components/CountryFlag.tsx)
  - [frontend/src/components/MejorPosicion.tsx](../frontend/src/components/MejorPosicion.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PitchField.tsx](../frontend/src/components/PitchField.tsx)
  - [frontend/src/components/Specialty.tsx](../frontend/src/components/Specialty.tsx)
  - [frontend/src/components/SplitSelector.tsx](../frontend/src/components/SplitSelector.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/glosario.ts](../frontend/src/i18n/glosario.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
  - [frontend/src/utils/skillLevels.ts](../frontend/src/utils/skillLevels.ts)
- **Pide a `api.`:** `skills`, `teamOverview`
- **Rutas HTTP:** `/teams/:x/overview`, `/teams/:x/skills`
- **Endpoints:** `backend/app/api/v1/endpoints/analysis.py`, `backend/app/api/v1/endpoints/skills.py`
- **Aplicación:** `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.flor_de_fuerza`, `app.application.queries.habilidades`, `app.application.queries.squad` (19 rutas), `app.application.queries.team_overview`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.team_rating_engine`, `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (27):** `tests/test_alineacion_para_descubrir.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_changes_history.py`, `tests/test_economy_engine.py`, `tests/test_flor_de_fuerza.py`, `tests/test_formato_numeros.py`, `tests/test_habilidades.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_lados_del_carril.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_match_type_helpers.py`, `tests/test_once_del_ultimo_partido.py`, `tests/test_player_balance.py`, `tests/test_position_engine.py`, `tests/test_prediccion_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/players/:htPlayerId`

- **Página:** [frontend/src/pages/PlayerPage.tsx](../frontend/src/pages/PlayerPage.tsx) (1475 líneas)
- **Componentes y hooks suyos (17):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/CountryFlag.tsx](../frontend/src/components/CountryFlag.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/DateRangeFilter.tsx](../frontend/src/components/DateRangeFilter.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PlayerDistributionPanel.tsx](../frontend/src/components/PlayerDistributionPanel.tsx)
  - [frontend/src/components/Specialty.tsx](../frontend/src/components/Specialty.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/glosario.ts](../frontend/src/i18n/glosario.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
  - [frontend/src/utils/skillLevels.ts](../frontend/src/utils/skillLevels.ts)
- **Pide a `api.`:** `confirmCareerStage`, `playerBalance`, `playerDetail`
- **Rutas HTTP:** `/teams/:x/player-balance`, `/teams/:x/players/:x`, `/teams/:x/players/:x/career-stage`
- **Endpoints:** `backend/app/api/v1/endpoints/analysis.py`, `backend/app/api/v1/endpoints/player_balance.py`, `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.player_balance` (7 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.career_stage_engine`, `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.pricing_engine`, `app.domain.engines.salary_model` (7 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Tests (33):** `tests/test_camel_helper.py`, `tests/test_career_stage_engine.py`, `tests/test_changes_history.py`, `tests/test_closing_the_formula.py`, `tests/test_economy_engine.py`, `tests/test_experience_calibration_api.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_prediccion_engine.py`, `tests/test_previous_club_bonus.py`, `tests/test_pricing_engine.py`, `tests/test_salary_model.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_stint_edit.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_training_engine.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/positions`

- **Página:** [frontend/src/pages/PositionsPage.tsx](../frontend/src/pages/PositionsPage.tsx) (349 líneas)
- **Componentes y hooks suyos (12):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/CountryFlag.tsx](../frontend/src/components/CountryFlag.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PlayerLink.tsx](../frontend/src/components/PlayerLink.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
- **Pide a `api.`:** `squad`
- **Rutas HTTP:** `/teams/:x/squad`
- **Endpoints:** `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (14):** `tests/test_changes_history.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_position_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/lineup`

- **Página:** [frontend/src/pages/LineupPage.tsx](../frontend/src/pages/LineupPage.tsx) (825 líneas)
- **Componentes y hooks suyos (13):**
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
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/utils/lineupAvailability.ts](../frontend/src/utils/lineupAvailability.ts)
- **Pide a `api.`:** `lineup`, `lineupHindsight`, `squad`, `teamSpiritMultiplier`
- **Rutas HTTP:** `/teams/:x/lineup`, `/teams/:x/lineup/hindsight`, `/teams/:x/lineup/team-spirit`, `/teams/:x/squad`
- **Endpoints:** `backend/app/api/v1/endpoints/analysis.py`, `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.team_rating_engine`, `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (19):** `tests/test_alineacion_para_descubrir.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_changes_history.py`, `tests/test_formato_numeros.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_lados_del_carril.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_position_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/training`

- **Página:** [frontend/src/pages/TrainingPage.tsx](../frontend/src/pages/TrainingPage.tsx) (1912 líneas)
- **Componentes y hooks suyos (17):**
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
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
  - [frontend/src/utils/skillLevels.ts](../frontend/src/utils/skillLevels.ts)
  - [frontend/src/utils/staffEffects.ts](../frontend/src/utils/staffEffects.ts)
- **Pide a `api.`:** `club`, `playerTrainingLevels`, `postMatchTraining`, `trainingDevelopment`, `trainingFormula`, `trainingSquad`, `ultimoEntrenamiento`
- **Rutas HTTP:** `/teams/:x/club`, `/teams/:x/players/:x/training/levels`, `/teams/:x/training/development`, `/teams/:x/training/formula`, `/teams/:x/training/last`, `/teams/:x/training/post-match`, `/teams/:x/training/squad`
- **Endpoints:** `backend/app/api/v1/endpoints/analysis.py`, `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.club`, `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.ultimo_entrenamiento`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.staff_effects`, `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Tests (32):** `tests/test_changes_history.py`, `tests/test_closing_the_formula.py`, `tests/test_club_query.py`, `tests/test_economy_engine.py`, `tests/test_experience_calibration_api.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_psicologia.py`, `tests/test_squad_last_match_recency.py`, `tests/test_staff_effects.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_training_engine.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ultimo_entrenamiento.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/transfers/balance`

- **Página:** [frontend/src/pages/PlayerBalancePage.tsx](../frontend/src/pages/PlayerBalancePage.tsx) (2963 líneas)
- **Componentes y hooks suyos (21):**
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
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/hooks/useTheme.ts](../frontend/src/hooks/useTheme.ts)
  - [frontend/src/i18n/glosario.ts](../frontend/src/i18n/glosario.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
- **Pide a `api.`:** `deleteTransferAttempt`, `editStint`, `playerBalance`, `setManualPurchasePrice`, `transferAttempts`
- **Rutas HTTP:** `/teams/:x/player-balance`, `/teams/:x/players/:x/purchase-price`, `/teams/:x/stints/:x`, `/teams/:x/transfer-attempts`, `/teams/:x/transfer-attempts/:x`
- **Endpoints:** `backend/app/api/v1/endpoints/player_balance.py`, `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.queries.player_balance` (7 rutas), `app.application.queries.transfer_attempts`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.salary_model` (7 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas), `app.domain.value_objects.skill`
- **Tests (11):** `tests/test_age.py`, `tests/test_camel_helper.py`, `tests/test_economy_engine.py`, `tests/test_player_balance.py`, `tests/test_previous_club_bonus.py`, `tests/test_salary_model.py`, `tests/test_stint_edit.py`, `tests/test_transfer_attempts.py`, `tests/test_transparencia.py`, `tests/test_weekly.py`, `tests/test_youth_arrival.py`

### `/libro`

- **Página:** [frontend/src/pages/LibroDeVisitasPage.tsx](../frontend/src/pages/LibroDeVisitasPage.tsx) (136 líneas)
- **Componentes y hooks suyos (5):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `guestbook`, `signGuestbook`
- **Rutas HTTP:** `/guestbook`
- **Endpoints:** `backend/app/api/v1/endpoints/libro.py`
- **Tests (1):** `tests/test_team_isolation.py`

### `/academy`

- **Página:** [frontend/src/pages/AcademyPage.tsx](../frontend/src/pages/AcademyPage.tsx) (4006 líneas)
- **Componentes y hooks suyos (17):**
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
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
  - [frontend/src/utils/chiCuadrado.ts](../frontend/src/utils/chiCuadrado.ts)
  - [frontend/src/utils/countryCodes.ts](../frontend/src/utils/countryCodes.ts)
  - [frontend/src/utils/skillLevels.ts](../frontend/src/utils/skillLevels.ts)
- **Pide a `api.`:** `academy`, `academyComparativa`, `academyScouts`, `academyScoutsLedger`, `academySkillScores`, `academyTrainingPlan`
- **Rutas HTTP:** `/teams/:x/academy`, `/teams/:x/academy/comparativa`, `/teams/:x/academy/scouts`, `/teams/:x/academy/scouts-ledger`, `/teams/:x/academy/skill-scores`, `/teams/:x/academy/training-plan`
- **Endpoints:** `backend/app/api/v1/endpoints/academy.py`
- **Aplicación:** `app.application.queries.academy`, `app.application.queries.ojeadores`, `app.application.queries.player_balance` (7 rutas), `app.application.queries.team_overview`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.academy_engine`, `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.salary_model` (7 rutas), `app.domain.engines.youth_skill_score`, `app.domain.engines.youth_training_plan` (5 rutas), `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas)
- **Tests (24):** `tests/test_academy_comparativa.py`, `tests/test_academy_engine.py`, `tests/test_academy_training_plan_contract.py`, `tests/test_alineacion_para_descubrir.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_economy_engine.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineas_de_entrenamiento.py`, `tests/test_metodo_ocho.py`, `tests/test_middleware_idioma.py`, `tests/test_plan_de_entrenamiento.py`, `tests/test_player_balance.py`, `tests/test_previous_club_bonus.py`, `tests/test_prioridad_de_entrenamiento.py`, `tests/test_rellena_banquillo.py`, `tests/test_salary_model.py`, `tests/test_stint_edit.py`, `tests/test_transparencia.py`, `tests/test_ultimo_entrenamiento.py`, `tests/test_weekly.py`, `tests/test_youth_skill_score.py`

### `/matches`

- **Página:** [frontend/src/pages/MatchesPage.tsx](../frontend/src/pages/MatchesPage.tsx) (684 líneas)
- **Componentes y hooks suyos (13):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/MatchSectorMap.tsx](../frontend/src/components/MatchSectorMap.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/glosario.ts](../frontend/src/i18n/glosario.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
- **Pide a `api.`:** `matchDetail`, `matches`
- **Rutas HTTP:** `/teams/:x/matches`, `/teams/:x/matches/:x`
- **Endpoints:** `backend/app/api/v1/endpoints/matches.py`
- **Aplicación:** `app.application.queries.matches`, `app.application.queries.nombre_del_torneo` (6 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.match_analysis`, `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (12):** `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_economy_engine.py`, `tests/test_formato_numeros.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_match_analysis.py`, `tests/test_match_parsers.py`, `tests/test_match_type_helpers.py`, `tests/test_player_balance.py`, `tests/test_prediccion_engine.py`, `tests/test_transparencia.py`, `tests/test_weekly.py`

### `/league`

- **Página:** [frontend/src/pages/LeaguePage.tsx](../frontend/src/pages/LeaguePage.tsx) (1600 líneas)
- **Componentes y hooks suyos (19):**
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
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/hooks/useTheme.ts](../frontend/src/hooks/useTheme.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/pages/SimularJornada.tsx](../frontend/src/pages/SimularJornada.tsx)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
- **Pide a `api.`:** `league`, `leagueComparison`, `leagueTeamOfWeek`
- **Rutas HTTP:** `/teams/:x/league`, `/teams/:x/league/comparison`, `/teams/:x/league/team-of-the-week`
- **Endpoints:** `backend/app/api/v1/endpoints/league.py`
- **Aplicación:** `app.application.commands.sync_team` (7 rutas), `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.flor_de_fuerza`, `app.application.queries.league` (5 rutas), `app.application.queries.nombre_del_torneo` (6 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.season_simulator` (6 rutas), `app.domain.engines.semilla` (6 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.team_of_the_week`, `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (60):** `tests/test_alineacion_para_descubrir.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_cantera_por_equipo.py`, `tests/test_changes_history.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_flor_de_fuerza.py`, `tests/test_formato_numeros.py`, `tests/test_historial_con_reemplazo.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_insights_endpoint.py`, `tests/test_lados_del_carril.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_match_type_helpers.py`, `tests/test_metodo_de_resumen.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_ojeadores.py`, `tests/test_once_del_ultimo_partido.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_player_balance.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rival_scouting.py`, `tests/test_rivals_endpoint.py`, `tests/test_season_simulator.py`, `tests/test_sede.py`, `tests/test_squad_last_match_recency.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_team_isolation.py`, `tests/test_team_of_the_week.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_token_encryption.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`, `tests/test_youth_parser.py`

### `/cup`

- **Página:** [frontend/src/pages/CupPage.tsx](../frontend/src/pages/CupPage.tsx) (1082 líneas)
- **Componentes y hooks suyos (13):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/BarraDePrediccion.tsx](../frontend/src/components/BarraDePrediccion.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/PitchZoneMethodSelector.tsx](../frontend/src/components/PitchZoneMethodSelector.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/components/pitchZoneMethods.ts](../frontend/src/components/pitchZoneMethods.ts)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
- **Pide a `api.`:** `cup`, `rivalScouting`
- **Rutas HTTP:** `/teams/:x/cup`, `/teams/:x/rivals/:x/scouting`
- **Endpoints:** `backend/app/api/v1/endpoints/cup.py`, `backend/app/api/v1/endpoints/rivals.py`
- **Aplicación:** `app.application.commands.partidos_de_rivales`, `app.application.commands.sync_team` (7 rutas), `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.arena_engine` (6 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.match_analysis`, `app.domain.engines.next_match_analysis`, `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.taquilla`, `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (66):** `tests/test_alineacion_para_descubrir.py`, `tests/test_arena_engine.py`, `tests/test_arena_query.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_cantera_por_equipo.py`, `tests/test_changes_history.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_copa_de_esta_temporada.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_economy_engine.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_insights_endpoint.py`, `tests/test_lados_del_carril.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_match_analysis.py`, `tests/test_match_type_helpers.py`, `tests/test_metodo_de_resumen.py`, `tests/test_middleware_idioma.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_next_match_analysis.py`, `tests/test_ojeadores.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_partidos_de_rivales.py`, `tests/test_player_balance.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rival_scouting.py`, `tests/test_rivals_endpoint.py`, `tests/test_rivals_most_recent.py`, `tests/test_sede.py`, `tests/test_squad_last_match_recency.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_taquilla_del_partido.py`, `tests/test_team_isolation.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_token_encryption.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`, `tests/test_youth_parser.py`

### `/rivals`

- **Página:** [frontend/src/pages/RivalPickerPage.tsx](../frontend/src/pages/RivalPickerPage.tsx) (321 líneas)
- **Componentes y hooks suyos (8):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/DataTable.tsx](../frontend/src/components/DataTable.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
- **Pide a `api.`:** `cup`, `league`
- **Rutas HTTP:** `/teams/:x/cup`, `/teams/:x/league`
- **Endpoints:** `backend/app/api/v1/endpoints/cup.py`, `backend/app/api/v1/endpoints/league.py`
- **Aplicación:** `app.application.commands.sync_team` (7 rutas), `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.league` (5 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines.arena_engine` (6 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.match_analysis`, `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.season_simulator` (6 rutas), `app.domain.engines.semilla` (6 rutas), `app.domain.engines.taquilla`, `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (48):** `tests/test_arena_engine.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_cantera_por_equipo.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_copa_de_esta_temporada.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_economy_engine.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_historial_con_reemplazo.py`, `tests/test_insights_endpoint.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_match_analysis.py`, `tests/test_match_type_helpers.py`, `tests/test_metodo_de_resumen.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_ojeadores.py`, `tests/test_once_del_ultimo_partido.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_player_balance.py`, `tests/test_player_history.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rivals_endpoint.py`, `tests/test_season_simulator.py`, `tests/test_sede.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_taquilla_del_partido.py`, `tests/test_team_overview.py`, `tests/test_token_encryption.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_transparencia.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_parser.py`

### `/rivals/:rivalHtTeamId`

- **Página:** [frontend/src/pages/RivalPage.tsx](../frontend/src/pages/RivalPage.tsx) (1365 líneas)
- **Componentes y hooks suyos (14):**
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
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
  - [frontend/src/utils/abreviaturas.ts](../frontend/src/utils/abreviaturas.ts)
- **Pide a `api.`:** `dashboard`, `rivalScouting`
- **Rutas HTTP:** `/teams/:x/dashboard`, `/teams/:x/rivals/:x/scouting`
- **Endpoints:** `backend/app/api/v1/endpoints/rivals.py`, `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.commands.partidos_de_rivales`, `app.application.commands.sync_team` (7 rutas), `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.dashboard` (6 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.next_match_analysis`, `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (69):** `tests/test_alineacion_para_descubrir.py`, `tests/test_arena_query.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_camel_helper.py`, `tests/test_cantera_por_equipo.py`, `tests/test_changes_history.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_insights_endpoint.py`, `tests/test_lados_del_carril.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_middleware_idioma.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_next_match_analysis.py`, `tests/test_ojeadores.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_partidos_de_rivales.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rival_scouting.py`, `tests/test_rivals_endpoint.py`, `tests/test_rivals_most_recent.py`, `tests/test_sede.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_team_isolation.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_token_encryption.py`, `tests/test_training_engine.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`, `tests/test_youth_parser.py`

### `/economy`

- **Página:** [frontend/src/pages/EconomyPage.tsx](../frontend/src/pages/EconomyPage.tsx) (1374 líneas)
- **Componentes y hooks suyos (11):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/chartOptions.ts](../frontend/src/charts/chartOptions.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/DateRangeFilter.tsx](../frontend/src/components/DateRangeFilter.tsx)
  - [frontend/src/components/EnlaceATransparencia.tsx](../frontend/src/components/EnlaceATransparencia.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `economy`
- **Rutas HTTP:** `/teams/:x/economy`
- **Endpoints:** `backend/app/api/v1/endpoints/economy.py`
- **Aplicación:** `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.semilla` (6 rutas), `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (26):** `tests/test_alineacion_para_descubrir.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_changes_history.py`, `tests/test_dashboard_query.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_lados_del_carril.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_middleware_idioma.py`, `tests/test_player_balance.py`, `tests/test_position_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_timeseries_modelos_nuevos.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/arena`

- **Página:** [frontend/src/pages/ArenaPage.tsx](../frontend/src/pages/ArenaPage.tsx) (510 líneas)
- **Componentes y hooks suyos (10):**
  - [frontend/src/charts/Chart.tsx](../frontend/src/charts/Chart.tsx)
  - [frontend/src/charts/colors.ts](../frontend/src/charts/colors.ts)
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/hooks/useTheme.ts](../frontend/src/hooks/useTheme.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `arena`
- **Rutas HTTP:** `/teams/:x/arena`
- **Endpoints:** `backend/app/api/v1/endpoints/arena.py`
- **Aplicación:** `app.application.queries.arena`, `app.application.queries.nombre_del_torneo` (6 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines.arena_engine` (6 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.value_objects.ht_constants` (25 rutas)
- **Tests (8):** `tests/test_arena_engine.py`, `tests/test_arena_query.py`, `tests/test_camel_helper.py`, `tests/test_economy_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_prediccion_engine.py`, `tests/test_transparencia.py`, `tests/test_weekly.py`

### `/insights`

- **Página:** [frontend/src/pages/InsightsPage.tsx](../frontend/src/pages/InsightsPage.tsx) (200 líneas)
- **Componentes y hooks suyos (7):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Insights.tsx](../frontend/src/components/Insights.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/hooks/useFocoDeLista.ts](../frontend/src/hooks/useFocoDeLista.ts)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
- **Pide a `api.`:** `archiveInsight`, `archivedInsights`, `insights`, `restoreInsight`
- **Rutas HTTP:** `/teams/:x/insights`, `/teams/:x/insights/:x/archive`, `/teams/:x/insights/archived`
- **Endpoints:** `backend/app/api/v1/endpoints/analysis.py`
- **Aplicación:** `app.application.commands.sync_team` (7 rutas), `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.academy`, `app.application.queries.alineacion_enviada` (7 rutas), `app.application.queries.arena`, `app.application.queries.economy` (8 rutas), `app.application.queries.league` (5 rutas), `app.application.queries.nombre_del_torneo` (6 rutas), `app.application.queries.player_balance` (7 rutas), `app.application.queries.prediccion_liga` (7 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.academy_engine`, `app.domain.engines.arena_engine` (6 rutas), `app.domain.engines.asignacion_optima` (9 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.lineup_optimizer` (8 rutas), `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.rival_scouting` (7 rutas), `app.domain.engines.salary_model` (7 rutas), `app.domain.engines.season_simulator` (6 rutas), `app.domain.engines.semilla` (6 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.engines.youth_training_plan` (5 rutas), `app.domain.value_objects.formations` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas)
- **Infraestructura:** `app.infrastructure.chpp.client` (8 rutas), `app.infrastructure.chpp.parsers` (7 rutas), `app.infrastructure.security.tokens` (7 rutas)
- **Tests (74):** `tests/test_academy_comparativa.py`, `tests/test_academy_engine.py`, `tests/test_academy_training_plan_contract.py`, `tests/test_alineacion_para_descubrir.py`, `tests/test_arena_engine.py`, `tests/test_arena_query.py`, `tests/test_asignacion_optima.py`, `tests/test_cache_por_sync.py`, `tests/test_cantera_por_equipo.py`, `tests/test_changes_history.py`, `tests/test_chpp_client_conexion.py`, `tests/test_closing_the_formula.py`, `tests/test_cup_endpoint.py`, `tests/test_dashboard_query.py`, `tests/test_desbloqueo_de_habilidades.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_entrenador_se_lee.py`, `tests/test_entrenador_y_etapas.py`, `tests/test_entrenamiento_completo.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_historial_con_reemplazo.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_insights.py`, `tests/test_insights_endpoint.py`, `tests/test_lados_del_carril.py`, `tests/test_league_comparison_endpoint.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_match_type_helpers.py`, `tests/test_metodo_de_resumen.py`, `tests/test_metodo_ocho.py`, `tests/test_middleware_idioma.py`, `tests/test_minutos_de_seleccion.py`, `tests/test_ojeadores.py`, `tests/test_once_del_ultimo_partido.py`, `tests/test_partidos_ajenos_sin_ficha.py`, `tests/test_plan_de_entrenamiento.py`, `tests/test_player_balance.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_prediccion_engine.py`, `tests/test_prediccion_liga.py`, `tests/test_previous_club_bonus.py`, `tests/test_prioridad_de_entrenamiento.py`, `tests/test_proximo_partido_liga.py`, `tests/test_rivals_endpoint.py`, `tests/test_salary_model.py`, `tests/test_season_simulator.py`, `tests/test_sede.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stint_edit.py`, `tests/test_sync_corte_de_base.py`, `tests/test_sync_diff_integration.py`, `tests/test_sync_endpoint_auth.py`, `tests/test_sync_flow.py`, `tests/test_tacticas.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_token_encryption.py`, `tests/test_training_engine.py`, `tests/test_training_forecast_endpoint.py`, `tests/test_transparencia.py`, `tests/test_ultimo_entrenamiento.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weather.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`, `tests/test_youth_parser.py`, `tests/test_youth_skill_score.py`

### `/sync`

- **Página:** [frontend/src/pages/SyncPage.tsx](../frontend/src/pages/SyncPage.tsx) (202 líneas)
- **Componentes y hooks suyos (7):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/SyncProgressPanel.tsx](../frontend/src/components/SyncProgressPanel.tsx)
  - [frontend/src/hooks/useFormat.ts](../frontend/src/hooks/useFormat.ts)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `dashboard`
- **Rutas HTTP:** `/teams/:x/dashboard`
- **Endpoints:** `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.dashboard` (6 rutas), `app.application.queries.economy` (8 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.post_match_training` (7 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.training_squad` (7 rutas), `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
- **Tests (32):** `tests/test_cache_por_sync.py`, `tests/test_changes_history.py`, `tests/test_closing_the_formula.py`, `tests/test_dashboard_query.py`, `tests/test_economy_engine.py`, `tests/test_economy_query.py`, `tests/test_experience_calibration_api.py`, `tests/test_formato_numeros.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_loyalty_engine.py`, `tests/test_match_type_helpers.py`, `tests/test_player_balance.py`, `tests/test_player_detail_endpoint.py`, `tests/test_player_history.py`, `tests/test_position_engine.py`, `tests/test_post_match_training.py`, `tests/test_prediccion_engine.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stamina_reference.py`, `tests/test_stats.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_training_engine.py`, `tests/test_training_squad.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_htms.py`

### `/news`

- **Página:** [frontend/src/pages/SyncChangesPage.tsx](../frontend/src/pages/SyncChangesPage.tsx) (868 líneas)
- **Componentes y hooks suyos (16):**
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
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `changesHistory`, `deleteTransferAttempt`, `lastMatchReport`, `setTimesSeen`, `squad`, `syncChanges`, `transferAttempts`
- **Rutas HTTP:** `/teams/:x/changes/history`, `/teams/:x/last-match-report`, `/teams/:x/squad`, `/teams/:x/sync/changes`, `/teams/:x/transfer-attempts`, `/teams/:x/transfer-attempts/:x`
- **Endpoints:** `backend/app/api/v1/endpoints/player_balance.py`, `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.changes_history`, `app.application.queries.parte_del_partido`, `app.application.queries.player_balance` (7 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.sync_comparison`, `app.application.queries.transfer_attempts`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.player_balance` (7 rutas), `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.salary_model` (7 rutas), `app.domain.engines.sync_diff`, `app.domain.value_objects.formatting` (17 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.ht_time` (9 rutas), `app.domain.value_objects.skill`
- **Tests (32):** `tests/test_age.py`, `tests/test_cache_por_sync.py`, `tests/test_cambios_academia_profundo.py`, `tests/test_cambios_del_ultimo_sync.py`, `tests/test_cambios_juveniles.py`, `tests/test_camel_helper.py`, `tests/test_changes_history.py`, `tests/test_economy_engine.py`, `tests/test_formato_numeros.py`, `tests/test_formatting.py`, `tests/test_ht_constants.py`, `tests/test_htms.py`, `tests/test_league_matches_academy_queries.py`, `tests/test_lineup_optimizer.py`, `tests/test_middleware_idioma.py`, `tests/test_player_balance.py`, `tests/test_position_engine.py`, `tests/test_previous_club_bonus.py`, `tests/test_salary_model.py`, `tests/test_squad_last_match_recency.py`, `tests/test_stint_edit.py`, `tests/test_sync_comparison.py`, `tests/test_sync_diff.py`, `tests/test_team_overview.py`, `tests/test_team_rating_engine.py`, `tests/test_transfer_attempts.py`, `tests/test_transparencia.py`, `tests/test_ventanas_de_comparacion.py`, `tests/test_veteranos_y_deficit.py`, `tests/test_weekly.py`, `tests/test_youth_arrival.py`, `tests/test_youth_htms.py`

### `/transparency`

- **Página:** [frontend/src/pages/TransparencyPage.tsx](../frontend/src/pages/TransparencyPage.tsx) (980 líneas)
- **Componentes y hooks suyos (6):**
  - [frontend/src/components/Ayuda.tsx](../frontend/src/components/Ayuda.tsx)
  - [frontend/src/components/Panels.tsx](../frontend/src/components/Panels.tsx)
  - [frontend/src/components/Tabs.tsx](../frontend/src/components/Tabs.tsx)
  - [frontend/src/hooks/useTeam.ts](../frontend/src/hooks/useTeam.ts)
  - [frontend/src/i18n/index.ts](../frontend/src/i18n/index.ts)
  - [frontend/src/i18n/tx.ts](../frontend/src/i18n/tx.ts)
- **Pide a `api.`:** `calculos`, `experienceModel`, `loyaltyModel`, `positionModel`, `trainingFormula`
- **Rutas HTTP:** `/teams/:x/experience/calibration`, `/teams/:x/loyalty/model`, `/teams/:x/training/formula`, `/teams/calculos`, `/teams/positions/model`
- **Endpoints:** `backend/app/api/v1/endpoints/analysis.py`, `backend/app/api/v1/endpoints/teams.py`
- **Aplicación:** `app.application.dto.dashboard` (19 rutas), `app.application.dto.squad` (19 rutas), `app.application.queries.player_history` (9 rutas), `app.application.queries.squad` (19 rutas), `app.application.queries.training_context` (10 rutas), `app.application.queries.transparencia`, `app.application.queries.weekly` (25 rutas)
- **Dominio:** `app.domain.engines` (22 rutas), `app.domain.engines.economy_engine` (21 rutas), `app.domain.engines.experience_engine`, `app.domain.engines.loyalty_engine` (9 rutas), `app.domain.engines.metodo_ocho`, `app.domain.engines.position_engine` (20 rutas), `app.domain.engines.prediccion` (9 rutas), `app.domain.engines.season_simulator` (6 rutas), `app.domain.engines.stats` (11 rutas), `app.domain.engines.training_engine` (10 rutas), `app.domain.engines.youth_skill_score`, `app.domain.engines.youth_training_plan` (5 rutas), `app.domain.value_objects.ht_constants` (25 rutas), `app.domain.value_objects.stamina_reference` (9 rutas)
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
- **Rutas HTTP:** `/usage`, `/usage/log`
- **Endpoints:** `backend/app/api/v1/endpoints/uso.py`
- **Dominio:** `app.domain.engines` (22 rutas)
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

**Tests que cubren esa parte compartida (67):** correrlos al tocarla.

## Lo más caro de leer

Los veinte ficheros más largos. Cualquier cambio que los toque paga su
tamaño entero, así que son los candidatos a partirse por funcionalidad.

| Líneas | Fichero |
| --: | --- |
| 7257 | [backend/app/application/commands/sync_team.py](../backend/app/application/commands/sync_team.py) |
| 4147 | [frontend/src/services/api.ts](../frontend/src/services/api.ts) |
| 4006 | [frontend/src/pages/AcademyPage.tsx](../frontend/src/pages/AcademyPage.tsx) |
| 2963 | [frontend/src/pages/PlayerBalancePage.tsx](../frontend/src/pages/PlayerBalancePage.tsx) |
| 2757 | [backend/app/application/queries/transparencia.py](../backend/app/application/queries/transparencia.py) |
| 2309 | [backend/app/api/v1/endpoints/analysis.py](../backend/app/api/v1/endpoints/analysis.py) |
| 1912 | [frontend/src/pages/TrainingPage.tsx](../frontend/src/pages/TrainingPage.tsx) |
| 1856 | [frontend/src/pages/wiki/contenido.ts](../frontend/src/pages/wiki/contenido.ts) |
| 1702 | [backend/app/api/v1/endpoints/rivals.py](../backend/app/api/v1/endpoints/rivals.py) |
| 1670 | [backend/app/infrastructure/chpp/parsers/__init__.py](../backend/app/infrastructure/chpp/parsers/__init__.py) |
| 1628 | [backend/app/infrastructure/db/models.py](../backend/app/infrastructure/db/models.py) |
| 1600 | [frontend/src/pages/LeaguePage.tsx](../frontend/src/pages/LeaguePage.tsx) |
| 1546 | [backend/app/application/queries/economy.py](../backend/app/application/queries/economy.py) |
| 1475 | [frontend/src/pages/PlayerPage.tsx](../frontend/src/pages/PlayerPage.tsx) |
| 1374 | [frontend/src/pages/EconomyPage.tsx](../frontend/src/pages/EconomyPage.tsx) |
| 1365 | [frontend/src/pages/RivalPage.tsx](../frontend/src/pages/RivalPage.tsx) |
| 1279 | [backend/app/api/v1/endpoints/cup.py](../backend/app/api/v1/endpoints/cup.py) |
| 1252 | [backend/app/application/queries/player_balance.py](../backend/app/application/queries/player_balance.py) |
| 1241 | [backend/app/application/queries/sync_comparison.py](../backend/app/application/queries/sync_comparison.py) |
| 1231 | [backend/app/application/queries/league.py](../backend/app/application/queries/league.py) |
