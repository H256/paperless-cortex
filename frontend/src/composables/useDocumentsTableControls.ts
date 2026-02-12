import type { Ref } from 'vue'

export const useDocumentsTableControls = (
  ordering: Ref<string>,
  page: Ref<number>,
  totalPages: Ref<number>,
  load: () => Promise<void>,
) => {
  const sortDir = (field: string) => {
    const current = ordering.value.replace('-', '')
    if (current !== field) return null
    return ordering.value.startsWith('-') ? 'desc' : 'asc'
  }

  const toggleSort = (field: string) => {
    const dir = sortDir(field)
    if (!dir || dir === 'desc') {
      ordering.value = field
    } else {
      ordering.value = `-${field}`
    }
    page.value = 1
  }

  const onPrevPage = async () => {
    if (page.value <= 1) return
    page.value -= 1
    await load()
  }

  const onNextPage = async () => {
    if (page.value >= totalPages.value) return
    page.value += 1
    await load()
  }

  return {
    toggleSort,
    onPrevPage,
    onNextPage,
  }
}
