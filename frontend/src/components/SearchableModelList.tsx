import { useMemo, useState } from "react";

type Props = {
  id: string;
  label?: string;
  options: string[];
  value: string;
  onChange: (next: string) => void;
  defaultOptionLabel?: string;
  placeholder?: string;
  emptyMessage?: string;
};

export function SearchableModelList({
  id,
  label,
  options,
  value,
  onChange,
  defaultOptionLabel,
  placeholder,
  emptyMessage = "No matching models.",
}: Props) {
  const [query, setQuery] = useState("");
  const normalizedLabel = label?.trim() ?? "";
  const accessibleLabel = normalizedLabel || "Search models";

  const allOptions = useMemo(
    () => Array.from(new Set([value, ...options].filter(Boolean))),
    [options, value]
  );

  const normalizedQuery = query.trim().toLowerCase();
  const filteredOptions = useMemo(
    () =>
      normalizedQuery
        ? allOptions.filter((m) => m.toLowerCase().includes(normalizedQuery))
        : allOptions,
    [allOptions, normalizedQuery]
  );

  const showDefault =
    defaultOptionLabel !== undefined &&
    (!normalizedQuery || defaultOptionLabel.toLowerCase().includes(normalizedQuery));

  const searchPlaceholder =
    placeholder ?? (allOptions.length > 0 ? `Search ${allOptions.length} models` : "Search models");

  return (
    <div className="searchable-list-wrapper">
      {normalizedLabel ? (
        <label className="field-label" htmlFor={id}>{normalizedLabel}</label>
      ) : null}
      <input
        id={id}
        type="search"
        className="searchable-list-input"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={searchPlaceholder}
        aria-label={accessibleLabel}
      />
      <div className="searchable-list-options" aria-label={`${accessibleLabel} options`}>
        {showDefault && (
          <button
            type="button"
            className={`searchable-list-option${!value ? " active" : ""}`}
            onClick={() => onChange("")}
          >
            {defaultOptionLabel}
          </button>
        )}
        {filteredOptions.map((model) => (
          <button
            type="button"
            key={model}
            className={`searchable-list-option${model === value ? " active" : ""}`}
            onClick={() => onChange(model)}
            title={model}
          >
            {model}
          </button>
        ))}
        {!showDefault && filteredOptions.length === 0 && (
          <p className="searchable-list-empty">{emptyMessage}</p>
        )}
      </div>
    </div>
  );
}
