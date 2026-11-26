const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {mono, wav} = require('../pages/audio.js');

test('folds a stereo source into a mono channel before routing', () => {
  const data = [Float32Array.of(1, -.5), Float32Array.of(-1, 1)];
  const buffer = {length: 2, numberOfChannels: 2, getChannelData: i => data[i]};
  assert.deepEqual(Array.from(mono(buffer)), [0, .25]);
});

test('exports separated channels, configured gains, and silence for the shorter track', () => {
  const bytes = wav(Float32Array.of(1, -1), Float32Array.of(-1), 48000, .5, .25);
  const view = new DataView(bytes);
  assert.equal(Buffer.from(bytes).toString('ascii', 0, 4), 'RIFF');
  assert.equal(view.getUint16(22, true), 2);
  assert.equal(view.getUint32(24, true), 48000);
  assert.equal(view.getUint32(40, true), 8);
  assert.equal(view.getInt16(44, true), 16384);
  assert.equal(view.getInt16(46, true), -8192);
  assert.equal(view.getInt16(48, true), -16384);
  assert.equal(view.getInt16(50, true), 0);
});

test('an isolated right channel exports silence on the left', () => {
  const view = new DataView(wav(null, [1], 44100, 1, 1));
  assert.equal(view.getInt16(44, true), 0);
  assert.equal(view.getInt16(46, true), 32767);
});

test('the UI starts both channels at the same time and applies gain updates and seeking', async () => {
  const node = () => ({
    value: '75', disabled: false, events: {},
    addEventListener(name, listener) { this.events[name] = listener; },
  });
  const nodes = new Map();
  const get = key => {
    if (!nodes.has(key)) nodes.set(key, node());
    return nodes.get(key);
  };
  const panels = [new Map(), new Map()].map(map => ({
    querySelector(key) {
      if (!map.has(key)) map.set(key, node());
      return map.get(key);
    },
  }));
  const channels = [], starts = [], gains = [];
  class Audio {
    sampleRate = 1000;
    currentTime = 10;
    resume() { return Promise.resolve(); }
    createBuffer(_, length, rate) {
      const data = new Float32Array(length);
      return {duration: length / rate, getChannelData: () => data};
    }
    createBufferSource() {
      return {connect() {}, disconnect() {}, stop() {}, start(when, offset) { starts.push([when, offset]); }};
    }
    createChannelMerger() { return {connect() {}, disconnect() {}}; }
    createGain() {
      return {
        gain: {setTargetAtTime(value) { gains.push(value); }},
        connect(_, __, index) { channels.push(index); },
        disconnect() {},
      };
    }
  }
  const context = {
    DualAudio: {mono, wav},
    document: {getElementById: get, querySelectorAll: () => panels, addEventListener() {}},
    window: {AudioContext: Audio}, location: {search: ''}, URLSearchParams,
    requestAnimationFrame() {}, cancelAnimationFrame() {},
  };
  vm.runInNewContext(fs.readFileSync(require.resolve('../pages/app.js'), 'utf8'), context);
  assert.equal(get('play').disabled, true);
  get('sample').events.click();
  get('play').events.click();
  await new Promise(setImmediate);
  assert.deepEqual(channels, [0, 1]);
  assert.deepEqual(starts, [[10.035, 0], [10.035, 0]]);
  assert.equal(get('play').textContent, 'Pause');
  const slider = panels[1].querySelector('input[type=range]');
  slider.value = '40';
  slider.events.input();
  assert.deepEqual(gains, [.4]);
  get('seek').value = '3';
  get('seek').events.input();
  await new Promise(setImmediate);
  assert.deepEqual(starts.slice(-2), [[10.035, 3], [10.035, 3]]);
  get('play').events.click();
  assert.equal(get('play').textContent, 'Lecture');
});
