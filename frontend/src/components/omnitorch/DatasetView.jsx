import { postML, imageUrl } from "../../api/mlApi.js";
import { Field, Empty, RecordDetails } from "./shared.jsx";
import { short } from "./formatters.js";

export default function DatasetView({
  submit,
  selection,
  datasetName,
  source,
  setDatasetId,
  setNotice,
  setDatasetName,
  setSource,
  images,
  updateMember,
  busy,
  datasets,
}) {
  return (
    <>
      <form
        className="ml-card"
        onSubmit={(e) =>
          submit(e, "Creating snapshot", async () => {
            const members = Object.entries(selection)
              .filter(([, m]) => m.selected)
              .map(([image_id, m]) => ({
                image_id,
                label: m.label.trim() || null,
                split: m.split,
              }));
            const result = await postML("datasets", {
              name: datasetName,
              source,
              members,
            });
            setDatasetId(result.id);
            setNotice(
              `Snapshot “${result.name}” created. Its labels and membership are immutable.`,
            );
          })
        }
      >
        <h2>Curate a dataset snapshot</h2>
        <p>
          Assign labels and splits deliberately. Training needs at least two
          classes and a labeled validation split. Keep test images held out for
          evaluation.
        </p>
        <div className="ml-form-grid">
          <Field label="Dataset name">
            <input
              required
              maxLength={120}
              value={datasetName}
              onChange={(e) => setDatasetName(e.target.value)}
            />
          </Field>
          <Field label="Source / origin">
            <input
              required
              maxLength={120}
              value={source}
              onChange={(e) => setSource(e.target.value)}
            />
          </Field>
        </div>
        {!images.length ? (
          <Empty>Upload images in Data before creating a dataset.</Empty>
        ) : (
          <div className="ml-curation">
            {images.map((item) => (
              <div className="ml-member" key={item.id}>
                <label className="ml-image-choice">
                  <input
                    type="checkbox"
                    checked={!!selection[item.id]?.selected}
                    onChange={(e) =>
                      updateMember(item.id, {
                        selected: e.target.checked,
                      })
                    }
                  />
                  <img src={imageUrl(item.id)} alt="" width="48" height="48" />
                  <span>
                    {item.filename} <small>{short(item.id)}</small>
                  </span>
                </label>
                <Field label={`Label for ${item.filename}`}>
                  <input
                    maxLength={120}
                    placeholder="Optional until training"
                    value={selection[item.id]?.label || ""}
                    onChange={(e) =>
                      updateMember(item.id, { label: e.target.value })
                    }
                  />
                </Field>
                <Field label={`Split for ${item.filename}`}>
                  <select
                    value={selection[item.id]?.split || "train"}
                    onChange={(e) =>
                      updateMember(item.id, { split: e.target.value })
                    }
                  >
                    <option value="train">Train</option>
                    <option value="validation">Validation</option>
                    <option value="test">Test</option>
                  </select>
                </Field>
              </div>
            ))}
          </div>
        )}
        <p className="ml-note">
          Preprocessing v1: EXIF orientation → white alpha background → RGB →
          bilinear resize to 32 × 32 → values scaled by 1/255. Duplicate image
          content is rejected within a snapshot.
        </p>
        <button
          className="primary-button"
          disabled={!!busy || !Object.values(selection).some((m) => m.selected)}
        >
          Create immutable snapshot
        </button>
      </form>
      {datasets.map((item) => (
        <article className="ml-card" key={item.id}>
          <h3>{item.name}</h3>
          <p>
            {item.split_counts.train} train · {item.split_counts.validation}{" "}
            validation · {item.split_counts.test} test
          </p>
          <RecordDetails
            record={item}
            title={`Snapshot ${short(item.id)} · ${new Date(item.created_at).toLocaleString()}`}
          />
        </article>
      ))}
    </>
  );
}
