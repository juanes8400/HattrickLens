# Corrections to the specification

The documents in this folder are the product specification. Several statements
in them are contradicted or completed by evidence gathered against the live
CHPP API and a real club. The specs are kept unedited for traceability; the
corrections live here and the implementation follows this file.

---

## 1. CHPP uses OAuth 1.0a, not OAuth2

**Where:** `ARCHITECTURE.md` — "OAuth2 / CHPP" in the architecture diagram.
`API.md` — "OAuth2/JWT authentication".

**Evidence:** the full three-legged flow was executed against the live service.
The endpoints are

```
https://chpp.hattrick.org/oauth/request_token.ashx
https://chpp.hattrick.org/oauth/authorize.aspx
https://chpp.hattrick.org/oauth/access_token.ashx
```

signed with HMAC-SHA1 and using `oauth_token` / `oauth_verifier`. Requests to
`chppxml.ashx` carry an OAuth 1.0a signature. There is no authorization-code
exchange and no bearer token.

**Impact:** the client library, the token store and the callback handler all
differ. JWT still applies, but only for HT Lens' own session, never for CHPP.

**Implementation:** `app/infrastructure/chpp/client.py`.

---

## 2. Scheduled synchronisation is not allowed for this class of application

**Where:** `CHPP.md` — "Incremental Sync ... Triggered: Scheduled jobs" and
"Future Extensions: Background synchronisation queue".

**Evidence:** the CHPP Manual states that for manager-assistant applications
downloads must be initiated by the user and not by a timer, that files must be
fetched sequentially rather than in parallel within a session, and that
tracking other teams' players is not permitted.

**Impact:** this is not a detail — it shapes the whole product. The sync button
is a permanent, prominent element rather than a settings toggle, and the value
proposition rests on analysing accumulated history rather than on freshness.

**Implementation:** `SyncTeamHandler` fetches files one at a time; Celery Beat
only performs internal maintenance and never calls CHPP. An exemption can be
requested from the Hattrick team when applying for CHPP approval, and the
scheduler is ready for it, but the default behaviour complies today.

---

## 3. "Never overwrite" needs a mechanism, not a policy

**Where:** `DATABASE.md` — "Never overwrite: skills, TSI, economy, attendance,
match ratings. Always append historical records."

**Gap:** the intent is right but nothing enforces it, and appending blindly on
every synchronisation multiplies rows for data that has not changed.

**Implementation:** every mutable entity has a `content_hash` column holding a
SHA-256 of its canonical fields. A snapshot is written only when the hash
differs from the previous one, and existing snapshots are never updated. The
invariant is covered by a test that runs two consecutive syncs over identical
data and asserts that the second writes nothing.

---

## 4. Assistant coaches: two of them, and the number is a sum of levels

**Where:** `TRAINING_ENGINE.md` — "Maximum two assistants."

**The specification is right and an earlier correction here was wrong.** Hattrick
allows **at most two** assistant coaches, each up to level 5, and the training
formula takes the **sum of their levels** — 5+5, 3+2, 1+0. It is never a
head-count. The maximum possible value is therefore **10**.

This also explains the 3.5% coefficient: 10 × 3.5% = 35%, so the denominator
`1 − Σ×3.5%` bottoms out at 0.65 and can never approach zero. The cap is the
game's own limit, not a numerical guard bolted on afterwards.

**What this refutes.** A previous version of this file claimed the observed
weeks required a level sum near 12.7 and concluded that Hattrick Control's
"Entrenadores aux.: 10" was a head-count. That conclusion is impossible: 12.7
exceeds what two level-5 assistants can produce. The 10 on screen **is** the sum
of levels, and the club is at the ceiling. `TrainingSetup` now raises on any
value above 10, so this class of error cannot recur silently.

**What it costs.** Removing that free parameter re-opens a question it had been
papering over. See §5.

**Implementation:** `assistant_level_sum_cap: 10` in `app/config/training.yaml`,
enforced by `validate_assistant_level_sum`.

---

## 5. Training formula — supplied and validated

The specification lists the modifiers but not the equation that combines them.
Supplied by the domain expert and implemented verbatim:

```
weeks = base_weeks[skill]
      ÷ (1 + Σ levels of at most 2 assistants × 3.5%)       ← max sum = 10
      × (1 + 6% × (age − 17))
      × (1 + 10% × max(7 − coach_level, 0) − 5% if the coach is excellent)
      × (1 − 1% × (intensity − 100))
      × (1 − stamina_share)
```

**The coach term applies below the reference level, not above it.** `max(7 − level, 0)`
means a weak coach costs weeks while a strong one simply stops costing them.
Because the term is zero at level 7 and above, the 5% excellent bonus cannot be
counted twice — which is what the earlier `max(level − 7, 0)` reading did.

| Coach | Factor |
|---|---:|
| level 5, not excellent | 1.20 |
| level 7, excellent | 0.95 |
| level 8, excellent | 0.95 |

