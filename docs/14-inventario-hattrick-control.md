# 14 — Inventario de Hattrick Control

Catálogo de las pantallas de Hattrick Control analizadas durante el descubrimiento
(julio 2026, versión en español, cuenta juanes840 / Pulgas Arrechas 537758).

**Veredicto** para cada pantalla:
- **Imitar** — la función es correcta y la replicamos con UX moderna.
- **Superar** — la función existe pero se queda corta; tenemos una versión claramente mejor.
- **Automatizar** — HC obliga a trabajo manual que hoy la API resuelve sola.
- **Descartar** — no aporta o choca con las reglas CHPP.

---

## Ventana Equipo

| # | Pantalla | Qué hace | Fuente CHPP | Veredicto | Historias |
|---|---|---|---|---|---|
| 1 | Jugadores | Tabla maestra: skills, TSI, salario, precio compra, mejor posición calculada, carácter/agresividad/honestidad/liderazgo, goles | `players` + `playerdetails` | Imitar | HL-010, HL-013, HL-021 |
| 2 | Detalles | Grupos A/B/C/D manuales + ficha individual + % de entrenamiento por skill | local + `playerdetails` | Superar | HL-011, HL-012 |
| 3 | Posiciones | Ranking de la plantilla para cada slot, con órdenes individuales (ofensivo, defensivo, hacia dentro) | calculado | Imitar | HL-020, HL-022 |
| 4 | Histórico | Fotos de plantilla por fecha con agregados (edad media, TSI total, salario total) | snapshots locales | Superar | HL-004, HL-016 |
| 5 | Cambios · Histórico | Subidas de skill, forma y experiencia entre capturas | diffs | Superar | HL-005, HL-033 |
| 6 | Cambios · Condición | Tabla de entrenamiento de resistencia + curva con bandas de referencia por edad | diffs | Imitar | HL-039 |
| 7 | Cambios · TSI | Log diario de TSI, forma y condición con deltas | diffs | Imitar | HL-017 |
| 8 | Cambios · Último entrenamiento | Resumen de subidas y bajadas de la última semana | diffs | Imitar | HL-033 |
| 9 | Lesiones | Lesionados actuales + histórico con doctor y fisio | diffs | Imitar | HL-018 |
| 10 | Club · Aficionados | Socios, expectativas de la temporada, ánimo tras cada partido, público y clima | `economy`, `arenadetails` | Imitar | HL-062, HL-131 |
| 11 | Club · Gráfico | Espíritu, confianza, aficionados y patrocinadores en el tiempo | `training`, `economy` | Imitar | HL-052 |
| 12 | Club · Empleados | Conteo de staff por tipo a lo largo del tiempo | `staff` | Imitar | HL-019 |
| 13 | Compras | Historial de compras con precio, TSI y skills al comprar | `transfersteam` | Imitar | HL-100 |
| 14 | Ventas | Ventas con precio de compra, de venta y beneficio | `transfersteam` | Superar | HL-100, HL-036 |
| 15 | Rendimiento | Ratings del jugador partido a partido, media por posición, mejor y peor, comparación de dos jugadores | `matchlineup` | Imitar | HL-076 |
| 16 | Próximo partido | Alineación enviada, táctica, actitud, experiencia por formación | `matchorders` | Imitar | HL-120 |
| 17 | Alineación | Constructor de alineación con guardado + tabla clima × especialidad | local | Superar | HL-121, HL-123 |

## Ventana Partidos

| # | Pantalla | Qué hace | Fuente CHPP | Veredicto | Historias |
|---|---|---|---|---|---|
| 18 | Alineación | Alineaciones de ambos equipos con estrellas por jugador y experiencia de formación | `matchlineup` | Imitar | HL-071 |
| 19 | Calificaciones | Ratings por sector con delta vs rival, posesión por mitad, HatStats / GardierStats / PeasoStats / LoddarStats | `matchdetails` | Imitar | HL-071, HL-074 |
| 20 | Reporte | Crónica narrativa del partido | `matchdetails` | Imitar | HL-071 |
| 21 | Eventos | Ocasiones clasificadas: normal, evento especial y contraataque, desglosadas por tipo | `matchdetails` | Imitar | HL-072 |
| 22 | Resumen | Todos los partidos por competición con táctica, HatStats y sectores | `matches` | Imitar | HL-075 |
| 23 | Gráfico | Serie histórica de ratings con selección de series y opción "evitar walkovers" | derivado | Imitar | HL-075 |
| 24 | Estadísticas | Local/visitante, ganados/empatados/perdidos, mejores registros históricos | derivado | Imitar | HL-077 |
| 25 | Posiciones | Rendimiento por formación y táctica; uso y nota media de cada jugador por rol | `matchlineup` | Imitar | HL-076 |
| 26 | Resumen Eventos | Ocasiones y goles a favor y en contra con tasas de conversión por tipo | derivado | **Superar** | HL-073 |
| 27 | Liga | Tabla de cualquier equipo con jornada anterior y siguiente | `leaguedetails` | Imitar | HL-080 |

## Ventana Liga

