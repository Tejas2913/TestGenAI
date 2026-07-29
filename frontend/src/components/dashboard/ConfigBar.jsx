/**
 * ConfigBar — language + framework selectors.
 *
 * Connected to GenerationStore. Disabled during generation (Phase F3+).
 * Python-only for MVP; architecture supports future languages.
 */
import { useGenerationStore } from '../../stores/useGenerationStore'
import Select from '../common/Select'

const LANGUAGE_OPTIONS = [
  { value: 'python', label: 'Python' },
  // Future: { value: 'javascript', label: 'JavaScript' },
]

const FRAMEWORK_OPTIONS = {
  python: [
    { value: 'pytest', label: 'pytest' },
    { value: 'unittest', label: 'unittest' },
  ],
}

export default function ConfigBar() {
  const language = useGenerationStore((s) => s.language)
  const framework = useGenerationStore((s) => s.framework)
  const isGenerating = useGenerationStore((s) => s.isGenerating)
  const setLanguage = useGenerationStore((s) => s.setLanguage)
  const setFramework = useGenerationStore((s) => s.setFramework)

  const frameworks = FRAMEWORK_OPTIONS[language] || FRAMEWORK_OPTIONS.python

  return (
    <div className="flex items-end gap-3">
      <Select
        id="language-select"
        label="Language"
        value={language}
        onChange={setLanguage}
        options={LANGUAGE_OPTIONS}
        disabled={isGenerating}
      />

      <Select
        id="framework-select"
        label="Framework"
        value={framework}
        onChange={setFramework}
        options={frameworks}
        disabled={isGenerating}
      />
    </div>
  )
}
