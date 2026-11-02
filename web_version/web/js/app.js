/**
 * DualAudio - Client JavaScript
 * Gère l'interface réactive, les VU-mètres temps réel, le Web Audio API
 * et les interactions utilisateur.
 */

const STATE = {
    apps: [],
    device: "",
    diagnostics: null,
    rules: {},
    settings: {},
    isDraggingBalance: false,
    isDraggingVolume: false,
    activeSliderApp: null,
    searchFilter: ""
};

// Icônes SVG par application
const APP_ICONS = {
    teams: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="6" fill="#6264A7"/><path d="M14.5 9a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM17.5 10h-6a1.5 1.5 0 0 0-1.5 1.5v3.5a3 3 0 0 0 3 3h3a3 3 0 0 0 3-3v-3.5a1.5 1.5 0 0 0-1.5-1.5z" fill="#FFF"/><path d="M9.5 8.5A2 2 0 1 0 9.5 4.5a2 2 0 0 0 0 4zm1.5 2h-4A1.5 1.5 0 0 0 5.5 12v3a2.5 2.5 0 0 0 2.5 2.5h2v-5.5a1.5 1.5 0 0 1 1-1.42z" fill="#E0E0FF"/></svg>`,
    vlc: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="6" fill="#FF8800"/><path d="M12 3l-4 13h8l-4-13z" fill="#FFFFFF"/><path d="M7 16h10l-1 3H8l-1-3z" fill="#FFB347"/><circle cx="12" cy="19.5" r="1.5" fill="#FFFFFF"/></svg>`,
    chrome: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="6" fill="#4285F4"/><circle cx="12" cy="12" r="8" fill="#FFF"/><circle cx="12" cy="12" r="4" fill="#4285F4"/></svg>`,
    edge: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="6" fill="#0078D7"/><path d="M12 6a6 6 0 0 1 6 6c0 3.3-2.7 6-6 6a6 6 0 0 1-6-6c0-3.3 2.7-6 6-6z" fill="#50E6FF"/></svg>`,
    spotify: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="6" fill="#1DB954"/><circle cx="12" cy="12" r="7" fill="#121212"/><path d="M8 10c2.5-.5 5.5-.3 8 1M8.5 12.5c2.2-.4 4.8-.2 7 .8M9 15c1.8-.3 3.8-.1 5.5.6" stroke="#1DB954" stroke-width="1.6" stroke-linecap="round"/></svg>`,
    discord: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="6" fill="#5865F2"/><path d="M16.5 8.5c-.8-.4-1.7-.7-2.6-.8-.1.2-.3.6-.4.9-1-.2-2-.2-3 0-.1-.3-.3-.7-.4-.9-.9.1-1.8.4-2.6.8-1.5 2.2-1.9 4.3-1.7 6.4 1 1 2.2 1.4 3.4 1.4.3-.4.6-.8.8-1.2-.5-.2-1-.5-1.4-.9.1-.1.2-.2.3-.3 2.1 1 4.5 1 6.6 0 .1.1.2.2.3.3-.4.4-.9.7-1.4.9.2.4.5.8.8 1.2 1.2 0 2.4-.4 3.4-1.4.2-2.3-.4-4.4-1.7-6.4zM9.5 13.5c-.6 0-1-.5-1-1.2s.4-1.2 1-1.2 1 .5 1 1.2-.4 1.2-1 1.2zm5 0c-.6 0-1-.5-1-1.2s.4-1.2 1-1.2 1 .5 1 1.2-.4 1.2-1 1.2z" fill="#FFF"/></svg>`,
    system: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="6" fill="#00A4EF"/><path d="M6 10v4h3l4 4V6l-4 4H6z" fill="#FFF"/><path d="M16 9a4 4 0 0 1 0 6" stroke="#FFF" stroke-width="2" stroke-linecap="round"/></svg>`,
    default: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect width="24" height="24" rx="6" fill="#6366F1"/><path d="M12 4v16m-6-6l6 6 6-6" stroke="#FFF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`
};

function getIconSvg(iconKey) {
    return APP_ICONS[iconKey] || APP_ICONS.default;
}

