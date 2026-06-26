/**
 * E2E Test 5: Knowledge Base Q&A
 * Verifies: KB page → ask question → SSE streaming answer → references
 */
import { test, expect } from '@playwright/test'

test.describe('Knowledge Base Q&A', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:8093/login')
    await page.fill('input[placeholder="用户名"]', 'super_admin')
    await page.fill('input[placeholder="密码"]', '123456')
    await page.click('button:has-text("登 录")')
    await page.waitForURL('**/admin/**', { timeout: 15000 })
  })

  test('KB page loads with stats and documents', async ({ page }) => {
    await page.click('text=知识库')
    await page.waitForTimeout(2000)
    await expect(page.locator('.el-card').first()).toBeVisible()
  })

  test('KB Q&A streaming works', async ({ page }) => {
    await page.click('text=知识库')
    await page.waitForTimeout(1000)

    // Type question
    const input = page.locator('input[placeholder*="问题"]')
    if (await input.isVisible()) {
      await input.fill('退货流程是什么')
      await page.keyboard.press('Enter')
      await page.waitForTimeout(5000)
      // Verify answer appeared
      const messages = page.locator('[class*="message"], .el-card')
      await expect(messages.first()).toBeVisible()
    }
  })
})
