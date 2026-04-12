import type { BriefingForm } from "../types";

type Props = {
  value: BriefingForm;
  onChange: (next: BriefingForm) => void;
};

export function BriefingDialog({ value, onChange }: Props) {
  return (
    <section className="card setup-card">
      <div className="card-heading">
        <p className="eyebrow">Briefing</p>
        <h3>What should the board debate?</h3>
      </div>
      <label className="field">
        Topic
        <textarea
          value={value.text}
          onChange={(event) => onChange({ ...value, text: event.target.value })}
          rows={4}
          placeholder="Should we launch in EU this quarter?"
        />
      </label>
      <label className="field">
        Objectives <span>(one per line)</span>
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
