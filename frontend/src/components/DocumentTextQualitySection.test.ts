// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentTextQualitySection from './DocumentTextQualitySection.vue'

const baseProps = {
  content: 'Rechnung',
  contentQuality: { score: 100, reasons: [], metrics: {} },
  contentQualityError: '',
  ocrScoresLoading: false,
  ocrScoresError: '',
  ocrScores: [
    {
      source: 'paperless_ocr',
      verdict: 'good',
      quality_score: 40,
      components: { heuristics: 40, ppl_penalty: 0 },
      noise: {},
      ppl: { supported: false, reason: 'logprobs not provided by server' },
    },
    {
      source: 'vision_ocr',
      verdict: 'good',
      quality_score: 6.14,
      components: { heuristics: 6.14, ppl_penalty: 0 },
      noise: {},
      ppl: { supported: true, ppl: 12.5 },
    },
  ],
}

describe('DocumentTextQualitySection', () => {
  it('shows one readability scale where higher is better', () => {
    const wrapper = mount(DocumentTextQualitySection, { props: baseProps })

    expect(wrapper.get('[data-testid="readability-vision_ocr"]').text()).toContain('94 / 100')
    expect(wrapper.get('[data-testid="readability-paperless_ocr"]').text()).toContain('60 / 100')
    expect(wrapper.text()).toContain('higher is better')
    expect(wrapper.text()).not.toContain('Lower is better')
    wrapper.unmount()
  })

  it('says "not measured" instead of a zero penalty when no perplexity is available', () => {
    const wrapper = mount(DocumentTextQualitySection, { props: baseProps })

    expect(wrapper.get('[data-testid="readability-paperless_ocr"]').text()).toContain('not measured')
    expect(wrapper.get('[data-testid="readability-paperless_ocr"]').text()).not.toMatch(/Perplexity\s*0\.00/)
    expect(wrapper.get('[data-testid="readability-vision_ocr"]').text()).toContain('perplexity 12.5')
    wrapper.unmount()
  })

  it('shows the recommended source and the text agreement', () => {
    const wrapper = mount(DocumentTextQualitySection, {
      props: {
        ...baseProps,
        ocrComparison: {
          agreement: 0.87,
          recommendedSource: 'vision_ocr',
          reason: 'Readability 94 vs 60 for the other text.',
        },
      },
    })

    expect(wrapper.get('[data-testid="recommended-source"]').text()).toContain('Vision OCR')
    expect(wrapper.get('[data-testid="agreement"]').text()).toContain('87%')
    wrapper.unmount()
  })

  it('explains when there is no clear better source', () => {
    const wrapper = mount(DocumentTextQualitySection, {
      props: {
        ...baseProps,
        ocrComparison: {
          agreement: 0.3,
          recommendedSource: null,
          reason: 'Both texts read about equally well.',
        },
      },
    })

    expect(wrapper.find('[data-testid="recommended-source"]').exists()).toBe(false)
    expect(wrapper.get('[data-testid="no-recommendation"]').text()).toContain('equally well')
    expect(wrapper.get('[data-testid="agreement"]').classes().join(' ')).toContain('rose')
    wrapper.unmount()
  })
})
