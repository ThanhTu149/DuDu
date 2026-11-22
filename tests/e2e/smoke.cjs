/**
 * Smoke test end-to-end cho giao diện DuDu.
 *
 * Chạy khi server đã sẵn sàng:
 *   node tests/e2e/smoke.cjs
 *
 * Biến môi trường:
 *   BASE_URL  mặc định http://127.0.0.1:8000
 *
 * Kiểm tra: lập kế hoạch 48 đơn → mở lịch sử → khôi phục kế hoạch → nhập CSV mẫu (12 đơn).
 * Lỗi JS trên trang hoặc response >= 400 đều làm test fail; ảnh chụp khi fail nằm trong
 * tests/e2e/artifacts/.
 */

const path = require("path");
const fs = require("fs");
const { chromium } = require("playwright");

const BASE_URL = process.env.BASE_URL || "http://127.0.0.1:8000";
const ARTIFACT_DIR = path.join(__dirname, "artifacts");
const SAMPLE_CSV = path.join(__dirname, "..", "..", "data", "samples", "don-hang-mau.csv");

function fail(message) {
  throw new Error(message);
}

async function main() {
  // CI để trống; máy dev có thể chỉ định Chromium sẵn có qua E2E_CHROMIUM
  const launchOptions = process.env.E2E_CHROMIUM ? { executablePath: process.env.E2E_CHROMIUM } : {};
  const browser = await chromium.launch(launchOptions);
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
  const pageErrors = [];
  const badResponses = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400) {
      badResponses.push(`${response.status()} ${response.url()}`);
    }
  });

  const steps = [];
  try {
    await page.addInitScript(() => localStorage.setItem("dudu_intro_seen", "1"));
    await page.goto(BASE_URL, { waitUntil: "networkidle" });

    // 1. Lập kế hoạch mặc định
    await page.click("#plan-btn");
    await page.waitForFunction(
      () => (document.querySelector("#kpi-note")?.textContent || "").includes("48 điểm giao"),
      null,
      { timeout: 30000 },
    );
    steps.push("plan-48");

    // 2. Mở lịch sử và khôi phục bản ghi đầu tiên
    await page.click("#history-btn");
    await page.waitForSelector("#modal:not([hidden]) .history-item", { timeout: 15000 });
    const historyCount = await page.locator(".history-item").count();
    if (historyCount < 1) fail("lịch sử không có bản ghi nào");
    await page.click(".history-item");
    await page.waitForFunction(() => document.querySelector("#modal")?.hidden === true, null, { timeout: 15000 });
    await page.waitForFunction(
      () => (document.querySelector("#toast")?.textContent || "").includes("khôi phục"),
      null,
      { timeout: 15000 },
    );
    steps.push("history-restore");

    // 3. Nhập CSV mẫu
    if (!fs.existsSync(SAMPLE_CSV)) fail(`không thấy file mẫu: ${SAMPLE_CSV}`);
    await page.setInputFiles("#import-file", SAMPLE_CSV);
    await page.waitForFunction(
      () => (document.querySelector("#kpi-note")?.textContent || "").includes("12 điểm giao"),
      null,
      { timeout: 30000 },
    );
    const toast = await page.evaluate(() => document.querySelector("#toast")?.textContent.trim() || "");
    if (!toast.includes("Đã nhập 12 đơn")) fail(`toast nhập CSV không đúng: ${toast}`);
    steps.push("csv-import");

    if (pageErrors.length) fail(`lỗi JS: ${pageErrors.join(" | ")}`);
    if (badResponses.length) fail(`response lỗi: ${badResponses.join(" | ")}`);

    console.log(JSON.stringify({ ok: true, baseUrl: BASE_URL, steps, historyCount }));
  } catch (error) {
    fs.mkdirSync(ARTIFACT_DIR, { recursive: true });
    try {
      await page.screenshot({ path: path.join(ARTIFACT_DIR, "failure.png"), fullPage: true });
      fs.writeFileSync(path.join(ARTIFACT_DIR, "failure.json"), JSON.stringify({
        message: error.message,
        steps,
        pageErrors,
        badResponses,
      }, null, 2));
    } catch {
      /* bỏ qua lỗi chụp ảnh */
    }
    console.error(JSON.stringify({
      ok: false,
      message: error.message,
      steps,
      pageErrors,
      badResponses,
      artifact: ARTIFACT_DIR,
    }, null, 2));
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});

