import React, { useState } from "react";
import { useOnnxClient } from "../lib/useOnnxClient";

export default function Inference() {
  const { status, error, model, predict, CLASSES } = useOnnxClient();
  const [file, setFile] = useState<File | null>(null);
  const [running, setRunning] = useState(false);
  const [probs, setProbs] = useState<{label:string; prob:number}[] | null>(null);

  async function onRun() {
    if (!file) return;
    setRunning(true); setProbs(null);
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
    <div style={{ padding: 24, maxWidth: 980, margin: "0 auto" }}>
      <h1 style={{ marginBottom: 8 }}>Client-side Inference</h1>
      <p style={{ marginTop: 0, color: "#666" }}>
        Loads the current ONNX model from the central server and runs inference completely in the browser (WASM).
      </p>

      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "1fr", marginTop: 16 }}>
        <div style={{ padding: 16, border: "1px solid #e5e7eb", borderRadius: 12, background: "#fff" }}>
          <h3 style={{ marginTop: 0 }}>Model</h3>
          {status === "loading" && <div>Loading model…</div>}
          {status === "error" && (
            <div style={{ color: "crimson" }}>
              Model: Not loaded ❌ — {error}
            </div>
          )}
          {status === "ready" && model && (
            <div style={{ color: "green" }}>
              Model: Loaded ✅ <code>{model.version}</code>
              {model.onnx_url && (
                <div style={{ marginTop: 6, color: "#666" }}>
                  ONNX: <a href={`${(import.meta.env.VITE_API_BASE ?? "http://localhost:8000")}${model.onnx_url}`} target="_blank" rel="noreferrer">{model.onnx_url}</a>
                </div>
              )}
            </div>
          )}
          {status === "idle" && <div>Model: Not loaded ❌</div>}
        </div>

        <div style={{ padding: 16, border: "1px solid #e5e7eb", borderRadius: 12, background: "#fff" }}>
          <h3 style={{ marginTop: 0 }}>Input</h3>
          <input type="file" accept="image/*" onChange={(e)=> setFile(e.target.files?.[0] ?? null)} />
          <div style={{ marginTop: 12 }}>
            <button className="btn" onClick={onRun} disabled={status!=="ready" || !file || running}>
              {running ? "Running…" : "Run Inference"}
            </button>
          </div>
        </div>

        <div style={{ padding: 16, border: "1px solid #e5e7eb", borderRadius: 12, background: "#fff" }}>
          <h3 style={{ marginTop: 0 }}>Result</h3>
          {!probs && <div>No output yet.</div>}
          {probs && (
            <div>
              <div style={{ marginBottom: 8 }}>
                <b>Top-1:</b> {top ? `${top.label} (${(top.prob*100).toFixed(2)}%)` : "-"}
              </div>
              <table style={{ width: "100%", borderCollapse: "collapse", border: "1px solid #eee" }}>
                <thead>
                  <tr>
                    <th style={{ textAlign: "left", padding: 8, borderBottom: "1px solid #eee" }}>Class</th>
                    <th style={{ textAlign: "right", padding: 8, borderBottom: "1px solid #eee" }}>Probability</th>
                  </tr>
                </thead>
                <tbody>
                  {CLASSES.map(c => {
                    const row = probs.find(p => p.label === c) || { prob: 0 };
                    return (
                      <tr key={c}>
                        <td style={{ padding: 8, borderBottom: "1px solid #f5f5f5" }}>{c}</td>
                        <td style={{ padding: 8, textAlign: "right", borderBottom: "1px solid #f5f5f5", fontVariantNumeric: "tabular-nums" }}>
                          {(row.prob*100).toFixed(2)}%
                        </td>
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
