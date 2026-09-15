import { postML, imageUrl, mlRequest } from "../../api/mlApi.js";
import { SelectRecord, RecordDetails, Field } from "./shared.jsx";
import { short, percent } from "./formatters.js";

export default function InferenceView({
  submit,
  modelId,
  imageId,
  setNotice,
  setModelId,
  models,
  setImageId,
  images,
  selectedModel,
  busy,
  inferences,
  setDemo,
  perform,
  demo,
}) {
  return (
    <>
      <form
        className="ml-card"
        onSubmit={(e) =>
          submit(e, "Running inference", async () => {
            await postML("inferences", {
              model_id: modelId,
              image_id: imageId,
            });
            setNotice("Inference completed. The checkpoint was not modified.");
          })
        }
      >
        <h2>Inspect model output</h2>
        <div className="ml-form-grid">
          <SelectRecord
            label="Checkpoint"
            value={modelId}
            onChange={setModelId}
            items={models}
          />
          <SelectRecord
            label="Image"
            value={imageId}
            onChange={setImageId}
            items={images}
            describe={(item) => `${item.filename} · ${short(item.id)}`}
          />
        </div>
        {selectedModel && (
          <p>Trained labels: {selectedModel.classes.join(", ")}</p>
        )}
        {imageId && (
          <img
            className="ml-inference-preview"
            src={imageUrl(imageId)}
            alt="Selected inference input"
          />
        )}
        <button
          className="primary-button"
          disabled={!!busy || !modelId || !imageId}
        >
          Run inference
        </button>
      </form>
      {inferences.map((item) => (
        <article className="ml-card" key={item.id}>
          <p className="eyebrow">
            Checkpoint {short(item.configuration.model_id)} · image{" "}
            {short(item.configuration.image_id)}
          </p>
          <h3>{item.prediction}</h3>
          {item.outputs.map((output) => (
            <div className="ml-probability" key={output.label}>
              <span>{output.label}</span>
              <meter
                min="0"
                max="1"
                value={output.probability}
                aria-label={`${output.label} probability`}
              />
              <strong>{percent(output.probability)}</strong>
            </div>
          ))}
          <p>{item.interpretation}</p>
          <RecordDetails
            record={item}
            title="Logits, probabilities & runtime"
          />
        </article>
      ))}
      <details className="ml-card">
        <summary>Legacy Fashion-MNIST demo</summary>
        <p>
          The bundled clothing classifier remains available as a pipeline
          demonstration. It has no engineering-image understanding.
        </p>
        <Field label="Demo image">
          <input
            type="file"
            accept="image/*"
            disabled={!!busy}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) {
                setDemo(null);
                perform("Running legacy demo", async () => {
                  const form = new FormData();
                  form.append("file", file);
                  setDemo(
                    await mlRequest("/classify-demo", {
                      method: "POST",
                      body: form,
                    }),
                  );
                });
              }
            }}
          />
        </Field>
        {demo && (
          <>
            <h3>
              {demo.prediction?.label} · {demo.prediction?.confidence_percent}
            </h3>
            <RecordDetails record={demo} title="Demo result" />
          </>
        )}
      </details>
    </>
  );
}
