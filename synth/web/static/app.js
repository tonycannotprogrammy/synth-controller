const INITIAL = typeof window.__INITIAL_STATE__ === "string"
  ? JSON.parse(window.__INITIAL_STATE__)
  : (window.__INITIAL_STATE__ || {});
let config = INITIAL.config || {};
let runtime = INITIAL.state || { keys: {}, encoders: {}, synth: {} };

const NOTE_RANGE = buildNotes("C3", "C6");
const ENCODER_ACTIONS = ["none", "transpose", "volume", "waveform"];
const WAVEFORMS = ["sine", "square", "saw", "triangle"];

const keysGrid = document.getElementById("keys-grid");
const encodersList = document.getElementById("encoders-list");
const synthSettings = document.getElementById("synth-settings");
const toast = createToast();
const keyElements = new Map();
const encoderElements = new Map();
const synthElements = {};

renderAll();
connectWebSocket();

function renderAll() {
  runtime.lastKeyFreq = runtime.lastKeyFreq || {};
  renderKeys();
  renderEncoders();
  renderSynth();
  applyRuntimeState();
}

function renderKeys() {
  keyElements.clear();
  keysGrid.innerHTML = "";
  const keys = config?.matrix?.keys || [];
  keys.forEach((key) => {
    const card = document.createElement("div");
    card.className = "key-card";
    card.dataset.keyId = key.id;

    const title = document.createElement("div");
    title.className = "key-card-title";
    const id = document.createElement("span");
    id.className = "key-id";
    id.textContent = key.id;
    const label = document.createElement("span");
    label.className = "key-label";
    label.textContent = key.label || "—";
    title.append(id, label);

    const select = document.createElement("select");
    ensureNoteOption(select, key.note);
    NOTE_RANGE.forEach((note) => {
      const option = document.createElement("option");
      option.value = note;
      option.textContent = note;
      if (note === key.note) option.selected = true;
      select.appendChild(option);
    });
    select.value = key.note;
    select.addEventListener("change", async () => {
      try {
        await api(`/api/keys/${key.id}/note`, { note: select.value });
        key.note = select.value;
        showToast(`Saved ${key.id} → ${select.value}`);
      } catch (err) {
        showToast(err.message || "Failed to update key", true);
        select.value = key.note;
      }
    });

    const actions = document.createElement("div");
    actions.className = "key-actions";
    const testBtn = document.createElement("button");
    testBtn.className = "secondary";
    testBtn.textContent = "Preview";
    testBtn.addEventListener("click", async () => {
      testBtn.disabled = true;
      try {
        await api(`/api/test-note/${key.id}`, null, "POST");
        showToast(`Previewed ${key.id}`);
      } catch (err) {
        showToast(err.message || "Preview failed", true);
      } finally {
        setTimeout(() => (testBtn.disabled = false), 600);
      }
    });

    const status = document.createElement("div");
    status.className = "status-badge";
    status.textContent = `${key.note}`;

    actions.append(testBtn, status);
    card.append(title, select, actions);
    keysGrid.appendChild(card);
    keyElements.set(key.id, { card, select, status });
  });
}

