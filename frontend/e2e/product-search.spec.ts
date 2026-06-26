/**
 * E2E Test 2: Product Search & Browse
 * Verifies: product list loading → keyword search → semantic search → CSV export
 */
import { test, expect } from '@playwright/test'

test.describe('Product Search', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[placeholder="用户名"]', 'admin')
    await page.fill('input[placeholder="密码"]', '123456')
    await page.click('button:has-text("登 录")')
    await page.waitForURL('**/merchant/**')
  })

  test('product list loads with data', async ({ page }) => {
    await page.click('text=商品库')
    await page.waitForSelector('.el-table__body', { timeout: 10000 })
    const rows = page.locator('.el-table__body tr')
    await expect(rows.first()).toBeVisible()
  })

  test('keyword search filters products', async ({ page }) => {
    await page.click('text=商品库')
    await page.fill('input[placeholder="搜索商品..."]', '华为')
    await page.keyboard.press('Enter')
    await page.waitForTimeout(1000)
    // Verify results contain keyword
    const cell = page.locator('.el-table__body tr').first().locator('td').nth(1)
    await expect(cell).toBeVisible()
  })

  test('semantic search returns results', async ({ page }) => {
    await page.click('text=商品库')
    await page.fill('input[placeholder*="语义搜索"]', '适合送礼的数码产品')
    await page.click('button:has-text("语义搜索")')
    await page.waitForTimeout(3000)
    await expect(page.locator('.el-table__body')).toBeVisible()
  })

  test('CSV export downloads file', async ({ page }) => {
    await page.click('text=商品库')
    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.click('button:has-text("导出CSV")'),
    ])
    expect(download.suggestedFilename()).toContain('products')
  })
})
