export default function FormField({ label, error, children, required }) {
  return <label className={`form-field ${error ? 'has-error' : ''}`}><span>{label}{required && <b>*</b>}</span>{children}{error && <small>{error}</small>}</label>;
}
