# Publicidad con Google AdSense

Qué está hecho, qué falta, y en qué orden. Lo de código está terminado; lo que
queda son decisiones y trámites que no se pueden hacer desde aquí.

**Estado: montado y APAGADO.** Sin `VITE_ADSENSE_CLIENT` en el entorno el sitio
no carga un solo script ajeno, no pinta ningún hueco, no genera `ads.txt` y no
enseña la barra de cookies. Encenderlo es poner una variable; apagarlo,
quitarla.

---

## 1. ¿Lo permite CHPP? — comprobado el 2026-10-23

**El Manual CHPP no dice nada sobre publicidad.** Se leyó entero: trata del
logo y el copyright, la seguridad, los ficheros XML y las reglas extra de los
asistentes de mánager. Ni una línea sobre anuncios en el sitio de la
aplicación.

Lo que sí dice, y va a favor:

> *CHPP programs are allowed to charge their users for registration.*

O sea que **monetizar está expresamente permitido**. Lo que no está escrito es
el caso concreto de la publicidad de terceros.

Y lo que hay que mirar con cuidado, porque es por donde podría entrar una
prohibición:

> *Along with the CHPP rules, all approved applications/websites also have to
> comply with the general game rules. This also includes potential
> forums/message boards for the application and its users.*

Las reglas generales prohíben:

> *Making cheating accusations, **advertising for real life goods** (this
> includes referral links from which you may benefit)… **These rules apply to
> all areas of Hattrick.***

**Lectura:** esa prohibición es sobre lo que los USUARIOS publican, y su
alcance declarado son «todas las áreas de Hattrick» — el juego, no el sitio de
una aplicación de terceros. El Manual la extiende a las aplicaciones
ilustrándolo con **foros y tablones**, que es justo donde los usuarios
publican. No hay ninguna regla que prohíba a un CHPP poner anuncios en su
propia web.

**Pero tampoco hay una que lo autorice**, y el Manual exige aprobación previa
de funciones:

> *It is not allowed to start developing applications and/or functions before
> they are properly approved.*

**Qué hacer:** preguntar al equipo CHPP antes de encender la variable. No
porque esté prohibido —no lo está— sino porque el coste de equivocarse es
perder el acceso CHPP, y eso mata el producto entero. Una pregunta por el
canal de CHPP cuesta nada.

