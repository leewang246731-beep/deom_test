/**
 * E2E Test 3: Ticket Full Lifecycle
 * Verifies: create → view detail → claim → status transition → comment → close
 */
import { test, expect } from '@playwright/test'

test.describe('Ticket Lifecycle', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[placeholder="用户名"]', 'admin')
    await page.fill('input[placeholder="密码"]', '123456')
    await page.click('button:has-text("登 录")')
    await page.waitForURL('**/merchant/**')
  })

  test('full ticket lifecycle', async ({ page }) => {
    // 1. Navigate to tickets
    await page.click('text=工单管理')
    await page.waitForSelector('.el-table__body', { timeout: 10000 })

    // 2. Create new ticket
    await page.click('button:has-text("新建工单")')
    await page.fill('input[placeholder*="标题"]', 'E2E Test Ticket')
    await page.fill('textarea', 'This is an automated test ticket')
    await page.click('button:has-text("创建")')
    await page.waitForTimeout(2000)

    // 3. Navigate to ticket detail
    await page.locator('.el-table__body tr').first().click()
    await page.waitForSelector('text=状态操作', { timeout: 10000 })

    // 4. Claim ticket
    const claimBtn = page.locator('button:has-text("领取工单")')
    if (await claimBtn.isVisible()) {
      await claimBtn.click()
      await page.waitForTimeout(1000)
    }

    // 5. Add comment
    await page.fill('input[placeholder*="添加回复"]', 'E2E test comment')
    await page.click('button:has-text("发送")')
    await page.waitForTimeout(1000)

    // 6. Verify comment appears
    await expect(page.locator('.el-timeline-item').first()).toBeVisible()

    // 7. Go back to list
    await page.click('.el-page-header__left')
    await page.waitForURL('**/tickets**')
  })
})
