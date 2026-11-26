/** Un módulo del menú hecho de varias pantallas (2026-11-26, pedido del
 *  usuario): el nombre del módulo, su barra de pestañas y, debajo, la pestaña
 *  abierta.
 *
 *  Cada pestaña es SU PROPIA DIRECCIÓN y no un estado de la página. Por tres
 *  razones:
 *  - un enlace lleva directo a la pestaña, y el botón «atrás» vuelve a la de
 *    antes;
 *  - la entrada del menú se resalta sola, porque todas cuelgan de la misma
 *    raíz (`/team`, `/team/classes`…);
 *  - el registro de uso sigue contando cada pestaña con el nombre de la
 *    pantalla que era: el historial no se parte al juntarlas.
 *
 *  La barra es la misma `Tabs` del resto de la aplicación, así que se ve y se
 *  maneja con el teclado igual que cualquier otra. */
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { PanelDePestanas, Tabs } from "./Tabs";

export type PestanaDeModulo<T extends string> = {
  key: T;
  to: string;
  label: string;
};

export function ModuloConPestanas<T extends string>({
  titulo,
  grupo,
  pestanas,
  activa,
  children,
}: {
  titulo: string;
  /** Nombre del grupo de pestañas, para enlazar cada pestaña con su panel. */
  grupo: string;
  pestanas: PestanaDeModulo<T>[];
  activa: T;
  children: ReactNode;
}) {
  const navigate = useNavigate();
  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{titulo}</h1>
      <Tabs
        grupo={grupo}
        label={titulo}
        tabs={pestanas.map(({ key, label }) => ({ key, label }))}
        active={activa}
        onChange={(key) => {
          const destino = pestanas.find((p) => p.key === key);
          if (destino) navigate(destino.to);
        }}
      />
      <PanelDePestanas grupo={grupo} activa={activa} className="space-y-4">
        {children}
      </PanelDePestanas>
    </div>
  );
}
