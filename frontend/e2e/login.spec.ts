/**
 * E2E Test 1: Login Flow
 * Verifies: login form → API call → token storage → redirect
 */
import { test, expect } from '@playwright/test'

test.describe('Login Flow', () => {
  test('merchant login succeeds with correct credentials', async ({ page }) => {
    await page.goto('/login')
    await expect(page.locator('h2')).toContainText('商户工作台')

    // Fill credentials
    await page.fill('input[placeholder="用户名"]', 'admin')
    await page.fill('input[placeholder="密码"]', '123456')
    await page.click('button:has-text("登 录")')

    // Verify redirect to dashboard
    await page.waitForURL('**/merchant/dashboard**', { timeout: 15000 })
    await expect(page.locator('h3')).toContainText('工作台')
  })

  test('login fails with wrong password', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[placeholder="用户名"]', 'admin')
    await page.fill('input[placeholder="密码"]', 'wrong')
    await page.click('button:has-text("登 录")')

    // Error message should appear
    await expect(page.locator('.el-message--error')).toBeVisible({ timeout: 10000 })
  })

  test('empty form shows validation', async ({ page }) => {
    await page.goto('/login')
    await page.click('button:has-text("登 录")')
    await expect(page.locator('.el-form-item__error')).toBeVisible()
  })

  test('logout redirects to login', async ({ page }) => {
    // Login first
    await page.goto('/login')
    await page.fill('input[placeholder="用户名"]', 'admin')
    await page.fill('input[placeholder="密码"]', '123456')
    await page.click('button:has-text("登 录")')
    await page.waitForURL('**/merchant/dashboard**')

    // Logout via sidebar
    await page.click('text=退出登录')
    await page.waitForURL('**/login')
    await expect(page.locator('h2')).toBeVisible()
  })
})
