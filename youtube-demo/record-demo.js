/**
 * HAMSVIC Office — Product Demo Browser Recording
 * Records a 1920x1080 browser session demonstrating key features.
 * Uses Django admin login for reliable session, then navigates user-facing pages.
 * Outputs: recordings/raw-demo.webm
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const BASE = 'http://localhost:8000';
const RECORDINGS_DIR = path.join(__dirname, 'recordings');
const SCREENSHOT_DIR = path.join(__dirname, 'screenshots');

fs.mkdirSync(RECORDINGS_DIR, { recursive: true });
fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

let screenshotIndex = 0;
async function screenshot(page, label) {
  screenshotIndex++;
  const name = `${String(screenshotIndex).padStart(2, '0')}-${label}.png`;
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, name), fullPage: false });
  console.log(`  [screenshot] ${name}`);
}

async function main() {
  console.log('=== HAMSVIC Office Demo Recording ===\n');

  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    recordVideo: { dir: RECORDINGS_DIR, size: { width: 1920, height: 1080 } },
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
  });

  const page = await context.newPage();

  try {
    // ── SCENE 1: Landing Page ──
    console.log('[Scene 1] Landing Page');
    await page.goto(BASE + '/', { waitUntil: 'networkidle', timeout: 15000 });
    await sleep(4000);
    await screenshot(page, 'landing-page');

    await page.evaluate(() => window.scrollTo({ top: 600, behavior: 'smooth' }));
    await sleep(2500);
    await screenshot(page, 'landing-features');

    await page.evaluate(() => window.scrollTo({ top: 1200, behavior: 'smooth' }));
    await sleep(2500);
    await screenshot(page, 'landing-stats');

    // ── SCENE 2: Login Page (show OTP flow visually) ──
    console.log('[Scene 2] Login Page');
    await page.goto(BASE + '/accounts/login/', { waitUntil: 'networkidle' });
    await sleep(2000);
    await screenshot(page, 'login-page');

    // Type email slowly for demo effect
    const emailInput = page.locator('input[name="identifier"]');
    await emailInput.click();
    await sleep(500);
    await emailInput.type('demo@hamsvic.com', { delay: 80 });
    await sleep(1500);
    await screenshot(page, 'login-email-typed');

    // Submit to get OTP popup
    await page.locator('button[type="submit"]').click();
    await sleep(3000);

    // Capture OTP popup screenshot if visible
    try {
      const otpPopup = page.locator('#otpCodeDisplay');
      await otpPopup.waitFor({ timeout: 5000 });
      await screenshot(page, 'otp-popup');
      await sleep(2500);
    } catch { /* popup may not show */ }

    // Take verify page screenshot if we're there
    try {
      await page.waitForURL('**/verify-otp/**', { timeout: 3000 });
      await screenshot(page, 'verify-otp-page');
    } catch { /* may still be on login page with popup */ }

    // ── RELIABLE LOGIN via Django Admin ──
    console.log('  [Login] Using Django admin for reliable session...');
    await page.goto(BASE + '/admin/login/', { waitUntil: 'networkidle' });
    await sleep(500);
    await page.fill('#id_username', 'admin');
    await page.fill('#id_password', 'DemoPass123!');
    await page.click('[type="submit"]');
    await sleep(3000);
    console.log(`  [Login] After admin login: ${page.url()}`);

    // Navigate to user dashboard
    await page.goto(BASE + '/dashboard/', { waitUntil: 'networkidle' });
    await sleep(2000);
    const url = page.url();
    console.log(`  [Login] Dashboard URL: ${url}`);

    // ── SCENE 3: Dashboard ──
    console.log('[Scene 3] Dashboard');
    await page.goto(BASE + '/dashboard/', { waitUntil: 'networkidle' });
    await sleep(3000);
    await screenshot(page, 'dashboard');

    await page.evaluate(() => window.scrollTo({ top: 400, behavior: 'smooth' }));
    await sleep(2500);
    await screenshot(page, 'dashboard-modules');

    await page.evaluate(() => window.scrollTo({ top: 800, behavior: 'smooth' }));
    await sleep(2000);
    await screenshot(page, 'dashboard-bottom');

    // ── SCENE 4: Create New Estimate ──
    console.log('[Scene 4] New Estimate');
    await page.goto(BASE + '/datas/', { waitUntil: 'networkidle' });
    await sleep(2500);
    await screenshot(page, 'estimate-work-type');

    // Select "Original Work"
    const originalCard = page.locator('#card-original');
    if (await originalCard.count() > 0) {
      await originalCard.click();
      await sleep(2000);
      await screenshot(page, 'estimate-original-selected');
    }

    // Select "Electrical" category
    const electricalBtn = page.locator('#btn-electrical');
    if (await electricalBtn.count() > 0) {
      await electricalBtn.click();
      await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
      await sleep(3000);
      await screenshot(page, 'estimate-groups');

      // Browse groups - click the first group card
      const groupCards = page.locator('a.group-card, a.action-card');
      const groupCount = await groupCards.count();
      console.log(`  Found ${groupCount} group cards`);

      if (groupCount > 0) {
        await groupCards.first().click();
        await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
        await sleep(3000);
        await screenshot(page, 'estimate-items');

        // Try to select items
        const toggleBtns = page.locator('.toggle-item-btn, .item-toggle, .add-item-btn');
        const checkboxes = page.locator('input[type="checkbox"]');
        const itemRows = page.locator('.item-row, .item-card, tr[data-item]');

        const toggleCount = await toggleBtns.count();
        const cbCount = await checkboxes.count();
        const rowCount = await itemRows.count();
        console.log(`  Found: ${toggleCount} toggle btns, ${cbCount} checkboxes, ${rowCount} item rows`);

        if (toggleCount > 0) {
          for (let i = 0; i < Math.min(3, toggleCount); i++) {
            await toggleBtns.nth(i).click();
            await sleep(800);
          }
        } else if (cbCount > 0) {
          for (let i = 0; i < Math.min(3, cbCount); i++) {
            await checkboxes.nth(i).click();
            await sleep(800);
          }
        } else if (rowCount > 0) {
          for (let i = 0; i < Math.min(3, rowCount); i++) {
            await itemRows.nth(i).click();
            await sleep(800);
          }
        }
        await sleep(1500);
        await screenshot(page, 'estimate-items-selected');
      }
    }

    // ── SCENE 5: Workslip Module ──
    console.log('[Scene 5] Workslip');
    await page.goto(BASE + '/workslip/', { waitUntil: 'networkidle' });
    await sleep(3000);
    await screenshot(page, 'workslip-home');

    // ── SCENE 6: Bill Module ──
    console.log('[Scene 6] Bill');
    await page.goto(BASE + '/bill/', { waitUntil: 'networkidle' });
    await sleep(3000);
    await screenshot(page, 'bill-page');

    // ── SCENE 7: Self-Formatted Forms ──
    console.log('[Scene 7] Self-Formatted Forms');
    await page.goto(BASE + '/self-formatted/', { waitUntil: 'networkidle' });
    await sleep(3000);
    await screenshot(page, 'self-formatted');

    // ── SCENE 8: Saved Works ──
    console.log('[Scene 8] Saved Works');
    await page.goto(BASE + '/saved-works/', { waitUntil: 'networkidle' });
    await sleep(3000);
    await screenshot(page, 'saved-works');

    // ── SCENE 9: Temporary Works ──
    console.log('[Scene 9] Temporary Works');
    await page.goto(BASE + '/tempworks/', { waitUntil: 'networkidle' });
    await sleep(3000);
    await screenshot(page, 'temp-works');

    // ── SCENE 10: AMC Module ──
    console.log('[Scene 10] AMC');
    await page.goto(BASE + '/amc/', { waitUntil: 'networkidle' });
    await sleep(3000);
    await screenshot(page, 'amc');

    // ── SCENE 11: Letter Settings ──
    console.log('[Scene 11] Letter Settings');
    await page.goto(BASE + '/letter-settings/', { waitUntil: 'networkidle' });
    await sleep(3000);
    await screenshot(page, 'letter-settings');

    await page.evaluate(() => window.scrollTo({ top: 500, behavior: 'smooth' }));
    await sleep(2000);
    await screenshot(page, 'letter-settings-scroll');

    // ── SCENE 12: Pricing Page ──
    console.log('[Scene 12] Pricing');
    await page.goto(BASE + '/subscriptions/pricing/', { waitUntil: 'networkidle' });
    await sleep(3000);
    await screenshot(page, 'pricing');

    await page.evaluate(() => window.scrollTo({ top: 600, behavior: 'smooth' }));
    await sleep(2000);
    await screenshot(page, 'pricing-scroll');

    // ── SCENE 13: User Profile ──
    console.log('[Scene 13] Profile');
    await page.goto(BASE + '/accounts/profile/', { waitUntil: 'networkidle' });
    await sleep(2500);
    await screenshot(page, 'profile');

    // ── SCENE 14: My Subscription ──
    console.log('[Scene 14] My Subscription');
    await page.goto(BASE + '/my-subscription/', { waitUntil: 'networkidle' });
    await sleep(2500);
    await screenshot(page, 'my-subscription');

    // ── SCENE 15: Final Dashboard ──
    console.log('[Scene 15] Final Dashboard');
    await page.goto(BASE + '/dashboard/', { waitUntil: 'networkidle' });
    await sleep(4000);
    await screenshot(page, 'final-dashboard');

    console.log('\n=== Recording complete ===');
  } catch (error) {
    console.error('ERROR during recording:', error.message);
    await screenshot(page, 'error-state').catch(() => {});
  } finally {
    await page.close();
    await context.close();
    await browser.close();
  }

  // Rename video file
  const videos = fs.readdirSync(RECORDINGS_DIR).filter(f => f.endsWith('.webm'));
  if (videos.length > 0) {
    const latest = videos.sort().pop();
    const src = path.join(RECORDINGS_DIR, latest);
    const dst = path.join(RECORDINGS_DIR, 'raw-demo.webm');
    if (src !== dst) {
      try { fs.unlinkSync(dst); } catch {}
      fs.renameSync(src, dst);
    }
    const stats = fs.statSync(dst);
    console.log(`\nVideo saved: recordings/raw-demo.webm (${(stats.size / 1024 / 1024).toFixed(1)} MB)`);
  }
}

main().catch(e => {
  console.error('Fatal error:', e);
  process.exit(1);
});
