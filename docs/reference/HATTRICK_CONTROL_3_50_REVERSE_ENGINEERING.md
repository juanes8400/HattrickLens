# Referencia de implementación: Hattrick Control 3.50.02.1619

## Alcance y procedencia

Esta referencia procede de la extracción autorizada por el autor que entregó el usuario. El original se conserva sin modificar en `C:\Users\Juan Esteban\Desktop\IDR\DeDe.3.50.02.1619.bin\Dumps\HattrickControl`.

La extracción de DeDe conserva nombres de unidades, controles de formularios y desensamblado. No siempre recupera el cuerpo Delphi de las funciones auxiliares. Este documento separa lo recuperado directamente de lo que todavía debe reconstruirse: nada pendiente se presenta como fórmula oficial de Hattrick.

| Estado | Significado |
| --- | --- |
| `portado` | El flujo o cálculo se lee directamente de una rutina recuperada. |
| `estructural` | Están recuperados formulario, entradas, salidas y flujo; falta una rutina auxiliar o datos de perfil. |
| `pendiente` | Hay una referencia útil, pero aún no alcanza para reproducir un resultado numérico. |

## Mapa de pantallas recuperado

| Módulo de Hattrick Control | Pantallas/funciones que confirma | Estado en Lens |
| --- | --- | --- |
| `UEquipo` | Jugadores, detalles, posiciones, histórico, cambios y alineación; incluye `CambiosJugadores`, `CompletarCambios`, `HallarFormulas`. | Base estructural de Equipo; Cambios y Posiciones ya existen. |
| `UEntrenamiento` | Entrenamiento actual, histórico, entrenos, mejoras, previsión, beneficios, compras y ventas. | Entrenamiento actual y previsión en curso; las demás vistas quedan en el mapa. |
| `UExperiencia` | Tabla por jugador, suma de partidos, porcentaje a la próxima subida e histórico. | Cálculo de puntos y calibración histórica. |
| `UPartidos` | Partido, eventos, tácticas y resúmenes. | Base para el módulo de partidos. |
| `ULiga` | Serie y análisis de clasificación. | Base para Liga. |
| `UCalculoTemporada` | Cálculo de temporada. | Referencia para simulación futura. |

## Experiencia — `portado`

La rutina `TFExperiencia.Suma` suma, por jugador, los contadores de partidos ponderados. `TFExperiencia.Porcentaje` calcula `puntos × 100 / puntos_por_nivel`. Los controles muestran que Hattrick Control lo trataba como un **perfil editable**: amistosos, amistosos internacionales, liga, clasificación, copa y el umbral de subida tienen controles independientes.

Lens conserva ese modelo: el perfil inicial está visible en `backend/app/config/experience.yaml` y se sustituye por evidencia de intervalos CHPP completos, nunca por un pop aislado.

Fuentes: `UExperiencia.pas` (`Suma`, `Porcentaje`, `CompletarSubidas`) y `UExperiencia.dfm`.

## Entrenamiento — `estructural`

Hattrick Control no usaba una única constante opaca. `UOptions` contiene un control de semanas por tipo para Resistencia, Balón parado, Defensa, Anotación, Lateral, Jugadas, Portería y Pases. `UEntrenamiento` combina el valor elegido con nivel del entrenador, ayudantes, intensidad, porcentaje de condición, edad y los decrementos editables del perfil.

`TFOptions.BitBtnRestaurarEntrClick` intenta restaurar esos valores desde `data\Defaults.dat`; ese archivo no forma parte de la extracción entregada. La llamada auxiliar que combina los factores tampoco quedó con nombre ni código Delphi recuperable. Por tanto:

- La selección de habilidad y la estructura del perfil son referencias directas de Hattrick Control.
- Los coeficientes numéricos heredados de Lens son un perfil de compatibilidad transitorio, no una «fórmula canónica» confirmada por esta extracción.
- Cada previsión debe conservar su procedencia y validarse contra intervalos CHPP completos antes de elevar su confianza.

Fuentes: `UEntrenamiento.pas` (`CalculoPorcentajeEntrenoTabla`, `EntrenamientoSemana`, `SubidasEntrenoJugadores`), `UEntrenamiento.dfm`, `UOptions.pas` (`SemanasEntrenoTrackBar`, `BitBtnRestaurarEntrClick`) y `UOptions.dfm`.

## Posiciones — `estructural`

`TFEquipo.HallarFormulas` alimenta una calculadora con forma, experiencia, condición, fidelidad/origen, balón parado, defensa, pases, portería, anotación, lateral y jugadas. Devuelve los roles que vemos en el programa: portero; cuatro defensas centrales; cuatro laterales; cuatro medios; cuatro extremos; tres delanteros, además de posición ideal.

La matriz numérica vive en una rutina auxiliar sin nombre recuperable en el dump. Mientras se reconstruye, Lens conserva la matriz numérica del Manual no Escrito —con etiqueta explícita de índice de aportes, no estrellas oficiales— y adopta de Hattrick Control la taxonomía de roles, las entradas y la pantalla.

Fuentes: `UEquipo.pas` (`HallarFormulas`, `OrdenarPorPosicion`) y `UEquipo.dfm`.

## Regla de integración

1. Una rutina recuperada sustituye una suposición previa cuando reproduce su resultado con datos reales.
2. Un control o formulario recuperado define la funcionalidad y explicación de interfaz, aunque su fórmula auxiliar todavía esté pendiente.
3. Los parámetros sin valor recuperable quedan configurables, con etiqueta de perfil y evidencia; no se esconden como constantes del juego.
4. Los XML y CHPP son la fuente de los datos del equipo; Hattrick Control es la referencia de cálculo e interacción, no una fuente de datos.
