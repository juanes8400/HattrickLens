/** Mis clasificaciones (2026-11-18, decidido por el usuario): una sola
 *  pestaña con un selector dentro, para que la barra de arriba no crezca con
 *  cada clasificación nueva. Se lee aquí; se edita en Personalizar. */
import { Tabs } from "../Tabs";
import { tx } from "../../i18n/tx";
import type { ClasesDeJugador } from "../../services/api";
import { clasificaciones, grupoPropioDe } from "./clasificaciones";
import { COLOR, type Grupo } from "./colores";
import { ListaDeGrupos } from "./comun";
import { useClasificacionPropiaElegida } from "./elegida";

export function MisClasificaciones({
  datos,
  onIrAPersonalizar,
}: {
  datos: ClasesDeJugador;
  onIrAPersonalizar: () => void;
}) {
  const [elegidaId, setElegidaId] = useClasificacionPropiaElegida();
  const propia =
    datos.classifications.find((c) => c.id === elegidaId) ??
    datos.classifications[0];

  if (!propia)
    return (
      <p className="text-sm text-[var(--muted)]">
        {tx(
          "Todavía no has creado ninguna clasificación propia, como «Mercado» o «Rol».",
        )}{" "}
        <button
          type="button"
          onClick={onIrAPersonalizar}
          className="text-[var(--accent)] underline underline-offset-2"
        >
          {tx("Créala en Personalizar")}
        </button>
      </p>
    );

  const vista = clasificaciones(datos).find(
    (c) => c.clave === `propia-${propia.id}`,
  );
  const grupos: Grupo[] = [
    ...(vista?.grupos ?? []),
    {
      clave: "sin",
      nombre: tx("Sin grupo"),
      color: COLOR.gris,
      jugadores: datos.players.filter(
        (j) => grupoPropioDe(j, propia.id) == null,
      ),
    },
  ];

  return (
    <div className="space-y-4">
      {datos.classifications.length > 1 && (
        <Tabs
          modo="filtro"
          label={tx("Tus clasificaciones")}
          tabs={datos.classifications.map((c) => ({
            key: String(c.id),
            label: c.classificationName,
          }))}
          active={String(propia.id)}
          onChange={(k) => setElegidaId(Number(k))}
        />
      )}
      {propia.groups.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">
          {tx("«{{c}}» todavía no tiene grupos.", {
            c: propia.classificationName,
          })}{" "}
          <button
            type="button"
            onClick={onIrAPersonalizar}
            className="text-[var(--accent)] underline underline-offset-2"
          >
            {tx("Créalos en Personalizar")}
          </button>
        </p>
      ) : (
        <ListaDeGrupos grupos={grupos} />
      )}
    </div>
  );
}
