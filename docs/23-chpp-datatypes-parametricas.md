# CHPP DataTypes: tablas parametricas

Fecha de lectura: 2026-07-30

Fuente: `https://www85.hattrick.org/Community/CHPP/NewDocs/DataTypes.aspx`.

Nota: la URL oficial requiere sesion de Hattrick para leerla en navegador. Esta
nota se construyo con la tabla DataTypes aportada por Juan y se cruza con los
XML reales de `backend/tests/fixtures` y `docs/chpp-reference/Traslation_ESP.txt`.

## Tipos escalares

- `Boolean`: `true` / `false`.
- `Boolean*`: `true` / `false` / vacio.
- `Bit`: `0` falso, `1` verdadero.
- `Char`: literal de un caracter.
- `DateTime`: `YYYY-MM-DD HH:MM:SS` en CE(ST).
- `DateTime*`: igual que `DateTime`; `0001-01-01 00:00:00` significa fecha vacia.
- `Decimal`: usar para dinero/calculos precisos.
- `Float`: flotante.
- `Integer`: entero con signo.
- `unsigned Integer`: entero sin signo.
- `unsigned Integer*`: entero sin signo o vacio.
- `String`, `String*`, `String (HTML encoded)`, `URI`.
- `Money`: entero en SEK; HT Lens lo convierte con `worlddetails.CurrencyRate`.

## Entrenamiento y habilidades

### `trainingType`

| ID | Significado | Skill principal HT Lens |
| --- | --- | --- |
| 0 | General, deprecated | form / no usado |
| 1 | Stamina, deprecated | `stamina` |
| 2 | Set Pieces | `set_pieces` |
| 3 | Defending | `defending` |
| 4 | Scoring | `scoring` |
| 5 | Winger | `winger` |
| 6 | Scoring and Set Pieces | `scoring` como primaria |
| 7 | Passing | `passing` |
| 8 | Playmaking | `playmaking` |
| 9 | Keeper | `keeper` |
| 10 | Passing, defenders + midfielders | `passing` |
| 11 | Defending, defenders + midfielders | `defending` |
| 12 | Winger, wingers + attackers | `winger` |

Correccion aplicada: `backend/app/domain/value_objects/ht_constants.py` tenia
parte de esta tabla desplazada. Ahora `TRAINING_TYPES` y
`TRAINING_TARGET_SKILL` siguen DataTypes.

### `SkillID`

| ID | Skill |
| --- | --- |
| 1 | Goaltending |
| 2 | Stamina |
| 3 | Set pieces |
| 4 | Defending |
| 5 | Scoring |
| 6 | Winger |
| 7 | Passing |
| 8 | Playmaking |
| 9 | Trainer |
| 10 | Leadership |
| 11 | Experience |

Correccion aplicada: `app/config/training.yaml` ahora alinea `skill_id_map` con
esta tabla DataTypes.

### `SkillLevel`

0 a 20: de `non-existent` / `nulo` hasta `divine` / `divino`. La version
espanola vive en `docs/chpp-reference/Traslation_ESP.txt`.

## Partido

### `MatchTypeID`

| ID | Significado | Uso HT Lens |
| --- | --- | --- |
| 1 | League match | competitivo |
| 2 | Qualification match | competitivo |
| 3 | Cup match | competitivo |
| 4 | Friendly normal rules | amistoso |
| 5 | Friendly cup rules | amistoso |
| 7 | Hattrick Masters | competitivo |
| 8 | International friendly normal rules | amistoso |
| 9 | International friendly cup rules | amistoso |
| 10 | National teams competition normal rules | seleccion |
| 11 | National teams competition cup rules | seleccion |
| 12 | National teams friendly | amistoso |
| 50 | Tournament league match | no oficial en analisis base |
| 51 | Tournament playoff match | no oficial en analisis base |
| 61 | Duel | no oficial |
| 62 | Ladder match | no oficial |
| 80 | Preparation match | no oficial |
| 100 | Youth league match | juvenil |
| 101 | Youth friendly match | juvenil |
| 103 | Youth friendly cup rules | juvenil |
| 105 | Youth international friendly | juvenil |
| 106 | Youth international friendly cup rules | juvenil |

Correccion aplicada: `NON_OFFICIAL_MATCH_TYPES` ahora incluye 50, 51, 61, 62 y
80. `FRIENDLY_MATCH_TYPES` incluye 4, 5, 8, 9 y 12.

### `MatchStatus`

0 no iniciado, 1 en curso, 2 finalizado. Algunos XML tambien llegan con texto
como `FINISHED`; los parsers deben tolerar ambas formas segun fichero/version.

### `MatchTacticType`

0 normal, 1 pressing, 2 counter-attacks, 3 attack in the middle, 4 attack in
wings, 7 play creatively, 8 long shots.

### `MatchTeamAttitude`

-1 PIC / jugar relajados, 0 normal, 1 MOTS / partido de la temporada.

### `WeatherID`

0 lluvia, 1 cubierto, 2 parcialmente nublado, 3 soleado.

### `MatchBehaviourID`

-1 sin cambio, 0 normal, 1 ofensivo, 2 defensivo, 3 hacia el medio, 4 hacia la
banda, 5 delantero extra, 6 interior extra, 7 defensa extra.

