export default function ToggleSwitch({ checked, onChange, label }) {
  return (
    <label className="toggle-switch">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="toggle-track"><i /></span>
      {label && <span>{label}</span>}
    </label>
  );
}
