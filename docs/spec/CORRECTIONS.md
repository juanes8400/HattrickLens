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

La fórmula comunitaria vigente usa la suma dentro de
`K_asistentes = 0,66 + 0,032 × suma`. Con nivel combinado 10, el coeficiente
es 0,98. El límite 10 es una regla del juego, no un guard numérico agregado.

**What this refutes.** A previous version of this file claimed the observed
weeks required a level sum near 12.7 and concluded that Hattrick Control's
"Entrenadores aux.: 10" was a head-count. That conclusion is impossible: 12.7
exceeds what two level-5 assistants can produce. The 10 on screen **is** the sum
of levels, and the club is at the ceiling. `TrainingSetup` now raises on any
value above 10, so this class of error cannot recur silently.

**Implementation:** `assistant_level_sum_cap: 10` in `app/config/training.yaml`,
enforced by `validate_assistant_level_sum`.

---

## 5. Training formula — fórmula pública HT-Tools

La fórmula lineal anterior quedó refutada. No diferenciaba el costo de una
subida 3→4 y una 17→18. El motor vigente porta la función por tramos, reloj de
edad y coeficientes públicos de HT-Tools; ver `TRAINING_ENGINE.md`.

```text
K = K_entrenamiento × K_entrenador × K_asistentes
    × intensidad × (1 − resistencia) × exposición

semanas = 16 × (reloj_edad⁻¹(reloj_edad
          + (F(nivel+1) − F(nivel+subnivel))/K) − edad)
```

**Private-data boundary.** Account snapshots may be used to apply the formula,
show observed pops and detect implementation errors, but never to fit its
coefficients. A previous draft attempted to infer combined coach/stamina terms
from this manager's observations. That inference is retired and its numerical
results must not be restored. Formula parameters require a general external
source with explicit provenance.

**Propiedades corregidas.** El nivel actual sí cambia el costo. El subnivel,
cuando se conoce, reduce el trabajo restante. Pases cortos y largos seleccionan
coeficientes diferentes según `TrainingType`. La resistencia reduce la parte
disponible para la habilidad técnica.

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

The training coefficients now come from the public HT-Tools implementation.
Private account history is not an admissible source for fitting or choosing
between parameter values. It may only contrast whether Lens applies that
external formula consistently. Age uses the published clock table, not the
retired linear `+6%` approximation.

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

## 9. La fórmula de entrenamiento: datos CHPP, coeficientes públicos

Cada valor particular del club se lee de su fuente real:

| Término | Ficha CHPP | Campo |
|---|---|---|
| Tipo | `training` | `TrainingType` |
| Intensidad | `training` | `TrainingLevel` |
| % condición | `training` | `StaminaTrainingPart` |
| Ayudantes | `stafflist` | suma de `StaffLevel` para `StaffType=1` |
| Entrenador | `stafflist` | `TrainerSkillLevel` (1–5) |

`TrainingContextService` adjunta la procedencia de cada entrada y la expone en
`GET /teams/{id}/training/formula`. El tipo selecciona además el coeficiente
correcto de HT-Tools; en particular, tipo 7 (Pases cortos) y tipo 10 (Pases
largos) ya no comparten un número genérico.

**Contraste sin inferencia.** `trainingevents` aporta pops confirmados. La
distancia entre dos pops permite mostrar semanas observadas frente a semanas
estimadas, pero no calibra, corrige ni reemplaza la fórmula pública.

**Límites restantes.** CHPP no publica el subnivel decimal y la tabla pública
de edad acaba en 34. Ambos límites aparecen en la interfaz; no se completan con
regresiones sobre la cuenta del manager.

**Implementación:** `app/domain/engines/training_engine.py`,
`app/application/queries/training_context.py` y `app/config/training.yaml`.
