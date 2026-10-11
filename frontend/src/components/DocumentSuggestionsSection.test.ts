// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentSuggestionsSection from './DocumentSuggestionsSection.vue'

const mountSection = () =>
  mount(DocumentSuggestionsSection, {
    props: {
      suggestions: {
        vision_ocr: {
          parsed: {
            title: 'Rechnung Teufel',
            date: '2026-09-20',
            correspondent: 'Lautsprecher Teufel GmbH',
            tags: ['Rechnung', 'Einkauf'],
            summary: 'Rechnung ueber Kopfhoerer.',
          },
        },
      },
      suggestionsError: '',
      suggestionsLoading: false,
      suggestionVariants: {},
      suggestionVariantLoading: {},
      suggestionVariantError: {},
      currentValues: { title: 'scan_001', date: '', correspondent: '', tags: 'Arzt', note: '' },
      currentTagList: ['Arzt'],
      importDate: '2026-10-11T12:34:56+02:00',
    },
  })

const mountSectionNoImportDate = () =>
  mount(DocumentSuggestionsSection, {
    props: {
      suggestions: { vision_ocr: { parsed: {} } },
      suggestionsError: '',
      suggestionsLoading: false,
      suggestionVariants: {},
      suggestionVariantLoading: {},
      suggestionVariantError: {},
      currentValues: { title: '', date: '', correspondent: '', tags: '', note: '' },
      currentTagList: [],
      importDate: '',
    },
  })

describe('DocumentSuggestionsSection selective apply', () => {
  it('preselects nothing and shows no apply bar', () => {
    const wrapper = mountSection()
    expect(wrapper.find('[data-testid="apply-selected-bar"]').exists()).toBe(false)
    const boxes = wrapper.findAll('input[type="checkbox"]')
    expect(boxes.length).toBeGreaterThan(0)
    expect(boxes.every((box) => !(box.element as HTMLInputElement).checked)).toBe(true)
  })

  it('emits only the checked fields and merges selected tags with existing ones', async () => {
    const wrapper = mountSection()
    await wrapper.find('[data-testid="select-vision_ocr-title"]').setValue(true)
    const tagChip = wrapper.findAll('button').find((b) => b.text() === 'Einkauf')
    expect(tagChip).toBeTruthy()
    await tagChip!.trigger('click')

    await wrapper.find('[data-testid="apply-selected"]').trigger('click')

    expect(wrapper.emitted('applySelected')).toEqual([
      [
        [
          { source: 'vision_ocr', field: 'title', value: 'Rechnung Teufel' },
          { source: 'vision_ocr', field: 'tags', value: ['Arzt', 'Einkauf'] },
        ],
      ],
    ])
  })

  it('preset "No correspondent" clears the correspondent via the apply path', async () => {
    const wrapper = mountSection()
    await wrapper.find('[data-testid="preset-no-correspondent"]').trigger('click')
    expect(wrapper.emitted('applyToDocument')).toEqual([[ 'preset', 'correspondent', '' ]])
  })

  it('preset "Issue date = import date" sends only the import date part', async () => {
    const wrapper = mountSection()
    await wrapper.find('[data-testid="preset-issue-date-import"]').trigger('click')
    expect(wrapper.emitted('applyToDocument')).toEqual([[ 'preset', 'date', '2026-10-11' ]])
  })

  it('preset "Issue date = import date" is disabled without an import date', async () => {
    const wrapper = mountSectionNoImportDate()
    const button = wrapper.find('[data-testid="preset-issue-date-import"]')
    expect((button.element as HTMLButtonElement).disabled).toBe(true)
    await button.trigger('click')
    expect(wrapper.emitted('applyToDocument')).toBeUndefined()
  })
})
