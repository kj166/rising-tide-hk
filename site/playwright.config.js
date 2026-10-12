import { defineConfig } from "@playwright/test";

// Smoke tests against two static builds: build/ (SHOW_LANDSD_AERIAL default true) and build-noaerial/ (false).
// `npm run test:e2e` builds both first. Maps need network access (OpenFreeMap tiles, Google Fonts).
const chrome = { channel: "chrome", launchOptions: { args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"] } };
// Public-build check (scripts/build_public.py --verify): E2E_DIR=<build dir> E2E_BASE=/rising-tide-hk runs the
// "noaerial" project only, against that build served under the base path like GitHub Pages.
const pub = process.env.E2E_DIR;
const base = process.env.E2E_BASE ?? "";
export default defineConfig(pub ? {
  testDir: "tests",
  timeout: 90_000,
  retries: 0,
  workers: 2,
  reporter: [["list"]],
  projects: [{ name: "noaerial", use: { ...chrome, baseURL: `http://localhost:4183${base}/`, viewport: { width: 1440, height: 900 } } }],
  webServer: [{ command: `node scripts/serve.mjs ${pub} 4183 ${base}`, port: 4183, reuseExistingServer: false }],
} : {
  testDir: "tests",
  timeout: 90_000,
  retries: 0,
  workers: 2,
  reporter: [["list"]],
  projects: [
    { name: "aerial", use: { ...chrome, baseURL: "http://localhost:4180", viewport: { width: 1440, height: 900 } } },
    { name: "noaerial", use: { ...chrome, baseURL: "http://localhost:4181", viewport: { width: 1440, height: 900 } } },
  ],
  webServer: [
    { command: "node scripts/serve.mjs build 4180", port: 4180, reuseExistingServer: true },
    { command: "node scripts/serve.mjs build-noaerial 4181", port: 4181, reuseExistingServer: true },
  ],
});
