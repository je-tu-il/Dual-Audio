((root) => {
  function mono(buffer) {
    const output = new Float32Array(buffer.length);
    const channels = buffer.numberOfChannels;
    for (let channel = 0; channel < channels; channel++) {
      const data = buffer.getChannelData(channel);
      for (let frame = 0; frame < output.length; frame++) output[frame] += data[frame] / channels;
    }
    return output;
  }

  function wav(left, right, rate, leftGain, rightGain) {
    const frames = Math.max(left?.length ?? 0, right?.length ?? 0);
    const data = new DataView(new ArrayBuffer(44 + frames * 4));
    const tag = (at, text) => [...text].forEach((char, i) => data.setUint8(at + i, char.charCodeAt(0)));
    tag(0, 'RIFF');
    data.setUint32(4, data.byteLength - 8, true);
    tag(8, 'WAVE'); tag(12, 'fmt ');
    data.setUint32(16, 16, true);
    data.setUint16(20, 1, true);
    data.setUint16(22, 2, true);
    data.setUint32(24, rate, true);
    data.setUint32(28, rate * 4, true);
    data.setUint16(32, 4, true);
    data.setUint16(34, 16, true);
    tag(36, 'data');
    data.setUint32(40, frames * 4, true);
    const pcm = value => Math.round(Math.max(-1, Math.min(1, value)) * (value < 0 ? 32768 : 32767));
    for (let i = 0; i < frames; i++) {
      data.setInt16(44 + i * 4, pcm((left?.[i] ?? 0) * leftGain), true);
      data.setInt16(46 + i * 4, pcm((right?.[i] ?? 0) * rightGain), true);
    }
    return data.buffer;
  }

  const api = {mono, wav};
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.DualAudio = api;
})(globalThis);

