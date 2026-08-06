import { useEffect, useState } from "react";

/**
 * Tracks `<html data-theme>`, toggled by AppLayout's theme button. No state
 * lives in React for the theme itself (it's a plain DOM attribute), so this
 * is the one place that observes it — anything that needs to render
 * differently per theme (canvas-based charts, mainly) reads from here
 * instead of assuming dark.
 */
export function useIsDarkTheme(): boolean {
  const [isDark, setIsDark] = useState(
    () => document.documentElement.dataset.theme !== "light",
  );

  useEffect(() => {
    const root = document.documentElement;
    const observer = new MutationObserver(() => {
      setIsDark(root.dataset.theme !== "light");
    });
    observer.observe(root, { attributes: true, attributeFilter: ["data-theme"] });
    return () => observer.disconnect();
  }, []);

  return isDark;
}
