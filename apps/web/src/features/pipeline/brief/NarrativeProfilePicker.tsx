import { useId, useRef, type KeyboardEvent } from 'react';
import { BookOpen, Check } from 'lucide-react';
import { narrativeProfilePrompt, narrativeProfiles } from './narrativeProfiles';

type Props = {
  value: string;
  onChange: (value: string) => void;
};

export function NarrativeProfilePicker({ onChange, value }: Props) {
  const selected = narrativeProfiles.find((profile) => profile.name === value) ?? narrativeProfiles[0];
  const titleId = useId();
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);

  function selectByKeyboard(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    const last = narrativeProfiles.length - 1;
    const nextIndex = event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? last
        : event.key === 'ArrowRight' || event.key === 'ArrowDown'
          ? index === last ? 0 : index + 1
          : event.key === 'ArrowLeft' || event.key === 'ArrowUp'
            ? index === 0 ? last : index - 1
            : null;
    if (nextIndex === null) return;
    event.preventDefault();
    onChange(narrativeProfiles[nextIndex].name);
    optionRefs.current[nextIndex]?.focus();
  }

  return (
    <section aria-labelledby={titleId} className="narrative-profile-picker">
      <header>
        <span><BookOpen size={15} /></span>
        <div><h3 id={titleId}>叙事角色</h3><p>选择贯穿全书的观察与表达策略。</p></div>
      </header>
      <div aria-label="叙事角色" className="narrative-profile-options" role="radiogroup">
        {narrativeProfiles.map((profile, index) => {
          const active = profile.name === selected.name;
          return (
            <button
              aria-checked={active}
              className={active ? 'selected' : ''}
              key={profile.name}
              onClick={() => onChange(profile.name)}
              onKeyDown={(event) => selectByKeyboard(event, index)}
              ref={(element) => { optionRefs.current[index] = element; }}
              role="radio"
              tabIndex={active ? 0 : -1}
              type="button"
            >
              <span><strong>{profile.name}</strong><small>{profile.summary}</small></span>
              {active ? <Check size={15} /> : null}
            </button>
          );
        })}
      </div>
      <div className="narrative-profile-detail">
        <div><strong>{selected.role}</strong><span>{selected.bestFor}</span></div>
        <details>
          <summary>查看完整角色 Prompt</summary>
          <pre>{narrativeProfilePrompt(selected)}</pre>
        </details>
      </div>
    </section>
  );
}
