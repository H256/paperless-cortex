import type { DocumentRow } from '../services/documents'

export type AttentionBadge = { key: 'no_correspondent' | 'import_date'; label: string; title: string }

const dayOf = (value: unknown): string => (typeof value === 'string' ? value.slice(0, 10) : '')

/** The issue date falls on the import day: Paperless most likely found no date. */
export const issueDateIsImportDate = (doc: DocumentRow): boolean => {
  const issueDay = dayOf(doc.document_date) || dayOf(doc.created)
  const addedDay = dayOf(doc.added)
  return Boolean(issueDay) && issueDay === addedDay
}

/** Why a not-yet-reviewed document needs a closer look (empty for reviewed documents). */
export const attentionBadges = (doc: DocumentRow): AttentionBadge[] => {
  if (doc.review_status === 'reviewed') return []
  const badges: AttentionBadge[] = []
  const hasCorrespondent = Boolean(
    doc.correspondent || doc.correspondent_name || doc.pending_correspondent_name,
  )
  if (!hasCorrespondent) {
    badges.push({
      key: 'no_correspondent',
      label: 'No correspondent',
      title: 'No correspondent is assigned yet',
    })
  }
  if (issueDateIsImportDate(doc)) {
    badges.push({
      key: 'import_date',
      label: 'Date = import date',
      title: 'The issue date equals the import date, Paperless probably found no date',
    })
  }
  return badges
}