function renderEncoders() {
  encoderElements.clear();
  encodersList.innerHTML = "";
  const encoders = config?.encoders || [];
  encoders.forEach((encoder) => {
    const card = document.createElement("div");
    card.className = "encoder-card";

    const meta = document.createElement("div");
    meta.className = "encoder-meta";
    meta.innerHTML = `<strong>${encoder.name}</strong><span>GPIO ${encoder.A}/${encoder.B}</span>`;

    const actionRow = document.createElement("div");
    actionRow.style.display = "flex";
    actionRow.style.gap = "0.7rem";

    const actionSelect = document.createElement("select");
    ENCODER_ACTIONS.forEach((action) => {
      const option = document.createElement("option");
      option.value = action;
      option.textContent = action;
      if (action === encoder.action) option.selected = true;
      actionSelect.appendChild(option);
    });
    actionSelect.addEventListener("change", async () => {
      try {
        await api(`/api/encoders/${encoder.name}`, { action: actionSelect.value });
        encoder.action = actionSelect.value;
        showToast(`Saved ${encoder.name} action`);
      } catch (err) {
        showToast(err.message || "Failed to update encoder", true);
        actionSelect.value = encoder.action;
      }
    });

    const stepInput = document.createElement("input");
    stepInput.type = "number";
    stepInput.step = "0.01";
    stepInput.placeholder = "step";
    if (encoder.step !== undefined) {
      stepInput.value = encoder.step;
    }
    stepInput.addEventListener("change", async () => {
      const value = parseFloat(stepInput.value);
      const payload = Number.isFinite(value) ? { step: value } : { step: null };
      try {
        await api(`/api/encoders/${encoder.name}`, payload);
        encoder.step = payload.step;
        showToast(`Saved ${encoder.name} step`);
      } catch (err) {
        showToast(err.message || "Failed to update step", true);
      }
    });

    actionRow.append(actionSelect, stepInput);

    const status = document.createElement("div");
    status.className = "status-badge";
    status.textContent = "Idle";

    card.append(meta, actionRow, status);
    encodersList.appendChild(card);
    encoderElements.set(encoder.name, { card, status, actionSelect, stepInput });
  });
}

function renderSynth() {
  synthSettings.innerHTML = "";
  synthElements.waveform = null;
  synthElements.volume = null;
  synthElements.transpose = null;
  synthElements.envelope = null;
  const synth = config?.synth || {};

  // Waveform selector
  const waveformCard = createSettingCard("Waveform", synth.waveform);
  synthElements.waveform = waveformCard.valueEl;
  const waveformSelect = document.createElement("select");
  WAVEFORMS.forEach((wf) => {
    const option = document.createElement("option");
    option.value = wf;
    option.textContent = wf;
    if (wf === synth.waveform) option.selected = true;
    waveformSelect.appendChild(option);
  });
  waveformSelect.addEventListener("change", () => {
    updateSynth({ waveform: waveformSelect.value });
  });
  waveformCard.body.appendChild(waveformSelect);

  // Volume slider
  const volumeCard = createSettingCard("Volume", synth.volume);
  synthElements.volume = volumeCard.valueEl;
  const volumeInput = document.createElement("input");
  volumeInput.type = "range";
  volumeInput.min = "0";
  volumeInput.max = "1";
  volumeInput.step = "0.01";
  volumeInput.value = synth.volume ?? 0.7;
  volumeInput.addEventListener("input", debounce(() => {
    updateSynth({ volume: Number(volumeInput.value) });
  }, 180));
  volumeCard.body.appendChild(volumeInput);

  // Transpose control
  const transposeCard = createSettingCard("Transpose", synth.transpose);
  synthElements.transpose = transposeCard.valueEl;
  const transposeInput = document.createElement("input");
  transposeInput.type = "number";
  transposeInput.min = "-24";
  transposeInput.max = "24";
  transposeInput.value = synth.transpose ?? 0;
  transposeInput.addEventListener("change", () => {
    updateSynth({ transpose: parseInt(transposeInput.value, 10) });
  });
  transposeCard.body.appendChild(transposeInput);

  // Envelope controls
  const envelopeCard = createSettingCard("Envelope", `${synth.attack_ms} / ${synth.release_ms}`);
  synthElements.envelope = envelopeCard.valueEl;
  const attackInput = document.createElement("input");
  attackInput.type = "number";
  attackInput.min = "0";
  attackInput.max = "500";
  attackInput.value = synth.attack_ms ?? 5;
  attackInput.addEventListener("change", () => {
    updateSynth({ attack_ms: parseInt(attackInput.value, 10) });
  });

  const releaseInput = document.createElement("input");
  releaseInput.type = "number";
  releaseInput.min = "10";
  releaseInput.max = "5000";
  releaseInput.value = synth.release_ms ?? 180;
  releaseInput.addEventListener("change", () => {
    updateSynth({ release_ms: parseInt(releaseInput.value, 10) });
  });

  const envelopeRow = document.createElement("div");
  envelopeRow.style.display = "grid";
  envelopeRow.style.gridTemplateColumns = "repeat(auto-fit, minmax(120px, 1fr))";
  envelopeRow.style.gap = "0.7rem";

  const attackWrapper = document.createElement("label");
  attackWrapper.textContent = "Attack (ms)";
  attackWrapper.appendChild(attackInput);
  attackWrapper.style.display = "grid";
  attackWrapper.style.gap = "0.3rem";

  const releaseWrapper = document.createElement("label");
  releaseWrapper.textContent = "Release (ms)";
  releaseWrapper.appendChild(releaseInput);
  releaseWrapper.style.display = "grid";
  releaseWrapper.style.gap = "0.3rem";

  envelopeRow.append(attackWrapper, releaseWrapper);
  envelopeCard.body.appendChild(envelopeRow);

  synthSettings.append(waveformCard.card, volumeCard.card, transposeCard.card, envelopeCard.card);
}

