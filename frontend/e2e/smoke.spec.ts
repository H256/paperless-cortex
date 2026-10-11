import { expect, test, type Page } from '@playwright/test'

// Stubbed-backend fixtures. The e2e suite serves the SPA via `vite preview`
// with no live API backend; we intercept /api/* at the browser level so the
// highest-risk user-facing flows (document list, writeback dry-run) and the
// error/empty-state paths are covered by real API-backed assertions.
// See issue #171 (AUDIT FE-006).

const json = (page: Page, url: string | RegExp, status: number, body: unknown) =>
  page.route(url, (route) =>
    route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) }),
  )

const stubDocumentsList = (page: Page, status: number) =>
  json(
    page,
    /\/api\/documents\/(\?.*)?$/,
    status,
    {
      count: 2,
      next: null,
      previous: null,
      results: [
        { id: 1, title: 'Fixture Document One', content: null, correspondent: null, document_type: null, document_date: '2026-01-01', created: '2026-01-01T00:00:00Z', modified: '2026-01-01T00:00:00Z', tags: [], correspondent_name: null, review_status: null, local_cached: false, local_overrides: false, has_embeddings: false, has_suggestions: false, has_vision_pages: false },
        { id: 2, title: 'Fixture Document Two', content: null, correspondent: null, document_type: null, document_date: '2026-01-02', created: '2026-01-02T00:00:00Z', modified: '2026-01-02T00:00:00Z', tags: [], correspondent_name: null, review_status: null, local_cached: false, local_overrides: false, has_embeddings: false, has_suggestions: false, has_vision_pages: false },
      ],
    },
  )

const stubTags = (page: Page) => json(page, /\/api\/tags(\?.*)?$/, 200, { results: [] })
const stubCorrespondents = (page: Page) => json(page, /\/api\/correspondents(\?.*)?$/, 200, { results: [] })

const stubWritebackPreview = (page: Page) =>
  json(
    page,
    /\/api\/writeback\/dry-run\/preview(\?.*)?$/,
    200,
    {
      count: 2,
      page: 1,
      page_size: 100,
      items: [
        {
          doc_id: 10,
          changed: true,
          changed_fields: ['title'],
          title: { field: 'title', original: 'Old Title', proposed: 'New Title', changed: true },
          document_date: { field: 'document_date', original: null, proposed: null, changed: false },
          correspondent: { field: 'correspondent', original: null, proposed: null, changed: false },
          tags: { field: 'tags', original: null, proposed: null, changed: false },
          note: { field: 'note', original: null, proposed: null, changed: false },
        },
        {
          doc_id: 11,
          changed: false,
          changed_fields: [],
          title: { field: 'title', original: 'Same', proposed: 'Same', changed: false },
          document_date: { field: 'document_date', original: null, proposed: null, changed: false },
          correspondent: { field: 'correspondent', original: null, proposed: null, changed: false },
          tags: { field: 'tags', original: null, proposed: null, changed: false },
          note: { field: 'note', original: null, proposed: null, changed: false },
        },
      ],
    },
  )

const stubWritebackJobs = (page: Page) =>
  json(
    page,
    /\/api\/writeback\/jobs(\?.*)?$/,
    200,
    {
      items: [
        { id: 1, status: 'pending', dry_run: false, docs_selected: 1, docs_changed: 1, calls_count: 1, created_at: '2026-01-01T00:00:00Z', started_at: null, finished_at: null, error: null },
      ],
    },
  )

const stubWritebackHistory = (page: Page) =>
  json(page, /\/api\/writeback\/history(\?.*)?$/, 200, { items: [] })

test('documents route loads', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/documents$/)
  await expect(page.getByRole('heading', { name: 'Documents', exact: true })).toBeVisible()
})

test('queue route loads', async ({ page }) => {
  await page.goto('/queue')
  await expect(page.getByRole('heading', { name: 'Queue Manager' })).toBeVisible()
})

test('documents list renders rows from a stubbed backend', async ({ page }) => {
  await stubDocumentsList(page, 200)
  await stubTags(page)
  await stubCorrespondents(page)
  await page.goto('/')
  await expect(page).toHaveURL(/\/documents$/)
  await expect(page.getByRole('heading', { name: 'Documents', exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open document Fixture Document One' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Open document Fixture Document Two' })).toBeVisible()
})

test('writeback dry-run renders preview items from a stubbed backend', async ({ page }) => {
  await stubWritebackPreview(page)
  await stubWritebackJobs(page)
  await stubWritebackHistory(page)
  await page.goto('/writeback')
  await expect(page.getByRole('heading', { name: 'Writeback' })).toBeVisible()
  await expect(page.getByText('Document 10')).toBeVisible()
  await expect(page.getByText('Document 11')).toBeVisible()
  await expect(page.getByText('changed: title')).toBeVisible()
  await expect(page.getByText('no changes')).toBeVisible()
})

test('API-level errors are surfaced, not silent', async ({ page }) => {
  // Record every app-level API error (the mechanism that drives the user-facing
  // toast) so we can assert a non-2xx response is surfaced rather than silent.
  await page.addInitScript(() => {
    ;(window as unknown as { __appErrors: Array<{ status?: number }> }).__appErrors = []
    window.addEventListener('app-error', (event) => {
      const detail = (event as CustomEvent<{ status?: number }>).detail
      ;(window as unknown as { __appErrors: Array<{ status?: number }> }).__appErrors.push(detail ?? {})
    })
  })
  await stubDocumentsList(page, 500)
  await stubTags(page)
  await stubCorrespondents(page)
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Documents', exact: true })).toBeVisible()
  await page.waitForFunction(
    () => (window as unknown as { __appErrors: Array<{ status?: number }> }).__appErrors.length > 0,
  )
  const status = await page.evaluate(
    () => (window as unknown as { __appErrors: Array<{ status?: number }> }).__appErrors[0]?.status,
  )
  expect(status).toBe(500)
})
