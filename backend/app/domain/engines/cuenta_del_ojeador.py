"""Lo que cuesta cada ojeador y lo que ha traído.

2026-08-26, pedido por el usuario. La idea es simple y la aritmética también;
lo que tiene miga son las tres decisiones de abajo, que son suyas y quedan
escritas aquí para que se puedan discutir sin leer código.

**Cuesta 5.000 por semana desde que se le contrató.** Si se le despidió, hasta
el día en que dejó de aparecer en la lista: Hattrick no dice cuándo se va un
ojeador, así que ese día es el último en que se le vio y el error queda acotado
a lo que se tarde entre dos sincronizaciones.

**Se le abona la venta MENOS la comisión, más las reventas futuras.** Dicho
así por el usuario: lo que de verdad entró por ese canterano, no el precio del
escaparate.

**Los canteranos que no trajo ningún ojeador quedan fuera.** En esta cuenta son
los catorce de la hornada fundacional, que llegaron solos al abrir la academia.
Es una situación irrepetible, así que no se les hace una fila aparte.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

#: Lo que Hattrick cobra por tener un ojeador, cada semana.
COSTE_SEMANAL = 5_000

_UNA_SEMANA = timedelta(days=7)


@dataclass(frozen=True)
class Ojeador:
    ht_scout_id: int
    nombre: str
    contratado: datetime | None
    #: Día en que dejó de aparecer. `None` = sigue contratado.
    se_fue: datetime | None = None
    region: str | None = None


@dataclass(frozen=True)
class Descubrimiento:
    """Un canterano y lo que dejó. Sólo los que ya salieron dejan dinero."""

    nombre: str
    #: Lo que entró por venderlo, ya sin la comisión del agente.
    venta_neta: int = 0
    #: Comisiones cobradas por reventas suyas posteriores.
    reventas: int = 0
    #: Sigue en la academia o en el primer equipo: aún no ha dejado nada.
    sigue_en_el_club: bool = True
    #: Cuándo lo trajo. Sirve para saber cuánto lleva un ojeador sin traer
    #: nada, que al principio es la única señal que hay: sin ventas todavía,
    #: un ojeador que lleva semanas cobrando y sin fichar es la información.
    llegada: datetime | None = None
    #: En qué se puede convertir, si el ojeador ya reveló algo. `None` = aún
    #: no se sabe, que NO es lo mismo que malo.
    techo: int | None = None


@dataclass
class CuentaDeUnOjeador:
    ojeador: Ojeador
    descubrimientos: list[Descubrimiento] = field(default_factory=list)
    semanas: int = 0

    @property
    def coste(self) -> int:
        return self.semanas * COSTE_SEMANAL

    @property
    def ingresos(self) -> int:
        return sum(d.venta_neta + d.reventas for d in self.descubrimientos)

    @property
    def saldo(self) -> int:
        return self.ingresos - self.coste

    @property
    def traidos(self) -> int:
        return len(self.descubrimientos)

    @property
    def vendidos(self) -> int:
        return sum(1 for d in self.descubrimientos if not d.sigue_en_el_club)

    @property
    def sigue_contratado(self) -> bool:
        return self.ojeador.se_fue is None

    @property
    def coste_por_canterano(self) -> int | None:
        """Lo que ha costado cada uno de los que trajo.

        `None` si no ha traído ninguno: dividir entre cero no es infinito, es
        que la pregunta no aplica todavía.
        """
        return round(self.coste / self.traidos) if self.traidos else None

    def dias_sin_traer(self, ahora: datetime) -> int | None:
        """Desde su último fichaje, o desde que se le contrató si no trajo nada.

        Es la señal que sirve DESDE EL PRIMER DIA: sin ventas todavía, lo único
        que distingue a un ojeador de otro es a cuántos trae y cada cuánto.
        """
        fechas = [d.llegada for d in self.descubrimientos if d.llegada is not None]
        ultima = max(fechas) if fechas else self.ojeador.contratado
        if ultima is None:
            return None
        return max(0, (ahora - ultima).days)


def semanas_cobradas(ojeador: Ojeador, ahora: datetime) -> int:
    """Semanas COMPLETAS que ha estado, que son las que se cobran.

    Se cuentan enteras a propósito: media semana no se paga, y redondear hacia
    arriba le cargaría a un ojeador recién contratado un coste que aún no ha
    tenido. Un ojeador de tres días cuesta cero, y eso es cierto.
    """
    if ojeador.contratado is None:
        return 0
    hasta = ojeador.se_fue or ahora
    if hasta <= ojeador.contratado:
        return 0
    return int((hasta - ojeador.contratado) / _UNA_SEMANA)


def cuenta(
    ojeadores: list[Ojeador],
    descubrimientos: dict[int, list[Descubrimiento]],
    ahora: datetime,
) -> list[CuentaDeUnOjeador]:
    """Una fila por ojeador, del que más saldo deja al que menos.

    `descubrimientos` va por `ht_scout_id`. Un ojeador sin canteranos sale
    igual, con su coste y sin ingresos: es la información más útil que puede
    dar la tabla —que lleva semanas cobrando y no ha traído nada—.
    """
    filas = [
        CuentaDeUnOjeador(
            ojeador=o,
            descubrimientos=list(descubrimientos.get(o.ht_scout_id, [])),
            semanas=semanas_cobradas(o, ahora),
        )
        for o in ojeadores
    ]
    return sorted(filas, key=lambda f: (-f.saldo, f.ojeador.nombre))


@dataclass(frozen=True)
class Totales:
    coste: int
    ingresos: int
    saldo: int
    ojeadores: int
    traidos: int


def totales(filas: list[CuentaDeUnOjeador]) -> Totales:
    return Totales(
        coste=sum(f.coste for f in filas),
        ingresos=sum(f.ingresos for f in filas),
        saldo=sum(f.saldo for f in filas),
        ojeadores=len(filas),
        traidos=sum(f.traidos for f in filas),
    )
