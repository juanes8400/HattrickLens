"""El parser del mercado de transferencias.

`transfersearch.xml` es el único fichero de CHPP que enseña jugadores ajenos
con sus habilidades a la vista. Sirve para poner al lado de un jugador tuyo lo
que se pide hoy por los que se le parecen, y por eso lo que más importa aquí no
son los campos sino las TRES trampas del fichero, que son las que vigila este
test:

  · un `HighestBid` de 0 significa «nadie ha pujado», no «ofrecieron cero»;
  · `InjuryLevel` usa -1 para sano y 0 para magullado, así que un default de 0
    dejaría el mercado entero tocado;
  · `ItemCount` vale -1 cuando hay más de 100 resultados, y eso no es un
    recuento que se pueda redondear a 0.
"""

from pathlib import Path

from app.infrastructure.chpp.parsers import get_parser

FIXTURES = Path(__file__).parent / "fixtures"


def _parsea() -> dict:
    datos = (FIXTURES / "transfersearch.xml").read_bytes()
    return get_parser("transfersearch")(datos)


def test_trae_los_tres_resultados_con_su_precio_y_su_plazo() -> None:
    datos = _parsea()
    assert len(datos["results"]) == 3
    primero = datos["results"][0]
    assert primero["ht_player_id"] == 491002001
    assert primero["first_name"] == "Aurelio"
    assert primero["last_name"] == "Barrantes"
    assert primero["asking_price"] == 4_200_000
    assert primero["deadline"] == "2026-10-06 21:30:00"


def test_el_cero_de_la_puja_no_es_una_oferta_de_cero() -> None:
    """Es la diferencia entre «nadie quiso» y «ofrecieron cero».

    Importa para lo que viene después: si se promedian las pujas para decir
    qué paga el mercado, meter los ceros de los que nadie quiso tira la media
    al suelo y la pantalla diría una mentira.
    """
    con_puja, sin_puja, _ = _parsea()["results"]
    assert con_puja["highest_bid"] == 4_500_000
    assert con_puja["has_bids"] is True
    assert con_puja["bidder_team_name"] == "Los Cartujos"

    assert sin_puja["highest_bid"] == 0
    assert sin_puja["has_bids"] is False
    # Y sin `BidderTeam` en el XML, que es como viene cuando no hay pujas.
    assert sin_puja["bidder_team_id"] == 0
    assert sin_puja["bidder_team_name"] == ""


def test_sano_magullado_y_lesionado_son_tres_cosas_distintas() -> None:
    """-1 sano, 0 magullado, n semanas de baja."""
    sano, lesionado, magullado = _parsea()["results"]
    assert sano["injury_level"] == -1
    assert lesionado["injury_level"] == 2
    assert magullado["injury_level"] == 0


def test_sin_dato_de_lesion_el_jugador_esta_sano_y_no_magullado() -> None:
    """El default tiene que ser -1.

    Con 0, que es el default de `_int`, un resultado al que le falte el campo
    saldría magullado, y la documentación dice que `InjuryLevel` no viene
    «si hay un partido en juego»: no es un caso raro, es media tarde de
    domingo. Esta prueba existe porque la de arriba NO vigila el default: en
    el fixture el campo viene siempre.
    """
    sin_campo = b"""<?xml version="1.0" encoding="utf-8"?>
    <HattrickData>
      <TransferSearch>
        <ItemCount>1</ItemCount>
        <PageSize>25</PageSize>
        <PageIndex>0</PageIndex>
        <TransferResults>
          <TransferResult>
            <PlayerId>491002009</PlayerId>
            <FirstName>Sin</FirstName>
            <LastName>Datos</LastName>
            <AskingPrice>100000</AskingPrice>
            <Details>
              <Age>25</Age>
              <TSI>50000</TSI>
            </Details>
          </TransferResult>
        </TransferResults>
      </TransferSearch>
    </HattrickData>"""
    jugador = get_parser("transfersearch")(sin_campo)["results"][0]
    assert jugador["injury_level"] == -1
    # Y lo que falta de verdad no se inventa: cero es cero.
    assert jugador["salary"] == 0
    assert jugador["skills"]["playmaking"] == 0


def test_las_habilidades_llegan_con_los_nombres_de_la_casa() -> None:
    """Los mismos que la plantilla propia: comparar no debe obligar a traducir."""
    primero = _parsea()["results"][0]
    assert primero["skills"] == {
        "keeper": 1,
        "defending": 4,
        "playmaking": 9,
        "winger": 6,
        "passing": 11,
        "scoring": 5,
        "set_pieces": 3,
        "stamina": 8,
    }


def test_el_vendedor_y_su_liga_viajan_con_cada_resultado() -> None:
    """Sin la liga no se sabe si el precio es de tu mercado o de otro país."""
    primero = _parsea()["results"][0]
    assert primero["seller_team_id"] == 7654321
    assert primero["seller_team_name"] == "Combo del Chavo"
    assert primero["seller_league_id"] == 92


def test_menos_uno_en_el_recuento_significa_muchos_y_se_respeta() -> None:
    """Hattrick dice -1 cuando hay más de 100. Convertirlo en 0 o en 100 sería
    inventarse un recuento que nadie dio."""
    datos = _parsea()
    assert datos["item_count"] == -1
    assert datos["page_size"] == 3
    assert datos["page_index"] == 0


def test_un_error_de_chpp_no_revienta_ni_miente() -> None:
    """Mismo trato que el resto de parsers: búsqueda vacía, no excepción."""
    datos = get_parser("transfersearch")((FIXTURES / "chpperror.xml").read_bytes())
    assert datos["results"] == []
    assert datos["item_count"] == 0


def test_una_busqueda_sin_resultados_no_es_un_error() -> None:
    vacia = b"""<?xml version="1.0" encoding="utf-8"?>
    <HattrickData>
      <FileName>transfersearch.xml</FileName>
      <TransferSearch>
        <ItemCount>0</ItemCount>
        <PageSize>25</PageSize>
        <PageIndex>0</PageIndex>
        <TransferResults></TransferResults>
      </TransferSearch>
    </HattrickData>"""
    datos = get_parser("transfersearch")(vacia)
    assert datos["results"] == []
    assert datos["item_count"] == 0
    assert datos["page_size"] == 25
