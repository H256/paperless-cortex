// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentSimilarSection from './DocumentSimilarSection.vue'

const baseProps = {
  similarMatches: [],
  duplicateMatches: [],
  loading: false,
  error: '',
  similarMinScore: 0.5,
  duplicateThreshold: 0.92,
}

describe('DocumentSimilarSection hide reviewed', () => {
  it('emits the toggled value', async () => {
    const wrapper = mount(DocumentSimilarSection, {
      props: { ...baseProps, hideReviewed: true },
    })
    const box = wrapper.find('[data-testid="hide-reviewed-toggle"] input')
    expect((box.element as HTMLInputElement).checked).toBe(true)
    await box.setValue(false)
    expect(wrapper.emitted('update:hide-reviewed')).toEqual([[false]])
  })

  it('explains an empty result caused by hidden reviewed documents', () => {
    const wrapper = mount(DocumentSimilarSection, {
      props: { ...baseProps, hideReviewed: true, hiddenReviewed: 4 },
    })
    expect(wrapper.text()).toContain('4 reviewed hidden')
    expect(wrapper.text()).toContain('(4 hidden)')
  })
})
