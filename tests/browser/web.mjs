import { chromium } from "playwright";
import { mkdirSync, existsSync } from "node:fs";
const artifacts = process.env.E2E_ARTIFACTS || "work/web-browser";
mkdirSync(artifacts, { recursive: true });
const executablePath =
  process.env.E2E_CHROMIUM_BIN ||
  ["/usr/bin/chromium", "/usr/bin/google-chrome"].find(existsSync);
for (let i = 0; i < 40; i++) {
  try {
    if ((await fetch("http://127.0.0.1:18030/health")).ok) break;
  } catch {}
  await new Promise((r) => setTimeout(r, 500));
}
const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ["--no-sandbox"],
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  timezoneId: "America/Sao_Paulo",
});
const page = await context.newPage(),
  errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => {
  if (m.type() === "error" && !m.text().includes("401")) errors.push(m.text());
});
await page.goto("http://127.0.0.1:18030");
await page.getByRole("heading", { name: "Entre na sua operação" }).waitFor();
await page.locator("#username").fill("SyntheticAdmin");
await page.locator("#password").fill("Initial-Test-Pass12!");
await page.getByRole("button", { name: "Entrar na central" }).click();
await page.getByRole("heading", { name: "Uma senha só sua" }).waitFor();
await page.locator("#current_password").fill("Initial-Test-Pass12!");
await page.locator("#new_password").fill("Personal-Test-Pass34!");
await page.locator("#confirm_password").fill("Personal-Test-Pass34!");
await page.getByRole("button", { name: "Salvar e continuar" }).click();
await page.getByRole("heading", { name: "Dashboard", exact: true }).waitFor();
await page.waitForTimeout(300);
await page.screenshot({
  path: artifacts + "/dashboard-desktop.png",
  fullPage: true,
});
await page.getByRole("link", { name: "Relatórios", exact: true }).click();
await page.locator("#results-card tbody tr").first().waitFor();
await page.locator("#next-page").click();
await page.waitForFunction(
  () => document.querySelector(".page-btn.active")?.textContent === "2",
);
for (const format of ["csv", "pdf"]) {
  const event = page.waitForEvent("download");
  await page.locator("#export-" + format).click();
  const download = await event;
  await download.saveAs(artifacts + "/report." + format);
}
await page.getByRole("link", { name: "Clientes rsyslog", exact: true }).click();
await page
  .getByRole("heading", { name: "Clientes rsyslog", exact: true })
  .waitFor();
await page.getByRole("button", { name: "Novo cliente" }).click();
await page.locator("#name").fill("Cliente do teste E2E");
await page.locator("#source_ip").fill("192.168.50.4");
await page.getByRole("button", { name: "Salvar cliente" }).click();
await page
  .getByRole("heading", { name: "Cliente do teste E2E", exact: true })
  .waitFor();
await page.screenshot({
  path: artifacts + "/clients-desktop.png",
  fullPage: true,
});
await page.getByRole("link", { name: "Usuários", exact: true }).click();
await page.getByRole("heading", { name: "Usuários", exact: true }).waitFor();
await page.getByRole("button", { name: "Novo usuário" }).click();
await page.locator("#user-username").fill("NovoOperador");
await page.locator("#temp-password").fill("Temporary-Test-Pass56!");
await page.getByRole("button", { name: "Salvar usuário" }).click();
await page.getByText("NovoOperador", { exact: true }).waitFor();
await page.locator("#nav-toggle").click();
if (
  !(await page
    .locator(".layout")
    .evaluate((e) => e.classList.contains("collapsed")))
)
  throw Error("Sidebar did not collapse");
await page.setViewportSize({ width: 390, height: 844 });
await page.locator("#nav-toggle").click();
await page.getByRole("link", { name: "Dashboard", exact: true }).click();
await page.getByRole("heading", { name: "Dashboard", exact: true }).waitFor();
await page.screenshot({
  path: artifacts + "/dashboard-mobile.png",
  fullPage: true,
});
if (
  await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
)
  throw Error("Mobile horizontal overflow");
await page.locator("#nav-toggle").click();
await page.getByRole("link", { name: "Relatórios", exact: true }).click();
await page.locator("#results-card tbody tr").first().waitFor();
await page.screenshot({
  path: artifacts + "/reports-mobile.png",
  fullPage: true,
});
if (
  await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)
)
  throw Error("Mobile report overflow");
console.log(
  JSON.stringify({
    browser: "PASS",
    scenarios: [
      "forced-password",
      "dashboard",
      "pagination",
      "csv",
      "pdf",
      "client-create",
      "user-create",
      "sidebar",
      "mobile",
    ],
    errors,
  }),
);
await browser.close();
if (errors.length) process.exitCode = 1;