// ============================================================
// AUDIO TESTER (Web Audio API)
// ============================================================
let audioCtx = null;

function playTestTone(channel) {
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }

        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();

        // Fréquence agréable : 440 Hz (La) pour gauche, 880 Hz pour droite, 660 Hz pour centre
        const freq = channel === 'left' ? 440 : (channel === 'right' ? 880 : 660);
        osc.type = 'sine';
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime);

        // Panning stéréo
        const panVal = channel === 'left' ? -1.0 : (channel === 'right' ? 1.0 : 0.0);
        let panNode = null;
        if (audioCtx.createStereoPanner) {
            panNode = audioCtx.createStereoPanner();
            panNode.pan.setValueAtTime(panVal, audioCtx.currentTime);
        }

        // Enveloppe sonore douce (Fade In / Fade Out)
        gain.gain.setValueAtTime(0.001, audioCtx.currentTime);
        gain.gain.linearRampToValueAtTime(0.3, audioCtx.currentTime + 0.06);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.7);

        if (panNode) {
            osc.connect(panNode);
            panNode.connect(gain);
        } else {
            osc.connect(gain);
        }
        gain.connect(audioCtx.destination);

        osc.start();
        osc.stop(audioCtx.currentTime + 0.75);

        // Animation visuelle de l'écouteur testé
        if (channel === 'left' || channel === 'both') {
            const el = document.getElementById('earLeftBox');
            el.classList.add('active-glow');
            setTimeout(() => el.classList.remove('active-glow'), 800);
        }
        if (channel === 'right' || channel === 'both') {
            const el = document.getElementById('earRightBox');
            el.classList.add('active-glow');
            setTimeout(() => el.classList.remove('active-glow'), 800);
        }

        const channelLabel = channel === 'left' ? "Oreille Gauche (440Hz)" : (channel === 'right' ? "Oreille Droite (880Hz)" : "Stéréo Centrée (660Hz)");
        showToast(`Son test joué dans : ${channelLabel}`);
    } catch (e) {
        console.error("Erreur Web Audio:", e);
    }
}

// ============================================================
// API CLIENT
// ============================================================
async function fetchState() {
    try {
        const res = await fetch("/api/state");
        if (!res.ok) return;
        const data = await res.json();
        
        STATE.device = data.device || "Casque Audio";
        STATE.diagnostics = data.diagnostics || null;
        STATE.apps = data.apps || [];
        STATE.rules = data.rules || {};
        STATE.settings = data.settings || {};

        updateDeviceHeader();
        updateDiagnosticBanner();
        updateHeadphoneHud();
        renderAppsList();
    } catch (err) {
        console.warn("Erreur fetchState:", err);
    }
}

async function openSystemSettings(target) {
    try {
        await fetch("/api/open_settings", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ target: target })
        });
        showToast("Ouverture des paramètres Windows...");
    } catch (err) {
        console.error("Erreur openSystemSettings:", err);
    }
}

function updateDiagnosticBanner() {
    const banner = document.getElementById("diagBanner");
    const title = document.getElementById("diagTitle");
    const desc = document.getElementById("diagDesc");
    if (!banner || !STATE.diagnostics) return;

    const diag = STATE.diagnostics;
    if (diag.is_pc_speakers && diag.unplugged_headsets && diag.unplugged_headsets.length > 0) {
        banner.style.display = "flex";
        const names = diag.unplugged_headsets.join(", ");
        title.textContent = `Casque détecté mais non connecté en audio (${names})`;
        desc.textContent = `Windows voit votre casque, mais son profil audio Bluetooth est inactif. Le son continue donc de sortir des haut-parleurs du PC. Cliquez ci-dessous pour reconnecter l'audio dans Windows.`;
    } else {
        banner.style.display = "none";
    }
}

async function setAppBalance(processName, balance) {
    try {
        await fetch("/api/balance", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ process_name: processName, balance: parseFloat(balance) })
        });
        fetchState();
    } catch (err) {
        console.error("Erreur setAppBalance:", err);
    }
}

