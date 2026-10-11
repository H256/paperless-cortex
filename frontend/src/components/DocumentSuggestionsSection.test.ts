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

describe('DocumentSuggestionsSection guidance for Suggest new', () => {
  const mountWithText = () =>
    mount(DocumentSuggestionsSection, {
      attachTo: document.body,
      props: {
        suggestions: {
          vision_ocr: { parsed: { title: 'Rechnung', date: '2026-09-18' } },
        },
        suggestionsError: '',
        suggestionsLoading: false,
        suggestionVariants: {},
        suggestionVariantLoading: {},
        suggestionVariantError: {},
        currentValues: { title: '', date: '', correspondent: '', tags: '', note: '' },
        textSources: [
          {
            key: 'paperless_ocr',
            label: 'Paperless OCR',
            text: 'Lieferdatum: 18.09.2026\nRechnungsdatum: 20.09.2026\nZahlbar bis 04.10.2026',
          },
          { key: 'vision_ocr', label: 'Vision OCR', text: 'Vision text' },
        ],
      },
    })

  const selectInText = (wrapper: ReturnType<typeof mountWithText>, needle: string) => {
    const pre = wrapper.find('[data-testid="guidance-text"]').element
    const node = pre.firstChild as Text
    const start = (node.textContent ?? '').indexOf(needle)
    const range = document.createRange()
    range.setStart(node, start)
    range.setEnd(node, start + needle.length)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
  }

  const suggestButtons = (wrapper: ReturnType<typeof mountWithText>) =>
    wrapper.findAll('button').filter((b) => b.text().includes('Suggest new'))

  it('shows the document text with a source switch', () => {
    const wrapper = mountWithText()
    expect(wrapper.find('[data-testid="guidance-text"]').text()).toContain('Rechnungsdatum')
    expect(wrapper.find('[data-testid="guidance-source"]').exists()).toBe(true)
    wrapper.unmount()
  })

  it('uses the marked passage and the hint for every Suggest new request', async () => {
    const wrapper = mountWithText()
    selectInText(wrapper, 'Rechnungsdatum: 20.09.2026')
    await wrapper.find('[data-testid="guidance-use-selection"]').trigger('click')
    await wrapper.find('[data-testid="guidance-hint"]').setValue('Rechnungsdatum, nicht Lieferdatum')

    expect(wrapper.find('[data-testid="guidance-focus"]').text()).toContain(
      'Rechnungsdatum: 20.09.2026',
    )

    await suggestButtons(wrapper)[0]!.trigger('click')

    const calls = wrapper.emitted('suggestField') ?? []
    expect(calls).toHaveLength(1)
    expect(calls[0]?.[2]).toEqual({
      focus_text: 'Rechnungsdatum: 20.09.2026',
      hint: 'Rechnungsdatum, nicht Lieferdatum',
    })
    wrapper.unmount()
  })

  it('sends no guidance when nothing was marked or typed', async () => {
    const wrapper = mountWithText()
    await suggestButtons(wrapper)[0]!.trigger('click')
    const calls = wrapper.emitted('suggestField') ?? []
    expect(calls[0]).toHaveLength(2)
    wrapper.unmount()
  })

  it('lets the reviewer choose the OCR text the model reads', async () => {
    const wrapper = mountWithText()
    expect(wrapper.find('[data-testid="guidance-model-text"]').exists()).toBe(true)

    await wrapper.find('[data-testid="guidance-model-text"]').setValue('paperless_ocr')
    await suggestButtons(wrapper)[0]!.trigger('click')

    const calls = wrapper.emitted('suggestField') ?? []
    expect(calls[0]?.[2]).toEqual({ text_source: 'paperless_ocr' })
    wrapper.unmount()
  })

  it('does not offer a text choice when only one text is available', () => {
    const wrapper = mount(DocumentSuggestionsSection, {
      props: {
        suggestions: { vision_ocr: { parsed: { title: 'Rechnung' } } },
        suggestionsError: '',
        suggestionsLoading: false,
        suggestionVariants: {},
        suggestionVariantLoading: {},
        suggestionVariantError: {},
        currentValues: { title: '', date: '', correspondent: '', tags: '', note: '' },
        textSources: [{ key: 'content', label: 'Document text', text: 'Only text' }],
      },
    })
    expect(wrapper.find('[data-testid="guidance-model-text"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('rejects a selection outside of the document text', async () => {
    const wrapper = mountWithText()
    const outside = document.createElement('p')
    outside.textContent = 'somewhere else'
    document.body.appendChild(outside)
    const range = document.createRange()
    range.selectNodeContents(outside)
    window.getSelection()?.removeAllRanges()
    window.getSelection()?.addRange(range)

    await wrapper.find('[data-testid="guidance-use-selection"]').trigger('click')

    expect(wrapper.find('[data-testid="guidance-focus"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Select a passage inside the document text first.')
    outside.remove()
    wrapper.unmount()
  })

  it('clears the focus passage', async () => {
    const wrapper = mountWithText()
    selectInText(wrapper, 'Zahlbar bis 04.10.2026')
    await wrapper.find('[data-testid="guidance-use-selection"]').trigger('click')
    expect(wrapper.find('[data-testid="guidance-focus"]').exists()).toBe(true)

    await wrapper.find('[data-testid="guidance-clear-focus"]').trigger('click')

    expect(wrapper.find('[data-testid="guidance-focus"]').exists()).toBe(false)
    wrapper.unmount()
  })
})
