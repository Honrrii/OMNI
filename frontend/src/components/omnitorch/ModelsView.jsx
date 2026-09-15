import { Empty, Metrics, RecordDetails } from "./shared.jsx";
import { short } from "./formatters.js";

export default function ModelsView({
  models,
  modelId,
  evaluations,
  setModelId,
  setStep,
}) {
  return (
    <>
      <div className="ml-section-title">
        <div>
          <h2>Local model registry</h2>
          <p>
            Each completed training run creates a new checkpoint. Selection is
            explicit; no model is automatically promoted.
          </p>
        </div>
      </div>
      {!models.length && (
        <Empty>
          No trained checkpoints. Complete a training run to register your first
          model.
        </Empty>
      )}
      {models.map((item) => (
        <article
          className={`ml-card ${modelId === item.id ? "ml-selected" : ""}`}
          key={item.id}
        >
          <p className="eyebrow">
            {item.architecture} / {short(item.id)}
          </p>
          <h3>{item.classes.join(" · ")}</h3>
          <p>{item.architecture_detail}</p>
          <p>
            Dataset {short(item.dataset_id)} · seed {item.configuration.seed} ·{" "}
            {item.configuration.epochs} epochs ·{" "}
            {new Date(item.created_at).toLocaleString()}
          </p>
          <Metrics metrics={item.metrics.validation} />
          <p className="ml-note">
            Metrics above are training-time validation. Separate evaluations:{" "}
            {
              evaluations.filter((e) => e.configuration.model_id === item.id)
                .length
            }
            .
          </p>
          <button
            className="secondary-button"
            onClick={() => {
              setModelId(item.id);
              setStep("Inference");
            }}
          >
            Use checkpoint for inference →
          </button>
          <RecordDetails
            record={item}
            title="Checkpoint, configuration & provenance"
          />
        </article>
      ))}
    </>
  );
}
