export const conflictFieldLabel = (field: string) => {
  if (field === 'issue_date' || field === 'document_date') return 'Issue date'
  if (field === 'title') return 'Title'
  if (field === 'correspondent') return 'Correspondent'
  if (field === 'tags') return 'Tags'
  if (field === 'note') return 'Note'
  return field
}

export const conflictValue = (value: unknown) => {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}
