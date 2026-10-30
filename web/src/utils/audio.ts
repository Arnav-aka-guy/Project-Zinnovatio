/**
 * audio.ts — In-browser audio recording, Web Audio level analyser,
 * and 16 kHz mono 16-bit PCM WAV encoder.
 */

/**
 * Encodes Float32 mono PCM samples to a 16-bit PCM WAV Blob.
 */
export function encodeWAV(samples: Float32Array, sampleRate: number): Blob {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  function writeString(offset: number, str: string) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }

  /* RIFF chunk descriptor */
  writeString(0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, 'WAVE');

  /* fmt sub-chunk */
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
  view.setUint16(20, 1, true); // AudioFormat (1 for PCM)
  view.setUint16(22, 1, true); // NumChannels (1 = mono)
  view.setUint32(24, sampleRate, true); // SampleRate
  view.setUint32(28, sampleRate * 2, true); // ByteRate (SampleRate * NumChannels * BitsPerSample/8)
  view.setUint16(32, 2, true); // BlockAlign (NumChannels * BitsPerSample/8)
  view.setUint16(34, 16, true); // BitsPerSample (16 bits)

  /* data sub-chunk */
  writeString(36, 'data');
  view.setUint32(40, samples.length * 2, true);

  // Convert Float32 (-1.0 to 1.0) to signed 16-bit PCM (-32768 to 32767)
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }

  return new Blob([buffer], { type: 'audio/wav' });
}

/**
 * Resamples an AudioBuffer to 16 kHz mono PCM WAV Blob using OfflineAudioContext.
 */
export async function resampleTo16kMono(audioBuffer: AudioBuffer): Promise<Blob> {
  const targetSampleRate = 16000;
  const numFrames = Math.ceil(audioBuffer.duration * targetSampleRate);
  const offlineCtx = new OfflineAudioContext(1, numFrames, targetSampleRate);

  const source = offlineCtx.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(offlineCtx.destination);
  source.start(0);

  const renderedBuffer = await offlineCtx.startRendering();
  const monoSamples = renderedBuffer.getChannelData(0);
  return encodeWAV(monoSamples, targetSampleRate);
}

/**
 * Merges an array of Float32Array chunks into a single Float32Array.
 */
export function mergeFloat32Arrays(chunks: Float32Array[]): Float32Array {
  let totalLength = 0;
  for (let i = 0; i < chunks.length; i++) {
    totalLength += chunks[i].length;
  }
  const merged = new Float32Array(totalLength);
  let offset = 0;
  for (let i = 0; i < chunks.length; i++) {
    merged.set(chunks[i], offset);
    offset += chunks[i].length;
  }
  return merged;
}

/**
 * Downsamples Float32 mono PCM samples to 16 kHz with window averaging.
 */
export function downsampleBuffer(buffer: Float32Array, inputSampleRate: number, outputSampleRate = 16000): Float32Array {
  if (inputSampleRate === outputSampleRate) {
    return buffer;
  }
  if (inputSampleRate < outputSampleRate) {
    return buffer;
  }
  const sampleRateRatio = inputSampleRate / outputSampleRate;
  const newLength = Math.round(buffer.length / sampleRateRatio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < result.length) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * sampleRateRatio);
    let accum = 0;
    let count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

