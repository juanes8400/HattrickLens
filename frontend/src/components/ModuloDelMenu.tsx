/** Un módulo del menú con sus pestañas: Jugadores (8.0.0) y Puestos (8.1.0),
 *  2026-11-26, pedido del usuario.
 *
 *  Juntan cinco pantallas que eran entradas propias del menú Club:
 *  - Jugadores: la tabla, Clasificación de jugadores, la Distribución del
 *    salario y la evolución semanal (antes «Habilidades»). El salario y la
 *    evolución van aquí porque se parten por los grupos de las
 *    clasificaciones; decisión del usuario.
 *  - Puestos: Profundidad, Mejor posición y Posiciones («Por puesto»).
 *
 *  Las pestañas y sus direcciones viven en `layouts/modulos`. Las direcciones
 *  viejas (`/classes`, `/overview`, `/positions`) redirigen a su pestaña. */
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { nombreNav } from "../layouts/navegacion";
import { MODULOS, type Modulo, type PestanaDe } from "../layouts/modulos";
import { ModuloConPestanas } from "./ModuloConPestanas";

export function ModuloDelMenu<M extends Modulo>({
  de,
  activa,
  children,
}: {
  de: M;
  activa: PestanaDe<M>;
  children: ReactNode;
}) {
  // Con el gancho, y no con `nombreDePestana`, para que la barra se repinte
  // al cambiar de idioma.
  const { t } = useTranslation();
  const modulo = MODULOS[de];
  return (
    <ModuloConPestanas
      titulo={nombreNav(modulo.nombre, modulo.clave)}
      grupo={`modulo-${de}`}
      activa={activa as string}
      pestanas={modulo.pestanas.map((p) => ({
        key: p.key as string,
        to: p.to,
        label: t(`modulos.${de}.${p.key}`, p.texto),
      }))}
    >
      {children}
    </ModuloConPestanas>
  );
}
