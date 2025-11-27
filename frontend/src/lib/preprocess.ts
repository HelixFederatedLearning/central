// src/lib/preprocess.ts
export async function imageToTensor(
  img: HTMLImageElement | HTMLCanvasElement | ImageBitmap,
  size = 300
): Promise<Float32Array> {
  // draw to an offscreen canvas at 300x300
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  ctx.drawImage(img as any, 0, 0, size, size);

  const { data } = ctx.getImageData(0, 0, size, size);

  // Normalize to ImageNet mean/std
  const mean = [0.485, 0.456, 0.406];
  const std = [0.229, 0.224, 0.225];

  // NCHW float32
  const out = new Float32Array(3 * size * size);
  const stride = size * size;
  for (let i = 0; i < size * size; i++) {
    const r = data[i * 4 + 0] / 255;
    const g = data[i * 4 + 1] / 255;
    const b = data[i * 4 + 2] / 255;
    out[0 * stride + i] = (r - mean[0]) / std[0];
    out[1 * stride + i] = (g - mean[1]) / std[1];
    out[2 * stride + i] = (b - mean[2]) / std[2];
  }
  return out;
}

export function softmax(logits: Float32Array): Float32Array {
  const max = Math.max(...logits);
  const exps = logits.map(v => Math.exp(v - max));
  const sum = exps.reduce((a, b) => a + b, 0);
  return new Float32Array(exps.map(v => v / sum));
}

export function topk(probs: Float32Array, labels: string[], k = 5) {
  const pairs = probs.map((p, i) => ({ i, p })).sort((a, b) => b.p - a.p);
  return pairs.slice(0, Math.min(k, probs.length)).map(({ i, p }) => ({
    label: labels[i] ?? `class_${i}`,
    score: p,
  }));
}
