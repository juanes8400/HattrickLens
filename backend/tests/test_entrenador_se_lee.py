"""El nivel del entrenador principal tiene que llegar de verdad.

2026-09-01, visto por el usuario: «Nivel del Entrenador no está siendo leído,
aparece 0/5 en varias pantallas». No era un fallo de pintado.

Lo que pasaba, verificado en vivo contra esta cuenta pidiendo el fichero del
cuerpo técnico en sus dos versiones:

  * la versión 1.0 --la que se pedía-- NO trae el nodo del entrenador. Sólo
    la lista de empleados. No es que venga vacío: no viene.
  * la 1.2 sí lo trae, con nivel, liderazgo, tipo y estado.

Y el guardado tiene una guarda deliberada --si el nodo falta, no se toca lo
que ya había, para que una respuesta incompleta no borre al entrenador--. Esa
guarda, con la versión que nunca manda el nodo, significaba que el nivel no se
escribía JAMÁS: se quedaba en el 0 con el que nace la fila.

Es el mismo patrón que ya mordió con el libro de traspasos: una versión mal
fijada no falla, no avisa y no rompe ningún test — simplemente calla un campo.
Por eso lo que se vigila aquí es la VERSIÓN pedida, no el valor.
"""

from pathlib import Path

from app.application.commands.sync_team import FILE_VERSIONS
from app.infrastructure.chpp.parsers import get_parser

FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: Las versiones que sabemos que traen al entrenador. La 1.0 y la 1.1 no.
CON_ENTRENADOR = {"1.2"}


def test_se_pide_una_version_que_traiga_al_entrenador() -> None:
    pedida = FILE_VERSIONS["stafflist"]
    assert pedida in CON_ENTRENADOR, (
        f"el cuerpo técnico se pide en la versión {pedida}, que no trae el nodo del "
        "entrenador: su nivel se quedaría en 0 para siempre"
    )


def test_el_lector_saca_nivel_tipo_y_liderazgo() -> None:
    datos = get_parser("stafflist")((FIXTURES / "stafflist.xml").read_bytes())
    tr = datos["trainer"]
    assert tr["skill_level"] == 5
    assert tr["leadership"] == 5
    assert tr["trainer_type"] == 2
    assert tr["ht_trainer_id"] > 0


def test_el_ejemplo_declara_la_version_que_de_verdad_trae_eso() -> None:
    """El ejemplo decía ser 1.0 y llevaba un entrenador dentro, que es algo que
    la 1.0 real nunca devuelve. Mientras dijera eso, este fichero respaldaba
    justo la creencia equivocada que causó el fallo."""
    texto = (FIXTURES / "stafflist.xml").read_text(encoding="utf-8")
    assert "<Version>1.2</Version>" in texto


def test_sin_nodo_de_entrenador_el_lector_no_inventa_uno() -> None:
    """La otra mitad: cuando de verdad no viene, tiene que salir vacío para que
    el guardado conserve lo último que sí se supo."""
    sin_el = b"""<?xml version="1.0" encoding="utf-8"?>
<HattrickData>
  <FileName>stafflist.xml</FileName>
  <Version>1.0</Version>
  <StaffList>
    <StaffMembers>
      <Staff><Name>A</Name><StaffId>1</StaffId><StaffType>1</StaffType>
      <StaffLevel>5</StaffLevel><Cost>10</Cost></Staff>
    </StaffMembers>
  </StaffList>
</HattrickData>"""
    datos = get_parser("stafflist")(sin_el)
    assert datos["trainer"] == {}
    assert len(datos["staff_members"]) == 1
