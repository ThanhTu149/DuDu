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
const APP_ORIGIN = new URL(BASE_URL).origin;
const ARTIFACT_DIR = path.join(__dirname, "artifacts");
const SAMPLE_CSV = path.join(__dirname, "..", "..", "data", "samples", "don-hang-mau.csv");

function fail(message) {
  throw new Error(message);
}

/**
 * Chờ một điều kiện trong trang bằng cách poll qua `page.evaluate`.
 *
 * Không dùng `page.waitForFunction` của Playwright: một số bản (vd 1.49) chạy predicate
 * bằng eval trong main world, sẽ bị CSP `script-src 'self'` chặn. `page.evaluate` dùng
 * CDP callFunctionOn nên không bị chặn.
 */
async function waitFor(page, predicate, label, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (await page.evaluate(predicate)) return;
    await page.waitForTimeout(120);
  }
  fail(`hết thời gian chờ: ${label}`);
}

async function main() {
  // Dọn ảnh lỗi của lần chạy trước để artifact không gây nhầm lẫn.
  fs.rmSync(ARTIFACT_DIR, { recursive: true, force: true });
  // CI để trống; máy dev có thể chỉ định Chromium sẵn có qua E2E_CHROMIUM
  const launchOptions = process.env.E2E_CHROMIUM ? { executablePath: process.env.E2E_CHROMIUM } : {};
  const browser = await chromium.launch(launchOptions);
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } });
  const pageErrors = [];
  const badResponses = [];
  const consoleErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const text = message.text();
    // Font/CDN bên thứ ba hoặc favicon không phải lỗi của app; CI có thể chặn mạng ngoài.
    if (/fonts\.googleapis\.com|fonts\.gstatic\.com|favicon\.ico/.test(text)) return;
    consoleErrors.push(text);
  });
  page.on("response", (response) => {
    const url = response.url();
    if (response.status() >= 400 && url.startsWith(APP_ORIGIN) && !url.endsWith("/favicon.ico")) {
      badResponses.push(`${response.status()} ${url}`);
    }
  });

  const steps = [];
  try {
    await page.addInitScript(() => localStorage.setItem("dudu_intro_seen", "1"));
    const documentResponse = await page.goto(BASE_URL, { waitUntil: "networkidle" });

    // 0. Header bảo mật + kiểm tra a11y cơ bản (ảnh có alt, nút có tên, id không trùng)
    const csp = documentResponse?.headers()["content-security-policy"] || "";
    if (!csp.includes("default-src 'self'")) fail(`thiếu Content-Security-Policy: ${csp}`);
    const a11yIssues = await page.evaluate(() => {
      const issues = [];
      if (document.documentElement.lang !== "vi") issues.push("html thiếu lang=vi");
      for (const image of document.querySelectorAll("img")) {
        if (!image.hasAttribute("alt")) issues.push(`img thiếu alt: ${image.getAttribute("src")}`);
      }
      for (const button of document.querySelectorAll("button")) {
        const name = (button.textContent || "").trim()
          || button.getAttribute("aria-label") || button.getAttribute("title");
        if (!name) issues.push(`button thiếu tên: #${button.id || "(không id)"}`);
      }
      const ids = [...document.querySelectorAll("[id]")].map((element) => element.id);
      const duplicates = ids.filter((id, index) => ids.indexOf(id) !== index);
      if (duplicates.length) issues.push(`id trùng: ${[...new Set(duplicates)].join(", ")}`);
      return issues;
    });
    if (a11yIssues.length) fail(`a11y: ${a11yIssues.join(" | ")}`);
    steps.push("csp+a11y");

    // 1. Lập kế hoạch mặc định
    await page.click("#plan-btn");
    await waitFor(
      page,
      () => (document.querySelector("#kpi-note")?.textContent || "").includes("48 điểm giao"),
      "kế hoạch 48 đơn",
    );
    steps.push("plan-48");

    // 2. Mở lịch sử và khôi phục bản ghi đầu tiên
    await page.click("#history-btn");
    await page.waitForSelector("#modal:not([hidden]) .history-item", { timeout: 15000 });
    const historyCount = await page.locator(".history-item").count();
    if (historyCount < 1) fail("lịch sử không có bản ghi nào");
    await page.click(".history-item");
    await waitFor(page, () => document.querySelector("#modal")?.hidden === true, "đóng modal lịch sử", 15000);
    await waitFor(
      page,
      () => (document.querySelector("#toast")?.textContent || "").includes("khôi phục"),
      "toast khôi phục",
      15000,
    );
    steps.push("history-restore");

    // 3. Nhập CSV mẫu
    if (!fs.existsSync(SAMPLE_CSV)) fail(`không thấy file mẫu: ${SAMPLE_CSV}`);
    await page.setInputFiles("#import-file", SAMPLE_CSV);
    await waitFor(
      page,
      () => (document.querySelector("#kpi-note")?.textContent || "").includes("12 điểm giao"),
      "kế hoạch nhập CSV 12 đơn",
    );
    const toast = await page.evaluate(() => document.querySelector("#toast")?.textContent.trim() || "");
    if (!toast.includes("Đã nhập 12 đơn")) fail(`toast nhập CSV không đúng: ${toast}`);
    steps.push("csv-import");

    if (pageErrors.length) fail(`lỗi JS: ${pageErrors.join(" | ")}`);
    if (consoleErrors.length) fail(`console error: ${consoleErrors.join(" | ")}`);
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
        consoleErrors,
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
      consoleErrors,
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




