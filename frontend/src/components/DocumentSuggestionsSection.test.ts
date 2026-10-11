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

  it('sends the page restriction with whitespace removed', async () => {
    const wrapper = mountWithText()
    await wrapper.find('[data-testid="guidance-pages"]').setValue(' 1, 3-4 ')
    await suggestButtons(wrapper)[0]!.trigger('click')

    const calls = wrapper.emitted('suggestField') ?? []
    expect(calls[0]?.[2]).toEqual({ pages: '1,3-4' })
    wrapper.unmount()
  })

  it('flags a malformed page restriction', async () => {
    const wrapper = mountWithText()
    expect(wrapper.find('[data-testid="guidance-pages-invalid"]').exists()).toBe(false)
    await wrapper.find('[data-testid="guidance-pages"]').setValue('first page')
    expect(wrapper.find('[data-testid="guidance-pages-invalid"]').exists()).toBe(true)
    await wrapper.find('[data-testid="guidance-pages"]').setValue('2-3')
    expect(wrapper.find('[data-testid="guidance-pages-invalid"]').exists()).toBe(false)
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

describe('DocumentSuggestionsSection comparison table', () => {
  const mountComparison = () =>
    mount(DocumentSuggestionsSection, {
      props: {
        suggestions: {
          vision_ocr: {
            parsed: {
              title: 'Rechnung Teufel',
              date: '2026-09-20',
              correspondent: 'Lautsprecher Teufel GmbH',
              tags: ['Rechnung'],
            },
          },
          paperless_ocr: {
            parsed: {
              title: 'Rechnung Teufel',
              date: '2026-09-25',
              correspondent: 'Lautsprecher Teufel GmbH',
              tags: ['Rechnung', 'Einkauf'],
            },
          },
          similar_docs: {
            parsed: {
              correspondent: 'Lautsprecher Teufel GmbH',
              tags: ['Rechnung'],
            },
          },
        },
        suggestionsError: '',
        suggestionsLoading: false,
        suggestionVariants: {},
        suggestionVariantLoading: {},
        suggestionVariantError: {},
        currentValues: { title: 'scan_001', date: '', correspondent: '', tags: '', note: '' },
        currentTagList: [],
        importDate: '',
      },
    })

  it('renders the comparison table with one row per field and all source columns', () => {
    const wrapper = mountComparison()
    expect(wrapper.find('[data-testid="suggestion-comparison-table"]').exists()).toBe(true)
    const header = wrapper.find('thead')
    expect(header.text()).toContain('Current')
    expect(header.text()).toContain('Vision OCR')
    expect(header.text()).toContain('Paperless OCR')
    expect(header.text()).toContain('Similar docs')
    const rows = wrapper.findAll('tbody tr')
    expect(rows.length).toBe(4)
    expect(rows[0]?.text()).toContain('Suggested title')
    expect(rows[1]?.text()).toContain('Suggested date')
  })

  it('marks cells without data and shows the agreement indicator', () => {
    const wrapper = mountComparison()
    expect(wrapper.text()).toContain('No data.')
    const titleAgreement = wrapper.find('[data-testid="agreement-title"]')
    expect(titleAgreement.text()).toBe('2 sources agree')
    const dateAgreement = wrapper.find('[data-testid="agreement-date"]')
    expect(dateAgreement.exists()).toBe(false)
    const correspondentAgreement = wrapper.find('[data-testid="agreement-correspondent"]')
    expect(correspondentAgreement.text()).toBe('3 sources agree')
  })

  it('emits jumpToPage for date candidates with page info', async () => {
    const wrapper = mount(DocumentSuggestionsSection, {
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
        textCandidates: { dates: [{ value: '2026-09-20', label: 'Rechnungsdatum', score: 1, evidence: '', page: 2 }] },
      },
    })
    const jump = wrapper.find('[data-testid="jump-page-candidate-date-2026-09-20"]')
    expect(jump.exists()).toBe(true)
    await jump.trigger('click')
    expect(wrapper.emitted('jumpToPage')).toEqual([[2]])
  })
})

describe('DocumentSuggestionsSection compact table', () => {
  const props = {
    suggestions: { vision_ocr: { parsed: { title: 'Rechnung Teufel' } } },
    suggestionsError: '',
    suggestionsLoading: false,
    suggestionVariants: {},
    suggestionVariantLoading: {},
    suggestionVariantError: {},
    currentValues: { title: '', date: '', correspondent: '', tags: '', note: '' },
    currentTagList: [],
  }

  it('uses a narrower table minimum in the split-view column', () => {
    const normal = mount(DocumentSuggestionsSection, { props })
    expect(normal.get('[data-testid="suggestion-table"]').classes().join(' ')).toContain('min-w-[760px]')
    normal.unmount()

    const compact = mount(DocumentSuggestionsSection, { props: { ...props, compact: true } })
    const classes = compact.get('[data-testid="suggestion-table"]').classes().join(' ')
    expect(classes).toContain('min-w-[600px]')
    expect(classes).not.toContain('min-w-[760px]')
    compact.unmount()
  })
})

describe('DocumentSuggestionsSection recommended text source', () => {
  const props = {
    suggestions: { vision_ocr: { parsed: { title: 'Rechnung' } } },
    suggestionsError: '',
    suggestionsLoading: false,
    suggestionVariants: {},
    suggestionVariantLoading: {},
    suggestionVariantError: {},
    currentValues: { title: '', date: '', correspondent: '', tags: '', note: '' },
    currentTagList: [],
    textSources: [
      { key: 'paperless_ocr', label: 'Paperless OCR', text: 'a' },
      { key: 'vision_ocr', label: 'Vision OCR', text: 'b' },
    ],
    recommendedTextSource: 'vision_ocr',
    recommendationReason: 'Readability 94 vs 60 for the other text.',
  }

  it('hints the better text but does not preselect it', () => {
    const wrapper = mount(DocumentSuggestionsSection, { props })
    expect(wrapper.get('[data-testid="recommended-text-source"]').text()).toContain('Vision OCR')
    const select = wrapper.get('[data-testid="guidance-model-text"]').element as HTMLSelectElement
    expect(select.value).toBe('')
    wrapper.unmount()
  })

  it('uses the recommended text only when the reviewer asks for it', async () => {
    const wrapper = mount(DocumentSuggestionsSection, { props })
    await wrapper.get('[data-testid="use-recommended-text-source"]').trigger('click')

    const select = wrapper.get('[data-testid="guidance-model-text"]').element as HTMLSelectElement
    expect(select.value).toBe('vision_ocr')
    expect(wrapper.find('[data-testid="use-recommended-text-source"]').exists()).toBe(false)
    wrapper.unmount()
  })
})


describe('DocumentSuggestionsSection picking from the comparison table', () => {
  const props = {
    suggestions: {
      vision_ocr: {
        parsed: {
          title: 'Festnetz-Rechnung Juli 2026',
          date: '2026-07-24',
          correspondent: 'Telekom Deutschland GmbH',
          tags: ['Internet', 'Rechnung', 'Telefon'],
        },
      },
      paperless_ocr: {
        parsed: {
          title: 'Festnetz-Rechnung Juli 2026',
          date: '2026-07-15',
          correspondent: 'Telekom Deutschland GmbH',
          tags: ['Rechnung', 'Telefon', '2026'],
        },
      },
      similar_docs: {
        parsed: {
          title: '0f6d9179-c360-44aa-8b98-c6567798a1a3',
          correspondent: 'Telekom Deutschland GmbH',
          tags: ['Internet', 'Neu'],
        },
      },
    },
    suggestionsError: '',
    suggestionsLoading: false,
    suggestionVariants: {},
    suggestionVariantLoading: {},
    suggestionVariantError: {},
    currentValues: { title: '', date: '15.7.2026', correspondent: '', tags: 'Rechnung', note: '' },
    currentTagList: ['Rechnung'],
  }

  it('selects the value of the clicked column, not just the first source', async () => {
    const wrapper = mount(DocumentSuggestionsSection, { props })

    await wrapper.get('[data-testid="pick-paperless_ocr-date"]').trigger('click')
    expect(wrapper.get('[data-testid="pick-paperless_ocr-date"]').attributes('aria-pressed')).toBe(
      'true',
    )
    expect(wrapper.get('[data-testid="pick-vision_ocr-date"]').attributes('aria-pressed')).toBe(
      'false',
    )

    await wrapper.get('[data-testid="apply-selected"]').trigger('click')
    expect(wrapper.emitted('applySelected')?.[0]?.[0]).toEqual([
      { source: 'paperless_ocr', field: 'date', value: '2026-07-15' },
    ])
    wrapper.unmount()
  })

  it('switches the choice to another column and clears it by clicking again', async () => {
    const wrapper = mount(DocumentSuggestionsSection, { props })

    await wrapper.get('[data-testid="pick-vision_ocr-title"]').trigger('click')
    await wrapper.get('[data-testid="pick-paperless_ocr-title"]').trigger('click')
    expect(wrapper.get('[data-testid="pick-paperless_ocr-title"]').attributes('aria-pressed')).toBe(
      'true',
    )
    expect(wrapper.get('[data-testid="pick-vision_ocr-title"]').attributes('aria-pressed')).toBe(
      'false',
    )

    await wrapper.get('[data-testid="pick-paperless_ocr-title"]').trigger('click')
    expect(wrapper.find('[data-testid="apply-selected-bar"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('combines tags from several columns into one set', async () => {
    const wrapper = mount(DocumentSuggestionsSection, { props })

    await wrapper.get('[data-testid="tag-vision_ocr-Internet"]').trigger('click')
    await wrapper.get('[data-testid="tag-paperless_ocr-2026"]').trigger('click')
    await wrapper.get('[data-testid="tag-similar_docs-Neu"]').trigger('click')

    await wrapper.get('[data-testid="apply-selected"]').trigger('click')
    const item = (wrapper.emitted('applySelected')?.[0]?.[0] as Array<{
      field: string
      value: string[]
    }>)[0]
    expect(item?.field).toBe('tags')
    expect([...(item?.value ?? [])].sort()).toEqual(['2026', 'Internet', 'Neu', 'Rechnung'])
    wrapper.unmount()
  })

  it('lets the reviewer pick the correspondent of the similar documents', async () => {
    const wrapper = mount(DocumentSuggestionsSection, { props })
    await wrapper.get('[data-testid="pick-similar_docs-correspondent"]').trigger('click')
    await wrapper.get('[data-testid="apply-selected"]').trigger('click')

    expect(wrapper.emitted('applySelected')?.[0]?.[0]).toEqual([
      { source: 'similar_docs', field: 'correspondent', value: 'Telekom Deutschland GmbH' },
    ])
    wrapper.unmount()
  })

  it('shows only correspondent and tags for the similar documents', () => {
    const wrapper = mount(DocumentSuggestionsSection, { props })
    expect(wrapper.find('[data-testid="pick-similar_docs-title"]').exists()).toBe(false)
    expect(wrapper.find('[data-testid="pick-similar_docs-date"]').exists()).toBe(false)
    wrapper.unmount()
  })

  it('asks for a new value of the column whose cell was used', async () => {
    const wrapper = mount(DocumentSuggestionsSection, { props })
    await wrapper.get('[data-testid="suggest-paperless_ocr-date"]').trigger('click')

    expect(wrapper.emitted('suggestField')?.[0]).toEqual(['paperless_ocr', 'date'])
    wrapper.unmount()
  })
})

describe('DocumentSuggestionsSection summary cell', () => {
  it('shows the summary text in the cell and lets the reviewer pick it', async () => {
    const wrapper = mountSection()
    const cell = wrapper.get('[data-testid="pick-vision_ocr-note"]')
    expect(cell.text()).toBe('Rechnung ueber Kopfhoerer.')

    await cell.trigger('click')
    await wrapper.get('[data-testid="apply-selected"]').trigger('click')
    expect(wrapper.emitted('applySelected')?.[0]?.[0]).toEqual([
      { source: 'vision_ocr', field: 'note', value: 'Rechnung ueber Kopfhoerer.' },
    ])
    wrapper.unmount()
  })

  it('clamps a long summary and lets the reviewer expand it', async () => {
    const long = 'Lange Zusammenfassung. '.repeat(30).trim()
    const wrapper = mount(DocumentSuggestionsSection, {
      props: {
        suggestions: { vision_ocr: { parsed: { summary: long } } },
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
    const clamped = () => wrapper.get('[data-testid="pick-vision_ocr-note"] span').classes()
    expect(clamped()).toContain('line-clamp-4')

    await wrapper.get('[data-testid="expand-vision_ocr-note"]').trigger('click')
    expect(clamped()).not.toContain('line-clamp-4')
    wrapper.unmount()
  })
})
