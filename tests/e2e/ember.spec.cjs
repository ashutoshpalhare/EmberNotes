const { test, expect } = require('@playwright/test');

test('notes editor previews Markdown safely, autosaves, and exports data', async ({ page }) => {
  await page.goto('/accounts/login/');
  await page.getByLabel(/username/i).fill('e2e-user');
  await page.getByLabel(/password/i).fill('E2E-strong-pass-123!');
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/$/);

  await page.getByRole('button', { name: /new note/i }).click();
  await expect(page).toHaveURL(/\/notes\/\d+\/$/);
  await page.getByLabel('Note title').fill('Browser test note');
  await page.getByLabel('Note body').fill('# Hello from Playwright\n\n**Bold text**\n\n<script>window.pwned = true</script>');
  await page.getByRole('button', { name: 'Preview' }).click();
  await expect(page.locator('#markdown-preview h1')).toHaveText('Hello from Playwright');
  await expect(page.locator('#markdown-preview strong')).toHaveText('Bold text');
  await expect(page.locator('#markdown-preview script')).toHaveCount(0);
  expect(await page.evaluate(() => window.pwned)).toBeUndefined();

  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await expect(page.getByLabel('Note body')).toBeVisible();
  await expect(page.getByText('All changes saved')).toBeVisible({ timeout: 10000 });

  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('link', { name: /export notes/i }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('ember-notes-export.json');
});

test('import page is reachable and documents safe additive import', async ({ page }) => {
  await page.goto('/accounts/login/');
  await page.getByLabel(/username/i).fill('e2e-user');
  await page.getByLabel(/password/i).fill('E2E-strong-pass-123!');
  await page.getByRole('button', { name: /sign in/i }).click();
  await page.getByRole('link', { name: /import notes/i }).click();
  await expect(page.getByRole('heading', { name: 'Import your notes' })).toBeVisible();
  await expect(page.getByText(/existing notes are not overwritten/i)).toBeVisible();
});
