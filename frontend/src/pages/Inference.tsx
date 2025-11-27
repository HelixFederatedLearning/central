// src/pages/Inference.tsx
import React, { useState } from "react";
import { useOnnxClient } from "../lib/useOnnxClient";
import "./inference.css";

export default function Inference() {
  const { status, error, model, predict, CLASSES } = useOnnxClient();
  const [file, setFile] = useState<File | null>(null);
  const [running, setRunning] = useState(false);
  const [probs, setProbs] = useState<{ label: string; prob: number }[] | null>(null);

  async function onRun() {
    if (!file) return;
    setRunning(true);
    setProbs(null);
    try {
      const res = await predict(file);
      setProbs(res);
    } catch (e: any) {
      alert(e?.message || String(e));
    } finally {
      setRunning(false);
    }
  }

  const top = probs?.[0];

  return (
    <div className="infer-wrap">
      <div className="infer-header">
        <h1>Client-side Inference</h1>
        <p>
          Loads the current ONNX model from the central server and runs inference completely in the
          browser (WASM).
        </p>
      </div>

      <div className="infer-grid">
        {/* Model panel */}
        <div className="infer-panel">
          <h3>Model</h3>
          {status === "loading" && <div className="muted">Loading model…</div>}

          {status === "error" && (
            <div className="infer-model-error">
              Model: Not loaded ❌ — {error}
            </div>
          )}

          {status === "ready" && model && (
            <div className="infer-model-ok">
              Model: Loaded ✅{" "}
              <code className="infer-model-id">{model.version}</code>
              {model.onnx_url && (
                <div className="infer-model-url">
                  ONNX:{" "}
                  <a
                    href={`${
                      import.meta.env.VITE_API_BASE ?? "http://localhost:8000"
                    }${model.onnx_url}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {model.onnx_url}
                  </a>
                </div>
              )}
            </div>
          )}

          {status === "idle" && <div>Model: Not loaded ❌</div>}
        </div>

        {/* Input panel */}
        <div className="infer-panel">
          <h3>Input</h3>
          <div className="infer-input">
            {/* Custom “choose file/folder” block */}
            <label className="infer-file-label">
              <div className="infer-file-main">
                <span className="infer-file-title">Select image</span>
                <span className="infer-file-hint">
                  PNG / JPG · single image (drag &amp; drop or click)
                </span>
              </div>
              <span className="infer-file-button">Browse</span>
              {/* if you want folder selection instead, add webkitdirectory here */}
              <input
                className="infer-file-input"
                type="file"
                accept="image/*"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>

            {file && (
              <div className="infer-file-meta mono">
                Selected: <span>{file.name}</span>
              </div>
            )}

            <button
              className="btn infer-run-btn"
              onClick={onRun}
              disabled={status !== "ready" || !file || running}
            >
              {running ? "Running…" : "Run Inference"}
            </button>
          </div>
        </div>

        {/* Result panel (spans full width) */}
        <div className="infer-panel infer-panel--full">
          <h3>Result</h3>
          {!probs && <div className="muted">No output yet.</div>}

          {probs && (
            <div>
              <div className="infer-result-top">
                <b>Top-1:</b>{" "}
                {top ? `${top.label} (${(top.prob * 100).toFixed(2)}%)` : "-"}
              </div>
              <table className="infer-table">
                <thead>
                  <tr>
                    <th>Class</th>
                    <th>Probability</th>
                  </tr>
                </thead>
                <tbody>
                  {CLASSES.map((c) => {
                    const row = probs.find((p) => p.label === c) || { prob: 0 };
                    return (
                      <tr key={c}>
                        <td>{c}</td>
                        <td>{(row.prob * 100).toFixed(2)}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
