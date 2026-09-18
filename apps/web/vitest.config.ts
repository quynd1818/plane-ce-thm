import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
  oxc: { jsx: { runtime: "automatic" } },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.tsx"],
  },
  resolve: {
    alias: {
      "@/helpers": path.resolve(__dirname, "helpers"),
      "@/app": path.resolve(__dirname, "app"),
      "@": path.resolve(__dirname, "core"),
      "next/navigation": path.resolve(__dirname, "app/compat/next/navigation.ts"),
    },
  },
});
