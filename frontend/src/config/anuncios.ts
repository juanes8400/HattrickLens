/** La publicidad: si la hay, de quién es, y dónde puede salir.
 *
 *  UN SOLO INTERRUPTOR, igual que `apoyo.ts`. Encender la publicidad es una
 *  decisión de producto, y tiene que tomarse en un sitio para que ninguna
 *  pantalla pueda discrepar con otra.
 *
 *  NACE APAGADO Y ES INERTE. Sin `VITE_ADSENSE_CLIENT` en el entorno no se
 *  carga ningún script, no se pinta ningún hueco y no se genera `ads.txt`.
 *  Desplegar esto sin configurar nada deja el sitio exactamente como estaba,
 *  que es lo que permite subirlo sin esperar a tener la cuenta aprobada.
 *
 *  DOS CONDICIONES, NO UNA. Un anuncio sólo aparece si está CONFIGURADO y
 *  además el visitante ha CONSENTIDO. La segunda no es cortesía: desde el
 *  16 de enero de 2024 Google exige a sus editores una plataforma de
 *  consentimiento certificada para el tráfico del EEE y el Reino Unido
 *  --Suiza desde el 31 de julio de 2024-- y sin ella sólo sirve «anuncios
 *  limitados». Ver `Consentimiento.tsx`.
 */

/** El identificador de editor de AdSense, de la forma `ca-pub-0000000000000000`.
 *
 *  Viene del entorno y no del código a propósito: es lo único que cambia
 *  entre un despliegue con publicidad y uno sin ella, y así el mismo build
 *  sirve para los dos.
 */
export const CLIENTE_ADSENSE: string = (
  import.meta.env.VITE_ADSENSE_CLIENT ?? ""
).trim();

/** Si el identificador tiene la forma que Google espera.
 *
 *  Se comprueba la FORMA y no sólo que haya algo: un valor a medio pegar
 *  --«ca-pub-» suelto, o el número sin prefijo-- cargaría el script de Google
 *  para no servir nada, y el fallo sería invisible. Mejor no cargarlo.
 */
export const clienteValido = (valor: string = CLIENTE_ADSENSE): boolean =>
  /^ca-pub-\d{16}$/.test(valor);

/** Si este despliegue lleva publicidad configurada.
 *
 *  NO basta para pintar un anuncio: hace falta además el consentimiento. La
 *  condición completa vive en `Anuncio.tsx`, que es quien pinta.
 */
export const hayAnuncios = (): boolean => clienteValido();

/** QUIÉN PREGUNTA POR LAS COOKIES. Dos modos, y la diferencia importa.
 *
 *  `"propia"` (por defecto) — pregunta nuestra barra, y el script de Google
 *  NO se carga hasta que alguien dice que sí. Es lo más conservador que se
 *  puede hacer, y vale para tráfico fuera del EEE, el Reino Unido y Suiza.
 *
 *  `"google"` — manda la plataforma CERTIFICADA de Google («Privacidad y
 *  mensajes», dentro de la cuenta de AdSense). Nuestra barra desaparece para
 *  no preguntar dos veces.
 *
 *  Y AQUÍ ESTÁ LA VUELTA DE TUERCA QUE HAY QUE ENTENDER ANTES DE CAMBIARLO:
 *  la plataforma de Google VIAJA DENTRO del propio script de AdSense, así que
 *  en ese modo el script se carga ANTES de preguntar. No es una contradicción
 *  ni un descuido: para eso existe el Modo de consentimiento v2 de
 *  `index.html`, que arranca con las cuatro señales en `denied`. Google carga,
 *  pregunta, y no pone cookies de publicidad ni personaliza hasta que la
 *  respuesta llega. Sin esos valores por defecto esto sí sería una fuga.
 *
 *  Para el EEE hace falta una certificada: desde el 16-01-2024 Google sólo
 *  sirve «anuncios limitados» sin ella. Nuestra barra NO lo es.
 */
export type QuienPregunta = "propia" | "google";

export const CMP: QuienPregunta =
  import.meta.env.VITE_ADSENSE_CMP === "google" ? "google" : "propia";

/** Si quien pregunta es la plataforma certificada de Google. */
export const preguntaGoogle = (): boolean => hayAnuncios() && CMP === "google";

/** Los huecos declarados, con el identificador que les da AdSense.
 *
 *  Se declaran aquí y no en cada pantalla para que se vea de un vistazo
 *  CUÁNTOS hay y dónde. La política de Google prohíbe los anuncios en
 *  páginas sin contenido propio, así que cada hueco nuevo es una decisión
 *  que hay que poder revisar en una lista corta.
 *
 *  `slot` vacío = declarado pero todavía sin crear en AdSense; el hueco no
 *  se pinta hasta que tenga el suyo.
 */
export type HuecoDeAnuncio = {
  id: string;
  /** Para qué sirve, en una línea. */
  donde: string;
  /** El `data-ad-slot` de AdSense. */
  slot: string;
};

export const HUECOS: HuecoDeAnuncio[] = [
  {
    id: "bienvenida",
    donde: "Bajo la presentación, en la pantalla pública de bienvenida.",
    slot: import.meta.env.VITE_ADSENSE_SLOT_BIENVENIDA ?? "",
  },
  {
    id: "guia",
    donde:
      "Al pie de la Guía pública, que es la única pantalla abierta con contenido largo.",
    slot: import.meta.env.VITE_ADSENSE_SLOT_GUIA ?? "",
  },
];

export const huecoPorId = (id: string): HuecoDeAnuncio | undefined =>
  HUECOS.find((h) => h.id === id);
