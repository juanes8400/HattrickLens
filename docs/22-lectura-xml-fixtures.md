# Lectura de XML reales de Hattrick Lens

Fecha de lectura: 2026-07-30

Carpeta leida: `backend/tests/fixtures`.

Estos XML son fixtures CHPP reales usados por los tests del backend. Representan
un club conectado via CHPP y sirven como contrato de datos para parsers,
sincronizacion, modelos e interfaz.

## Inventario

| XML | Version | Que representa | Parser |
| --- | --- | --- | --- |
| `teamdetails.xml` | 3.6 | Usuario, equipos, liga, serie, copa, estadio, fanclub y estado del club | `parse_teamdetails` |
| `players.xml` | 2.6 | Plantilla completa del equipo propio | `parse_players` |
| `playerdetails.xml` | 3.2 | Ficha extendida de un jugador | `parse_playerdetails` |
| `training.xml` | 2.2 | Entrenamiento actual/ultimo, moral, confianza y experiencia de formaciones | `parse_training` |
| `club.xml` | 1.0 | Staff agregado, inversion y nivel de juveniles | `parse_club` |
| `stafflist.xml` | 1.0 | Entrenador principal y miembros de staff | `parse_stafflist` |
| `trainingevents.xml` | 1.0 | Subidas de habilidad confirmadas por CHPP | `parse_trainingevents` |
| `economy.xml` | 1.1 | Caja, ingresos, costes, proyeccion y ultimo balance semanal | `parse_economy` |
| `worlddetails.xml` | 1.8 | Liga/pais, temporada, jornada, moneda y fechas de updates | `parse_worlddetails` |
| `matches.xml` | 2.9 | Calendario/resultados del equipo propio | `parse_matches` |
| `rival_matches.xml` | 2.9 | Calendario/resultados de un rival permitido por CHPP | `parse_matches` |
| `matchdetails.xml` | 3.1 | Ratings, posesion, tacticas, estadio y eventos de un partido | `parse_matchdetails` |
| `matchlineup.xml` | 1.2 | Alineacion real del rival en un partido | `parse_matchlineup` |
| `matchlineup_home.xml` | 1.2 | Alineacion real propia en el mismo partido | `parse_matchlineup` |
| `leaguedetails.xml` | 1.6 | Tabla de posiciones de la serie | `parse_leaguedetails` |
| `transfersteam.xml` | 1.1 | Historial de transferencias del equipo | `parse_transfersteam` |

## Foto de datos normalizados

- Usuario CHPP fixture: `10857807`.
- Club principal: `Pulgas Arrechas`, HT team id `537758`, liga Colombia,
  serie `V.92`.
- Plantilla: 24 jugadores con edad, TSI, forma, condicion, experiencia, salario,
  personalidad, lealtad, especialidad, goles y skills.
- Entrenamiento: tipo `10`, intensidad `100`, condicion `25`, ultimo
  entrenamiento tipo `10`, ultimo stamina `10`.
- Entrenador: `Volodymyr Manakin`, tipo equilibrado, skill level `5`,
  liderazgo `5`.
- Staff agregado de club: asistentes de entrenador `7`, form coach `3`,
  medico `2`, psicologo `1`, inversion juvenil `11240`, nivel juvenil `4`.
- Economia: caja positiva, proyeccion semanal y desglose de ingresos/costes.
- Mundo: Colombia temporada `84`, jornada `3`, moneda `US$`, currency rate
  `10.0`, fechas de entrenamiento, liga y economia.
- Partidos: 17 registros propios; `rival_matches.xml` trae 7 registros de un
  rival.
- Partido detallado: ratings por sector, posesion por mitad, tacticas y estadio.
- Alineaciones: una del rival y una propia para el mismo match id.
- Training events: 5 pops confirmados con `SkillID`, viejo/nuevo nivel,
  temporada, jornada y dia.

## Como se entienden juntos

### Conexion y cuenta

`teamdetails.xml` es la pieza de identidad. Tras OAuth, el backend usa
`teamdetails` para encontrar `UserID`, `Loginname` y el/los equipos. De ahi se
crea o actualiza el usuario local y se elige el primer equipo. Para el asistente,
este XML responde:

- que club esta conectado;
- en que liga/serie juega;
- si tiene copa activa;
- si hay amistoso y si es posible retar;
- estadio, fanclub, ranking y bot status.

Oportunidad: el parser actual solo conserva usuario, equipo, liga y serie.
Puede ampliarse para checklist semanal: copa, amistoso, estadio, fanclub,
ranking, region y desafios posibles.

### Plantilla y jugador

`players.xml` es la foto de plantilla para sync normal. Trae datos suficientes
para alineacion, entrenamiento, salarios, lesiones, tarjetas y valoraciones.
Incluye skills exactas solo del equipo propio, como exige CHPP.

`playerdetails.xml` complementa a un jugador individual. Es importante porque:

- `CareerAssists` no existe en `players.xml`;
- el nombre del club madre viene aqui;
- la ultima posicion/ratings/minutos vienen en `LastMatch`;
- contiene `RatingEndOfGame`, `ArrivalDate`, `AssistsCurrentTeam`,
  `MatchesCurrentTeam` y otros campos que pueden enriquecer la ficha.

Oportunidad: usar `playerdetails` bajo demanda, no para cada jugador siempre.
Sirve para una ficha profunda o para sincronizacion manual de detalles.

### Entrenamiento

