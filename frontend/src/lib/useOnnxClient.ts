import { useEffect, useRef, useState } from "react";
import * as ort from "onnxruntime-web";
import { get, set, del } from "idb-keyval";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const CLASSES = ["No_DR","Mild","Moderate","Severe","Proliferative_DR"];
const SIZE = 224;

type CurrentModelResp = {
  id: string;
  version: string;
  checksum: string;
  created_at: string;
  url: string;        // .pth
  onnx_url?: string;  // .onnx
};

function softmax(arr: number[]) {
  const m = Math.max(...arr);
  const exps = arr.map(v => Math.exp(v - m));
  const s = exps.reduce((a,b)=>a+b,0);
  return exps.map(v => v/s);
}

async function imageToNCHWTensor(file: File) {
  const bmp = await createImageBitmap(file);
  // offscreen if available; fallback to normal canvas
  const canvas: HTMLCanvasElement = document.createElement("canvas");
  canvas.width = SIZE; canvas.height = SIZE;
  const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
  // fit image into 224x224 (letterbox)
  const scale = Math.min(SIZE / bmp.width, SIZE / bmp.height);
  const w = bmp.width * scale, h = bmp.height * scale;
  const x = (SIZE - w) / 2, y = (SIZE - h) / 2;
  ctx.clearRect(0,0,SIZE,SIZE);
  ctx.drawImage(bmp, x, y, w, h);

  const { data } = ctx.getImageData(0, 0, SIZE, SIZE);
  const chw = new Float32Array(3 * SIZE * SIZE);
  const stride = SIZE * SIZE;
  for (let i = 0, p = 0; i < stride; i++, p += 4) {
    const r = data[p] / 255;
    const g = data[p+1] / 255;
    const b = data[p+2] / 255;
    chw[i] = r; chw[i + stride] = g; chw[i + 2*stride] = b;
  }
  return new ort.Tensor("float32", chw, [1,3,SIZE,SIZE]);
}

const isArrayBuffer = (v: unknown): v is ArrayBuffer => v instanceof ArrayBuffer;
const isUint8Array  = (v: unknown): v is Uint8Array  => v instanceof Uint8Array;
const toUint8Array  = (v: unknown) => (isUint8Array(v) ? v : isArrayBuffer(v) ? new Uint8Array(v) : null);

export function useOnnxClient() {
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [model, setModel] = useState<CurrentModelResp | null>(null);
  const sessionRef = useRef<ort.InferenceSession | null>(null);

  // Configure ORT wasm (do this ONCE before creating a session)
  useEffect(() => {
    // Choose ONE of the two lines below:

    // A) Local (requires public/ort/* present)
    ort.env.wasm.wasmPaths = "/ort/";

    // B) CDN (uncomment this if you don’t want local files)
    // ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.20.0/dist/";

    ort.env.wasm.proxy = false;       // workerless (no COOP/COEP needed)
    try {
      const cores = (navigator as any).hardwareConcurrency ?? 2;
      ort.env.wasm.numThreads = Math.max(1, Math.min(cores, 4));
    } catch {}
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setStatus("loading");
        setError(null);

        // 1) Get current model
        const r = await fetch(`${API_BASE}/v1/models/current`);
        if (!r.ok) throw new Error(`GET /v1/models/current -> ${r.status}`);
        const meta: CurrentModelResp = await r.json();
        setModel(meta);

        const modelURL = meta.onnx_url ? `${API_BASE}${meta.onnx_url}` : "";
        if (!modelURL) throw new Error("No ONNX model available (onnx_url missing)");

        // 2) Try to create session by URL directly
        try {
          const s1 = await ort.InferenceSession.create(modelURL, {
            executionProviders: ["wasm"],
            graphOptimizationLevel: "all",
          });
          if (cancelled) return;
          sessionRef.current = s1;
          setStatus("ready");
          return;
        } catch (e) {
          console.warn("[ORT] URL session failed, falling back to buffer:", (e as any)?.message || e);
        }

        // 3) Fallback: fetch as ArrayBuffer and cache in IndexedDB
        let buf: Uint8Array | null = null;
        const cached = await get(modelURL);
        if (cached) {
          const arr = toUint8Array(cached);
          if (arr) buf = arr; else await del(modelURL);
        }
        if (!buf) {
          const rf = await fetch(modelURL, { cache: "force-cache" });
          if (!rf.ok) {
            const txt = await rf.text().catch(()=> "");
            throw new Error(`Fetch ONNX failed: ${rf.status} ${rf.statusText} — ${txt.slice(0,200)}`);
          }
          const ab = await rf.arrayBuffer();
          await set(modelURL, ab);
          buf = new Uint8Array(ab);
        }

        const s2 = await ort.InferenceSession.create(buf, {
          executionProviders: ["wasm"],
          graphOptimizationLevel: "all",
        });
        if (cancelled) return;
        sessionRef.current = s2;
        setStatus("ready");
      } catch (e: any) {
        if (!cancelled) {
          setError(e?.message || String(e));
          setStatus("error");
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  async function predict(file: File) {
    if (!sessionRef.current) throw new Error("Model not ready");
    const x = await imageToNCHWTensor(file);
    const inputName = sessionRef.current.inputNames[0];
    const outputName = sessionRef.current.outputNames[0];
    const out = await sessionRef.current.run({ [inputName]: x });
    const logits = Array.from(out[outputName].data as Float32Array);
    const probs = softmax(logits);
    return CLASSES.map((label, i) => ({ label, prob: probs[i] ?? 0 }))
                  .sort((a,b) => b.prob - a.prob);
  }

  return { status, error, model, predict, CLASSES };
}
