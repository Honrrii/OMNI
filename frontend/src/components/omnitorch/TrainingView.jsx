import { postML } from "../../api/mlApi.js";
import { SelectRecord, Field, Empty, RecordDetails } from "./shared.jsx";
import { short, percent } from "./formatters.js";

export default function TrainingView({
  submit,
  datasetId,
  config,
  setRecords,
  setNotice,
  setDatasetId,
  datasets,
  selectedDataset,
  setConfig,
  busy,
  activeJob,
  latestJob,
  setModelId,
  setStep,
  jobs,
}) {
  return (
    <div className="ml-columns">
      <form
        className="ml-card"
        onSubmit={(e) =>
          submit(e, "Submitting training", async () => {
            const result = await postML("training", {
              dataset_id: datasetId,
              ...config,
            });
            setRecords((current) => ({
              ...current,
              jobs: [
                result,
                ...current.jobs.filter((job) => job.id !== result.id),
              ],
            }));
            setNotice(
              `Training request ${short(result.id)} accepted. Progress below comes from the worker.`,
            );
          })
        }
      >
        <p className="eyebrow">Controlled experiment</p>
        <h2>Train a classifier</h2>
        <SelectRecord
          label="Dataset"
          value={datasetId}
          onChange={setDatasetId}
          items={datasets}
          describe={(item) => `${item.name} · ${short(item.id)}`}
        />
        {selectedDataset && (
          <p>
            {selectedDataset.split_counts.train} training images ·{" "}
            {selectedDataset.split_counts.validation} validation images
          </p>
        )}
        <p className="ml-note">
          CPU · rgb_pool_mlp_v1
          <br />
          Average pool 8 × 8 → 192 inputs → 32 hidden units → class logits. SGD
          optimizer. Maximum 30 epochs / 300 seconds.
        </p>
        <div className="ml-form-grid">
          {[
            ["epochs", "Epochs", 1, 30, 1],
            ["batch_size", "Batch size", 1, 64, 1],
            ["learning_rate", "Learning rate", 0.00001, 0.1, 0.00001],
            ["seed", "Seed", 0, 2147483647, 1],
          ].map(([key, label, min, max, step]) => (
            <Field key={key} label={label}>
              <input
                type="number"
                required
                min={min}
                max={max}
                step={step}
                value={config[key]}
                onChange={(e) =>
                  setConfig({
                    ...config,
                    [key]: e.target.value === "" ? "" : Number(e.target.value),
                  })
                }
              />
            </Field>
          ))}
        </div>
        <button
          className="primary-button"
          disabled={!!busy || !!activeJob || !datasetId}
        >
          {activeJob ? "Training in progress" : "Start training"}
        </button>
      </form>
      <section className="ml-card">
        <h2>Experiment progress</h2>
        {!latestJob ? (
          <Empty>
            No training runs yet. Configure a dataset and start an experiment.
          </Empty>
        ) : (
          <>
            <p role="status">
              Run {short(latestJob.id)} · {latestJob.status} · epoch{" "}
              {latestJob.epoch} / {latestJob.configuration.epochs}
            </p>
            <progress
              aria-label="Completed training epochs"
              value={latestJob.epoch}
              max={latestJob.configuration.epochs}
            />
            {latestJob.error && <p className="ml-error">{latestJob.error}</p>}
            <div className="ml-table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Epoch</th>
                    <th>Train loss</th>
                    <th>Val. loss</th>
                    <th>Val. accuracy</th>
                  </tr>
                </thead>
                <tbody>
                  {latestJob.history.map((row) => (
                    <tr key={row.epoch}>
                      <td>{row.epoch}</td>
                      <td>{row.loss.toFixed(4)}</td>
                      <td>{row.validation_loss.toFixed(4)}</td>
                      <td>{percent(row.validation_accuracy)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {latestJob.model_id && (
              <button
                className="secondary-button"
                onClick={() => {
                  setModelId(latestJob.model_id);
                  setStep("Models");
                }}
              >
                Inspect checkpoint →
              </button>
            )}
            <RecordDetails record={latestJob} />
          </>
        )}
        {jobs.slice(1).map((job) => (
          <RecordDetails
            key={job.id}
            record={job}
            title={`Run ${short(job.id)} · ${job.status}`}
          />
        ))}
      </section>
    </div>
  );
}
