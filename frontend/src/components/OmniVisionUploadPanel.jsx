import { useEffect, useRef, useState } from "react";

const API_BASE = "http://127.0.0.1:8000/api/ml";

function ConfidenceBar({ percent }) {
  const value = parseFloat(percent) || 0;
  const color =
    value >= 80
      ? "rgba(124, 255, 200, 0.85)"
      : value >= 50
      ? "rgba(255, 191, 74, 0.85)"
      : "rgba(255, 122, 122, 0.85)";

  return (
    <div
      style={{
        margin: "8px 0",
        height: "8px",
        borderRadius: "999px",
        background: "rgba(255,255,255,0.08)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: `${Math.min(value, 100)}%`,
          height: "100%",
          background: color,
          borderRadius: "999px",
          transition: "width 0.5s ease",
        }}
      />
    </div>
  );
}

function InfoRow({ label, value }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "baseline",
        padding: "5px 0",
        borderBottom: "1px solid rgba(255,255,255,0.055)",
        gap: "12px",
      }}
    >
      <span style={{ color: "rgba(180,200,230,0.65)", fontSize: "0.78rem", flexShrink: 0 }}>
        {label}
      </span>
      <span
        style={{
          color: "#dff8ff",
          fontSize: "0.88rem",
          fontWeight: 700,
          textAlign: "right",
          wordBreak: "break-word",
        }}
      >
        {value ?? "—"}
      </span>
    </div>
  );
}

function TopKRow({ rank, item }) {
  const pct = parseFloat(item.confidence_percent) || 0;
  return (
    <div style={{ marginBottom: "10px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          fontSize: "0.84rem",
          marginBottom: "3px",
        }}
      >
        <span style={{ color: rank === 1 ? "#7cffc8" : "rgba(220,235,255,0.75)" }}>
          {rank}. {item.label}
        </span>
        <span style={{ color: "rgba(180,200,230,0.7)" }}>{item.confidence_percent}</span>
      </div>
      <ConfidenceBar percent={item.confidence_percent} />
    </div>
  );
}

