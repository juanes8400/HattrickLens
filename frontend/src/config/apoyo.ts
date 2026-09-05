/** Las vías por las que se puede apoyar el proyecto, y si se enseñan.
 *
 *  Viven aquí y no dentro de una pantalla porque las leen VARIOS sitios --el
 *  menú lateral, la página de Autor y la de apoyo-- y porque encenderlas es
 *  una decisión de producto que se toma en un solo interruptor, igual que
 *  `INTENTOS_DE_TRANSFERENCIA_VISIBLES`.
 */

/** Una forma de apoyar.
 *
 *  `enlace` o `llave`, nunca las dos: Bre-B no es una URL sino una llave que
 *  hay que COPIAR, y ése es justo el motivo de que el botón del menú lleve a
 *  una pantalla en vez de a un sitio externo. En un enlace directo la llave
 *  no cabía.
 */
export type ViaDeApoyo = {
  id: string;
  nombre: string;
  /** Por qué elegir ésta y no otra. Es lo único que convierte tres botones en
   *  una decisión que alguien puede tomar sin adivinar. */
  porQue: string;
  enlace?: string;
  llave?: string;
  /** Países cuyo club ve esta vía ARRIBA. Vacío = para todo el mundo. Es un
   *  orden, no un filtro: todas se enseñan siempre. Un colombiano que vive
   *  fuera y prefiere pagar con tarjeta internacional no puede quedarse sin
   *  su opción por dónde esté su club. */
  paisesPreferentes?: string[];
};

/** Ninguna de estas cadenas es un secreto: son datos de cobro hechos para
 *  repartirse. Aquí no hay ninguna clave de API ni hace falta —se enlaza, no
 *  se procesa— y por eso no viven en el entorno.
 *
 *  Tampoco se incrusta el widget de Buy Me a Coffee: es un script de terceros
 *  que se cargaría en cada pantalla, y no merece la pena traer código ajeno
 *  --ni lo que pueda mirar-- para pintar un botón que sabemos pintar.
 */
export const VIAS_DE_APOYO: ViaDeApoyo[] = [
  {
    id: "bre-b",
    nombre: "Bre-B",
    porQue:
      "Llega íntegro: no hay comisión de plataforma. Es la mejor si tienes " +
      "cuenta en un banco colombiano.",
    llave: "@JDE596",
    paisesPreferentes: ["Colombia"],
  },
  {
    id: "mercadopago",
    nombre: "Mercado Pago",
    // «de Colombia» va en la primera frase a propósito. Mercado Pago es de
    // uso diario en Argentina, México y Brasil, y quien lo vea ahí va a
    // suponer que es el suyo. No lo es: las cuentas de Mercado Pago no cruzan
    // fronteras --el saldo argentino no paga un cobro colombiano-- así que a
    // un argentino esto le llega como compra en el exterior, con el recargo
    // que eso lleva. Decirlo aquí le ahorra descubrirlo en la pasarela.
    porQue:
      "Enlace de Colombia, en pesos colombianos. Paga con PSE, tarjeta " +
      "colombiana o efectivo. Desde otro país llega como compra en el " +
      "exterior, aunque uses Mercado Pago a diario.",
    enlace: "https://link.mercadopago.com.co/hattricklens",
    paisesPreferentes: ["Colombia"],
  },
  {
    id: "paypal",
    nombre: "PayPal",
    // Antes que Buy Me a Coffee a propósito: BMC cobra su comisión ENCIMA de
    // un procesador y además paga vía PayPal, así que por el mismo donante
    // llega menos. Se queda arriba la barata (2026-09-05, decisión del
    // usuario: «no me interesa que aparezca algo social por más comisión»).
    porQue:
      "Pon tú el importe. No hace falta que tengas cuenta: se puede pagar " +
      "con tarjeta como invitado.",
    enlace: "https://paypal.me/juandelacalle",
  },
  {
    id: "buymeacoffee",
    nombre: "Buy Me a Coffee",
    porQue:
      "La alternativa si prefieres no usar PayPal. Tarjeta internacional, " +
      "desde cualquier país.",
    enlace: "https://buymeacoffee.com/juanes8400",
  },
];

/** Las vías ordenadas para quien tiene el club en `pais`.
 *
 *  Sin esto, alguien de Suecia veía como PRIMERA opción una llave de pagos
 *  colombiana y no entendía nada. Y al revés: un colombiano tenía delante una
 *  pasarela en dólares cuando puede pagar por PSE sin comisión.
 *
 *  TRES grupos y no dos, que fue un fallo real del primer intento: las del
 *  país, las que valen para todo el mundo, y al final las que son de OTRO
 *  país. Con dos grupos --«las suyas» y «el resto»-- el resto conservaba el
 *  orden declarado, y como Bre-B y Mercado Pago van declaradas primero, al
 *  sueco le seguía saliendo la llave colombiana arriba. Se comprobó con
 *  Colombia, que era el caso que sí funcionaba.
 *
 *  El orden dentro de cada grupo se conserva, así que la lista de arriba
 *  manda: entre las internacionales, PayPal antes que Buy Me a Coffee.
 */
export const viasPara = (pais: string | null | undefined): ViaDeApoyo[] => {
  const esDelPais = (v: ViaDeApoyo) =>
    (v.paisesPreferentes ?? []).some((p) => p === pais);
  const esUniversal = (v: ViaDeApoyo) =>
    (v.paisesPreferentes ?? []).length === 0;
  return [
    ...VIAS_DE_APOYO.filter(esDelPais),
    ...VIAS_DE_APOYO.filter(esUniversal),
    ...VIAS_DE_APOYO.filter((v) => !esDelPais(v) && !esUniversal(v)),
  ];
};

/** Si se enseña. Encendido el 2026-09-05 por decisión del usuario. */
export const APOYO_VISIBLE = true;

/** Si de verdad hay algo que enseñar. La condición en un solo sitio para que
 *  las pantallas no puedan discrepar. */
export const hayApoyo = () => APOYO_VISIBLE && VIAS_DE_APOYO.length > 0;
