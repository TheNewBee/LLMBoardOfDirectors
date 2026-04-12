import type { BriefingForm } from "../types";

type Props = {
  value: BriefingForm;
  onChange: (next: BriefingForm) => void;
};

export function BriefingDialog({ value, onChange }: Props) {
  return (
    <section className="card">
      <h3>1. Briefing</h3>
      <label>
        Topic
        <textarea
          value={value.text}
          onChange={(event) => onChange({ ...value, text: event.target.value })}
          rows={4}
          placeholder="Should we launch in EU this quarter?"
        />
      </label>
      <label>
        Objectives (one per line)
        <textarea
          value={value.objectives}
          onChange={(event) => onChange({ ...value, objectives: event.target.value })}
          rows={4}
          placeholder={"Stress test assumptions\nIdentify critical risks"}
        />
      </label>
    </section>
  );
}