## Posiciones, roles y ordenes

### `MatchRoleOldID`

Esquema antiguo 1-21 usado por algunos XML antiguos o slots simples:
portero, defensas, extremos, interiores, delanteros, suplentes, balon parado,
capitan y reemplazados.

### `MatchRoleID`

Esquema moderno:

- 100-113: once/catorce slots de campo modernos, de portero a delantero
  izquierdo.
- 114-120: suplentes.
- 200-206: suplentes en ordenes.
- 207-213: backups.
- 17-18: balon parado y capitan.
- 22-32: lanzadores de penaltis.
- 33-35: jugadores expulsados.

Correccion aplicada: `MATCH_ROLE_NAMES` ahora incluye 119, 120 y 200-213.

### `MatchPositionID`

1 portero, 2 lateral derecho, 3 defensa central #1, 4 defensa central #2,
5 lateral izquierdo, 6 extremo derecho, 7 interior #1, 8 interior #2,
9 extremo izquierdo, 10 delantero #1, 11 delantero #2.

## Jugadores, personas y club

- `PlayerCategoryID`: 0 sin categoria, 1 portero, 2 lateral, 3 defensa central,
  4 extremo, 5 interior, 6 delantero, 7 suplente, 8 reserva, 9 extra 1,
  10 extra 2.
- `PlayerAgreeability`: 0 nasty fellow a 5 beloved team member.
- `PlayerAggressiveness`: 0 tranquil a 5 unstable.
- `PlayerHonesty`: 0 infamous a 5 saintly.
- `SpecialtyID`: 0 sin especialidad, 1 tecnico, 2 rapido, 3 potente,
  4 imprevisible, 5 cabeceador, 6 resilient/estoico, 8 support/influyente.
- `StaffType`: 1 asistente, 2 medico, 3 portavoz, 4 psicologo deportivo,
  5 entrenador de forma, 6 director financiero, 7 asistente tactico.
- `GenderID`: 1 masculino, 2 femenino.
- `LeagueSystemID`: 1 masculino, 2 femenino.

## Fans y psicologia

- `TeamSpiritID`: 0 Cold War a 10 Paradise on Earth.
- `SelfConfidenceID`: 0 non-existent a 9 completely exaggerated.
- `SupportersPopularityID`: 0 murderous a 9 sending you love poems.

Las traducciones espanolas se pueden leer desde `Traslation_ESP.txt`; para
fans tambien existen `ref_FanMood.txt`, `ref_FanMatchExpectation.txt` y
`ref_FanSeasonExpectation.txt`.

## Juveniles y scouting

- `ScoutCommentTypeID`: tipo de comentario del scout/entrenador juvenil.
- `ScoutCommentSkillTypeID`: 1 keeper, 3 defending, 4 playmaker, 5 winger,
  6 scorer, 7 set pieces, 8 passing.
- `YouthLeagueStatusID`: 0 no completa, 1 creando partidos, 3 en curso,
  10 finalizada.
- `YouthLeagueType`: 1 regional, 2 nacional, 3 internacional.
- `ScoutSearchTypeID`: 0 cualquiera, 1 portero, 2 defensa, 3 lateral,
  4 mediocampista, 5 extremo, 6 delantero.
- `ScoutTravelTypeID`: 1 avion, 2 carro.

## Otros enums utiles

- `AchievementCategoryID`: ranking, team, matches, manager, special awards,
  supporter.
- `ArenaMatchType`: all, competitive only, league only, friendly only.
- `BookmarkTypeID`: equipos/usuarios, jugadores, partidos, foros, ligas,
  juveniles, posts, threads.
- `FriendlyType`: 0 normal rules, 1 cup rules, 12 national team friendly.
- `TournamentType`: single match, league, playoffs, cup, double elimination,
  ladder, swiss, division battle, wildcards, world cup.
- `positionChange`: 0 no change, 1 up, 2 down.
- `trackingTypeId`: selling, buying, mother club, previous team, hotlisted,
  losing bids, finished, transfer prospects.
- `coachModifier`: -10 100% defensivo a 10 100% ofensivo.
- `matchPart`: 0 antes, 1 primer tiempo, 2 segundo tiempo, 3 overtime,
  4 penaltis.
- `MatchRuleID`: 0 sin reglas, 1 canteranos, 2 sub-20, 3 mayores de 33.
- `CupLevel`: 1 national cup, 2 challenger cup, 3 consolation cup.
- `CupLevelIndex`: 1 emerald, 2 ruby, 3 sapphire.

## Impacto en el asistente

Estas tablas son el diccionario del asistente. Ninguna recomendacion debe
mostrar IDs crudos si hay traduccion DataTypes disponible. Los modulos mas
beneficiados son:

- previa de partido: `MatchTypeID`, `WeatherID`, `MatchTacticType`,
  `MatchTeamAttitude`, `MatchBehaviourID`;
- entrenamiento: `trainingType`, `SkillID`, `SkillLevel`;
- plantilla: `SpecialtyID`, personalidad, categoria y staff;
- cantera: scouts, comentarios, skills juveniles y estado de liga juvenil;
- economia/fans: popularidad, expectativas y confianza.
