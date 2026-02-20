import { expect, test } from '@playwright/test'

test('documents route loads', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/documents$/)
  await expect(page.getByRole('heading', { name: 'Documents', exact: true })).toBeVisible()
})

test('queue route loads', async ({ page }) => {
  await page.goto('/queue')
  await expect(page.getByRole('heading', { name: 'Queue Manager' })).toBeVisible()
})