async function setAppVolume(processName, volume) {
    try {
        await fetch("/api/volume", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ process_name: processName, volume: parseFloat(volume) })
        });
    } catch (err) {
        console.error("Erreur setAppVolume:", err);
    }
}

async function setAppMute(processName, muted) {
    try {
        await fetch("/api/mute", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ process_name: processName, muted: !muted })
        });
        fetchState();
    } catch (err) {
        console.error("Erreur setAppMute:", err);
    }
}

async function setAppPreset(processName, preset) {
    try {
        await fetch("/api/preset", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ process_name: processName, preset: preset })
        });
        
        const earTxt = preset === 'left' ? "Oreille Gauche" : (preset === 'right' ? "Oreille Droite" : "Les Deux Oreilles");
        showToast(`${processName} routé vers : ${earTxt}`);
        fetchState();
    } catch (err) {
        console.error("Erreur setAppPreset:", err);
    }
}

async function applyScenario(scenarioId) {
    try {
        const res = await fetch("/api/scenario", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ scenario: scenarioId })
        });
        const data = await res.json();
        showToast(data.message || "Scénario appliqué avec succès !");
        fetchState();
    } catch (err) {
        console.error("Erreur applyScenario:", err);
    }
}

// ============================================================
// UI RENDERING
// ============================================================
function updateDeviceHeader() {
    const el = document.getElementById("deviceName");
    if (el && STATE.device) {
        el.textContent = STATE.device;
    }
}

function updateHeadphoneHud() {
    const leftContainer = document.getElementById("leftEarApps");
    const rightContainer = document.getElementById("rightEarApps");
    const centerContainer = document.getElementById("centerEarApps");

    const leftApps = [];
    const rightApps = [];
    const centerApps = [];

    let leftHasSound = false;
    let rightHasSound = false;

    STATE.apps.forEach(app => {
        const b = app.balance;
        const peak = app.peak || 0;
        
        if (peak > 0.02) {
            if (b <= 0.2) leftHasSound = true;
            if (b >= -0.2) rightHasSound = true;
        }

        if (b <= -0.3) {
            leftApps.push(app);
        } else if (b >= 0.3) {
            rightApps.push(app);
        } else {
            centerApps.push(app);
        }
    });

    // Écouteur Gauche
    if (leftApps.length === 0) {
        leftContainer.innerHTML = `<div class="empty-hint">Aucune application</div>`;
    } else {
        leftContainer.innerHTML = leftApps.map(app => `
            <div class="app-pill pill-left" title="${app.display_name} (100% Gauche)">
                ${getIconSvg(app.icon)}
                <span>${app.display_name}</span>
            </div>
        `).join("");
    }

    // Écouteur Droit
    if (rightApps.length === 0) {
        rightContainer.innerHTML = `<div class="empty-hint">Aucune application</div>`;
    } else {
        rightContainer.innerHTML = rightApps.map(app => `
            <div class="app-pill pill-right" title="${app.display_name} (100% Droite)">
                ${getIconSvg(app.icon)}
                <span>${app.display_name}</span>
            </div>
        `).join("");
    }

    // Centre (Stéréo)
    if (centerApps.length === 0) {
        centerContainer.innerHTML = `<div class="empty-hint">Aucune</div>`;
    } else {
        centerContainer.innerHTML = centerApps.map(app => `
            <div class="app-pill pill-center" title="${app.display_name} (Centré)">
                ${getIconSvg(app.icon)}
                <span>${app.display_name}</span>
            </div>
        `).join("");
    }

    // Effet visuel si du son joue
    const leftBox = document.getElementById("earLeftBox");
    const rightBox = document.getElementById("earRightBox");
    if (leftHasSound) {
        leftBox.classList.add("active-glow");
    } else {
        leftBox.classList.remove("active-glow");
    }
    if (rightHasSound) {
        rightBox.classList.add("active-glow");
    } else {
        rightBox.classList.remove("active-glow");
    }
}

