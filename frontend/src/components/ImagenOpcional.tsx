import { useState } from "react";

/**
 * Una imagen que desaparece si el fichero no está.
 *
 * 2026-09-05. Estas tres --el escudo del club y el sello de proveedor
 * certificado-- se sirven desde `public/` y no se importan como módulo a
 * propósito: un `import` de Vite exige que el fichero exista al compilar, así
 * que si falta, la aplicación entera deja de construirse. Sirviéndolas por
 * ruta, lo peor que pasa es que no se vea una imagen.
 *
 * Sin el `onError` quedaría el icono de imagen rota, que es peor que nada:
 * parece que la aplicación falla cuando lo único que pasa es que falta un
 * fichero.
 */
export function ImagenOpcional({
  src,
  alt,
  className,
  width,
  height,
}: {
  src: string;
  alt: string;
  className?: string;
  width: number;
  height: number;
}) {
  const [falta, setFalta] = useState(false);
  if (falta) return null;
  return (
    <img
      src={src}
      alt={alt}
      width={width}
      height={height}
      loading="lazy"
      onError={() => setFalta(true)}
      className={className}
    />
  );
}

/** Dónde viven. En un solo sitio para que las tres pantallas no puedan
 *  discrepar sobre el nombre del fichero. */
export const ESCUDO = "/escudo.jpg";
export const SELLO_PROVEEDOR = "/chpp.png";
