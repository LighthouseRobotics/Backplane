// A demand comes from the driver before dispatch. An independent pixel
// reader must observe the calibrated target region after dispatch.
// This is X-server content acceptance, not compositor/physical scanout.
export function displayPixels(bytes: Uint8Array, width: number, height: number, maskCaret = false): Uint8Array {
  const header = new TextEncoder().encode(`P6\n${width} ${height}\n255\n`);
  if (bytes.length !== header.length + width * height * 3 || !header.every((b, i) => bytes[i] === b)) {
    throw new Error("native region readback is not the expected RGB PPM");
  }
  const pixels = bytes.slice(header.length);
  if (maskCaret) {
    // Only the solid caret colors in app/theme.bend are normalized. The
    // calibrated ASCII composer probe has no colored text or selection.
    const colors = new Map([[6271999, 1250843], [2060241, 15855852]]);
    for (let i = 0; i < pixels.length; i += 3) {
      const replacement = colors.get((pixels[i] << 16) | (pixels[i+1] << 8) | pixels[i+2]);
      if (replacement !== undefined) pixels.set([replacement >> 16, (replacement >> 8) & 255, replacement & 255], i);
    }
  }
  return pixels;
}

export async function awaitDisplay(
  expected: string,
  before: string,
  read: () => Promise<string>,
  now: () => number = () => performance.now(),
  pause: (ms: number) => Promise<void> = ms => new Promise(r => setTimeout(r, ms)),
  started = now(),
  timeoutMs = 2000,
): Promise<{ elapsed_ms: number; samples: number; pixel_sha256: string }> {
  if (!expected || expected === before) throw new Error("display demand does not distinguish the target from the preceding content");
  let samples = 0;
  while (now() - started <= timeoutMs) {
    const actual = await read();
    samples++;
    const elapsed = now() - started;
    if (actual === expected && elapsed <= timeoutMs) return { elapsed_ms: elapsed, samples, pixel_sha256: actual };
    await pause(4);
  }
  throw new Error("display demand timed out: expected content never reached the X-server region");
}
