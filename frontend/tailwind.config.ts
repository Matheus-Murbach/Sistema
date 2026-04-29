import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#f59e0b", hover: "#d97706" },
        success: "#16a34a",
        danger: "#dc2626",
        warning: "#d97706",
      },
    },
  },
  plugins: [],
};

export default config;