function getBalanceLabel(balance) {
    if (balance <= -0.9) return "👈 100% Oreille Gauche";
    if (balance >= 0.9) return "👉 100% Oreille Droite";
    if (Math.abs(balance) < 0.1) return "⚖️ Centré (Stéréo)";
    if (balance < 0) {
        const pct = Math.round(Math.abs(balance) * 100);
        return `👈 Gauche (${pct}%)`;
    } else {
        const pct = Math.round(balance * 100);
        return `👉 Droite (${pct}%)`;
    }
}

function renderAppsList() {
    const container = document.getElementById("appsContainer");
    const statsEl = document.getElementById("activeAppsCount");

    const query = STATE.searchFilter.toLowerCase().trim();
    const filtered = STATE.apps.filter(app => {
        if (!query) return true;
        return app.display_name.toLowerCase().includes(query) ||
               app.process_name.toLowerCase().includes(query) ||
               app.category.toLowerCase().includes(query);
    });

    if (statsEl) {
        statsEl.textContent = `${filtered.length} application${filtered.length > 1 ? 's' : ''} active${filtered.length > 1 ? 's' : ''}`;
    }

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="empty-state-card">
                <div class="empty-icon">🔇</div>
                <h3>Aucun flux audio détecté</h3>
                <p style="margin-top: 8px; font-size: 13px;">Lancez une vidéo dans VLC, ouvrez Teams, YouTube ou Spotify pour les contrôler ici.</p>
            </div>
        `;
        return;
    }

    // Vérifier si nous mettons à jour les cartes existantes (pour éviter les saccades de curseur)
    filtered.forEach(app => {
        let card = document.getElementById(`app-card-${app.process_name}`);
        if (!card) {
            // Créer une nouvelle carte
            card = document.createElement("div");
            card.className = "app-card";
            card.id = `app-card-${app.process_name}`;
            container.appendChild(card);
        }
        updateAppCard(card, app);
    });

    // Supprimer les cartes d'applications fermées
    const currentKeys = new Set(filtered.map(a => `app-card-${a.process_name}`));
    Array.from(container.children).forEach(child => {
        if (!currentKeys.has(child.id)) {
            child.remove();
        }
    });
}

function updateAppCard(card, app) {
    const b = app.balance;
    const isLeft = b <= -0.5;
    const isRight = b >= 0.5;
    const isCenter = !isLeft && !isRight;

    // Calcul du VU meter
    const peakPercent = Math.min(100, Math.round((app.peak || 0) * 100));

    // Si l'utilisateur n'est pas en train de manipuler ce slider spécifique
    const isEditingThis = (STATE.activeSliderApp === app.process_name);

    card.innerHTML = `
        <div class="app-card-header">
            <div class="app-identity">
                <div class="app-icon-badge">
                    ${getIconSvg(app.icon)}
                </div>
                <div class="app-title-group">
                    <div class="app-name-row">
                        <span class="app-name">${app.display_name}</span>
                        <span class="app-badge-category">${app.category}</span>
                    </div>
                    <span class="app-process-info">${app.process_name}</span>
                </div>
            </div>

            <!-- VU METER LIVE -->
            <div class="app-vu-meter-group" title="Niveau audio en direct : ${peakPercent}%">
                <span class="vu-label">ACTIVITÉ AUDIO</span>
                <div class="vu-meter-bar">
                    <div class="vu-meter-fill" style="width: ${peakPercent}%"></div>
                </div>
            </div>
        </div>

        <!-- 3-WAY DIRECT EAR ROUTING BUTTONS -->
        <div class="ear-switch-row">
            <button class="btn-ear-choice ${isLeft ? 'active-left' : ''}" onclick="setAppPreset('${app.process_name}', 'left')">
                <span class="ear-icon">👈 🎧</span>
                <span class="ear-text">Gauche uniquement</span>
                <span class="ear-desc">100% Oreille Gauche</span>
            </button>

            <button class="btn-ear-choice ${isCenter ? 'active-center' : ''}" onclick="setAppPreset('${app.process_name}', 'center')">
                <span class="ear-icon">⚖️ 🎧</span>
                <span class="ear-text">Stéréo normale</span>
                <span class="ear-desc">Les deux oreilles</span>
            </button>

            <button class="btn-ear-choice ${isRight ? 'active-right' : ''}" onclick="setAppPreset('${app.process_name}', 'right')">
                <span class="ear-icon">🎧 👉</span>
                <span class="ear-text">Droite uniquement</span>
                <span class="ear-desc">100% Oreille Droite</span>
            </button>
        </div>

        <!-- FINE BALANCE & VOLUME CONTROLS -->
        <div class="controls-bottom-row">
            <!-- Balance Slider -->
            <div class="control-item">
                <div class="control-header">
                    <span>BALANCE PANORAMIQUE</span>
                    <span class="control-value" id="bal-val-${app.process_name}">${getBalanceLabel(b)}</span>
                </div>
                <input type="range" class="slider-balance" min="-1" max="1" step="0.05" 
                       value="${isEditingThis ? document.getElementById(`bal-range-${app.process_name}`)?.value || b : b}"
                       id="bal-range-${app.process_name}"
                       onmousedown="STATE.activeSliderApp='${app.process_name}'"
                       onmouseup="STATE.activeSliderApp=null"
                       oninput="onBalanceSliderInput('${app.process_name}', this.value)"
                       onchange="onBalanceSliderChange('${app.process_name}', this.value)">
                <div class="slider-ticks">
                    <span>100% GAUCHE</span>
                    <span>CENTRÉ</span>
                    <span>100% DROITE</span>
                </div>
            </div>

            <!-- Volume Slider -->
            <div class="control-item">
                <div class="control-header">
                    <span>VOLUME GÉNÉRAL</span>
                    <span class="control-value" id="vol-val-${app.process_name}">${Math.round(app.master_volume * 100)}%</span>
                </div>
                <input type="range" min="0" max="1" step="0.02" 
                       value="${app.master_volume}"
                       id="vol-range-${app.process_name}"
                       oninput="onVolumeSliderInput('${app.process_name}', this.value)"
                       onchange="onVolumeSliderChange('${app.process_name}', this.value)">
                <div class="slider-ticks">
                    <span>0%</span>
                    <span>50%</span>
                    <span>100%</span>
                </div>
            </div>

            <!-- Actions -->
            <div class="app-actions">
                <button class="btn-mute ${app.is_muted ? 'is-muted' : ''}" onclick="setAppMute('${app.process_name}', ${app.is_muted})" title="${app.is_muted ? 'Réactiver le son' : 'Couper le son'}">
                    <span>${app.is_muted ? '🔇 Muet' : '🔊 Actif'}</span>
                </button>
            </div>
        </div>
    `;
}

function onBalanceSliderInput(pname, val) {
    const label = document.getElementById(`bal-val-${pname}`);
    if (label) {
        label.textContent = getBalanceLabel(parseFloat(val));
    }
}

function onBalanceSliderChange(pname, val) {
    STATE.activeSliderApp = null;
    setAppBalance(pname, parseFloat(val));
}

function onVolumeSliderInput(pname, val) {
    const label = document.getElementById(`vol-val-${pname}`);
    if (label) {
        label.textContent = `${Math.round(parseFloat(val) * 100)}%`;
    }
}

function onVolumeSliderChange(pname, val) {
    setAppVolume(pname, parseFloat(val));
}

function filterApps() {
    const input = document.getElementById("searchInput");
    STATE.searchFilter = input ? input.value : "";
    renderAppsList();
}

// ============================================================
// TOAST NOTIFICATIONS
// ============================================================
let toastTimer = null;
function showToast(msg) {
    const t = document.getElementById("toastMessage");
    if (!t) return;
    t.textContent = msg;
    t.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
        t.classList.remove("show");
    }, 2800);
}

// ============================================================
// INITIALISATION & LOOP
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
    fetchState();
    // Boucle de mise à jour rapide pour des VU-mètres fluides et une synchronisation en direct
    setInterval(fetchState, 450);

    const btnRefresh = document.getElementById("btnRefresh");
    if (btnRefresh) {
        btnRefresh.addEventListener("click", () => {
            fetchState();
            showToast("Flux audio actualisés");
        });
    }
});