function updateSynth(update) {
  api("/api/synth", update)
    .then(() => {
      config.synth = { ...(config.synth || {}), ...update };
      runtime.synth = { ...(runtime.synth || {}), ...update };
      applyRuntimeState();
    })
    .catch((err) => {
      showToast(err.message || "Failed to update synth", true);
    });
}

function applyRuntimeState() {
  for (const [keyId, refs] of keyElements) {
    const pressed = runtime.keys?.[keyId];
    refs.card.classList.toggle("pressed", Boolean(pressed));
    const note = config?.matrix?.keys?.find((k) => k.id === keyId)?.note;
    const freq = runtime.lastKeyFreq?.[keyId];
    if (freq && refs.status) {
      refs.status.textContent = `${note || keyId} • ${freq.toFixed(1)} Hz`;
    } else if (refs.status) {
      refs.status.textContent = note || keyId;
    }
  }
  for (const [name, refs] of encoderElements) {
    const data = runtime.encoders?.[name];
    if (data && refs.status) {
      const value = data.value;
      refs.status.textContent = `${data.action || `Δ${data.delta}`}: ${formatValue(value)}`;
    } else if (refs.status) {
      refs.status.textContent = "Idle";
    }
  }
  if (synthElements.waveform) {
    synthElements.waveform.textContent = formatValue(runtime.synth?.waveform ?? config?.synth?.waveform);
  }
  if (synthElements.volume) {
    synthElements.volume.textContent = formatValue(runtime.synth?.volume ?? config?.synth?.volume);
  }
  if (synthElements.transpose) {
    synthElements.transpose.textContent = formatValue(runtime.synth?.transpose ?? config?.synth?.transpose);
  }
  if (synthElements.envelope) {
    const attack = runtime.synth?.attack_ms ?? config?.synth?.attack_ms;
    const release = runtime.synth?.release_ms ?? config?.synth?.release_ms;
    synthElements.envelope.textContent = `${formatValue(attack)} / ${formatValue(release)}`;
  }
}

function connectWebSocket() {
  let retry = 0;
  const connect = () => {
    const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
    ws.addEventListener("open", () => {
      retry = 0;
      showToast("Connected to synth", false, 1200);
    });
    ws.addEventListener("message", (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "state") {
        config = msg.config || config;
        runtime = {
          keys: msg.state?.keys || {},
          encoders: msg.state?.encoders || {},
          synth: msg.state?.synth || {},
          lastKeyFreq: runtime.lastKeyFreq || {},
        };
        renderAll();
        return;
      }
      if (msg.type === "config") {
        config = msg.config || config;
        runtime.synth = (msg.config && msg.config.synth) || runtime.synth;
        renderAll();
        return;
      }
      if (msg.type === "key") {
        runtime.keys[msg.id] = msg.kind === "press";
        runtime.lastKeyFreq = runtime.lastKeyFreq || {};
        if (msg.freq) {
          runtime.lastKeyFreq[msg.id] = msg.freq;
        }
        applyRuntimeState();
        return;
      }
      if (msg.type === "enc") {
        runtime.encoders[msg.name] = msg;
        runtime.synth = runtime.synth || {};
        if (msg.action === "volume") runtime.synth.volume = msg.value;
        if (msg.action === "transpose") runtime.synth.transpose = msg.value;
        if (msg.action === "waveform") runtime.synth.waveform = msg.value;
        applyRuntimeState();
        return;
      }
    });
    ws.addEventListener("close", () => {
      retry += 1;
      showToast("Connection lost, retrying…", true, 1500);
      setTimeout(connect, Math.min(5000, retry * 1000));
    });
  };
  connect();
}

