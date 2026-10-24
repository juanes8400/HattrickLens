"""Cuanta gente distinta hay en el tiempo.

2026-10-23, pedido del usuario: «numero de usuarios en el tiempo (personas
activas vs tiempo)». Hasta hoy la pantalla contestaba cuanto se usa y quien,
pero nada contestaba si eso CRECE.

Estas pruebas no vigilan el dibujo. Vigilan las tres formas en que una serie
de personas activas puede dar un numero creible y falso:

- SUMAR GENTE. Quien entra lunes y martes son dos renglones diarios y UNA
  persona en la semana. Agrupar sumando los dias infla el numero, y lo infla
  mas cuanto mas fiel es el usuario, que es justo a quien se quiere ver.
- SALTARSE LOS HUECOS. Un fin de semana sin nadie no es un tramo que no exista.
  Sin rellenar, tres dias sueltos de un mes se pintan pegados y el grafico no
  queda incompleto: queda mintiendo.
- ESTRENAR A TODO EL MUNDO. Si «primera vez» se calcula sobre los eventos ya
  filtrados, acortar el plazo estrena de golpe a los de siempre y la serie dice
  que la aplicacion acaba de nacer.
"""

from datetime import datetime, timedelta

from app.domain.engines.uso_de_la_app import GRANOS, Evento, en_el_tiempo

#: Un lunes, para que las semanas empiecen donde se ve.
LUNES = datetime(2026, 10, 5, 10, 0, 0)


def _ev(usuario: int, dia: int, tipo: str = "page", visible_ms: int = 0) -> Evento:
    return Evento(
        sesion=f"s{usuario}-{dia}",
        tipo=tipo,
        modulo="Liga",
        etiqueta=None,
        cuando=LUNES + timedelta(days=dia),
        visible_ms=visible_ms,
        usuario=usuario,
        nombre=f"u{usuario}",
    )


# ── La gente no se suma ──────────────────────────────────────────────────────


def test_una_persona_todos_los_dias_sigue_siendo_una_en_la_semana() -> None:
    """El fallo que justifica calcular el grano en el servidor.

    Cinco dias seguidos de la MISMA persona: la serie diaria da cinco unos y la
    semanal tiene que dar UNO, no cinco. Si algun dia da cinco, alguien agrego
    sumando.
    """
    eventos = [_ev(1, d) for d in range(5)]

    diaria = en_el_tiempo(eventos, "day")
    assert [t.usuarios for t in diaria] == [1, 1, 1, 1, 1]

    semanal = en_el_tiempo(eventos, "week")
    assert len(semanal) == 1
    assert semanal[0].usuarios == 1


def test_tres_personas_en_dias_distintos_son_tres_en_la_semana() -> None:
    # Y el otro lado del mismo filo: distintas personas SI se cuentan.
    eventos = [_ev(1, 0), _ev(2, 1), _ev(3, 2)]
    semanal = en_el_tiempo(eventos, "week")
    assert len(semanal) == 1
    assert semanal[0].usuarios == 3


def test_las_sesiones_tampoco_se_suman() -> None:
    """Una sesion que cruza la medianoche es una, no dos.

    Se cuentan identificadores distintos, igual que la gente. En el grano
    diario aparece en los dos dias --no hay forma de partirla sin inventar un
    reparto-- pero en la semana es una sola.
    """
    eventos = [
        Evento("misma", "page", "Liga", None, LUNES + timedelta(hours=h), 0, 1, "u1")
        for h in (10, 20)
    ]
    semanal = en_el_tiempo(eventos, "week")
    assert semanal[0].sesiones == 1


# ── Los huecos ───────────────────────────────────────────────────────────────


def test_el_dia_sin_nadie_ocupa_su_sitio_con_un_cero() -> None:
    # Dia 0 y dia 3: la serie tiene que tener CUATRO tramos, no dos.
    serie = en_el_tiempo([_ev(1, 0), _ev(1, 3)], "day")
    assert [t.usuarios for t in serie] == [1, 0, 0, 1]
    assert [t.desde for t in serie] == [
        "2026-10-05",
        "2026-10-06",
        "2026-10-07",
        "2026-10-08",
    ]


def test_la_semana_vacia_tambien() -> None:
    serie = en_el_tiempo([_ev(1, 0), _ev(1, 21)], "week")
    assert [t.usuarios for t in serie] == [1, 0, 0, 1]


def test_el_mes_vacio_tambien_y_el_salto_de_ano_no_lo_rompe() -> None:
    noviembre = datetime(2026, 11, 20, 9, 0, 0)
    eventos = [
        Evento("a", "page", "Liga", None, noviembre, 0, 1, "u1"),
        Evento("b", "page", "Liga", None, datetime(2027, 2, 3, 9, 0, 0), 0, 2, "u2"),
    ]
    serie = en_el_tiempo(eventos, "month")
    assert [t.desde for t in serie] == [
        "2026-11-01",
        "2026-12-01",
        "2027-01-01",
        "2027-02-01",
    ]
    assert [t.usuarios for t in serie] == [1, 0, 0, 1]


