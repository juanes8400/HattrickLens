/** Jugadores (8.0.0, 2026-11-26): quién es cada uno, en qué grupo cae y cómo
 *  cambia la plantilla.
 *
 *  Junta cuatro cosas que eran tres entradas del menú y media: la tabla
 *  (Jugadores), Clasificación de jugadores, la Distribución del salario (una
 *  pestaña de Profundidad de plantilla) y la evolución semanal (Habilidades).
 *  El salario y la evolución van aquí, y no en Puestos, porque las dos se
 *  parten por los grupos de las clasificaciones; decisión del usuario.
 *
 *  Las direcciones viejas (`/classes`, `/overview`) redirigen a su pestaña. */
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { nombreNav } from "../layouts/navegacion";
import { PESTANAS, type PestanaDe } from "../layouts/modulos";
import { ModuloConPestanas } from "./ModuloConPestanas";

export function ModuloJugadores({
  activa,
  children,
}: {
  activa: PestanaDe<"jugadores">;
  children: ReactNode;
}) {
  // Con el gancho, y no con `nombreDePestana`, para que la barra se repinte
  // al cambiar de idioma.
  const { t } = useTranslation();
  return (
    <ModuloConPestanas
      titulo={nombreNav("Jugadores", "jugadores")}
      grupo="modulo-jugadores"
      activa={activa}
      pestanas={PESTANAS.jugadores.map((p) => ({
        key: p.key,
        to: p.to,
        label: t(`modulos.jugadores.${p.key}`, p.texto),
      }))}
    >
      {children}
    </ModuloConPestanas>
  );
}