async function api(url, body, method = "POST") {
  const options = { method, headers: { "Content-Type": "application/json" } };
  if (body !== null) {
    options.body = JSON.stringify(body);
  } else if (method === "POST" || method === "PUT") {
    options.body = "{}";
  }
  const response = await fetch(url, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed (${response.status})`);
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  return data;
}

function ensureNoteOption(select, note) {
  if (!NOTE_RANGE.includes(note)) {
    const option = document.createElement("option");
    option.value = note;
    option.textContent = note;
    select.appendChild(option);
  }
}

function createToast() {
  const el = document.createElement("div");
  el.className = "toast";
  document.body.appendChild(el);
  let timeout;
  return function show(message, isError = false, duration = 2000) {
    el.textContent = message;
    el.style.borderColor = isError ? "rgba(248,113,113,0.6)" : "rgba(56,189,248,0.6)";
    el.classList.add("show");
    clearTimeout(timeout);
    timeout = setTimeout(() => {
      el.classList.remove("show");
    }, duration);
  };
}

function showToast(message, isError = false, duration) {
  toast(message, isError, duration);
}

function debounce(fn, delay) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), delay);
  };
}

function buildNotes(start, end) {
  const sequence = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  const FLAT_TO_SHARP = {
    Db: "C#",
    Eb: "D#",
    Gb: "F#",
    Ab: "G#",
    Bb: "A#",
  };
  const parse = (note) => {
    const match = note.match(/^([A-G](?:#|b)?)(-?\d+)$/);
    if (!match) throw new Error(`Invalid note: ${note}`);
    let pitch = match[1].replace("♭", "b").replace("♯", "#");
    pitch = pitch[0].toUpperCase() + (pitch[1] ? pitch[1] : "");
    if (FLAT_TO_SHARP[pitch]) {
      pitch = FLAT_TO_SHARP[pitch];
    }
    return { pitch, octave: Number(match[2]) };
  };
  const s = parse(start);
  const e = parse(end);
  const notes = [];
  for (let oct = s.octave; oct <= e.octave; oct += 1) {
    sequence.forEach((pitch) => {
      if (oct === s.octave && sequence.indexOf(pitch) < sequence.indexOf(s.pitch)) return;
      if (oct === e.octave && sequence.indexOf(pitch) > sequence.indexOf(e.pitch)) return;
      notes.push(`${pitch}${oct}`);
    });
  }
  return notes;
}

function createSettingCard(title, value) {
  const card = document.createElement("div");
  card.className = "setting-card";
  const meta = document.createElement("div");
  meta.className = "setting-meta";
  const heading = document.createElement("strong");
  heading.textContent = title;
  const valueEl = document.createElement("span");
  valueEl.textContent = formatValue(value);
  meta.append(heading, valueEl);
  const body = document.createElement("div");
  body.style.display = "grid";
  body.style.gap = "0.6rem";
  card.append(meta, body);
  return { card, body, valueEl };
}

function formatValue(value) {
  if (value === undefined || value === null) return "—";
  if (typeof value === "number") {
    return Number.isInteger(value) ? `${value}` : value.toFixed(2);
  }
  return String(value);
}