`training.xml`, `club.xml`, `stafflist.xml`, `trainingevents.xml` y
`worlddetails.xml` juntos cierran el modulo de entrenamiento.

- `training` da tipo, intensidad, stamina, moral, confianza y experiencia por
  formacion.
- `club` da el total real de asistentes y staff agregado.
- `stafflist` da el entrenador real: nivel, liderazgo, tipo y coste.
- `trainingevents` da pops confirmados por Hattrick.
- `worlddetails` da fecha real del proximo update de entrenamiento.

Oportunidad: el asistente puede decir "quien entrena", "quien desperdicio
minutos", "cuando viene el proximo update", "que formacion domina el equipo" y
"que pops reales validan la formula".

### Economia

`economy.xml` trae caja actual, caja esperada, ingresos/costes de esta semana y
del ultimo update. Tambien fanclub y popularidad de supporters/sponsors.

Oportunidad: alimentar un bloque de caja proyectada, salarios peligrosos,
balance estructural y decisiones de venta/compra. Hay campos `LastCosts*` y
`LastIncome*` que conviene explotar mas para explicar cambios semanales.

### Liga y calendario

`leaguedetails.xml` trae tabla de ocho equipos de la serie. No trae temporada;
esa viene de `worlddetails.xml`. La jornada real del fichero es
`CurrentMatchRound`.

`matches.xml` trae fixtures/resultados propios, con status, goles, tipo de
partido, ordenes dadas, cup level/index y equipos local/visitante.

`rival_matches.xml` usa el mismo parser, pero debe tratarse como dato permitido
de rival, sin almacenar historico abusivo de plantilla rival.

Oportunidad: previa semanal, simulador de liga, riesgo de descenso/ascenso,
record por tipo de partido y deteccion de si faltan ordenes.

### Partido y tactica

`matchdetails.xml` es el XML tactico mas valioso. Trae:

- ratings: mediocampo, defensas derecha/centro/izquierda, ataques
  derecha/centro/izquierda;
- ratings de pelota parada indirecta ataque/defensa;
- posesion por mitad;
- tactica y nivel tactico;
- actitud del equipo;
- formacion;
- chances por sector: izquierda, centro, derecha, eventos especiales y otros;
- estadio, espectadores por sector y clima;
- arbitro;
- tarjetas, lesiones y goleadores.

El parser actual conserva ratings, posesion, tactica, actitud, estadio basico y
eventos genericos, pero todavia no explota todos los campos de chances, pelota
parada indirecta, referee, bookings, injuries y scorers.

Oportunidad: esta es la base del "asistente de partido": explicar por que se
gano/perdio, que sector fue rentable, que tactica rival uso, cuantos eventos
vinieron por banda/centro, y si el resultado fue coherente con ratings.

`matchlineup.xml` y `matchlineup_home.xml` agregan nombres, roles, posicion,
behaviour y estrellas. Juntos con `matchdetails` permiten unir:

- rating de equipo por sector;
- jugador que ocupo cada rol;
- orden/behaviour;
- estrellas de rendimiento.

Oportunidad: explicar "este lateral ofensivo subio ataque por derecha pero
debilito defensa", y entrenar el optimizador contra alineaciones reales.

### Transferencias

`transfersteam.xml` trae compras/ventas del equipo, precio, fecha, comprador,
vendedor, TSI, estadisticas agregadas y paginacion.

El parser actual guarda la transferencia individual, pero no expone todavia
`Stats`, `Pages`, `PageIndex`, `StartDate`, `EndDate`, `TransferID` ni `TSI`.

Oportunidad: ROI real de fichajes, precio de compra de jugadores actuales,
beneficio/perdida, y advertencias por ventas que afecten team spirit o
experiencia de formacion.

## Campos importantes aun subutilizados

- `teamdetails`: copa, amistoso, posibles desafios, fanclub, power rating,
  region, estadio, trophy list.
- `matchdetails`: chances por sector, pelota parada indirecta, formacion,
  bookings, injuries, scorers, referee y sold seats por tipo.
- `matchlineup`: `ExperienceLevel` del equipo y `RatingStarsEndOfMatch` si viene
  en nuevas versiones.
- `players`: `ArrivalDate`, `Cards`, `MatchesCurrentTeam`,
  `GoalsCurrentTeam`, `PlayerCategoryId`, `NationalTeamID`, `OwnerNotes`.
- `playerdetails`: ficha casi completa, incluyendo `TransferDetails` cuando el
  API lo entregue.
- `economy`: desglose anterior completo (`LastIncome*`, `LastCosts*`) para
  explicar variaciones.
- `transfersteam`: estadisticas agregadas, TSI y paginacion.

## Regla para construir el asistente

Cada recomendacion debe poder rastrearse a uno de estos XML. Ejemplos:

- "Te falta amistoso" viene de `teamdetails.FriendlyTeamID` y/o `matches`.
- "Este jugador desperdicio entreno" viene de `training.TrainingType` +
  `matchlineup.PositionCode` + minutos de `playerdetails.LastMatch` o
  detalles de partido.
- "Tu plan por bandas no tuvo volumen" viene de `matchdetails.NrOfChancesLeft`
  y `NrOfChancesRight`.
- "La formula de entrenamiento esta calibrada" viene de `trainingevents`.
- "Tu caja aguanta" viene de `economy` + `worlddetails.CurrencyRate`.
- "Este fichaje esta en ROI positivo/negativo" viene de `transfersteam` +
  valoracion actual.
