// @vitest-environment jsdom
import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

let DuplicatesView: unknown

vi.mock('vue-router', () => ({
  RouterLink: {
    props: ['to'],
    template: '<a :href="to"><slot /></a>',
  },
}))

const push = vi.fn()
vi.mock('../stores/toastStore', () => ({
  useToastStore: () => ({ push }),
}))

const pair = {
  doc_a_id: 1,
  doc_b_id: 2,
  score: 0.95,
  level: 'very_likely',
  embedding_score: 0.97,
  text_score: 0.83,
  keys_score: 1,
  meta_score: 1,
  signals: { key_conflict: false },
}

const groups = ref([
  {
    group_id: 1,
    doc_ids: [1, 2],
    best_score: 0.95,
    level: 'very_likely',
    documents: [
      { id: 1, title: 'Invoice', page_count: 1 },
      { id: 2, title: 'Invoice (scan)', page_count: 1 },
    ],
    pairs: [pair],
  },
])
const ignored = ref<unknown[]>([])
const load = vi.fn(async () => undefined)
const startScan = vi.fn(async () => ({ queued: true, docs: 4, enqueued: 4 }))
const setIgnored = vi.fn(async () => true)

vi.mock('../composables/useDuplicates', () => ({
  useDuplicates: () => ({
    groups,
    ignored,
    loading: ref(false),
    scanning: ref(false),
    error: ref(''),
    load,
    startScan,
    setIgnored,
  }),
}))

describe('DuplicatesView', () => {
  beforeAll(async () => {
    DuplicatesView = (await import('./DuplicatesView.vue')).default
  })

  beforeEach(() => {
    vi.clearAllMocks()
    ignored.value = []
  })

  it('renders groups and ignores a pair', async () => {
    const wrapper = mount(DuplicatesView as never)
    await flushPromises()
    expect(load).toHaveBeenCalledWith('check')
    expect(wrapper.findAll('[data-test="duplicate-group"]')).toHaveLength(1)
    expect(wrapper.text()).toContain('Very likely')
    expect(wrapper.text()).toContain('Invoice (scan)')

    await wrapper.find('[data-test="ignore-pair"]').trigger('click')
    await flushPromises()
    expect(setIgnored).toHaveBeenCalledWith(pair, true)
    expect(load).toHaveBeenCalledTimes(2)
  })

  it('lists ignored pairs and restores them', async () => {
    ignored.value = [{ ...pair, ignored: true, documents: [{ id: 1, title: 'Invoice' }] }]
    const wrapper = mount(DuplicatesView as never)
    await wrapper.find('[data-test="tab-ignored"]').trigger('click')
    expect(wrapper.findAll('[data-test="ignored-pair"]')).toHaveLength(1)

    await wrapper.find('[data-test="unignore-pair"]').trigger('click')
    await flushPromises()
    expect(setIgnored).toHaveBeenCalledWith(expect.objectContaining({ doc_a_id: 1 }), false)
  })

  it('queues a scan', async () => {
    const wrapper = mount(DuplicatesView as never)
    await wrapper.find('[data-test="scan"]').trigger('click')
    await flushPromises()
    expect(startScan).toHaveBeenCalled()
    expect(push).toHaveBeenCalledWith(expect.stringContaining('queued'), 'success')
  })
})
