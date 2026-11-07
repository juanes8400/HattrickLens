"""¿Siguen siendo los mismos ocho equipos? Se comprueba en cada sincronización.

2026-11-07, pedido del usuario: «crea un mecanismo continuo de verificación
para verificar la composición de la liga».

QUÉ HABÍA. Una pieza sola, `trasladar_equipo_reemplazado`, que arregla UN caso
concreto y muy real --el 2026-09-13 etbenianos1 fue reemplazado por Kivaré con
otro id justo después de la jornada 8, y el calendario guardado se quedó con el
equipo viejo en las jornadas 9 a 14, así que ninguna pantalla encontraba al
rival--. Pero se rinde en silencio en cuanto el caso no es exactamente uno por
uno:

    if len(viejos) != 1 or len(nuevos) != 1:
        return 0

Dos reemplazos la misma semana, un cambio de nombre sin cambio de id, una foto
que llega con siete equipos en vez de ocho, o el salto de temporada entero: en
todos ésos el arreglo no se aplica y nadie se enteraba. El calendario se queda
apuntando a quien ya no está y lo único que se ve en pantalla es un rival que
no aparece.

QUÉ HACE ESTO. Compara la composición que Hattrick acaba de mandar con la que
teníamos guardada y devuelve un veredicto: cuántos llegaron, quién entró, quién
salió, a quién le cambió el nombre, y si lo que pasó es un reemplazo limpio de
uno por uno --el único que se puede arreglar solo-- o algo que hay que decir.

NO ARREGLA NADA. Es a propósito: aquí sólo se mira. Quien llame decide si
traslada partidos, si lo anota en Cambios o si lo guarda en el registro, y así
este módulo se puede probar entero sin base de datos.

LAS PLAZAS NO SE DAN POR OCHO SIN MÁS. Son ocho en todas las series de liga de
Hattrick, pero la comprobación recibe el número: una foto incompleta --un
fichero a medias, una llamada cortada-- tiene que poder distinguirse de una
liga que de verdad cambió, y para eso hace falta saber contra qué se compara.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.domain.engines.sync_diff import Change

#: Cuántos equipos tiene una serie de liga en Hattrick. Es el valor por
#: defecto y no una constante escondida: quien compruebe puede pasar otro.
PLAZAS_DE_UNA_SERIE = 8


@dataclass(frozen=True, slots=True)
class Equipo:
    """Un equipo de la serie, por su id de Hattrick y su nombre de hoy."""

    ht_team_id: int
    nombre: str


@dataclass(frozen=True, slots=True)
class Renombrado:
    """El mismo equipo, con otro nombre. ES OTRA COSA QUE UN REEMPLAZO.

    Un manager puede cambiar el nombre de su club cuando quiera, y el id no se
    mueve. Confundir las dos cosas tiene coste en las dos direcciones: tratar
    un renombrado como un reemplazo trasladaría sus partidos a sí mismo y
    anunciaría un equipo nuevo que no existe, y tratar un reemplazo como un
    renombrado dejaría el calendario apuntando a un id muerto.
    """

    ht_team_id: int
    antes: str
    ahora: str


@dataclass(frozen=True, slots=True)
class Veredicto:
    """Lo que se encontró al comparar las dos composiciones."""

    #: Cuántas plazas debería tener la serie, y cuántas llegaron de verdad.
    plazas: int
    llegaron: int
    #: Los que están ahora y no estaban.
    entraron: tuple[Equipo, ...]
    #: Los que estaban y ya no están.
    salieron: tuple[Equipo, ...]
    #: Mismo id, otro nombre.
    renombrados: tuple[Renombrado, ...]
    #: `(viejo, nuevo)` sólo cuando salió exactamente uno y entró exactamente
    #: uno. Es el único caso que se puede arreglar sin preguntar a nadie, y es
    #: el que `trasladar_equipo_reemplazado` ya sabe hacer.
    reemplazo_limpio: tuple[Equipo, Equipo] | None

    @property
    def foto_incompleta(self) -> bool:
        """Llegaron menos equipos de los que tiene la serie.

        NO ES UN CAMBIO DE LIGA: es una foto a medias. Pasa con un fichero
        cortado o una llamada que falló, y lo importante es no confundirlo con
        «se fueron cuatro equipos», que es lo que parecería mirando sólo
        `salieron`. Quien arregle tiene que negarse a tocar nada en este caso.
        """
        return 0 < self.llegaron < self.plazas

    @property
    def sin_nada_guardado(self) -> bool:
        """No había composición anterior con la que comparar.

        Es la primera vez, o es una serie nueva --un ascenso, un descenso, el
        salto de temporada--. Todos los equipos salen como «entraron», y eso no
        es un hallazgo: es que no hay nada que verificar todavía.
        """
        return self.llegaron > 0 and len(self.entraron) == self.llegaron and not self.salieron

    @property
    def cuadra(self) -> bool:
        """Si la composición es la misma de antes, nombres incluidos.

        Es el caso normal y el que no se enseña: un panel que dice «todo bien»
        en cada sincronización enseña a saltárselo.
        """
        return (
            self.llegaron == self.plazas
            and not self.entraron
            and not self.salieron
            and not self.renombrados
        )

    @property
    def hay_que_decirlo(self) -> bool:
        """Si el usuario tiene que saber de esto.

        Todo lo que no cuadra, con dos excepciones que no son hallazgos:

        · La primera foto de una serie. No había con qué comparar.
        · Que no llegara NINGUN equipo. Eso no es una liga vacía: es que no hay
          liga sincronizada todavía, o que la llamada no trajo nada. Decir
          «salieron los ocho» ahí sería anunciar un desastre inexistente.
        """
        if self.cuadra or self.llegaron == 0:
            return False
        return not self.sin_nada_guardado

    @property
    def se_arregla_solo(self) -> bool:
        """Si el traslado automático de partidos puede con esto.

        Sólo el reemplazo limpio de uno por uno, y sólo con la foto completa:
        con siete equipos de ocho, el «uno que falta» puede ser el que no llegó
        y no el que se fue, y trasladar partidos a ciegas los mandaría al sitio
        equivocado.
        """
        return self.reemplazo_limpio is not None and not self.foto_incompleta


def verificar(
    guardados: Iterable[Equipo],
    llegados: Iterable[Equipo],
    plazas: int = PLAZAS_DE_UNA_SERIE,
) -> Veredicto:
    """Compara la composición guardada con la que acaba de llegar.

    `guardados` vacío significa «no había nada», no «se fueron todos»: lo dice
    `sin_nada_guardado` y es lo que distingue una serie nueva de una vaciada.

    POR ID Y NO POR NOMBRE. El id es lo único estable: un manager renombra su
    club cuando quiere, y dos clubes distintos pueden llamarse casi igual.
    Comparar por nombre daría reemplazos inventados cada vez que alguien le
    pone un sufijo a su equipo.
    """
    antes = {e.ht_team_id: e for e in guardados if e.ht_team_id}
    ahora = {e.ht_team_id: e for e in llegados if e.ht_team_id}

    entraron = tuple(ahora[i] for i in sorted(set(ahora) - set(antes)))
    salieron = tuple(antes[i] for i in sorted(set(antes) - set(ahora)))
    renombrados = tuple(
        Renombrado(ht_team_id=i, antes=antes[i].nombre, ahora=ahora[i].nombre)
        for i in sorted(set(antes) & set(ahora))
        # Un nombre VACÍO no es un renombrado: es que no lo sabíamos. Pasa en
        # las filas viejas y en una foto que llegó sin nombres, y anunciarlo
        # como «se cambió el nombre» sería inventar un cambio.
        if antes[i].nombre and ahora[i].nombre and antes[i].nombre != ahora[i].nombre
    )

    # El reemplazo limpio: uno se fue, uno llegó. No se exige que la foto esté
    # completa aquí --eso lo decide `se_arregla_solo`-- para que quien mire
    # pueda ver la pareja aunque no se pueda tocar nada todavía.
    limpio = (salieron[0], entraron[0]) if len(salieron) == 1 and len(entraron) == 1 else None

    return Veredicto(
        plazas=plazas,
        llegaron=len(ahora),
        entraron=entraron,
        salieron=salieron,
        renombrados=renombrados,
        reemplazo_limpio=limpio,
    )


#: A partir de cuántos equipos movidos se resume en vez de enumerar.
#:
#: Tres. Con uno o dos se dice quién --«etbenianos1 fue reemplazado por
#: Kivaré»-- porque es lo que el usuario necesita para ir a mirar. Con media
#: liga cambiada, dieciséis líneas no informan más que una: lo que ha pasado es
#: que la serie guardada y la que llega no son la misma, y eso se dice de una
#: vez.
DEMASIADOS_PARA_ENUMERAR = 3


def cambios_de(veredicto: Veredicto) -> tuple[Change, ...]:
    """El veredicto como filas de Cambios, o vacío si no hay nada que decir.

    POR QUÉ EN CAMBIOS Y NO EN UNA PANTALLA NUEVA. El usuario pidió «un
    mecanismo continuo de verificación», y lo continuo ya existe: cada
    sincronización deja sus hallazgos en `sync_changes`, que se guardan, se
    navegan por fecha y se enseñan en el informe. Inventar una tabla, un
    endpoint y un panel para esto sería construir un segundo registro al lado
    del que ya funciona.

    `category="liga"` las pone con el resto de lo de la liga. No entran en
    `MEANINGFUL_CATEGORIES`, así que un reemplazo de equipo no hace que una
    sincronización cuente como «tuvo cambios» para el navegador de informes:
    eso es para lo que le pasó a TU club, y esto le pasó a la serie.
    """
    if not veredicto.hay_que_decirlo:
        return ()

    filas: list[Change] = []

    # La foto a medias va PRIMERA y aparte: mientras no esté completa, todo lo
    # demás que se lea de ella puede ser un artefacto de la llamada y no un
    # cambio. Decirlo antes evita que el usuario salga a buscar a un equipo que
    # no se ha ido.
    if veredicto.foto_incompleta:
        filas.append(
            Change(
                category="liga",
                metric="composicion",
                label="Composición de la liga",
                kind="event",
                good=False,
                summary=(
                    f"La clasificación llegó con {veredicto.llegaron} equipos "
                    f"de {veredicto.plazas}: no se ha dado por cambiada la liga"
                ),
            )
        )
        return tuple(filas)

    if veredicto.reemplazo_limpio is not None:
        viejo, nuevo = veredicto.reemplazo_limpio
        filas.append(
            Change(
                category="liga",
                metric="composicion",
                label="Composición de la liga",
                subject=nuevo.nombre,
                kind="event",
                good=None,
                summary=f"{viejo.nombre} fue reemplazado por {nuevo.nombre} en la liga",
            )
        )
    elif (
        len(veredicto.entraron) >= DEMASIADOS_PARA_ENUMERAR
        or len(veredicto.salieron) >= DEMASIADOS_PARA_ENUMERAR
    ):
        filas.append(
            Change(
                category="liga",
                metric="composicion",
                label="Composición de la liga",
                kind="event",
                good=None,
                summary=(
                    f"La liga cambió de equipos: entraron {len(veredicto.entraron)} "
                    f"y se fueron {len(veredicto.salieron)}"
                ),
            )
        )
    else:
        for e in veredicto.entraron:
            filas.append(
                Change(
                    category="liga",
                    metric="composicion",
                    label="Composición de la liga",
                    subject=e.nombre,
                    kind="event",
                    good=None,
                    summary=f"{e.nombre} entró en la liga",
                )
            )
        for e in veredicto.salieron:
            filas.append(
                Change(
                    category="liga",
                    metric="composicion",
                    label="Composición de la liga",
                    subject=e.nombre,
                    kind="event",
                    good=None,
                    summary=f"{e.nombre} ya no está en la liga",
                )
            )

    # Los renombrados van siempre, y aparte de todo lo anterior: un club que se
    # cambia el nombre no entra ni sale, y el usuario lo va a ver distinto en su
    # clasificación sin que nada se lo haya dicho.
    for r in veredicto.renombrados:
        filas.append(
            Change(
                category="liga",
                metric="composicion",
                label="Composición de la liga",
                subject=r.ahora,
                kind="event",
                good=None,
                summary=f"{r.antes} ahora se llama {r.ahora}",
            )
        )
    return tuple(filas)


def sin_repetir(cambios: Iterable[Change], ya_dichos: Iterable[str]) -> tuple[Change, ...]:
    """Los hallazgos que no se han dicho ya.

    HACE FALTA, Y NO ES UN LUJO. La composición se compara contra la ÚLTIMA
    JORNADA GUARDADA, y una jornada se guarda una sola vez. Si el reemplazo
    ocurre DESPUÉS de que esa jornada se guardara --que es lo normal, porque un
    equipo se abandona cuando se abandona-- la foto guardada no se actualiza
    hasta la jornada siguiente. Sin esto, el mismo aviso saldría en cada
    sincronización durante días, y un aviso que se repite deja de leerse.

    `trasladar_equipo_reemplazado` no tiene este problema porque se cura solo:
    cambia los partidos, y a la segunda ya no encuentra nada que cambiar. Esto
    sólo mira, así que la memoria tiene que estar en alguna parte, y el sitio
    honesto es lo que ya se dijo.

    Se compara por la FRASE entera. Dos reemplazos distintos dan frases
    distintas, así que el segundo sí se cuenta; el mismo reemplazo da la misma
    frase y se calla. Y un renombrado de vuelta --«ahora se llama X» después de
    «ahora se llama Y»-- también es otra frase, que es lo correcto: volvió a
    cambiar.
    """
    dichos = set(ya_dichos)
    return tuple(c for c in cambios if c.summary not in dichos)
