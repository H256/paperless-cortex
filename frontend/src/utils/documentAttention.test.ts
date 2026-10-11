import { describe, expect, it } from 'vitest'
import { attentionBadges, issueDateIsImportDate } from './documentAttention'
import type { DocumentRow } from '../services/documents'

const doc = (extra: Partial<DocumentRow>): DocumentRow => ({ id: 1, title: 'd', ...extra })

describe('attentionBadges', () => {
  it('flags a missing correspondent and an issue date equal to the import date', () => {
    const badges = attentionBadges(
      doc({ created: '2026-09-20', added: '2026-09-20T08:00:00+00:00', review_status: 'unreviewed' }),
    )
    expect(badges.map((badge) => badge.key)).toEqual(['no_correspondent', 'import_date'])
  })

  it('does not flag documents that have a correspondent and a real date', () => {
    const badges = attentionBadges(
      doc({
        correspondent: 4,
        document_date: '2026-09-01',
        added: '2026-09-20T08:00:00+00:00',
        review_status: 'unreviewed',
      }),
    )
    expect(badges).toEqual([])
  })

  it('counts a pending (locally assigned) correspondent as present', () => {
    const badges = attentionBadges(
      doc({ pending_correspondent_name: 'ACME', review_status: 'needs_review' }),
    )
    expect(badges.map((badge) => badge.key)).not.toContain('no_correspondent')
  })

  it('never flags reviewed documents', () => {
    expect(
      attentionBadges(
        doc({ created: '2026-09-20', added: '2026-09-20T08:00:00+00:00', review_status: 'reviewed' }),
      ),
    ).toEqual([])
  })

  it('prefers the recognized document date over created', () => {
    expect(
      issueDateIsImportDate(
        doc({ document_date: '2026-09-18', created: '2026-09-20', added: '2026-09-20T08:00:00' }),
      ),
    ).toBe(false)
    expect(issueDateIsImportDate(doc({}))).toBe(false)
  })
})
