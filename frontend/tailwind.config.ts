import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "var(--color-primary)",
          hover:   "var(--color-primary-hover)",
          dark:    "var(--color-primary-dark)",
          subtle:  "var(--color-primary-subtle)",
          tint:    "var(--color-primary-tint)",
        },
        success: {
          DEFAULT: "var(--color-success)",
          subtle:  "var(--color-success-subtle)",
          dark:    "var(--color-success-dark)",
        },
        danger: {
          DEFAULT: "var(--color-danger)",
          subtle:  "var(--color-danger-subtle)",
          dark:    "var(--color-danger-dark)",
        },
        warning: {
          DEFAULT: "var(--color-warning)",
          subtle:  "var(--color-warning-subtle)",
          dark:    "var(--color-warning-dark)",
        },
        surface: "var(--color-surface)",
        sidebar: "var(--color-sidebar-bg)",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
      },
      borderRadius: {
        md:   "var(--radius-sm)",
        lg:   "var(--radius-md)",
        full: "var(--radius-full)",
      },
      boxShadow: {
        sm:    "var(--shadow-card)",
        modal: "var(--shadow-modal)",
      },
    },
  },
  plugins: [],
};

export default config;
