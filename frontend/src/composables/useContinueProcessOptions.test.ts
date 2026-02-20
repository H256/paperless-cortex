import { describe, expect, it } from 'vitest'
import { useContinueProcessOptions } from './useContinueProcessOptions'

describe('useContinueProcessOptions', () => {
  it('uses balanced defaults', () => {
    const { processOptions, batchLabel, processParams } = useContinueProcessOptions()
    expect(processOptions.includeSync).toBe(true)
    expect(processOptions.strategy).toBe('balanced')
    expect(batchLabel.value).toBe('All')
    expect(processParams().embeddings_mode).toBe('auto')
  })

  it('maps paperless_only strategy', () => {
    const { processOptions, processParams } = useContinueProcessOptions()
    processOptions.strategy = 'paperless_only'
    const params = processParams()
    expect(params.include_vision_ocr).toBe(false)
    expect(params.include_embeddings_paperless).toBe(true)
    expect(params.include_embeddings_vision).toBe(false)
    expect(params.embeddings_mode).toBe('paperless')
  })

  it('maps max_coverage strategy', () => {
    const { processOptions, processParams } = useContinueProcessOptions()
    processOptions.strategy = 'max_coverage'
    const params = processParams()
    expect(params.include_vision_ocr).toBe(true)
    expect(params.include_embeddings_paperless).toBe(true)
    expect(params.include_embeddings_vision).toBe(true)
    expect(params.embeddings_mode).toBe('both')
  })
})
