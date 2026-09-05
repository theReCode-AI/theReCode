import path from "node:path";
import { defineConfig, loadEnv } from "vite"; // 1. Import loadEnv
import react from "@vitejs/plugin-react";
import flowbiteReact from "flowbite-react/plugin/vite";

export default defineConfig(({ mode }) => {
  // 2. Load the env file based on the current mode (development/production)
  // Passing '' as the third argument loads ALL variables regardless of prefix
  const env = loadEnv(mode, process.cwd(), '');

  console.log("Loaded environment variables:", env.VITE_API_BASE_URL);

  return {
    plugins: [react(), flowbiteReact()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/api": {
          // 3. Access your variable using env.VITE_API_BASE_URL
          target: env.VITE_API_BASE_URL+"/api/v1" || "http://localhost:8000/api/v1",
          changeOrigin: true,
        },
      },
    },
  };
});
