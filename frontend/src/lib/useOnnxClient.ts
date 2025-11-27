// client/src/lib/useOnnxClient.ts
import { useEffect, useRef, useState } from "react";
import * as ort from "onnxruntime-web";

type ModelInfo = {
  id: string;
  version: string;
  checksum: string;
  created_at: string;
  url: string;        // .pth (unused in browser)
  onnx_url?: string;  // e.g. /artifacts/<id>/global.onnx
};

type Status = "idle" | "loading" | "ready" | "error";

const CENTRAL_BASE = (import.meta.env.VITE_CENTRAL_BASE as string) || "http://localhost:8000";
const CLASSES = ["No_DR", "Mild", "Moderate", "Severe", "Proliferative_DR"];

// ORT WASM setup (must be before creating a session)
ort.env.wasm.wasmPaths = "/ort/";   // served from client/public/ort
ort.env.wasm.numThreads = 1;        // avoid cross-origin isolation issues
ort.env.wasm.proxy = false;
ort.env.wasm.simd = true;

export function useOnnxClient() {
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [model, setModel] = useState<ModelInfo | null>(null);
  const sessionRef = useRef<ort.InferenceSession | null>(null);
  const inputNameRef = useRef<string | null>(null);
  const outputNameRef = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setStatus("loading");
        setError(null);

        // 1) Get current model meta from central
        const r = await fetch(`${CENTRAL_BASE}/v1/models/current`);
        if (!r.ok) {
          const t = await r.text().catch(() => "");
          throw new Error(`GET /v1/models/current failed: ${r.status} ${r.statusText} — ${t}`);
        }
        const m: ModelInfo = await r.json();
        if (cancelled) return;
        setModel(m);

        // 2) Must have an ONNX URL
        if (!m.onnx_url) {
          throw new Error("Central returned no onnx_url for the current model.");
        }
        const onnxUrl = `${CENTRAL_BASE}${m.onnx_url}`;

        // 3) Load ORT session
        const session = await ort.InferenceSession.create(onnxUrl, {
          executionProviders: ["wasm"],
          graphOptimizationLevel: "all",
        });
        if (cancelled) return;

        sessionRef.current = session;

        // Discover input/output names dynamically
        const inputs = session.inputNames;
        const outputs = session.outputNames;
        if (!inputs?.length || !outputs?.length) {
          throw new Error(`ONNX model has no inputs/outputs. inputs=${inputs?.length} outputs=${outputs?.length}`);
        }
        inputNameRef.current = inputs[0];
        outputNameRef.current = outputs[0];

        setStatus("ready");
      } catch (e: any) {
        setError(e?.message || String(e));
        setStatus("error");
      }
    })();
    return () => { cancelled = true; };
  }, []);

  async function predict(file: File) {
    if (!file) throw new Error("No file provided");
    if (!sessionRef.current) throw new Error("Model not ready");
    const inputName = inputNameRef.current!;
    const outputName = outputNameRef.current!;

    const img = await fileToImageData(file, 224, 224);
    const tensor = toCHWTensor(img, 224);
    try {
      const out = await sessionRef.current.run({ [inputName]: tensor });
      const tensorOut = out[outputName] ?? Object.values(out)[0];
      const logits = Array.from(tensorOut.data as Float32Array);
      const probs = softmax(logits);
      return CLASSES.map((label, i) => ({ label, prob: probs[i] ?? 0 }))
        .sort((a, b) => b.prob - a.prob);
    } catch (err: any) {
      // Helpful message if input name mismatch happens
      throw new Error(`ORT run failed: ${err?.message || err}. Input="${inputName}", Output="${outputName}"`);
    }
  }

  return { status, error, model, predict, CLASSES };
}

/* ---------- helpers ---------- */
function softmax(arr: number[]) {
  const m = Math.max(...arr);
  const exps = arr.map(v => Math.exp(v - m));
  const s = exps.reduce((a, b) => a + b, 0);
  return exps.map(v => v / s);
}

async function fileToImageData(file: File, W: number, H: number): Promise<ImageData> {
  const bmp = await createImageBitmap(file);
  const canvas = typeof OffscreenCanvas !== "undefined"
    ? new OffscreenCanvas(W, H)
    : (() => { const c = document.createElement("canvas"); c.width = W; c.height = H; return c; })();
  const ctx = (canvas as any).getContext("2d", { willReadFrequently: true }) as OffscreenCanvasRenderingContext2D | CanvasRenderingContext2D;
  ctx.drawImage(bmp, 0, 0, W, H);
  return ctx.getImageData(0, 0, W, H);
}

function toCHWTensor(img: ImageData, size: number) {
  const chw = new Float32Array(3 * size * size);
  const ch = size * size;
  const data = img.data;
  let i = 0;
  for (let p = 0; p < size * size; p++) {
    const r = data[i++] / 255;
    const g = data[i++] / 255;
    const b = data[i++] / 255;
    i++;
    chw[p] = r;
    chw[p + ch] = g;
    chw[p + 2 * ch] = b;
  }
  return new ort.Tensor("float32", chw, [1, 3, size, size]);
}
