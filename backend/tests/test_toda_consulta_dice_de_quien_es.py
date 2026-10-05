"""Ninguna consulta a Hattrick se manda sin decir de quien es.

2026-09-27, instruccion del usuario: «todo debe ser consultado usando TeamID,
no dejando vacio para rellenar con default».

POR QUE IMPORTA. El token de CHPP identifica una CUENTA, no un club, y una
cuenta puede llevar varios. Cuando una peticion no dice de que club habla,
Hattrick la resuelve con el club PRINCIPAL de la cuenta, en silencio y con una
respuesta perfectamente valida. Ya paso dos veces:

  · septiembre de 2026, los juveniles: sin `youthTeamId`, la academia del
    primer equipo salia tambien como la del segundo. Lo reporto un usuario;
  · y un reporte abierto sobre el Estadio, con la misma pinta.

Y no es solo leer: `actionType=unlockskills` ESCRIBE, y sin el id de la
academia escribia sobre la del club principal.

COMO SE COMPRUEBA. Se recorren todas las llamadas del codigo por AST --no con
grep, que no ve una llamada partida en varias lineas-- y cada fichero tiene
que llevar el parametro que dice de quien es. Los que se identifican por otra
cosa (un partido, un jugador, una region) llevan la suya, y los poquisimos
casos que de verdad no pueden llevar ninguno estan nombrados uno a uno aqui
abajo, con su motivo.
"""

import ast
import pathlib

RAIZ = pathlib.Path(__file__).resolve().parents[1] / "app"

#: Que parametro identifica al sujeto de cada fichero. La mayoria es el club;
#: los demas se piden por su propia llave, y eso tambien cuenta como decir de
#: quien es: un partido jugado o la ficha de un jugador no dependen del token.
LLAVE_DE: dict[str, set[str]] = {
    "arenadetails": {"teamID", "arenaID"},
    "club": {"teamID"},
    "currentbids": {"teamID"},
    "economy": {"teamID"},
    "leaguedetails": {"leagueLevelUnitID"},
    "leaguefixtures": {"leagueLevelUnitID"},
    "managercompendium": {"userID"},
    "matchdetails": {"matchID"},
    "matcheslatest": {"teamID"},
    "matches": {"teamID"},
    "matchesarchive": {"teamID"},
    "matchlineup": {"teamID"},
    "matchorders": {"teamId"},
    "nationalteamdetails": {"teamId"},
    "players": {"teamID"},
    "playerdetails": {"playerID"},
    "regiondetails": {"regionID"},
    "stafflist": {"teamID"},
    "teamdetails": {"teamID"},
    "trainingevents": {"playerID"},
    "training": {"teamID"},
    "transfersplayer": {"playerID"},
    "transfersteam": {"teamID"},
    "youthplayerdetails": {"youthPlayerId"},
    "youthplayerlist": {"youthTeamId"},
    "youthteamdetails": {"youthTeamId"},
}

#: Los que no tienen sujeto que nombrar, y por que.
SIN_SUJETO = {
    # El catalogo del mundo: paises, monedas, temporadas. No es de nadie.
    "worlddetails",
    # El listado de partidos de selecciones del ultimo mes, entero. No se pide
    # el de un equipo concreto: se busca en el a los jugadores propios.
    "nationalteammatches",
    # El diccionario oficial de terminos de Hattrick en un idioma.
    "translations",
    # El mercado de transferencias. Se busca en el mercado ENTERO por edad y
    # habilidades, no en los jugadores de un equipo: no hay a quien nombrar.
    "transfersearch",
}

#: Las excepciones, una a una, con su motivo. Se identifican por fichero y
#: modulo, no por linea: una linea se mueve sola en cuanto alguien edita algo.
PERDONADAS: dict[tuple[str, str], str] = {
    ("teamdetails", "api/v1/endpoints/auth_chpp.py"): (
        "Es la llamada que DESCUBRE que clubes tiene la cuenta, justo despues "
        "de autorizar. Todavia no hay ningun club elegido que nombrar: es la "
        "unica peticion de toda la aplicacion para la que eso es correcto."
    ),
}

#: Las llamadas que arman sus parametros en un diccionario y lo pasan con `**`.
#: El AST no puede leerlas, asi que se revisan a mano y se anotan aqui. Cada
#: una tiene que dejar claro EN SU PROPIO CODIGO de quien es lo que pide.
CON_PARAMETROS_SUELTOS: dict[str, str] = {
    "application/commands/sync_team/__init__.py": (
        "El bucle de la sincronizacion. Arranca con `{'teamID': ht_team_id}` "
        "para todos, y los tres ficheros que se piden por otra llave (las dos "
        "de liga y las dos de cantera) lo sustituyen ahi mismo."
    ),
    "api/v1/endpoints/rivals.py": (
        "Es una envoltura con cache que reenvia a la de verdad; los "
        "parametros los pone quien la llama."
    ),
}


