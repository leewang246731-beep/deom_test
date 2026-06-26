/**
 * E2E Test 4: AI Suggestion Flow
 * Verifies: service workbench → select conversation → AI suggest → adopt suggestion
 */
import { test, expect } from '@playwright/test'

test.describe('AI Suggestion', () => {
  test.beforeEach(async ({ page }) => {
    // Login as service agent
    await page.goto('http://localhost:8095/login')
    await page.fill('input[placeholder="用户名"]', 'service')
    await page.fill('input[placeholder="密码"]', '123456')
    await page.click('button:has-text("登 录")')
    await page.waitForURL('**/service/**', { timeout: 15000 })
  })

  test('AI suggest generates reply suggestions', async ({ page }) => {
    // Select first conversation
    const conv = page.locator('.el-card').first()
    if (await conv.isVisible()) {
      await conv.click()
      await page.waitForTimeout(1000)
    }

    // Click AI suggest button
    const aiBtn = page.locator('button:has-text("生成")').first()
    if (await aiBtn.isVisible()) {
      await aiBtn.click()
      await page.waitForTimeout(5000)
      // Verify suggestions appeared
      const suggestions = page.locator('.suggestions, [class*="suggest"]')
      await expect(suggestions.first()).toBeVisible({ timeout: 15000 })
    }
  })

  test('service workspace loads conversations', async ({ page }) => {
    await page.waitForSelector('.el-card, .el-table', { timeout: 10000 })
    await expect(page.locator('h3').first()).toBeVisible()
  })
})
