import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#1d4ed8", hover: "#1e40af" },
        success: "#16a34a",
        danger: "#dc2626",
        warning: "#d97706",
      },
    },
  },
  plugins: [],
};

export default config;
