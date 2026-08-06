# Qué se guarda histórico, y cómo — barrido de los 32 ficheros CHPP

Antes de construir hay que decidir, campo por campo, qué evoluciona en el tiempo
y qué no. No hay un solo patrón: hay **cuatro**, y mezclarlos es el error que
luego no se puede deshacer sin perder datos.

## Los cuatro patrones

1. **Identidad** — inmutable. Una fila para siempre. Ej.: `ht_player_id`, nombre,
   club madre, fecha de llegada. Nunca se versiona.
2. **Snapshot** (append-only + diffing por `content_hash`) — cosas que **derivan
   en el tiempo** y cuya evolución importa. Se escribe una fila **solo cuando
   algo cambia**. Es lo que alimenta todas las vistas "en el tiempo".
3. **Hecho / evento** (append-only, clave única, inmutable) — cosas que **pasan
   una vez** y no cambian: un partido, un gol, una subida de nivel, una venta.
   Se guardan con su fecha y no se tocan jamás.
4. **Estado actual** (se sobrescribe, sin histórico) — cosas volátiles cuyo
   pasado no aporta, o que el CHPP no deja versionar. Ej.: pujas activas, clima,
   próxima jornada, datos actuales de rivales.

> Regla CHPP transversal: de **jugadores de otros clubes** solo se guarda estado
> actual, nunca su histórico. Todo lo "histórico" de abajo es del propio club.

---

## Lo que SÍ necesita histórico (snapshots)

Estas son las "muchas cosas" que hay que versionar. Cada una es un snapshot con
`captured_at`, diffed por hash para no inflar la base.

### Jugador propio (`players` / `playerdetails`)
`player_snapshots` — una foto cuando cambie cualquiera de:
- **skills** (portería, defensa, jugadas, lateral, anotación, pases, balón parado)
- **resistencia**, **TSI**, **forma**, **experiencia** (nivel)
- **salario**
- **nivel de lesión** (y además el evento de lesión, ver hechos)
- **lealtad** (crece con el tiempo — histórico real)
- **bonus de club madre** (cambia si deja de ser su club madre)
- **especialidad** (normalmente fija; snapshot si se revela/cambia)
- **personalidad**: carácter, agresividad, honestidad (derivan despacio)
- **liderazgo**
- estado de listado en transferencias (o como evento de listado)

### Entrenamiento del equipo (`training`)
`training_snapshots` — **crítico para el plan**: hay que saber qué entrenaste
*en cada semana*, no solo hoy.
- **tipo de entrenamiento**, **intensidad**, **%condición**
- **moral**, **autoconfianza**
- **experiencia por formación** (442, 433, 550…) — crece con el uso
- entrenador y su fecha de llegada

### Staff del club (`club` + `stafflist`)
`staff_snapshots` — cambia poco pero cada cambio importa (curva del entrenador,
coste, efecto en forma/salud):
- **niveles de ayudantes**, entrenador de forma, médico, psicólogo, asistente
  táctico, director financiero, portavoz
- **nivel y tipo del entrenador principal**, liderazgo
- **inversión juvenil**, nivel de la academia

### Economía (`economy`)
`economy_snapshots` — la serie completa alimenta todo el módulo de economía:
- **caja**, ingresos (espectadores, patrocinios, financieros, temporales),
  costes (salarios, personal, estadio, juveniles, financieros)
- **tamaño del club de fans**, popularidad de patrocinadores y aficionados
- los `Last*` semanales

### Estadio (`arena_details`)
`arena_snapshots` — snapshot cuando cambie la **capacidad por sector**
(ampliaciones); además los eventos de ampliación (ver hechos). Región es fija.

### Afición (`fans`)
`fan_snapshots` — el **humor** y las **expectativas** (temporada/partido) derivan
partido a partido. La asistencia de cada partido es un **hecho** (ver abajo).

### Liga (`leaguedetails` / `leaguefixtures`)
`standings_snapshots` — la **clasificación por jornada** (para el bump chart y la
evolución de puntos). `leaguelevels` (plazas de ascenso/descenso) por temporada.

### Juveniles (`youthplayerdetails`)
`youth_snapshots` — skills juveniles **y sus techos**, que se van revelando
(`IsAvailable`, `MayUnlock`) — histórico del desarrollo.

---

## Lo que se guarda como HECHO (inmutable, con fecha)

No se versionan: ocurren una vez.

- **Partidos** (`matches` / `matchesarchive`): resultado, tipo, fecha. Inmutable
  al terminar.
- **Ratings por sector del partido** (`matchdetails`): mediocampo, defensas,
  ataques, balón parado indirecto, posesión, táctica, actitud, ocasiones por
  zona/SE. Un registro por (partido, equipo). De aquí sale la serie histórica.
- **Alineación y rendimiento** (`matchlineup`): rol, comportamiento,
  `RatingStars` por (jugador, partido).
- **Eventos de partido** (`matchdetails`): goles (con minuto y vía), tarjetas,
  lesiones, eventos especiales. Un registro por evento.
- **Subidas de nivel** (`trainingevents`): `SkillID`, viejo→nuevo, temporada,
  jornada. Único por (jugador, habilidad, nivel nuevo) — idempotente.
- **Transferencias** (`transfersteam`): compras/ventas con precio, TSI, fechas.
- **Hitos del jugador** (`playerevents`): con tipo, fecha, texto.
- **Logros del manager** (`achievements`): logro + fecha + puntos.
- **Ampliaciones de estadio** (`arena_details`: `RebuiltDate`, `ExpansionDate`).
- **Promociones/ventas de canteranos** (former youth).

---

## Lo que NO se guarda histórico (estado actual, se sobrescribe)

- **`worlddetails`**: temporada, jornada, fechas, tasa de moneda. Estado del
  mundo; se necesita para *fechar* lo demás, pero su pasado no se versiona.
- **`currentbids`**: pujas activas — volátiles, se reemplazan.
- **`transfersearch`**: escaneo de mercado — efímero, iniciado por el usuario,
  no se persiste.
- **`regiondetails`**: clima de hoy/mañana — efímero (se puede loguear solo para
  el modelo de asistencia, no como histórico del usuario).
- **Próxima jornada / calendario futuro**: se refresca; los partidos jugados
  pasan a ser hechos.
- **Datos actuales de rivales**: solo estado presente (regla CHPP).

---

## Cómo se implementa (mecanismo, no política)

- Cada entidad *snapshot* tiene `content_hash` = SHA-256 de sus campos canónicos.
  En cada sync se compara con el último; si es igual, **no se escribe fila**.
  Un test corre dos syncs idénticos y verifica que el segundo no escribe nada.
- Cada entidad *hecho* tiene una **clave única natural** (p.ej. jugador+habilidad+
  nivel para un pop; `ht_match_id` para un partido) → inserción idempotente.
- Escala: particionado por tiempo (temporada/mes) en PostgreSQL, índices
  `(entidad_id, captured_at)`. Las consultas de histórico piden rango de fechas.
- Todo lo temporal se **fecha con la temporada+jornada de `worlddetails`**, no
  con la fecha del reloj, para que coincida con el calendario de Hattrick.