def test_los_tramos_rellenados_no_traen_basura() -> None:
    # Un cero tiene que ser un cero en todas sus columnas, no solo en gente.
    serie = en_el_tiempo([_ev(1, 0, visible_ms=60_000), _ev(1, 2)], "day")
    hueco = serie[1]
    assert (hueco.usuarios, hueco.nuevos, hueco.sesiones) == (0, 0, 0)
    assert (hueco.paginas, hueco.clics, hueco.minutos) == (0, 0, 0.0)


# ── La primera vez ───────────────────────────────────────────────────────────


def test_sin_el_estreno_de_siempre_la_columna_se_queda_en_cero() -> None:
    """Antes que mentir, nada.

    Sin el dato de cuando aparecio cada uno POR PRIMERA VEZ, lo unico que se
    podria usar es el primer evento de la lista filtrada --y eso estrenaria a
    todo el mundo cada vez que se acorta el plazo--. Asi que la columna se
    queda a cero y el grafico no dibuja una linea de crecimiento falsa.
    """
    serie = en_el_tiempo([_ev(1, 0), _ev(2, 1)], "day")
    assert [t.nuevos for t in serie] == [0, 0]


def test_el_estreno_cuenta_en_su_tramo() -> None:
    estrenos = {1: LUNES, 2: LUNES + timedelta(days=1)}
    serie = en_el_tiempo([_ev(1, 0), _ev(2, 1), _ev(1, 1)], "day", estrenos)
    assert [t.usuarios for t in serie] == [1, 2]
    assert [t.nuevos for t in serie] == [1, 1]


def test_quien_ya_venia_de_antes_no_estrena_dentro_del_plazo() -> None:
    """La prueba que da sentido a la consulta aparte.

    La persona 1 aparecio hace un mes; en la ventana que se esta mirando solo
    hay eventos suyos de esta semana. No puede contar como nueva.
    """
    estrenos = {1: LUNES - timedelta(days=30)}
    serie = en_el_tiempo([_ev(1, 0), _ev(1, 1)], "day", estrenos)
    assert [t.usuarios for t in serie] == [1, 1]
    assert [t.nuevos for t in serie] == [0, 0]


def test_el_estreno_de_quien_no_aparece_en_el_plazo_no_cuenta() -> None:
    # Un estreno que cae en un tramo de la serie, pero de alguien que en ese
    # tramo no hizo nada (se excluyo, o se filtro por otra cosa). Contarlo
    # daria mas estrenos que personas activas, que es imposible.
    estrenos = {1: LUNES, 9: LUNES}
    serie = en_el_tiempo([_ev(1, 0)], "day", estrenos)
    assert serie[0].usuarios == 1
    assert serie[0].nuevos == 1


def test_nunca_hay_mas_estrenos_que_personas() -> None:
    estrenos = dict.fromkeys(range(1, 6), LUNES)
    serie = en_el_tiempo([_ev(1, 0), _ev(2, 0)], "day", estrenos)
    for t in serie:
        assert t.nuevos <= t.usuarios


# ── Los bordes ───────────────────────────────────────────────────────────────


def test_sin_eventos_la_serie_esta_vacia() -> None:
    # Vacia, no un tramo de hoy con un cero: no se midio nada, no se afirma
    # nada.
    for grano in GRANOS:
        assert en_el_tiempo([], grano) == []


def test_un_grano_que_no_existe_cae_al_dia() -> None:
    # Llega del navegador, asi que puede llegar cualquier cosa.
    assert en_el_tiempo([_ev(1, 0)], "decada") == en_el_tiempo([_ev(1, 0)], "day")


def test_la_semana_empieza_en_lunes() -> None:
    domingo = datetime(2026, 10, 11, 23, 0, 0)
    serie = en_el_tiempo([Evento("a", "page", "Liga", None, domingo, 0, 1, "u1")], "week")
    assert serie[0].desde == "2026-10-05"


def test_el_relleno_tiene_tope() -> None:
    """Un dato con la fecha torcida no puede pedir un millon de casillas."""
    eventos = [
        _ev(1, 0),
        Evento("raro", "page", "Liga", None, datetime(2099, 1, 1), 0, 1, "u1"),
    ]
    assert len(en_el_tiempo(eventos, "day")) == 1200


def test_el_orden_es_del_mas_viejo_al_mas_nuevo() -> None:
    serie = en_el_tiempo([_ev(1, 4), _ev(1, 0), _ev(1, 2)], "day")
    assert [t.desde for t in serie] == sorted(t.desde for t in serie)


def test_las_columnas_de_volumen_suman_lo_de_siempre() -> None:
    eventos = [
        _ev(1, 0, visible_ms=30_000),
        _ev(1, 0, "click"),
        _ev(2, 0, visible_ms=90_000),
    ]
    t = en_el_tiempo(eventos, "day")[0]
    assert (t.paginas, t.clics, t.minutos) == (2, 1, 2.0)


