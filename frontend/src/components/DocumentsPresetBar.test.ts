// @vitest-environment jsdom
import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DocumentsPresetBar from './DocumentsPresetBar.vue'

const baseProps = {
  analysisFilter: 'all' as const,
  reviewStatus: 'all' as const,
  searchQuery: '',
}

const buttonByLabel = (wrapper: ReturnType<typeof mount>, label: string) =>
  wrapper.findAll('button').find((button) => button.text().startsWith(label))

describe('DocumentsPresetBar filter presets', () => {
  it('offers the no-correspondent and import-date presets with their shortcuts', () => {
    const wrapper = mount(DocumentsPresetBar, { props: baseProps })
    expect(buttonByLabel(wrapper, 'No correspondent')?.text()).toContain('Alt+5')
    expect(buttonByLabel(wrapper, 'Issue date = import date')?.text()).toContain('Alt+6')
    wrapper.unmount()
  })

  it('marks the presets active from the current filters', () => {
    const wrapper = mount(DocumentsPresetBar, {
      props: { ...baseProps, selectedCorrespondent: '-1', issueDateIsImportDate: true },
    })
    expect(buttonByLabel(wrapper, 'No correspondent')?.classes().join(' ')).toContain('indigo')
    expect(buttonByLabel(wrapper, 'Issue date = import date')?.classes().join(' ')).toContain(
      'indigo',
    )
    expect(buttonByLabel(wrapper, 'Unreviewed')?.classes().join(' ')).not.toContain('indigo')
    wrapper.unmount()
  })

  it('is inactive for a real correspondent id', () => {
    const wrapper = mount(DocumentsPresetBar, {
      props: { ...baseProps, selectedCorrespondent: '42' },
    })
    expect(buttonByLabel(wrapper, 'No correspondent')?.classes().join(' ')).not.toContain('indigo')
    wrapper.unmount()
  })

  it('emits the preset keys for clicks and Alt+5 / Alt+6', async () => {
    const wrapper = mount(DocumentsPresetBar, { props: baseProps })

    await buttonByLabel(wrapper, 'No correspondent')?.trigger('click')
    await buttonByLabel(wrapper, 'Issue date = import date')?.trigger('click')
    window.dispatchEvent(new KeyboardEvent('keydown', { key: '5', altKey: true }))
    window.dispatchEvent(new KeyboardEvent('keydown', { key: '6', altKey: true }))

    expect(wrapper.emitted('applyPreset')).toEqual([
      ['no_correspondent'],
      ['import_date'],
      ['no_correspondent'],
      ['import_date'],
    ])
    wrapper.unmount()
  })
})