**Retired validation.** The 18-value fit below was made while the assistant
speed term was accidentally multiplied into weeks. It is kept as an audit trail,
but is not used by Lens and is not evidence for the corrected model. New error
figures will come only from comparable CHPP pop intervals. The old model, against 18 observed "weeks to next level" values from Hattrick
Control, using the squad's real configuration — excellent coach at level 8,
100% intensity, 25% stamina share — the formula reaches **mean error 0.185
weeks, maximum 0.786, R² 0.936**:

| Player | Hattrick Control | HT Lens |
|---|---:|---:|
| Florin Tilvar | 7.2 | 7.6 |
| Karl-Ove Palmén | 7.5 | 7.6 |
| Aydin Davey | 8.1 | 8.3 |
| Hugo Chauvel | 9.5 | 9.5 |
| Klaus Bahlek | 10.7 | 10.2 |
| Raúl Cobos | 11.4 | 10.6 |

**Identifiability — the honest caveat.** Every constant multiplier in this
formula is confounded with the others when only one training configuration is
observed. Two of them are now pinned by facts rather than fitting:

- base weeks per skill: from the specification (passing = 5)
- assistant level sum: **10**, and it cannot be anything else — two assistants
  at level 5 is the game's ceiling (§4)

That leaves the coach factor and the stamina share, and the data identifies only
their **product: 0.8304**. Several readings fit equally well:

| Reading | Coach factor | Stamina share | Mean error | R² |
|---|---:|---:|---:|---:|
| Excellent coach, level 8 | 0.95 | 12.5% | 0.185 | 0.936 |
| Level 7, not excellent | 1.00 | 17% | 0.186 | 0.936 |
| Level 6, excellent | 1.05 | 20% | 0.217 | 0.933 |
| Level 6, not excellent | 1.10 | 25% | 0.191 | 0.929 |

The engine uses the first, because an excellent coach is what the club's staff
screen shows. But 0.95 × 0.875 and 1.00 × 0.83 are the same number, and no
amount of data from *this* configuration will separate them. Settling it needs a
second configuration: a change in this club's setup, or another club's data.

What is worth noting is that the stamina share **must** be in the formula. With
the assistant sum pinned at 10, the required product is 0.8304, and the coach
factor alone cannot go below 0.95. Something below 1 is mandatory, and the
stamina share is the only candidate the formula offers.

**Assistant direction, corrected.** Each assistant level contributes 3.5% of
training speed. The waiting time is therefore divided by
`1 + Σ×3.5%`. At the legal maximum of two level-5 assistants, that is a 35%
speed bonus and 74.1% of the no-assistant wait. The prior inverse expression
was a mathematical direction error and is no longer used.

**Stamina share belongs in the formula**, as the multiplier `(1 − share)`:
effort diverted to stamina is effort the main skill does not have to wait for.
An earlier reading excluded it; with the coach term corrected, including it is
what reproduces the observed weeks.

**One property worth knowing:** the formula has no term for the current skill
level, so a player at level 3 and one at level 17 of the same age take exactly
the same time. This agrees with the measured level effect of 0.068 in the
exponent — negligible next to 6% per year of age. An exponential age model with
a level term fits the same data more tightly (R² 0.999) and stays available in
configuration for comparison.

---

## 6. Experience points per level — measured, not declared

The specification says 28 points per level; reproducing Hattrick Control's
percentages appeared to need about 26.3. Rather than pick one and hardcode it,
the engine now measures.

`detect_level_ups` turns a chronological series of readings into observed
crossings, recording the points each player held immediately before levelling.
`calibrate` reports the **mean**, the **standard deviation**, the **number of
observations**, a **95% confidence interval**, and a **breakdown by starting
level**. It also reports its `source`: `configured` while the evidence is thin,
`observed` once there is enough.

Below `min_observations_to_calibrate` (5) the configured 28 stands. A mean over
one or two crossings is not evidence, and presenting it as one would be worse
than using the prior. Above the threshold the observed mean replaces it, and the
standard deviation says how far to trust it — including whether the cost is
constant across levels at all, which the by-level breakdown would expose.

The per-match point values remain **verified**: they reconstruct Hattrick
Control's "Suma" column for 19 players with zero error. League and international
friendly are confirmed; cup, qualification and plain friendly come from the
specification and are labelled as such in the API and the Motor screen.

Exposed at `GET /teams/{id}/experience/calibration` and rendered on the Motor
page, including how many more crossings are needed before the number changes.

---

## Open numeric conflicts

Two credible sources still disagree. Both values live in configuration; final
tuning is deferred until enough history has accumulated to settle them with
observed pops rather than argument.

| Constant | Specification | Measured | Default in use |
|---|---|---|---|
| Age factor shape | linear, 6% per year | exponential, 4.63% per year, R² 0.999 | linear (canonical formula) |
| Coach factor × stamina share | not stated | product = 0.8304, factors not separable | 0.95 × 0.875 |
| Assistant term direction | more assistants → more weeks | the only sign that fits | as supplied |

The experience constant has left this table: it is no longer a conflict to be
argued but a quantity the engine measures and reports with its uncertainty
(§6).

