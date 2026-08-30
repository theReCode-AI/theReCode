import { DarkThemeToggle } from "flowbite-react";

/** Flowbite dark/light toggle — persists via localStorage (`flowbite-theme-mode`). */
export function ThemeToggle({ className }: { className?: string }) {
  return (
    <DarkThemeToggle
      className={className}
      aria-label="Toggle dark mode"
      title="Toggle dark mode"
    />
  );
}
