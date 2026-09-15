import { postML } from "../../api/mlApi.js";
import {
  SelectRecord,
  Field,
  Empty,
  Metrics,
  Confusion,
  RecordDetails,
} from "./shared.jsx";
import { short } from "./formatters.js";

export default function EvaluationView({
  submit,
  modelId,
  datasetId,
  split,
  setNotice,
  setModelId,
  models,
  setDatasetId,
  datasets,
  setSplit,
  busy,
  evaluations,
}) {
  return (
    <>
      <form
        className="ml-card"
        onSubmit={(e) =>
          submit(e, "Evaluating checkpoint", async () => {
            await postML("evaluations", {
              model_id: modelId,
              dataset_id: datasetId,
              split,
            });
            setNotice("Evaluation completed and recorded.");
          })
        }
      >
        <h2>Measure a checkpoint</h2>
        <p>
          Evaluate an explicit split without changing weights. Test data must
          not overlap the checkpoint’s training or validation inputs.
        </p>
        <div className="ml-form-grid">
          <SelectRecord
            label="Checkpoint"
            value={modelId}
            onChange={setModelId}
            items={models}
          />
          <SelectRecord
            label="Dataset"
            value={datasetId}
            onChange={setDatasetId}
            items={datasets}
          />
          <Field label="Evaluation split">
            <select value={split} onChange={(e) => setSplit(e.target.value)}>
              <option value="test">Test · held out</option>
              <option value="validation">Validation</option>
            </select>
          </Field>
        </div>
        <button
          className="primary-button"
          disabled={!!busy || !modelId || !datasetId}
        >
          Run evaluation
        </button>
      </form>
      {!evaluations.length && (
        <Empty>
          No separate evaluations recorded yet. Training validation metrics
          remain attached to each model.
        </Empty>
      )}
      {evaluations.map((item) => (
        <article className="ml-card" key={item.id}>
          <h3>
            Checkpoint {short(item.configuration.model_id)} ·{" "}
            {item.configuration.split}
          </h3>
          <p>
            Dataset {short(item.configuration.dataset_id)} ·{" "}
            {new Date(item.created_at).toLocaleString()}
          </p>
          <Metrics metrics={item.metrics} />
          <Confusion record={item} />
          <RecordDetails record={item} />
        </article>
      ))}
    </>
  );
}