# ── La respuesta del endpoint ────────────────────────────────────────────────
#
# Lo de arriba prueba la aritmetica. Esto prueba que la aritmetica LLEGA: una
# clave mal escrita en el diccionario de la respuesta pasa ruff, pasa mypy,
# pasa las dieciocho pruebas de arriba y deja la pantalla vacia.

import asyncio
from datetime import UTC

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, require_admin
from app.infrastructure.db import models as m
from app.infrastructure.db.session import get_session
from app.main import app


@pytest.fixture
def cliente():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def montar() -> int:
        async with engine.begin() as conn:
            await conn.run_sync(m.Base.metadata.create_all)
        async with factory() as s:
            u = m.User(ht_user_id=7, login_name="yo")
            s.add(u)
            await s.flush()
            s.add(m.WorldContext(ht_league_id=19, country_code="CO", country_name="Colombia"))
            s.add(m.Team(ht_team_id=1, name="club", owner_user_id=u.id, ht_league_id=19, is_primary_club=True))
            await s.commit()
            return u.id

    user_id = asyncio.run(montar())

    async def sesion():
        async with factory() as s:
            yield s

    async def quien_soy():
        async with factory() as s:
            return await s.get(m.User, user_id)

    app.dependency_overrides[get_session] = sesion
    app.dependency_overrides[get_current_user] = quien_soy
    app.dependency_overrides[require_admin] = quien_soy
    yield TestClient(app), factory, user_id
    app.dependency_overrides.clear()


def _mandar(client, cuando: datetime, tipo: str = "click") -> None:
    r = client.post(
        "/api/v1/usage/events",
        json={
            "events": [
                {
                    "sessionId": "s1",
                    "kind": tipo,
                    "module": "Liga",
                    "label": "Ordenar",
                    "at": cuando.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "visibleMs": 1000,
                }
            ]
        },
    )
    assert r.status_code == 204, r.text


def test_la_serie_viaja_con_los_tres_granos(cliente) -> None:
    client, _, _ = cliente
    _mandar(client, datetime.now(UTC) - timedelta(minutes=1))

    datos = client.get("/api/v1/usage?dias=0").json()
    assert set(datos["overTime"]) == {"day", "week", "month"}
    for grano in ("day", "week", "month"):
        serie = datos["overTime"][grano]
        assert len(serie) == 1
        assert serie[0]["users"] == 1
        # Y con el nombre que espera la pantalla, no con otro parecido.
        assert set(serie[0]) == {
            "from",
            "users",
            "newUsers",
            "sessions",
            "pages",
            "clicks",
            "minutes",
        }


def test_el_estreno_se_cuenta_aunque_el_plazo_sea_corto(cliente) -> None:
    """La razon de que el estreno salga de una consulta aparte.

    Un clic de hace diez dias y otro de hoy. Mirando SIETE dias, el de hace
    diez no esta en la lista filtrada --asi que la serie no lo ve-- pero el
    estreno de esa persona es de entonces, no de hoy. Si «nuevos» saliera del
    primer evento de lo filtrado, hoy aparecerian como estreno.
    """
    client, _, _ = cliente
    _mandar(client, datetime.now(UTC) - timedelta(days=10))
    _mandar(client, datetime.now(UTC) - timedelta(minutes=1))

    corto = client.get("/api/v1/usage?dias=7").json()["overTime"]["day"]
    assert sum(t["newUsers"] for t in corto) == 0, "no puede estrenar quien ya venia"
    assert max(t["users"] for t in corto) == 1

    # Mirandolo todo, el estreno esta, y esta UNA vez.
    entero = client.get("/api/v1/usage?dias=0").json()["overTime"]["day"]
    assert sum(t["newUsers"] for t in entero) == 1


def test_cada_persona_trae_su_pais_para_la_bandera(cliente) -> None:
    client, _, _ = cliente
    _mandar(client, datetime.now(UTC) - timedelta(minutes=1))

    gente = client.get("/api/v1/usage?dias=0").json()["byUser"]
    assert len(gente) == 1
    # El mismo pais que el del mapa, y en minusculas, que es lo que pide la
    # libreria de banderas.
    assert gente[0]["countryCode"] == "co"
    assert gente[0]["countryName"] == "Colombia"


def test_quien_no_tiene_club_trae_el_pais_vacio_y_no_falta_la_clave(cliente) -> None:
    # Vacio y no ausente: la pantalla pinta el hueco de la bandera con lo que
    # llegue, y una clave que falta seria `undefined` en una propiedad que el
    # tipo declara como texto.
    client, factory, _ = cliente

    async def sin_club():
        async with factory() as s:
            otro = m.User(ht_user_id=99, login_name="nuevo")
            s.add(otro)
            await s.flush()
            s.add(
                m.UiEvent(
                    user_id=otro.id,
                    session_id="s9",
                    kind="click",
                    module="Liga",
                    label="x",
                    at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=2),
                    visible_ms=0,
                )
            )
            await s.commit()

    asyncio.run(sin_club())
    gente = client.get("/api/v1/usage?dias=0").json()["byUser"]
    nuevo = next(u for u in gente if u["name"] == "nuevo")
    assert nuevo["countryCode"] == ""
    assert nuevo["countryName"] == ""
