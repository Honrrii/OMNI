import { uploadImage, imageUrl } from "../../api/mlApi.js";
import { Field, Empty, RecordDetails } from "./shared.jsx";

export default function DataView({
  images,
  busy,
  perform,
  setNotice,
  refresh,
  loaded,
}) {
  return (
    <>
      <section className="ml-card">
        <div className="ml-section-title">
          <div>
            <p className="eyebrow">Image collection</p>
            <h2>Bring your own images</h2>
          </div>
          <span>{images.length} images</span>
        </div>
        <p>
          PNG, JPEG or WebP · up to 10 MiB and 16 megapixels per image. Original
          bytes stay intact; previews and RGB 32 × 32 inputs are separate
          artifacts.
        </p>
        <Field label="Upload images">
          <input
            type="file"
            multiple
            accept="image/png,image/jpeg,image/webp"
            disabled={!!busy}
            onChange={(event) => {
              const files = Array.from(event.target.files || []);
              event.target.value = "";
              if (files.length)
                perform("Importing images", async () => {
                  let count = 0;
                  for (const file of files) {
                    await uploadImage(file);
                    count++;
                    setNotice(`${count} images imported`);
                    await refresh();
                  }
                  setNotice(
                    `${count} images preserved. Create a dataset when you are ready.`,
                  );
                });
            }}
          />
        </Field>
      </section>
      {!images.length && loaded && (
        <Empty>
          Your image collection is empty. Upload images to inspect them and
          begin curating a dataset.
        </Empty>
      )}
      <div className="ml-image-grid">
        {images.map((item) => (
          <article className="ml-image-card" key={item.id}>
            <img
              src={imageUrl(item.id)}
              alt={`Preview of ${item.filename}`}
              loading="lazy"
              width="256"
              height="180"
            />
            <div>
              <h3>{item.filename}</h3>
              <p>
                {item.width} × {item.height} · {item.channels} channels ·{" "}
                {item.format}
              </p>
              <div className="ml-links">
                <a href={imageUrl(item.id, "original")}>Original</a>
                <a
                  href={imageUrl(item.id, "preprocessed")}
                  target="_blank"
                  rel="noreferrer"
                >
                  Training input ↗
                </a>
              </div>
              <RecordDetails record={item} title="Image provenance" />
            </div>
          </article>
        ))}
      </div>
    </>
  );
}
