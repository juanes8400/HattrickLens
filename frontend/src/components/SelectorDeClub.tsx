import { useTranslation } from "react-i18next";

import { TEAM_ID, useSessionProfile } from "../hooks/useTeam";
import type { SessionTeam } from "../services/api";
import { cambiarDeClub, nombreDelClub } from "./clubes";

/**
 * Con qué club se está mirando la aplicación (2026-10-07, pedido del usuario).
 *
 * Un manager de Hattrick puede llevar varios clubes --uno principal y los
 * secundarios-- y la aplicación ya los guarda todos: `/auth/chpp/session`
 * devuelve la lista, el backend lleva `team_id` en todas las rutas y hay
 * pruebas de lo que se hereda entre clubes y lo que no (la moneda sí, las
 * habilidades desbloqueadas de los juveniles no). Lo único que faltaba era
 * poder CAMBIAR sin volver a pasar por la autorización de Hattrick.
 *
 * Va en la barra lateral, debajo del nombre del club y encima de todo lo
 * demás, porque es la pregunta que hay que poder contestar ANTES de leer
 * cualquier cifra de la pantalla: «¿de qué club es esto?». En la cabecera de
 * arriba no cabía --ya lleva seis mandos-- y escondido en Ajustes sería un
 * sitio donde nadie va a buscar de qué club son los datos que tiene delante.
 *
 * Lista nativa y no un menú propio, por lo mismo que el selector de idioma: se
 * abre igual con teclado, con lector de pantalla y en el móvil.
 */
export function SelectorDeClub() {
  const perfil = useSessionProfile();
  return (
    <ElectorDeClub
      clubes={perfil.data?.teams ?? []}
      activo={TEAM_ID}
      onElegir={cambiarDeClub}
    />
  );
}

/** Lo que se ve, con los clubes dados: así se prueba sin sesión ni servidor. */
export function ElectorDeClub({
  clubes,
  activo,
  onElegir,
}: {
  clubes: SessionTeam[];
  activo: number;
  onElegir: (id: number) => void;
}) {
  const { t } = useTranslation();

  // CON UN SOLO CLUB NO HAY NADA QUE ELEGIR, y un mando con una única opción
  // no informa de nada que no diga ya el nombre de arriba: ocupa sitio en la
  // barra y hace creer que falta algo por configurar. La mayoría de los
  // managers tiene un club, así que lo normal es que esto no se vea.
  if (clubes.length < 2) return null;

  const etiqueta = t("layout.club", "Club");
  return (
    <div className="mb-3 flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5">
      <span aria-hidden="true" className="text-xs text-[var(--muted)]">
        ⇄
      </span>
      <select
        value={activo}
        onChange={(evento) => {
          const elegido = Number(evento.target.value);
          if (elegido !== activo) onElegir(elegido);
        }}
        aria-label={etiqueta}
        title={etiqueta}
        className="w-full cursor-pointer bg-transparent text-xs font-medium text-[var(--text)] outline-none"
      >
        {clubes.map((club, indice) => (
          <option key={club.id} value={club.id} className="text-[var(--text)]">
            {nombreDelClub(club, indice, t)}
          </option>
        ))}
      </select>
    </div>
  );
}
