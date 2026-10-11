// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentDetailHeader from './DocumentDetailHeader.vue'

const baseProps = {
  title: 'Rechnung',
  docId: 20,
  headerMetaLine: 'Document ID: 20',
  activeRunLabel: '',
  paperlessUrl: '',
  reviewMarking: false,
  canMarkReviewed: true,
  writebackRunning: false,
  canWriteback: true,
  writebackButtonTitle: '',
  writebackButtonLabel: 'Write back',
  reloadingAll: false,
}

describe('DocumentDetailHeader review navigation', () => {
  it('hides the controls without a remembered list', () => {
    const wrapper = mount(DocumentDetailHeader, { props: baseProps })
    expect(wrapper.find('[data-testid="review-queue-nav"]').exists()).toBe(false)
  })

  it('shows the position and emits prev, next and the auto-advance toggle', async () => {
    const wrapper = mount(DocumentDetailHeader, {
      props: {
        ...baseProps,
        queuePosition: { index: 2, total: 7 },
        hasPrev: true,
        hasNext: true,
        autoAdvance: true,
      },
    })
    expect(wrapper.find('[data-testid="review-position"]').text()).toBe('3 / 7')

    await wrapper.find('[data-testid="review-prev"]').trigger('click')
    await wrapper.find('[data-testid="review-next"]').trigger('click')
    await wrapper.find('[data-testid="review-auto-advance"]').setValue(false)

    expect(wrapper.emitted('prev')).toHaveLength(1)
    expect(wrapper.emitted('next')).toHaveLength(1)
    expect(wrapper.emitted('update:autoAdvance')).toEqual([[false]])
  })

  it('disables the buttons at the ends of the list', () => {
    const wrapper = mount(DocumentDetailHeader, {
      props: { ...baseProps, queuePosition: { index: 0, total: 3 }, hasPrev: false, hasNext: true },
    })
    expect((wrapper.find('[data-testid="review-prev"]').element as HTMLButtonElement).disabled).toBe(
      true,
    )
    expect((wrapper.find('[data-testid="review-next"]').element as HTMLButtonElement).disabled).toBe(
      false,
    )
  })
})