def _llamadas() -> list[tuple[str, int, str, set[str], bool]]:
    fuera = []
    for f in sorted(RAIZ.rglob("*.py")):
        arbol = ast.parse(f.read_text(encoding="utf-8"))
        modulo = f.relative_to(RAIZ).as_posix()
        for nodo in ast.walk(arbol):
            if not isinstance(nodo, ast.Call):
                continue
            fn = nodo.func
            if not (isinstance(fn, ast.Attribute) and fn.attr == "fetch"):
                continue
            if nodo.args and isinstance(nodo.args[0], ast.Constant):
                fichero = str(nodo.args[0].value)
            else:
                fichero = ""  # el nombre es una variable: es un despachador
            claves = {k.arg for k in nodo.keywords if k.arg}
            estrella = any(k.arg is None for k in nodo.keywords)
            fuera.append((modulo, nodo.lineno, fichero, claves, estrella))
    return fuera


def test_hay_llamadas_que_revisar() -> None:
    """Si el censo sale vacio, esta prueba no esta comprobando nada."""
    assert len(_llamadas()) > 40


def test_toda_consulta_dice_de_quien_es() -> None:
    culpables: list[str] = []
    for modulo, linea, fichero, claves, estrella in _llamadas():
        if not fichero:
            # Despachador: se revisa a mano y se anota arriba.
            if modulo not in CON_PARAMETROS_SUELTOS:
                culpables.append(
                    f"{modulo}:{linea} pide un fichero que sale de una variable y no "
                    "esta anotado en CON_PARAMETROS_SUELTOS"
                )
            continue
        if fichero in SIN_SUJETO:
            continue
        if (fichero, modulo) in PERDONADAS:
            continue
        llaves = LLAVE_DE.get(fichero)
        if llaves is None:
            culpables.append(
                f"{modulo}:{linea} pide «{fichero}», que no esta en LLAVE_DE: "
                "anade con que parametro se dice de quien es"
            )
            continue
        if claves & llaves:
            continue
        if estrella:
            # Los parametros van en un diccionario: no se puede leer aqui.
            if modulo in CON_PARAMETROS_SUELTOS:
                continue
            culpables.append(
                f"{modulo}:{linea} pide «{fichero}» con los parametros sueltos y sin anotar"
            )
            continue
        culpables.append(
            f"{modulo}:{linea} pide «{fichero}» sin {' ni '.join(sorted(llaves))}: "
            "Hattrick lo resolveria con el club principal de la cuenta"
        )

    assert not culpables, (
        "Consultas a Hattrick que no dicen de quien son. El token es la CUENTA, "
        "no el club, y sin decirlo contesta el club principal:\n  " + "\n  ".join(culpables)
    )


# ---------------------------------------------------------------------------
# Y lo mismo comprobado CORRIENDO, no leyendo. El bucle de la sincronizacion
# arma sus parametros en un diccionario, asi que la comprobacion estatica de
# arriba tiene que darlo por bueno de palabra. Aqui se sincroniza de verdad
# contra un doble que apunta cada peticion, y se mira lo que salio.


class _Apuntador:
    """El doble de Hattrick de siempre, anotando que se le pide y con que."""

    def __init__(self, interno) -> None:
        self._interno = interno
        self.peticiones: list[tuple[str, dict]] = []

    async def fetch(self, file: str, version: str = "latest", **params):
        self.peticiones.append((file, dict(params)))
        return await self._interno.fetch(file, version, **params)


def test_una_sincronizacion_de_verdad_nombra_el_club_en_cada_peticion() -> None:
    import asyncio

    from app.application.commands.sync_team import (
        DEFAULT_FILES,
        SyncTeamCommand,
        SyncTeamHandler,
    )
    from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
    from tests.conftest import HT_TEAM_ID, FakeCHPP, seeded_session

    async def caso():
        factory, team_id = await seeded_session()
        espia = _Apuntador(FakeCHPP())
        handler = SyncTeamHandler(SqlAlchemyUnitOfWork(factory), espia)
        await handler.execute(
            SyncTeamCommand(user_id=1, team_id=team_id, ht_team_id=HT_TEAM_ID, files=DEFAULT_FILES)
        )
        return espia.peticiones

    peticiones = asyncio.run(caso())
    assert peticiones, "si no se pidio nada, esta prueba no comprueba nada"

    mudas = []
    for fichero, params in peticiones:
        if fichero in SIN_SUJETO:
            continue
        llaves = LLAVE_DE.get(fichero)
        assert llaves is not None, f"«{fichero}» no esta en LLAVE_DE"
        if not (set(params) & llaves):
            mudas.append(f"«{fichero}» pedido con {sorted(params) or 'nada'}")

    assert not mudas, (
        "Una sincronizacion real mando peticiones sin decir de que club son:\n  "
        + "\n  ".join(sorted(set(mudas)))
    )