export default function OmniVisionUploadPanel() {
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("fashion_mnist_mlp");
  const [result, setResult] = useState(null);
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);

  // Load model list on mount.
  useEffect(() => {
    fetch(`${API_BASE}/models`)
      .then((res) => res.json())
      .then((data) => {
        if (Array.isArray(data.models)) {
          setModels(data.models);
        }
      })
      .catch(() => {
        // Non-fatal — model selector falls back to default.
      });
  }, []);

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setResult(null);
    setError("");
    setPreview(URL.createObjectURL(file));
  };

  const handleUpload = async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setError("Select an image file first.");
      return;
    }

    setLoading(true);
    setError("");
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("model_name", selectedModel);

    try {
      const response = await fetch(`${API_BASE}/analyze-image`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data?.detail || "OMNITorch inference failed.");
      }

      setResult(data);
    } catch (err) {
      setError(err.message || "Unknown error during OMNITorch inference.");
    } finally {
      setLoading(false);
    }
  };

  const panelStyle = {
    padding: "24px",
    border: "1px solid rgba(60,140,255,0.18)",
    borderRadius: "24px",
    background:
      "linear-gradient(145deg, rgba(255,255,255,0.035), rgba(255,255,255,0.01)), rgba(5,11,23,0.14)",
    backdropFilter: "blur(14px)",
    boxShadow: "0 24px 80px rgba(0,0,0,0.38)",
    maxWidth: "860px",
    margin: "0 auto",
    color: "#f7fbff",
  };

  const sectionStyle = {
    marginTop: "22px",
    padding: "16px",
    border: "1px solid rgba(255,255,255,0.075)",
    borderRadius: "18px",
    background: "rgba(255,255,255,0.030)",
  };

  return (
    <div style={panelStyle}>
      {/* Header */}
      <p
        style={{
          margin: "0 0 6px",
          color: "#7cffc8",
          textTransform: "uppercase",
          letterSpacing: "0.22em",
          fontSize: "0.72rem",
          fontWeight: 800,
        }}
      >
        OMNITorch v0.1
      </p>
      <h2 style={{ margin: "0 0 8px", fontSize: "1.65rem", fontWeight: 800, letterSpacing: "-0.03em" }}>
        Vision Inference Panel
      </h2>
      <p style={{ margin: 0, color: "rgba(200,215,235,0.72)", lineHeight: 1.6 }}>
        Upload an image to run OMNITorch inference. Currently using the Fashion-MNIST demo
        classifier. Future models will support CAD screenshot review and robot component
        classification.
      </p>

      {/* Model selector */}
      {models.length > 0 && (
        <div style={{ marginTop: "18px" }}>
          <label
            style={{
              display: "block",
              marginBottom: "6px",
              color: "rgba(180,200,230,0.65)",
              fontSize: "0.78rem",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.08em",
            }}
          >
            Model
          </label>
          <select
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            style={{
              width: "100%",
              padding: "10px 14px",
              color: "#f7fbff",
              background: "rgba(5,11,23,0.55)",
              border: "1px solid rgba(60,140,255,0.22)",
              borderRadius: "12px",
              fontSize: "0.88rem",
              outline: "none",
              cursor: "pointer",
            }}
          >
            {models.map((m) => (
              <option key={m.model_name} value={m.model_name}>
                {m.model_name} — {m.task_type} {!m.weights_available ? "(unavailable)" : ""}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Upload zone */}
      <div style={{ marginTop: "18px", display: "flex", gap: "14px", flexWrap: "wrap" }}>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileChange}
          style={{ flex: 1, minWidth: "200px" }}
        />

        <button
          onClick={handleUpload}
          disabled={loading}
          style={{
            padding: "11px 20px",
            borderRadius: "999px",
            border: "1px solid rgba(80,220,255,0.42)",
            background: loading
              ? "rgba(60,200,255,0.25)"
              : "linear-gradient(135deg, rgba(60,200,255,0.95), rgba(30,160,210,0.88))",
            color: "#01080e",
            fontWeight: 800,
            fontSize: "0.86rem",
            letterSpacing: "0.06em",
            textTransform: "uppercase",
            cursor: loading ? "not-allowed" : "pointer",
            opacity: loading ? 0.65 : 1,
            transition: "all 0.2s ease",
          }}
        >
          {loading ? "Analyzing..." : "Run OMNITorch"}
        </button>
      </div>

      {/* Image preview */}
      {preview && (
        <div style={{ marginTop: "16px" }}>
          <img
            src={preview}
            alt="Upload preview"
            style={{
              maxHeight: "180px",
              maxWidth: "100%",
              borderRadius: "14px",
              border: "1px solid rgba(60,140,255,0.18)",
              objectFit: "contain",
            }}
          />
        </div>
      )}

      {/* Error */}
      {error && (
        <p style={{ marginTop: "14px", color: "#fecaca", lineHeight: 1.55 }}>{error}</p>
      )}

      {/* Result */}
      {result && (
        <>
          {/* Primary prediction */}
          <div
            style={{
              ...sectionStyle,
              borderColor: "rgba(124,255,200,0.28)",
              background: "rgba(124,255,200,0.05)",
            }}
          >
            <p
              style={{
                margin: "0 0 4px",
                color: "#7cffc8",
                textTransform: "uppercase",
                letterSpacing: "0.18em",
                fontSize: "0.70rem",
                fontWeight: 800,
              }}
            >
              Prediction
            </p>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                flexWrap: "wrap",
                gap: "8px",
              }}
            >
              <h3
                style={{
                  margin: 0,
                  fontSize: "clamp(1.6rem, 4vw, 2.8rem)",
                  fontWeight: 900,
                  letterSpacing: "-0.04em",
                  color: "#ffffff",
                }}
              >
                {result.prediction?.label}
              </h3>
              <span
                style={{
                  padding: "8px 14px",
                  borderRadius: "999px",
                  background: "rgba(124,255,200,0.12)",
                  border: "1px solid rgba(124,255,200,0.36)",
                  color: "#dfffee",
                  fontWeight: 900,
                  fontSize: "1.1rem",
                  letterSpacing: "0.04em",
                }}
              >
                {result.prediction?.confidence_percent}
              </span>
            </div>
            <ConfidenceBar percent={result.prediction?.confidence_percent} />
          </div>

          {/* Top-K */}
          {result.top_k?.length > 1 && (
            <div style={sectionStyle}>
              <p
                style={{
                  margin: "0 0 12px",
                  color: "#dbeafe",
                  fontWeight: 700,
                  fontSize: "0.9rem",
                }}
              >
                Top Predictions
              </p>
              {result.top_k.map((item, index) => (
                <TopKRow key={item.label} rank={index + 1} item={item} />
              ))}
            </div>
          )}

          {/* OMNI Interpretation */}
          {result.omni_interpretation && (
            <div style={sectionStyle}>
              <p
                style={{
                  margin: "0 0 12px",
                  color: "#dbeafe",
                  fontWeight: 700,
                  fontSize: "0.9rem",
                }}
              >
                OMNI Interpretation
              </p>
              <p style={{ margin: "0 0 10px", color: "rgba(210,225,245,0.85)", lineHeight: 1.65 }}>
                {result.omni_interpretation.summary}
              </p>
              <InfoRow label="Engineering relevance" value={result.omni_interpretation.engineering_relevance} />
              <InfoRow label="Limitations" value={result.omni_interpretation.limitations} />
              <InfoRow label="Next step" value={result.omni_interpretation.next_step} />
            </div>
          )}

          {/* Runtime */}
          {result.runtime && (
            <div style={sectionStyle}>
              <p
                style={{
                  margin: "0 0 10px",
                  color: "#dbeafe",
                  fontWeight: 700,
                  fontSize: "0.9rem",
                }}
              >
                Runtime
              </p>
              <InfoRow label="Device" value={result.runtime.device} />
              <InfoRow label="PyTorch" value={result.runtime.torch_version} />
              <InfoRow label="CUDA available" value={result.runtime.cuda_available ? "Yes" : "No"} />
              {result.runtime.inference_ms != null && (
                <InfoRow label="Inference time" value={`${result.runtime.inference_ms} ms`} />
              )}
              <InfoRow label="Model" value={result.model_name} />
              <InfoRow label="Task" value={result.task_type} />
            </div>
          )}

          {/* Provenance */}
          {result.provenance && (
            <div
              style={{
                marginTop: "16px",
                padding: "12px 14px",
                border: "1px solid rgba(255,210,120,0.22)",
                borderRadius: "14px",
                background: "rgba(255,190,90,0.06)",
              }}
            >
              <strong style={{ color: "#ffe0b0", fontSize: "0.82rem" }}>
                Human review required:
              </strong>{" "}
              <span style={{ color: "rgba(255,230,180,0.80)", fontSize: "0.82rem" }}>
                OMNITorch results are not engineering decisions. This is a demo classifier.
                {result.provenance.model_version && ` Model v${result.provenance.model_version}.`}
              </span>
            </div>
          )}
        </>
      )}
    </div>
  );
}