Fuentes: [CHPP Manual](https://wiki.hattrick.org/wiki/CHPP_Manual) ·
[Rules](https://wiki.hattrick.org/wiki/Rules) ·
[House Rules](https://wiki.hattrick.org/wiki/House_Rules)

---

## 2. Hace falta un dominio propio

Hoy el sitio vive en `hattrick-lens.onrender.com`, que es un subdominio de
Render. AdSense pide un sitio del que seas dueño, y `ads.txt` tiene que estar
en una raíz que controles — la de `onrender.com` es de Render.

**Esto va antes que solicitar la cuenta.** Comprar el dominio, apuntarlo a
Render, y acordarse de que el callback de OAuth está registrado en Hattrick con
el host actual: **cambiar de dominio obliga a actualizarlo en la aplicación
CHPP** (`CHPP_CALLBACK_URL`) o la conexión deja de funcionar.

---

## 3. Una plataforma de consentimiento certificada

Desde el **16-01-2024** Google exige una CMP certificada (TCF v2.2) para servir
anuncios personalizados en el **EEE y el Reino Unido**, y desde el
**31-07-2024** también en **Suiza**. Sin ella sólo sirve «anuncios limitados».

**La barra que trae HT Lens NO es una CMP certificada.** Es el cimiento
correcto —todo denegado por defecto, nada se carga sin permiso— y sirve para
tráfico fuera de esas zonas.

La salida más simple es la propia de Google («Privacidad y mensajes», dentro de
la cuenta de AdSense): es gratis y está certificada. El código ya la contempla:
con `VITE_ADSENSE_CMP=google` nuestra barra desaparece y manda la suya.

**Ojo a la vuelta de tuerca:** la CMP de Google viaja DENTRO del script de
AdSense, así que en ese modo el script carga antes de preguntar. No es una
fuga: para eso están los cuatro `denied` del Modo de consentimiento v2 en
`index.html`, puestos antes que nada. Google carga, pregunta, y no pone cookies
de publicidad hasta que hay respuesta.

Fuente: [AdSense: CMP certificada](https://support.google.com/adsense/answer/13554116)

---

## 4. El muro de login, y el contenido público

Casi toda la aplicación está detrás del OAuth de Hattrick. **No descalifica**:
Google documenta un *crawler login* para enseñar anuncios en páginas
protegidas, y hay que configurarlo en la cuenta.

Pero la falta de contenido propio sí es la causa más común de rechazo, y era
la nuestra: el rastreador veía una pantalla de «conecta tu club» y dos páginas
legales. **Resuelto el 2026-10-23 abriendo la Wiki en `/guia`**: mil
ochocientas líneas que explican mecánicas de Hattrick y cómo calcula HT Lens,
sin pedir sesión. Medido en el navegador: **57.681 caracteres de texto y 39
encabezados**.

`/wiki` --la de dentro, con barra lateral-- no se tocó. Misma materia, dos
públicos, y cero riesgo para lo que ya funcionaba.

Lo público queda así, todo enlazado desde la bienvenida:

| ruta | qué es |
|---|---|
| `/welcome` | la entrada |
| `/guia` | la Wiki en abierto, el contenido largo |
| `/privacidad` y `/cookies` | las legales |
| `/apoyar` | las formas de apoyar |

Fuente: [AdSense: rastreador bloqueado por login](https://support.google.com/adsense/answer/10035)

---

## 4 bis. Los tres ficheros de la raíz, generados

`ads.txt`, `robots.txt` y `sitemap.xml` los escribe el build, no viven en
`public/`. El motivo es el mismo en los tres: **sólo valen si llevan un dato
real**, y un dato de ejemplo hace daño en silencio.

| sin configurar | con `VITE_SITIO_URL` / `VITE_ADSENSE_CLIENT` |
|---|---|
| `robots.txt` sin línea `Sitemap:` | con ella, apuntando al dominio |
| sin `sitemap.xml` | las cuatro rutas públicas |
| sin `ads.txt` | `google.com, pub-…, DIRECT, f08c47fec0942fa0` |

Un `ads.txt` con un identificador de ejemplo le dice a Google que **nadie está
autorizado a vender este inventario**, y deja de servir anuncios sin romper
nada visible. Y un `Sitemap:` que apunte a un dominio equivocado manda al
rastreador a leer otra cosa. Por eso: o el dato real, o nada.

**Si se abre una pantalla pública nueva**, va en `PUBLICAS` de
`vite.config.ts`. Si no, no la encuentra nadie.

## 5. Encenderlo

Cuando estén resueltos 1 a 4, en el entorno de Render:

```
VITE_ADSENSE_CLIENT=ca-pub-0000000000000000   # el tuyo, 16 dígitos
VITE_ADSENSE_SLOT_BIENVENIDA=0000000000       # el hueco de la bienvenida
VITE_ADSENSE_SLOT_GUIA=0000000000             # el hueco de la Guía
VITE_ADSENSE_CMP=google                       # si usas la CMP de Google
VITE_SITIO_URL=https://tu-dominio.com         # sin barra final: robots y sitemap
```

`ads.txt` se genera solo en el build, con el prefijo correcto (`pub-`, no
`ca-pub-`). Si el identificador no tiene la forma exacta, **no se genera nada y
no se carga nada**: un `ads.txt` a medio rellenar le dice a Google que nadie
está autorizado a vender este inventario, y deja de servir anuncios sin romper
nada visible.

## 6. Dónde vive cada pieza

| fichero | qué hace |
|---|---|
| `frontend/src/config/anuncios.ts` | el interruptor, el cliente, los huecos, quién pregunta |
| `frontend/src/config/consentimiento.ts` | la decisión: guardarla y contársela a Google |
| `frontend/src/components/Consentimiento.tsx` | la barra |
| `frontend/src/components/Anuncio.tsx` | el hueco |
| `frontend/src/pages/PrivacidadPage.tsx` | `/privacidad` y `/cookies` |
| `frontend/index.html` | los `denied` por defecto, antes que nada |
| `frontend/vite.config.ts` | genera `ads.txt`, `robots.txt` y `sitemap.xml` |
| `frontend/src/config/consentimiento.test.ts` | 11 pruebas de la regla que no puede romperse |
| `frontend/src/components/Anuncio.test.tsx` | 6 pruebas de que sin configurar no se pinta nada |

## 7. Añadir un hueco nuevo

Se declara en `HUECOS` de `config/anuncios.ts` —con su `id`, dónde va y la
variable de su `slot`— y se pinta con `<Anuncio hueco="su-id" />`. La lista
corta es a propósito: la política de Google prohíbe anuncios en páginas sin
contenido propio, así que cada hueco debe poder revisarse de un vistazo.
