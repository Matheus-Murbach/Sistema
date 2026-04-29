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
          tint:    "var(--color-success-tint)",
        },
        danger: {
          DEFAULT: "var(--color-danger)",
          hover:   "var(--color-danger-hover)",
          subtle:  "var(--color-danger-subtle)",
          dark:    "var(--color-danger-dark)",
          tint:    "var(--color-danger-tint)",
        },
        warning: {
          DEFAULT: "var(--color-warning)",
          subtle:  "var(--color-warning-subtle)",
          dark:    "var(--color-warning-dark)",
          tint:    "var(--color-warning-tint)",
        },
        tax: {
          icms:       "var(--color-tax-icms)",
          "icms-dark": "var(--color-tax-icms-dark)",
          "icms-tint": "var(--color-tax-icms-tint)",
          pis:        "var(--color-tax-pis)",
          "pis-dark": "var(--color-tax-pis-dark)",
        },
        page:    "var(--color-page-bg)",
        surface: "var(--color-surface)",
        muted:   "var(--color-text-muted)",
        sidebar: {
          DEFAULT: "var(--color-sidebar-bg)",
          text:    "var(--color-sidebar-text)",
          muted:   "var(--color-sidebar-muted)",
          accent:  "var(--color-sidebar-accent)",
        },
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
