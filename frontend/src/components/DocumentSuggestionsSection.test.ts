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
})

describe('DocumentSuggestionsSection text candidates', () => {
  const withCandidates = () => {
    const wrapper = mountSection()
    return wrapper.setProps({
      textCandidates: {
        dates: [
          {
            value: '2026-09-20',
            label: 'issue',
            score: 0.9,
            context: 'Rechnungsdatum: 20.09.2026',
            page: 1,
            occurrences: 2,
            sources: ['vision_ocr'],
          },
          {
            value: '2026-10-04',
            label: 'due',
            score: 0.2,
            context: 'Zahlbar bis 04.10.2026',
            page: 1,
            occurrences: 1,
            sources: ['vision_ocr'],
          },
        ],
        correspondents: [
          {
            name: 'Lautsprecher Teufel GmbH',
            known: true,
            score: 0.92,
            evidence: 'header',
            context: 'Lautsprecher Teufel GmbH',
            sources: ['vision_ocr'],
          },
        ],
      },
    }).then(() => wrapper)
  }

  it('renders the candidates block with formatted dates and labels', async () => {
    const wrapper = await withCandidates()
    const block = wrapper.find('[data-testid="text-candidates"]')
    expect(block.exists()).toBe(true)
    expect(block.text()).toContain('20.09.2026')
    expect(block.text()).toContain('issue date')
    expect(block.text()).toContain('Lautsprecher Teufel GmbH')
    expect(block.text()).toContain('known')
  })

  it('selecting candidates feeds the apply bar and emits only the chosen fields', async () => {
    const wrapper = await withCandidates()
    await wrapper.find('[data-testid="candidate-date-2026-09-20"]').trigger('click')
    await wrapper
      .find('[data-testid="candidate-correspondent-Lautsprecher Teufel GmbH"]')
      .trigger('click')

    expect(wrapper.find('[data-testid="apply-selected-bar"]').text()).toContain('2026-09-20')

    await wrapper.find('[data-testid="apply-selected"]').trigger('click')

    expect(wrapper.emitted('applySelected')).toEqual([
      [
        [
          { source: 'text_candidates', field: 'date', value: '2026-09-20' },
          { source: 'text_candidates', field: 'correspondent', value: 'Lautsprecher Teufel GmbH' },
        ],
      ],
    ])
  })

  it('toggles a candidate off and keeps one selection per field', async () => {
    const wrapper = await withCandidates()
    const first = wrapper.find('[data-testid="candidate-date-2026-09-20"]')
    const second = wrapper.find('[data-testid="candidate-date-2026-10-04"]')

    await first.trigger('click')
    await second.trigger('click')
    await wrapper.find('[data-testid="apply-selected"]').trigger('click')
    expect(wrapper.emitted('applySelected')?.[0]?.[0]).toEqual([
      { source: 'text_candidates', field: 'date', value: '2026-10-04' },
    ])

    await second.trigger('click')
    expect(wrapper.find('[data-testid="apply-selected-bar"]').exists()).toBe(false)
  })

  it('shows nothing when no candidates were found', () => {
    const wrapper = mountSection()
    expect(wrapper.find('[data-testid="text-candidates"]').exists()).toBe(false)
  })
})
