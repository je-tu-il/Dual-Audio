(() => {
  const get = id => document.getElementById(id);
  const status = get('status');
  const show = message => { status.textContent = message; };
  const tracks = Array.from(document.querySelectorAll('[data-track]'), panel => ({
    file: panel.querySelector('input[type=file]'), slider: panel.querySelector('input[type=range]'),
    info: panel.querySelector('.file-info'), output: panel.querySelector('output'),
    remove: panel.querySelector('.remove'), buffer: null, revision: 0,
  }));
  const play = get('play'), seek = get('seek'), reset = get('reset'), save = get('export');
  const back = get('back');
  if (new URLSearchParams(location.search).get('utm_source') === 'portfolio') {
    if (location.pathname.endsWith('/projects/dual-audio/index.html') || location.pathname.endsWith('/projects/dual-audio/')) {
      back.href = '../../index.html#catalogue';
      if (document.referrer) {
        const source = new URL(document.referrer);
        const catalogue = new URL(back.href);
        if (source.origin === catalogue.origin && [catalogue.pathname, new URL('./', catalogue).pathname].includes(source.pathname)) {
          catalogue.search = source.search;
          back.href = catalogue.href;
        }
      }
    }
    back.hidden = false;
  }
  const Audio = window.AudioContext || window.webkitAudioContext;
  if (!Audio) {
    get('sample').disabled = true;
    tracks.forEach(track => { track.file.disabled = true; });
    show('Ce navigateur ne prend pas en charge Web Audio.');
    return;
  }

  let context, offset = 0, startedAt = null, playback = [], frame, generation = 0;
  const audioContext = () => context ??= new Audio();
  const length = () => Math.max(...tracks.map(track => track.buffer?.duration ?? 0));
  const position = () => startedAt === null ? offset : Math.min(length(), offset + Math.max(0, context.currentTime - startedAt));
  const format = seconds => Math.floor(seconds / 60) + ':' + String(Math.floor(seconds % 60)).padStart(2, '0');
  const gainValue = track => Number(track.slider.value) / 100;
  function render() {
    const total = length();
    seek.disabled = reset.disabled = play.disabled = save.disabled = !total;
    seek.max = total;
    seek.value = position();
    get('time').textContent = format(position()) + ' / ' + format(total);
    play.textContent = startedAt === null ? 'Lecture' : 'Pause';
  }

  function stop(at = position()) {
    generation++;
    offset = at;
    startedAt = null;
    cancelAnimationFrame(frame);
    for (const channel of playback) {
      channel.source.stop();
      channel.source.disconnect();
      channel.gain.disconnect();
      channel.merger.disconnect();
    }
    playback = [];
    render();
  }

  function tick() {
    if (position() >= length()) { stop(0); show('Lecture terminée.'); return; }
    render();
    frame = requestAnimationFrame(tick);
  }

  async function start() {
    if (!length() || startedAt !== null) return;
    const token = ++generation;
    const ctx = audioContext();
    try { await ctx.resume(); }
    catch { if (token === generation) show('La lecture audio a été bloquée par le navigateur.'); return; }
    if (token !== generation) return;
    if (offset >= length()) offset = 0;
    const now = ctx.currentTime + .035;
    const merger = ctx.createChannelMerger(2);
    merger.connect(ctx.destination);
    for (const [index, track] of tracks.entries()) {
      if (!track.buffer || offset >= track.buffer.duration) continue;
      const source = ctx.createBufferSource();
      const gain = ctx.createGain();
      source.buffer = track.buffer;
      gain.gain.value = gainValue(track);
      source.connect(gain);
      gain.connect(merger, 0, index);
      source.start(now, offset);
      playback.push({source, gain, merger, index});
    }
    startedAt = now;
    show('Lecture stéréo en cours.');
    tick();
  }

  function setTrack(track, buffer, text) {
    stop(0);
    track.buffer = buffer;
    track.info.textContent = text;
    track.remove.disabled = !buffer;
    render();
  }

  async function load(track) {
    const file = track.file.files[0];
    if (!file) return;
    const revision = ++track.revision;
    if (file.size > 24 * 1024 * 1024) { show('Ce fichier dépasse 24 Mo. La piste actuelle est conservée.'); track.file.value = ''; return; }
    show('Décodage de ' + file.name + '…');
    try {
      const ctx = audioContext();
      const decoded = await ctx.decodeAudioData(await file.arrayBuffer());
      if (revision !== track.revision) return;
      if (!decoded.length || decoded.duration > 600) {
        track.file.value = '';
        show('Choisissez un extrait de 10 minutes maximum.');
        return;
      }
      const buffer = ctx.createBuffer(1, decoded.length, ctx.sampleRate);
      buffer.copyToChannel(DualAudio.mono(decoded), 0);
      setTrack(track, buffer, file.name + ' · ' + format(buffer.duration));
      show('Piste prête : ' + file.name);
    } catch {
      if (revision !== track.revision) return;
      track.file.value = '';
      show('Ce fichier ne peut pas être décodé. Essayez un WAV ou un MP3.');
    }
  }

  for (const [index, track] of tracks.entries()) {
    track.file.addEventListener('change', () => load(track));
    track.slider.addEventListener('input', () => {
      track.output.textContent = track.slider.value + ' %';
      const channel = playback.find(item => item.index === index);
      if (channel) channel.gain.gain.setTargetAtTime(gainValue(track), context.currentTime, .015);
    });
    track.remove.addEventListener('click', () => {
      track.revision++;
      track.file.value = '';
      setTrack(track, null, 'Aucun fichier chargé');
      show('Piste retirée.');
    });
  }

  get('sample').addEventListener('click', () => {
    const ctx = audioContext();
    for (const [index, track] of tracks.entries()) {
      track.revision++;
      track.file.value = '';
      const buffer = ctx.createBuffer(1, ctx.sampleRate * 8, ctx.sampleRate);
      const values = buffer.getChannelData(0);
      for (let i = 0; i < values.length; i++) {
        const t = i / ctx.sampleRate;
        const beat = t % 1.6 - index * .8;
        const envelope = beat >= 0 && beat < .45 ? Math.min(beat / .02, 1) * (1 - beat / .45) : 0;
        values[i] = .32 * envelope * Math.sin(2 * Math.PI * (index ? 523.25 : 329.63) * t);
      }
      setTrack(track, buffer, 'Signal de test · 0:08');
    }
    show('Sons d’essai chargés. Les deux oreillettes alternent.');
  });

  const toggle = () => { if (startedAt === null) start(); else { stop(); show('Lecture en pause.'); } };
  play.addEventListener('click', toggle);
  reset.addEventListener('click', () => { stop(0); show('Position remise au début.'); });
  seek.addEventListener('input', () => {
    const resume = startedAt !== null;
    stop(Number(seek.value));
    if (resume && offset < length()) start();
  });
  document.addEventListener('keydown', event => {
    if (event.code !== 'Space' || event.repeat || event.defaultPrevented || play.disabled) return;
    if (event.target.closest('button, a, input, select, textarea, [contenteditable]')) return;
    event.preventDefault();
    toggle();
  });
  save.addEventListener('click', () => {
    const [left, right] = tracks;
    const wave = DualAudio.wav(left.buffer?.getChannelData(0), right.buffer?.getChannelData(0), context.sampleRate, gainValue(left), gainValue(right));
    const url = URL.createObjectURL(new Blob([wave], {type: 'audio/wav'}));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'dual-audio-stereo.wav';
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    show('Mix WAV stéréo exporté.');
  });
  render();
})();

