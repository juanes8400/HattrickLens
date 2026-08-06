# Referencia CHPP — esquemas reales de la API

Los 32 `.txt` de esta carpeta son las definiciones oficiales de campos de cada
fichero CHPP (nombre, tipo, descripción). Son la fuente de verdad de los
parsers y los modelos: cuando un campo aquí contradiga un supuesto del código,
manda el esquema.

## Lo que cada fichero desbloquea, y qué bug arregla

### Cierran debates abiertos o bugs conocidos

- **`club`** → `AssistantTrainerLevels` (entero único, máx 10). **Cierra la
  fórmula de entrenamiento**: el nivel de los ayudantes ya no se infiere, se
  lee. También `FormCoachLevels`, `MedicLevels`, `SportPsychologistLevels`,
  `TacticalAssistantLevels`, `FinancialDirectorLevels`, `SpokespersonLevels`,
  `YouthLevel`, `Investment` (inversión semanal juvenil real).
- **`training`** → `TrainingLevel` (intensidad real), `StaminaTrainingPart`
  (%condición real), `TrainingType`, experiencia por formación (442, 433…),
  moral, autoconfianza. Con `club` + `stafflist`, **la fórmula queda
  totalmente identificada**: entrenador y condición dejan de estar confundidos.
- **`stafflist`** → `TrainerSkillLevel` (1–5 en API), `TrainerType`
  (0 def / 1 of / 2 equilibrado), `Leadership`, coste. El entrenador real.
- **`arena_details`** → `Terraces`, `Basic`, `Roof`, `VIP` (aforo real por
  sector) + `CurrentCapacity`, `ExpandedCapacity`, `ExpansionDate`, `RegionID`.
  **Arregla el bug de demanda censurada de raíz**: ya no se deriva el aforo.
- **`worlddetails`** → `CurrencyRate` (tasa real), `Season`, `MatchRound`,
  `MatchRoundsLeft`, `TrainingDate`, `SeriesMatchDate`, `NumberOfLevels`.
  **Arregla el lío de temporada/jornada (HL-007) y la moneda** de verdad.
- **`trainingevents`** → subidas de skill confirmadas: `SkillID`, `OldLevel`,
  `NewLevel`, `Season`, `MatchRound`, `DayNumber`. **La calibración dinámica
  de experiencia/entrenamiento deja de inferir pops de snapshots**: CHPP los
  entrega con fecha.
- **`leaguelevels`** → `NrOfDirectPromotion/DemotionSlotsPerSeries`,
  `NrOfQualification…`. **El simulador usa ascenso/descenso reales** en vez de
  asumir top-2/bottom-2.

### Cierran módulos que hoy responden "faltan datos"

- **`matchdetails`** → ocasiones YA clasificadas por CHPP:
  `NrOfChancesLeft/Center/Right/SpecialEvents/Other` por equipo, más
  `RatingIndirectSetPiecesDef/Att`, `TacticType`, `TacticSkill`,
  `TeamAttitude`, `StyleOfPlay`, posesión por mitad, goleadores (con minuto),
  tarjetas, lesiones, árbitro. **Hace innecesario mi mapa inventado de
  `event_type_id`.**
- **`matchlineup`** → `RoleID`, `Behaviour`, `RatingStars`,
  `RatingStarsEndOfMatch` por jugador. Rendimiento individual por posición.
- **`youthplayerdetails`** → skills juveniles con `IsAvailable`, `IsMaxReached`,
  `MayUnlock` y `*SkillMax` reales. **Cierra Juveniles**: techos de verdad, no
  supuestos.
- **`playerdetails`** → ficha completa: `StaminaSkill`, `PlayerForm`,
  `Loyalty`, `MotherClubBonus`, `Specialty`, personalidad (`Agreeability`,
  `Aggressiveness`, `Honesty`), `Leadership`, `Experience`, `TransferDetails`,
  `RatingEndOfGame`. Cierra la ficha de jugador y personalidad (HL-011/013).

### Habilitan módulos nuevos

- **`fans`** → `FanMood`, `FanMatchExpectation`, `FanSeasonExpectation`,
  `FanMoodAfterMatch`. Presión de la afición y gestión de expectativas.
- **`transfersteam`** → historial real de compras/ventas con `Price`, `TSI`,
  fechas, sumas totales. ROI de academia y P&L de fichajes reales.
- **`transfersearch`** → escaneo de mercado con skills, forma, especialidad,
  precio. Buscador de fichajes que encajen en una posición (usa position_engine).
- **`currentbids`** → pujas activas del equipo, con `Deadline` y `HighestBid`.
- **`playerevents`** → hitos del jugador (`PlayerEventTypeID`, fecha, texto).
- **`achievements`** → logros del manager con puntos y rango.
- **`managercompendium`** → identidad del usuario/equipos/último login.
- **`challenges`** → amistosos concertados y ofertas.
- **`matchorders`** / **`matchesarchive`** / **`cupmatches`** /
  **`leaguefixtures`** / **`leaguedetails`** / **`regiondetails`** (clima
  regional) / **`youthteamdetails`** (ojeador, viajes) / **`youthplayerlist`** /
  **`youthleaguefixtures`** / **`youthleaguedetails`**.

## Estado: la fórmula de entrenamiento está CERRADA

Implementado. Los cuatro términos se leen del CHPP (club, training, stafflist) y
se validan contra subidas confirmadas (trainingevents). Ver CORRECTIONS.md §9 y
`GET /teams/{id}/training/formula`. Sólo queda por reconciliar la escala 1–5 del
entrenador con la 7/8 de la fórmula, declarada provisional en training.yaml.

## Detalle clave para la fórmula de entrenamiento

`club.AssistantTrainerLevels` es un **entero único** con máximo 10 — coincide
exactamente con el tope que los datos ya exigían. Confirma que la variable de la
fórmula es un nivel agregado 0–10 leído de la API, no una cuenta de ayudantes.
Con `training.TrainingLevel` (intensidad) y `training.StaminaTrainingPart`
(%condición) también reales, el único término antes libre —el producto
entrenador × condición— se separa: `stafflist.TrainerSkillLevel` da el
entrenador, y la condición sale del propio fichero. La fórmula pasa de
"identificada salvo un producto" a "totalmente leída".
