"""Todas las anotaciones tienen que poder evaluarse de verdad.

Escrito el 2026-08-19, tras el segundo despliegue fallido. El entorno de
desarrollo corre Python 3.14 y la imagen que se despliega, 3.12. Desde 3.14
las anotaciones son perezosas (PEP 649): `-> dict[str, Any]` sin haber
importado `Any` no molesta a nadie mientras nadie las mire, y ni el arranque
en local ni la suite entera lo notaron. En 3.12 se evalúan al definir la
función, así que el mismo fichero revienta al importarse:

    NameError: name 'Any' is not defined

Es decir: un fallo que solo existe fuera de esta máquina. Este test fuerza la
evaluación de todas las anotaciones del paquete `app` para que la diferencia
entre las dos versiones no vuelva a esconder nada.
"""
import importlib
import inspect
import pkgutil

try:  # 3.14+
    import annotationlib

    def _evaluar(obj: object) -> None:
        annotationlib.get_annotations(obj, format=annotationlib.Format.VALUE)
except ImportError:  # 3.12/3.13: ya se evalúan al definir
    def _evaluar(obj: object) -> None:
        inspect.get_annotations(obj, eval_str=True)


def _todo_lo_anotable():
    import app as paquete

    for info in pkgutil.walk_packages(paquete.__path__, "app."):
        modulo = importlib.import_module(info.name)
        yield info.name, modulo
        # `list(...)` y no `.items()` a pelo: evaluar una anotación puede
        # disparar una importación perezosa que añade un nombre al módulo, y
        # entonces el diccionario cambia de tamaño mientras se recorre. En
        # 3.14 no pasaba --las anotaciones no se miran-- y en 3.12 tiraba la
        # suite entera en CI. Una foto de las claves lo cierra.
        for nombre, objeto in list(vars(modulo).items()):
            if not (inspect.isfunction(objeto) or inspect.isclass(objeto)):
                continue
            if getattr(objeto, "__module__", "") != info.name:
                continue
            yield f"{info.name}.{nombre}", objeto
            if inspect.isclass(objeto):
                for interno, metodo in list(vars(objeto).items()):
                    if inspect.isfunction(metodo):
                        yield f"{info.name}.{nombre}.{interno}", metodo


def test_every_annotation_in_the_app_can_be_evaluated() -> None:
    rotas = []
    for etiqueta, objeto in _todo_lo_anotable():
        try:
            _evaluar(objeto)
        except NameError as e:
            rotas.append(f"{etiqueta}: {e}")
    assert rotas == [], (
        "estas anotaciones no resuelven, así que en Python 3.12 el módulo "
        "falla al importarse (falta un import):\n  " + "\n  ".join(rotas)
    )
