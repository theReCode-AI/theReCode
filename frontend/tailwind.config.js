import flowbitePlugin from "flowbite/plugin";
import flowbiteReact from "flowbite-react/plugin/tailwindcss";

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    "node_modules/flowbite-react/lib/esm/**/*.js",
    ".flowbite-react/class-list.json",
  ],
  theme: {
    extend: {},
  },
  plugins: [flowbitePlugin, flowbiteReact],
};
