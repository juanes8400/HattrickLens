"""La taquilla se calcula con el desglose por sector, y el desglose no sale.

2026-09-28, decision del usuario con esas palabras: «guarda el desglose,
calcula con el, y no lo enseñes nunca».

Aqui se comprueba que el numero sea exacto. La otra mitad --que el desglose no
salga NUNCA por una respuesta, que es la condicion con la que se acepto volver
a guardarlo-- la vigila `test_nada_de_supporter.py`.
"""

from app.domain.engines.taquilla import taquilla_del_partido


class _Foto:
    """Una fila de `stadium_history` con el desglose del partido del usuario."""

    sold_terraces = 30627
    sold_basic = 13639
    sold_roof = 4527
    sold_vip = 1272


def test_la_taquilla_sale_exacta_de_las_entradas_por_sector() -> None:
    """El partido que mando el usuario, con los cuatro precios verificados.

        30.627 × 7  = 214.389   (General)
        13.639 × 10 = 136.390   (Preferentes)
         4.527 × 19 =  86.013   (Tribunas)
         1.272 × 35 =  44.520   (Palcos)
                       -------
                       481.312
    """
    assert taquilla_del_partido(_Foto()) == 481_312


def test_sin_desglose_no_hay_taquilla_y_no_se_inventa_un_cero() -> None:
    """Un cero diria «no entro nadie», que es otra cosa muy distinta.

    Los partidos sincronizados entre el 2026-09-01 y el 2026-09-28 no tienen
    desglose: se quedan fuera del total hasta que el sync vuelva a pedirlo.
    """

    class SinNada:
        sold_terraces = None
        sold_basic = None
        sold_roof = None
        sold_vip = None

    class AMedias:
        sold_terraces = 30627
        sold_basic = 13639
        sold_roof = None
        sold_vip = 1272

    assert taquilla_del_partido(SinNada()) is None
    # Con tres sectores no sale una taquilla: sale un numero mas bajo que
    # parece uno bueno, que es peor que no dar ninguno.
    assert taquilla_del_partido(AMedias()) is None

