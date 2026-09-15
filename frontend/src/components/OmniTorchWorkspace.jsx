import DataView from "./omnitorch/DataView.jsx";
import DatasetView from "./omnitorch/DatasetView.jsx";
import TrainingView from "./omnitorch/TrainingView.jsx";
import EvaluationView from "./omnitorch/EvaluationView.jsx";
import ModelsView from "./omnitorch/ModelsView.jsx";
import InferenceView from "./omnitorch/InferenceView.jsx";
import { useCallback, useEffect, useRef, useState } from "react";
import { mlRequest } from "../api/mlApi.js";
import "../styles/omnitorch-workspace.css";

const STEPS = ["Data", "Datasets", "Train", "Evaluate", "Models", "Inference"];
const COLLECTIONS = [
  "images",
  "datasets",
  "jobs",
  "models",
  "evaluations",
  "inferences",
];

export default function OmniTorchWorkspace() {
  const [step, setStep] = useState("Data");
  const [records, setRecords] = useState(
    Object.fromEntries(COLLECTIONS.map((key) => [key, []])),
  );
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState("");
  const [selection, setSelection] = useState({});
  const [datasetName, setDatasetName] = useState("");
  const [source, setSource] = useState("user-curated");
  const [datasetId, setDatasetId] = useState("");
  const [modelId, setModelId] = useState("");
  const [imageId, setImageId] = useState("");
  const [split, setSplit] = useState("test");
  const [config, setConfig] = useState({
    epochs: 5,
    batch_size: 16,
    learning_rate: 0.01,
    seed: 42,
  });
  const [demo, setDemo] = useState(null);
  const mounted = useRef(true);
  const refreshVersion = useRef(0);
  const tabRefs = useRef([]);
  const { images, datasets, jobs, models, evaluations, inferences } = records;
  const activeJob = jobs.find((job) =>
    ["queued", "running"].includes(job.status),
  );
  const activeJobId = activeJob?.id;
  const selectedDataset = datasets.find((item) => item.id === datasetId);
  const selectedModel = models.find((item) => item.id === modelId);
  const latestJob = activeJob || jobs[0];
  const refresh = useCallback(async () => {
    const version = ++refreshVersion.current;
    const results = await Promise.all(
      COLLECTIONS.map((key) => mlRequest(`/v2/${key}`)),
    );
    if (mounted.current && version === refreshVersion.current) {
      setRecords(
        Object.fromEntries(
          COLLECTIONS.map((key, i) => [key, results[i].items]),
        ),
      );
      setLoaded(true);
    }
  }, []);
  useEffect(() => {
    mounted.current = true;
    refresh().catch((err) => {
      if (mounted.current) setError(err.message);
    });
    return () => {
      mounted.current = false;
    };
  }, [refresh]);
  useEffect(() => {
    if (!activeJobId) return;
    let stopped = false;
    let timer;
    async function poll() {
      try {
        await refresh();
      } catch (err) {
        if (!stopped) setError(`Progress refresh failed: ${err.message}`);
      }
      if (!stopped) timer = setTimeout(poll, 1500);
    }
    timer = setTimeout(poll, 1500);
    return () => {
      stopped = true;
      clearTimeout(timer);
    };
  }, [activeJobId, refresh]);

  async function perform(label, action) {
    setBusy(label);
    setError("");
    setNotice("");
    try {
      await action();
      await refresh();
    } catch (err) {
      if (mounted.current) setError(err.message);
    } finally {
      if (mounted.current) setBusy("");
    }
  }
  function updateMember(id, changes) {
    setSelection((current) => ({
      ...current,
      [id]: { label: "", split: "train", ...current[id], ...changes },
    }));
  }
  function switchTab(event, index) {
    const offset =
      event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    const next =
      event.key === "Home"
        ? 0
        : event.key === "End"
          ? STEPS.length - 1
          : (index + offset + STEPS.length) % STEPS.length;
    if (!offset && !["Home", "End"].includes(event.key)) return;
    event.preventDefault();
    setStep(STEPS[next]);
    tabRefs.current[next]?.focus();
  }
  const submit = (event, label, action) => {
    event.preventDefault();
    perform(label, action);
  };

  return (
    <section className="page ml-workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">OMNITorch / 0.2</p>
          <h1>Image learning laboratory</h1>
          <p>
            Preserve your inputs. Curate a dataset. Run a reproducible
            experiment.
          </p>
        </div>
      </header>
      <div className="ml-policy">
        <span>Explicit learning</span>
        <p>
          Uploads preserve images. Training starts only when you request it.
          Evaluation and checkpoint selection are separate steps.
        </p>
      </div>
      <div className="ml-tabs" role="tablist" aria-label="Learning workflow">
        {STEPS.map((name, index) => (
          <button
            ref={(el) => {
              tabRefs.current[index] = el;
            }}
            key={name}
            id={`ml-tab-${name}`}
            role="tab"
            aria-selected={step === name}
            aria-controls={`ml-panel-${name}`}
            tabIndex={step === name ? 0 : -1}
            onKeyDown={(e) => switchTab(e, index)}
            onClick={() => setStep(name)}
          >
            <span>{String(index + 1).padStart(2, "0")}</span>
            {name}
          </button>
        ))}
      </div>
      <div className="ml-feedback" aria-live="polite">
        {busy ? `${busy}…` : notice}
      </div>
      {error && (
        <div className="ml-error" role="alert">
          <p>{error}</p>
          <button
            className="secondary-button"
            onClick={() => perform("Refreshing workspace", refresh)}
            disabled={!!busy}
          >
            Refresh workspace
          </button>
        </div>
      )}
      {!loaded && !error && (
        <p role="status">Loading local experiment records…</p>
      )}
      <div
        role="tabpanel"
        id={`ml-panel-${step}`}
        aria-labelledby={`ml-tab-${step}`}
        tabIndex={0}
      >
        {step === "Data" && (
          <DataView
            images={images}
            busy={busy}
            perform={perform}
            setNotice={setNotice}
            refresh={refresh}
            loaded={loaded}
          />
        )}
        {step === "Datasets" && (
          <DatasetView
            submit={submit}
            selection={selection}
            datasetName={datasetName}
            source={source}
            setDatasetId={setDatasetId}
            setNotice={setNotice}
            setDatasetName={setDatasetName}
            setSource={setSource}
            images={images}
            updateMember={updateMember}
            busy={busy}
            datasets={datasets}
          />
        )}
        {step === "Train" && (
          <TrainingView
            submit={submit}
            datasetId={datasetId}
            config={config}
            setRecords={setRecords}
            setNotice={setNotice}
            setDatasetId={setDatasetId}
            datasets={datasets}
            selectedDataset={selectedDataset}
            setConfig={setConfig}
            busy={busy}
            activeJob={activeJob}
            latestJob={latestJob}
            setModelId={setModelId}
            setStep={setStep}
            jobs={jobs}
          />
        )}
        {step === "Evaluate" && (
          <EvaluationView
            submit={submit}
            modelId={modelId}
            datasetId={datasetId}
            split={split}
            setNotice={setNotice}
            setModelId={setModelId}
            models={models}
            setDatasetId={setDatasetId}
            datasets={datasets}
            setSplit={setSplit}
            busy={busy}
            evaluations={evaluations}
          />
        )}
        {step === "Models" && (
          <ModelsView
            models={models}
            modelId={modelId}
            evaluations={evaluations}
            setModelId={setModelId}
            setStep={setStep}
          />
        )}
        {step === "Inference" && (
          <InferenceView
            submit={submit}
            modelId={modelId}
            imageId={imageId}
            setNotice={setNotice}
            setModelId={setModelId}
            models={models}
            setImageId={setImageId}
            images={images}
            selectedModel={selectedModel}
            busy={busy}
            inferences={inferences}
            setDemo={setDemo}
            perform={perform}
            demo={demo}
          />
        )}
      </div>
      <footer className="ml-footer">
        Classification foundation · component recognition, defect detection,
        segmentation, and mission-outcome learning remain future work.
      </footer>
    </section>
  );
}