**On "the shape of the age factor".** The shape is how training time grows with
age. *Linear* means each year adds a flat 6% of the base time, so 17 → 27 years
multiplies it by 1.60. *Exponential* means each year multiplies by 1.0463, so
the surcharge compounds on the previous year's — slower at first, faster later.
Across the squad's actual age range the two nearly coincide; they separate at
the extremes. The linear form is used because it is the canonical formula.

The full record, including the assumptions that were later disproved, is in
`docs/16-calibracion-y-supuestos.md`.

---

## 7. La capacidad del estadio por sector no es derivable de las ventas

**Dónde:** el primer diseño de `ArenaQueryService` repartía el aforo total
entre sectores en proporción a lo vendido, porque `stadium_history` sólo
guardaba `capacity_total`.

**El problema:** ese reparto vuelve un lleno **indetectable por construcción**.
Si la capacidad de cada sector se deduce de sus ventas, la ocupación sale
idéntica en los cuatro y ningún sector puede aparecer nunca al 100%. La demanda
censurada — lo único que de verdad importa para decidir una ampliación —
quedaba invisible, y el servicio devolvía `demandIsCensored: false` como si
fuera una medida cuando era un artefacto del cálculo.

No es un error de precisión: es un sesgo que apunta siempre en la misma
dirección, hacia «tu estadio es del tamaño adecuado».

**Cómo salió:** un test que llenaba tribunas al 100% en los tres partidos y
esperaba ver la censura marcada. Falló, y el fallo estaba en el diseño, no en
el test.

**Implementación:** migración `0005` añade `capacity_terraces`, `capacity_basic`,
`capacity_roof` y `capacity_vip` a `stadium_history`. Cuando CHPP no da el
desglose, el servicio sigue repartiendo pero marca `capacityIsReal: false`, se
niega a evaluar la censura y lo dice en la respuesta y en la pantalla.

---

## 8. El simulador de temporada encoge hacia la media, y dice cuándo eso manda

Un simulador de liga sin encogimiento produce probabilidades muy seguras en la
jornada 3 y muy equivocadas en la 14. Con cuatro jornadas jugadas, un equipo
que ha marcado 12 goles no es tres veces mejor que uno que ha marcado 4.

Las fuerzas de ataque y defensa se estiman como
`(goles + k × media_liga) / (partidos + k)` con `k = 5`. El umbral del aviso no
es arbitrario: mientras las jornadas jugadas sean **menos que k**, el prior de
«equipo medio» pesa más que la evidencia propia del equipo, y la respuesta lo
declara en vez de dejar que las probabilidades se lean como si salieran de los
datos del club.

**Implementación:** `app/domain/engines/season_simulator.py`, expuesto en
`GET /teams/{id}/league` y en `GET /league/model`.

---

## 9. La fórmula de entrenamiento, cerrada: de supuestos a lecturas del CHPP

Durante meses el motor de entrenamiento descansó sobre tres valores puestos a
mano —suma de niveles de ayudantes (10), nivel del entrenador (excelente) y
%condición (12,5%)— que ajustaban las 18 semanas observadas pero que no venían
del juego. El par entrenador × condición ni siquiera era separable: los datos
solo lo identificaban como producto (0,8304).

Con los esquemas reales del CHPP, cada término pasa a leerse:

| Término | Ficha CHPP | Campo |
|---|---|---|
| Ayudantes | `club` | `AssistantTrainerLevels` (entero 0–10) |
| Intensidad | `training` | `TrainingLevel` |
| %condición | `training` | `StaminaTrainingPart` |
| Entrenador | `stafflist` | `TrainerSkillLevel` (1–5) |

Al leer la intensidad y la condición por separado, el producto entrenador ×
condición **se rompe**: la condición deja de ser una incógnita y el entrenador
queda anclado a su valor. `TrainingContextService` construye el `TrainingSetup`
solo con estos valores y adjunta la **procedencia** de cada uno (fichero CHPP o
supuesto), expuesta en `GET /teams/{id}/training/formula` y en la pantalla del
Motor.

**Validación sin inferir.** `trainingevents` entrega subidas de habilidad
confirmadas por Hattrick, con temporada y jornada. La distancia entre dos
subidas consecutivas en la habilidad entrenada es el número real de semanas que
costó subir un nivel, y se compara con la predicción de la fórmula alimentada
con el contexto real: sobre las subidas del club de validación, error medio
0,3 semanas. Antes esos pops se *inferían* comparando fotos de la plantilla;
ahora son evidencia directa.

**Lo único que queda.** El CHPP entrega el nivel del entrenador en escala 1–5
mientras que la fórmula se calibró en la escala nominal 7/8. La correspondencia
vive en `training.yaml` marcada como provisional y se muestra en la nota del
entrenador, en vez de resolverse con un mapeo silencioso — la misma cautela que
evitó perpetuar el error del «tipo de entrenamiento 10».

**Implementación:** parsers `club`/`stafflist`/`worlddetails`/`trainingevents`,
migración `0006` (staff_snapshots, world_context, skill_ups),
`app/application/queries/training_context.py`.
