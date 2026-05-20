import { useState } from "react";

const API_ROOT = "http://127.0.0.1:8000";

export default function OmniVisionUploadPanel() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  function handleFileChange(event) {
    const file = event.target.files?.[0];

    setResult(null);
    setError("");

    if (!file) {
      setSelectedFile(null);
      setPreviewUrl("");
      return;
    }

    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  }

  async function handleAnalyzeImage() {
    if (!selectedFile) {
      setError("Please choose an image first.");
      return;
    }

    setStatus("loading");
    setError("");
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch(`${API_ROOT}/api/ml/classify-demo`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Image classification failed.");
      }

      setResult(data);
      setStatus("done");
    } catch (err) {
      setError(err.message);
      setStatus("error");
    }
  }

  return (
    <section className="omni-vision-panel">
      <div className="vision-header">
        <div>
          <p className="eyebrow">OMNI Vision</p>
          <h2>Image Intake Demo</h2>
          <p>
            Upload an image and send it to OMNI&apos;s PyTorch inference service.
            This currently uses a demo Fashion-MNIST model, but the pipeline can
            later support CAD screenshots, robot images, and sensor-vision tasks.
          </p>
        </div>
      </div>

      <div className="vision-grid">
        <div className="vision-card">
          <h3>Upload Image</h3>

          <input
            type="file"
            accept="image/png,image/jpeg,image/jpg,image/webp,image/bmp"
            onChange={handleFileChange}
          />

          {previewUrl && (
            <div className="vision-preview-wrap">
              <img
                src={previewUrl}
                alt="Selected upload preview"
                className="vision-preview"
              />
            </div>
          )}

          <button
            className="vision-button"
            onClick={handleAnalyzeImage}
            disabled={status === "loading"}
          >
            {status === "loading" ? "Analyzing..." : "Send to OMNI Vision"}
          </button>

          {error && <p className="vision-error">{error}</p>}
        </div>

        <div className="vision-card">
          <h3>ML Result</h3>

          {!result && (
            <p className="muted">
              No result yet. Upload an image and run the classifier.
            </p>
          )}

          {result && (
            <div className="vision-result">
              <p>
                <strong>Status:</strong> {result.status}
              </p>
              <p>
                <strong>File:</strong> {result.filename}
              </p>
              <p>
                <strong>Model:</strong> {result.result.model_name}
              </p>
              <p>
                <strong>Prediction:</strong> {result.result.predicted_class}
              </p>
              <p>
                <strong>Confidence:</strong>{" "}
                {(result.result.confidence * 100).toFixed(2)}%
              </p>
              <p>
                <strong>Device:</strong> {result.result.device}
              </p>
              <p className="muted">{result.result.note}</p>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}