| # | Pantalla | Qué hace | Fuente CHPP | Veredicto | Historias |
|---|---|---|---|---|---|
| 28 | Liga · Total/Local/Visitante | Clasificación con desglose y calendario completo de 14 jornadas | `leaguedetails`, `leaguefixtures` | Imitar | HL-080 |
| 29 | Liga · Previsión | Intento de pronóstico de la tabla final | heurística propia | **Superar** | HL-090, HL-091 |
| 30 | Liga · Gráfico | Evolución de puesto y puntos por equipo | derivado | Imitar | HL-084 |
| 31 | Rivales · Datos generales | Ficha pública del rival: usuario, si es bot, victorias, racha invicta, estadio, región | `teamdetails` | Imitar | HL-082 |
| 32 | Rivales · Jugadores | Plantilla del rival con skills y agregados | `players` con teamID ajeno | **Restringir** | HL-082 |
| 33 | Rivales · Resumen | Comparativa de los 8 equipos: TSI, salario, forma, experiencia, edad, lesionados | agregado | Imitar | HL-083 |
| 34 | Mejor equipo | Mejor once por formación, de la semana y de la temporada | calculado | **Superar** | HL-121 |

## Ventana Canteranos (jugadores promocionados)

| # | Pantalla | Qué hace | Fuente CHPP | Veredicto | Historias |
|---|---|---|---|---|---|
| 35 | Jugadores | Fichas con categoría manual (fontanero → crack) y **calculadora de 19 posiciones** con entrada manual de skills | manual | **Automatizar** | HL-023, HL-111 |
| 36 | Estadísticas | Inversión histórica en cantera vs ingresos por categoría | `economy` | **Superar** | HL-114 |
| 37 | ExJugadores | Todos los que pasaron por el club: dónde están hoy, TSI y goles actuales | `playerdetails` | **Superar** | HL-107 |

## Ventana Juveniles (academia actual)

| # | Pantalla | Qué hace | Fuente CHPP | Veredicto | Historias |
|---|---|---|---|---|---|
| 38 | Jugadores · Límite | Juveniles con fecha de promoción y días restantes | `youthplayerlist` | **Superar** | HL-112 |
| 39 | Ojeadores | Configuración de los tres ojeadores | `youthteamdetails` | Imitar | HL-113 |
| 40 | Entrenamiento juvenil | Pesos corregidos: principal 1,0 / secundario distinto ⅔ / secundario repetido ⅓; posición 1,0 / 0,5; liga 1,0 / amistoso 0,5 | `youthmatches` | **Superar** | HL-115 |

## Ventana Entrenamiento

| # | Pantalla | Qué hace | Fuente CHPP | Veredicto | Historias |
|---|---|---|---|---|---|
| 41 | Entrenamiento actual | Semanas al próximo nivel por jugador, config actual, entrenador y asistentes | `training` + calculado | Imitar | HL-030, HL-031 |
| 42 | Semanas | Minutos jugados en la posición entrenable por semana | `matchlineup` | Imitar | HL-032 |
| 43 | Mejoras | Registro de subidas detectadas con semana y edad | diffs | Imitar | HL-033 |
| 44 | Previsión subidas | **Vacía en HC** — la pestaña existe pero no proyecta | — | **Superar** | HL-034 |
| 45 | Resultados por skill | Beneficio medio por nivel entrenado, medido en ventas reales | `transfersteam` | **Superar** | HL-036 |

## Ventana Experiencia

| # | Pantalla | Qué hace | Fuente CHPP | Veredicto | Historias |
|---|---|---|---|---|---|
| 46 | Experiencia | Partidos por tipo, suma ponderada y % hacia el próximo nivel | `players` + `matchlineup` | Imitar | HL-040, HL-041 |

## Ventana Economía

| # | Pantalla | Qué hace | Fuente CHPP | Veredicto | Historias |
|---|---|---|---|---|---|
| 47 | Datos generales | Semana actual y anterior con ingresos y gastos desglosados | `economy` | Imitar | HL-050, HL-056 |
| 48 | Gráfico | Series de ingresos, gastos, beneficio y caja | derivado | Imitar | HL-052 |
| 49 | Detalles + Balance | Balance a 1/2/4/8/16/32 semanas y **balance sin transferencias** | derivado | **Superar** | HL-051, HL-053 |

## Ventana Estadio

| # | Pantalla | Qué hace | Fuente CHPP | Veredicto | Historias |
|---|---|---|---|---|---|
| 50 | Estadio | Capacidad por sector, coste semanal, ingresos a estadio lleno, ocupación por partido y por clima | `arenadetails`, `matchdetails` | **Superar** | HL-060 a HL-064 |

## Ventana Transferencias

| # | Pantalla | Qué hace | Fuente CHPP | Veredicto | Historias |
|---|---|---|---|---|---|
| 51 | Lista de seguimiento | Jugadores vigilados con límite de puja y fecha de cierre | manual | Imitar | HL-102, HL-103 |
| 52 | Visual Helps | Reglas de color por skill y rango | local | **Superar** | HL-104 |
| 53 | Decode data | Pegar el texto del mercado desde el navegador para parsearlo | manual | **Automatizar** | HL-105 |

---

## Conclusiones del descubrimiento

**Lo que hace grande a Hattrick Control.** El rating por posición, que aparece en seis
pantallas distintas y convierte datos en decisiones. El histórico longitudinal, que
ninguna web de Hattrick ofrece. Y el desglose de eventos de partido con tasas de
conversión, que es análisis táctico de verdad.

**Sus tres debilidades estructurales.** Todo son tablas sin síntesis: cuarenta columnas
y tú deduces. Nada es predictivo: hay pasado y presente, nunca futuro — la pestaña
"Previsión subidas" está literalmente vacía. Y captura datos solo cuando abres el
programa, por eso los históricos de un usuario real están casi vacíos.

**Lo que sale gratis y no debemos desaprovechar.** Coeficientes ya calibrados por la
comunidad que HC expone sin querer (ver `docs/16`), y un mapa completo de qué le
importa a un manager competitivo, validado por veinte años de uso.
