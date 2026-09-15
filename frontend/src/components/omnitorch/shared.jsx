import { cloneElement, useId } from "react";
import { short, percent } from "./formatters.js";
export function RecordDetails({ record, title = "Reproducibility record" }) {
  return (
    <details className="ml-record">
      <summary>{title}</summary>
      <pre>{JSON.stringify(record, null, 2)}</pre>
    </details>
  );
}
export function Empty({ children }) {
  return <div className="ml-empty">{children}</div>;
}
export function Field({ label, children }) {
  const id = useId();
  return (
    <div className="ml-field">
      <label htmlFor={id}>{label}</label>
      {cloneElement(children, { id })}
    </div>
  );
}
export function SelectRecord({ label, value, onChange, items, describe }) {
  return (
    <Field label={label}>
      <select required value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Select {label.toLowerCase()}</option>
        {items.map((item) => (
          <option key={item.id} value={item.id}>
            {describe?.(item) || item.name || short(item.id)}
          </option>
        ))}
      </select>
    </Field>
  );
}
export function Metrics({ metrics }) {
  return (
    <dl className="ml-metrics">
      <div>
        <dt>Loss</dt>
        <dd>{metrics.loss.toFixed(4)}</dd>
      </div>
      <div>
        <dt>Accuracy</dt>
        <dd>{percent(metrics.accuracy)}</dd>
      </div>
      <div>
        <dt>Images</dt>
        <dd>{metrics.sample_count}</dd>
      </div>
    </dl>
  );
}
export function Confusion({ record }) {
  return (
    <div className="ml-table-wrap">
      <table>
        <caption>
          Confusion matrix · rows are actual, columns are predicted
        </caption>
        <thead>
          <tr>
            <th scope="col">Actual / predicted</th>
            {record.classes.map((label) => (
              <th scope="col" key={label}>
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {record.metrics.confusion_matrix.map((row, i) => (
            <tr key={record.classes[i]}>
              <th scope="row">{record.classes[i]}</th>
              {row.map((count, j) => (
                <td key={j}>{count}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
