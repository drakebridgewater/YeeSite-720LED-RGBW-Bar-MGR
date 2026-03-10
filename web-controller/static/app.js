(() => {
    "use strict";

    const COLUMNS = 24;
    const socket = io();

    let activeEffect = null;
    let activeWhiteEffect = null;
    let isBlackout = false;
    let effectsMeta = {};
    let whiteEffectsMeta = {};
    let activeEffectColors = {};
    let activeEffectDimmers = {};
    let fadeTime = 0;

    const $ = (sel) => document.querySelector(sel);
    const rowTop = $("#rowTop");
    const rowMid = $("#rowMid");
    const rowBot = $("#rowBot");
    const sliderR = $("#sliderR");
    const sliderG = $("#sliderG");
    const sliderB = $("#sliderB");
    const sliderW = $("#sliderW");
    const sliderBright = $("#sliderBright");
    const colorPreview = $("#colorPreview");
    const whitePreview = $("#whitePreview");
    const colorPicker = $("#colorPicker");
    const effectsGrid = $("#effectsGrid");
    const presetsContainer = $("#colorPresets");
    const btnBlackout = $("#btnBlackout");
    const btnStop = $("#btnStop");
    const statusDot = $("#statusDot");
    const statusText = $("#statusText");
    const selToolbar = $("#selToolbar");
    const selCount = $("#selCount");
    const selApply = $("#selApply");
    const selGroup = $("#selGroup");
    const selAll = $("#selAll");
    const selClear = $("#selClear");
    const groupsList = $("#groupsList");
    const groupsEmpty = $("#groupsEmpty");
    const effectConfig = $("#effectConfig");
    const sliderSpeed = $("#sliderSpeed");
    const speedVal = $("#speedVal");
    const effectReset = $("#effectReset");
    const whiteEffectsGrid = $("#whiteEffectsGrid");
    const sliderWSpeed = $("#sliderWSpeed");
    const wSpeedVal = $("#wSpeedVal");
    const whiteEffectReset = $("#whiteEffectReset");
    const sliderRgbDim = $("#sliderRgbDim");
    const rgbDimVal = $("#rgbDimVal");
    const sliderWhiteDim = $("#sliderWhiteDim");
    const whiteDimVal = $("#whiteDimVal");
    const sliderFade = $("#sliderFade");
    const fadeValEl = $("#fadeVal");
    const sliderColorStrobeRate = $("#sliderColorStrobeRate");
    const colorStrobeRateVal = $("#colorStrobeRateVal");
    const sliderWhiteStrobeRate = $("#sliderWhiteStrobeRate");
    const whiteStrobeRateVal = $("#whiteStrobeRateVal");
    const btnStrobeLink = $("#btnStrobeLink");
    const scenesRow = $("#scenesRow");
    const scenesEmpty = $("#scenesEmpty");
    const btnSaveScene = $("#btnSaveScene");
    const customPresetsEl = $("#customPresets");
    const btnAddPreset = $("#btnAddPreset");

    // ---- KNOBS ----
    const KNOB_CONFIG = {
        rgbDim: { slider: sliderRgbDim, max: 100 },
        whiteDim: { slider: sliderWhiteDim, max: 100 },
        colorStrobeRate: { slider: sliderColorStrobeRate, min: 2, max: 20 },
        whiteStrobeRate: { slider: sliderWhiteStrobeRate, min: 2, max: 20 },
        effectSpeed: { slider: sliderSpeed, min: 10, max: 1000 },
        whiteSpeed: { slider: sliderWSpeed, min: 10, max: 1000 },
    };

    function syncKnobIndicator(key) {
        const cfg = KNOB_CONFIG[key];
        if (!cfg) return;
        const val = parseInt(cfg.slider.value);
        const min = cfg.min ?? 0;
        const range = cfg.max - min;
        const norm = range > 0 ? (val - min) / range : 0;
        const deg = -135 + norm * 270;
        const wrap = document.querySelector(`[data-knob="${key}"]`);
        if (wrap) {
            const ind = wrap.querySelector(".knob-indicator");
            if (ind) ind.style.transform = `rotate(${deg}deg)`;
        }
    }

    function setupKnob(key) {
        const cfg = KNOB_CONFIG[key];
        if (!cfg) return;
        const wrap = document.querySelector(`[data-knob="${key}"]`);
        const knob = wrap?.querySelector(".knob");
        if (!knob) return;

        function setVal(delta) {
            const min = cfg.min ?? 0;
            const v = parseInt(cfg.slider.value) + delta;
            cfg.slider.value = Math.max(min, Math.min(cfg.max, v));
            cfg.slider.dispatchEvent(new Event("input", { bubbles: true }));
            syncKnobIndicator(key);
        }

        knob.addEventListener("wheel", (e) => {
            e.preventDefault();
            setVal(e.deltaY > 0 ? -1 : 1);
        }, { passive: false });

        let startY = 0, startVal = 0, lastVal = 0;
        knob.addEventListener("mousedown", (e) => {
            e.preventDefault();
            startY = e.clientY;
            startVal = parseInt(cfg.slider.value);
            lastVal = startVal;
            const onMove = (ev) => {
                const dy = startY - ev.clientY;
                const step = Math.round(dy / 3);
                if (step !== 0) {
                    startY = ev.clientY;
                    lastVal = Math.max(0, Math.min(cfg.max, lastVal + step));
                    cfg.slider.value = lastVal;
                    cfg.slider.dispatchEvent(new Event("input", { bubbles: true }));
                    syncKnobIndicator(key);
                }
            };
            const onUp = () => {
                document.removeEventListener("mousemove", onMove);
                document.removeEventListener("mouseup", onUp);
            };
            document.addEventListener("mousemove", onMove);
            document.addEventListener("mouseup", onUp);
        });
    }

    ["rgbDim", "whiteDim", "colorStrobeRate", "whiteStrobeRate", "effectSpeed", "whiteSpeed"].forEach((k) => {
        setupKnob(k);
        syncKnobIndicator(k);
    });

    // ---- WHEEL-TO-ADJUST FOR ALL SLIDERS ----
    function setupSliderWheel(slider, step) {
        if (!slider) return;
        slider.addEventListener("wheel", (e) => {
            e.preventDefault();
            const min = parseInt(slider.min) || 0;
            const max = parseInt(slider.max) || 255;
            const stepVal = step ?? Math.max(1, Math.round((max - min) / 50));
            let val = parseInt(slider.value) + (e.deltaY > 0 ? -stepVal : stepVal);
            val = Math.max(min, Math.min(max, val));
            slider.value = val;
            slider.dispatchEvent(new Event("input", { bubbles: true }));
        }, { passive: false });
    }
    [sliderR, sliderG, sliderB, sliderW].forEach((s) => setupSliderWheel(s, 5));
    setupSliderWheel(sliderBright, 2);
    setupSliderWheel(sliderFade, 1);

    [sliderRgbDim, sliderWhiteDim, sliderColorStrobeRate, sliderWhiteStrobeRate, sliderSpeed, sliderWSpeed].forEach((s, i) => {
        const keys = ["rgbDim", "whiteDim", "colorStrobeRate", "whiteStrobeRate", "effectSpeed", "whiteSpeed"];
        s.addEventListener("input", () => syncKnobIndicator(keys[i]));
    });

    function updateMasterSliderFills() {
        $("#brightFill").style.width = sliderBright.value + "%";
        $("#fadeFill").style.width = (parseInt(sliderFade.value) / 50 * 100) + "%";
    }
    sliderBright.addEventListener("input", () => {
        const val = parseInt(sliderBright.value);
        $("#brightVal").textContent = val + "%";
        $("#brightFill").style.width = val + "%";
        socket.emit("set_brightness", { value: val / 100 });
    });
    sliderFade.addEventListener("input", () => {
        fadeTime = parseInt(sliderFade.value) / 10;
        fadeValEl.textContent = fadeTime.toFixed(1) + "s";
        $("#fadeFill").style.width = (parseInt(sliderFade.value) / 50 * 100) + "%";
    });

    let strobeLinked = false;
    btnStrobeLink.classList.toggle("linked", strobeLinked);
    btnStrobeLink.addEventListener("click", () => {
        strobeLinked = !strobeLinked;
        btnStrobeLink.classList.toggle("linked", strobeLinked);
        if (strobeLinked) {
            const v = parseInt(sliderColorStrobeRate.value);
            sliderWhiteStrobeRate.value = v;
            whiteStrobeRateVal.textContent = v;
            syncKnobIndicator("whiteStrobeRate");
            socket.emit("set_white_strobe_rate", { value: v });
        }
    });

    function onColorStrobeRateInput() {
        const val = parseInt(sliderColorStrobeRate.value);
        colorStrobeRateVal.textContent = val;
        socket.emit("set_color_strobe_rate", { value: val });
        if (strobeLinked) {
            sliderWhiteStrobeRate.value = val;
            whiteStrobeRateVal.textContent = val;
            syncKnobIndicator("whiteStrobeRate");
            socket.emit("set_white_strobe_rate", { value: val });
        }
    }
    function onWhiteStrobeRateInput() {
        const val = parseInt(sliderWhiteStrobeRate.value);
        whiteStrobeRateVal.textContent = val;
        socket.emit("set_white_strobe_rate", { value: val });
        if (strobeLinked) {
            sliderColorStrobeRate.value = val;
            colorStrobeRateVal.textContent = val;
            syncKnobIndicator("colorStrobeRate");
            socket.emit("set_color_strobe_rate", { value: val });
        }
    }
    sliderColorStrobeRate.addEventListener("input", onColorStrobeRateInput);
    sliderWhiteStrobeRate.addEventListener("input", onWhiteStrobeRateInput);

    // ---- SELECTION STATE ----
    const selected = new Set();
    let lastClickedZone = null;

    function zoneKey(row, col) { return `${row}-${col}`; }

    function parseZoneKey(key) {
        const [row, col] = key.split("-");
        return { row, col: parseInt(col) };
    }

    function zoneKeyToServer(key) {
        const { row, col } = parseZoneKey(key);
        if (row === "bot") return { type: "color", idx: col };
        if (row === "top") return { type: "color", idx: 47 - col };
        if (row === "mid") return { type: "white", idx: col };
        return null;
    }

    function selectionToServerPayload(r, g, b, w) {
        const colorZones = [];
        const whiteZones = [];
        for (const key of selected) {
            const z = zoneKeyToServer(key);
            if (!z) continue;
            if (z.type === "color") colorZones.push(z.idx);
            else whiteZones.push(z.idx);
        }
        return { color_zones: colorZones, white_zones: whiteZones, r, g, b, w };
    }

    function updateSelectionUI() {
        const n = selected.size;
        selToolbar.classList.toggle("visible", n > 0);
        selCount.textContent = n + " selected";

        document.querySelectorAll(".led-zone").forEach((el) => {
            const key = zoneKey(el.dataset.row, el.dataset.col);
            el.classList.toggle("selected", selected.has(key));
        });
    }

    function toggleZone(row, col, multi) {
        const key = zoneKey(row, col);
        if (multi) {
            if (selected.has(key)) selected.delete(key);
            else selected.add(key);
        } else {
            const wasOnly = selected.size === 1 && selected.has(key);
            selected.clear();
            if (!wasOnly) selected.add(key);
        }
        lastClickedZone = key;
        updateSelectionUI();
    }

    function rangeSelect(row, col) {
        if (!lastClickedZone) {
            toggleZone(row, col, false);
            return;
        }
        const prev = parseZoneKey(lastClickedZone);
        const rows = ["top", "mid", "bot"];
        const ri1 = rows.indexOf(prev.row);
        const ri2 = rows.indexOf(row);
        const rMin = Math.min(ri1, ri2);
        const rMax = Math.max(ri1, ri2);
        const cMin = Math.min(prev.col, col);
        const cMax = Math.max(prev.col, col);
        for (let ri = rMin; ri <= rMax; ri++) {
            for (let c = cMin; c <= cMax; c++) {
                selected.add(zoneKey(rows[ri], c));
            }
        }
        updateSelectionUI();
    }

    // ---- GROUPS ----
    let groups = loadGroups();

    function loadGroups() {
        try {
            return JSON.parse(localStorage.getItem("yeesite_groups") || "[]");
        } catch { return []; }
    }

    function saveGroups() {
        localStorage.setItem("yeesite_groups", JSON.stringify(groups));
    }

    function createGroup(name, zones) {
        const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
        groups.push({ id, name, zones: Array.from(zones), r: 0, g: 0, b: 0, w: 0, dim: 100 });
        saveGroups();
        renderGroups();
    }

    function deleteGroup(id) {
        groups = groups.filter((g) => g.id !== id);
        saveGroups();
        renderGroups();
    }

    function applyGroupColor(group) {
        const colorZones = [];
        const whiteZones = [];
        for (const key of group.zones) {
            const z = zoneKeyToServer(key);
            if (!z) continue;
            if (z.type === "color") colorZones.push(z.idx);
            else whiteZones.push(z.idx);
        }
        const d = (group.dim ?? 100) / 100;
        socket.emit("set_zones", {
            color_zones: colorZones,
            white_zones: whiteZones,
            r: Math.round(group.r * d),
            g: Math.round(group.g * d),
            b: Math.round(group.b * d),
            w: Math.round(group.w * d),
        });
    }

    function toggleGroupPower(group, offBtn) {
        group.isOff = !(group.isOff ?? false);
        if (group.isOff) {
            const colorZones = [];
            const whiteZones = [];
            for (const key of group.zones) {
                const z = zoneKeyToServer(key);
                if (!z) continue;
                if (z.type === "color") colorZones.push(z.idx);
                else whiteZones.push(z.idx);
            }
            socket.emit("set_zones", {
                color_zones: colorZones,
                white_zones: whiteZones,
                r: 0, g: 0, b: 0, w: 0,
            });
        } else {
            applyGroupColor(group);
        }
        offBtn.textContent = group.isOff ? "\u23FC" : "\u23FB";
        offBtn.title = group.isOff ? "Turn on" : "Turn off";
    }

    function highlightGroupZones(group) {
        selected.clear();
        group.zones.forEach((k) => selected.add(k));
        updateSelectionUI();
    }

    function renderGroups() {
        groupsEmpty.style.display = groups.length ? "none" : "block";
        groupsList.innerHTML = "";
        groups.forEach((g) => {
            g.isOff = g.isOff ?? false;
            const card = document.createElement("div");
            card.className = "group-card";
            const hexVal = rgbToHex(g.r, g.g, g.b);
            const dim = g.dim ?? 100;
            const offLabel = g.isOff ? "\u23FC" : "\u23FB";
            const offTitle = g.isOff ? "Turn on" : "Turn off";
            card.innerHTML = `
                <div class="group-header">
                    <span class="group-name">${esc(g.name)}</span>
                    <span class="group-zone-count">${g.zones.length}z</span>
                    <div class="group-actions">
                        <button class="group-btn off" data-action="off" title="${offTitle}">${offLabel}</button>
                        <button class="group-btn highlight" data-action="highlight" title="Show zones">&#9678;</button>
                        <button class="group-btn delete" data-action="delete" title="Delete">&times;</button>
                    </div>
                </div>
                <div class="group-quick">
                    <input type="color" class="group-color-picker" value="${hexVal}">
                    <div class="group-mini gs-w">
                        <label>W <span class="gm-val">${g.w}</span></label>
                        <input type="range" min="0" max="255" value="${g.w}" data-ch="w">
                    </div>
                    <div class="group-mini gs-dim">
                        <label>Dim <span class="gm-val">${dim}%</span></label>
                        <input type="range" min="0" max="100" value="${dim}" data-ch="dim">
                    </div>
                </div>
            `;

            const offBtn = card.querySelector('[data-action="off"]');
            card.querySelector('[data-action="delete"]').addEventListener("click", () => deleteGroup(g.id));
            card.querySelector('[data-action="highlight"]').addEventListener("click", () => highlightGroupZones(g));
            offBtn.addEventListener("click", () => toggleGroupPower(g, offBtn));

            const picker = card.querySelector(".group-color-picker");
            const wSlider = card.querySelector('[data-ch="w"]');
            const wVal = card.querySelector('.gs-w .gm-val');
            const dimSlider = card.querySelector('[data-ch="dim"]');
            const dimValEl = card.querySelector('.gs-dim .gm-val');
            setupSliderWheel(wSlider, 5);
            setupSliderWheel(dimSlider, 2);

            let groupThrottle = null;
            function throttledApply() {
                saveGroups();
                g.isOff = false;
                offBtn.textContent = "\u23FB";
                offBtn.title = "Turn off";
                if (groupThrottle) return;
                groupThrottle = setTimeout(() => {
                    groupThrottle = null;
                    applyGroupColor(g);
                }, 30);
            }

            picker.addEventListener("input", () => {
                const c = hexToRgb(picker.value);
                g.r = c.r; g.g = c.g; g.b = c.b;
                throttledApply();
            });

            wSlider.addEventListener("input", () => {
                g.w = parseInt(wSlider.value);
                wVal.textContent = g.w;
                throttledApply();
            });

            dimSlider.addEventListener("input", () => {
                g.dim = parseInt(dimSlider.value);
                dimValEl.textContent = g.dim + "%";
                throttledApply();
            });

            groupsList.appendChild(card);
        });
    }

    function esc(s) {
        const d = document.createElement("div");
        d.textContent = s;
        return d.innerHTML;
    }

    // ---- SCENES ----
    let scenes = loadScenes();

    function loadScenes() {
        try { return JSON.parse(localStorage.getItem("yeesite_scenes") || "[]"); }
        catch { return []; }
    }

    function saveScenesToStorage() {
        localStorage.setItem("yeesite_scenes", JSON.stringify(scenes));
    }

    function captureScene(name) {
        const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
        const scene = {
            id, name,
            r: parseInt(sliderR.value), g: parseInt(sliderG.value),
            b: parseInt(sliderB.value), w: parseInt(sliderW.value),
            brightness: parseInt(sliderBright.value),
            effect: activeEffect, whiteEffect: activeWhiteEffect,
            effectColors: { ...activeEffectColors },
            speed: parseInt(sliderSpeed.value),
            wSpeed: parseInt(sliderWSpeed.value),
            rgbDim: parseInt(sliderRgbDim.value),
            whiteDim: parseInt(sliderWhiteDim.value),
            colorStrobeRate: parseInt(sliderColorStrobeRate.value),
            whiteStrobeRate: parseInt(sliderWhiteStrobeRate.value),
            strobeLinked,
        };
        scenes.push(scene);
        saveScenesToStorage();
        renderScenes();
    }

    function recallScene(scene) {
        sliderR.value = scene.r; sliderG.value = scene.g;
        sliderB.value = scene.b; sliderW.value = scene.w;
        updateColorDisplay();
        sliderBright.value = scene.brightness;
        $("#brightVal").textContent = scene.brightness + "%";
        socket.emit("set_brightness", { value: scene.brightness / 100 });
        if (scene.colorStrobeRate != null) { sliderColorStrobeRate.value = scene.colorStrobeRate; colorStrobeRateVal.textContent = scene.colorStrobeRate; syncKnobIndicator("colorStrobeRate"); socket.emit("set_color_strobe_rate", { value: scene.colorStrobeRate }); }
        if (scene.whiteStrobeRate != null) { sliderWhiteStrobeRate.value = scene.whiteStrobeRate; whiteStrobeRateVal.textContent = scene.whiteStrobeRate; syncKnobIndicator("whiteStrobeRate"); socket.emit("set_white_strobe_rate", { value: scene.whiteStrobeRate }); }
        strobeLinked = !!scene.strobeLinked;
        btnStrobeLink.classList.toggle("linked", strobeLinked);
        if (scene.speed != null) { sliderSpeed.value = scene.speed; sendSpeed(); }
        if (scene.wSpeed != null) { sliderWSpeed.value = scene.wSpeed; sendWhiteSpeed(); }
        if (scene.rgbDim != null) { sliderRgbDim.value = scene.rgbDim; sendRgbDimmer(); }
        if (scene.whiteDim != null) { sliderWhiteDim.value = scene.whiteDim; sendWhiteDimmer(); }
        if (scene.effect && effectsMeta[scene.effect]) {
            activeEffect = scene.effect;
            activeEffectColors = scene.effectColors || {};
            activeEffectDimmers = {};
            updateEffectButtons();
            renderEffectConfig();
            socket.emit("set_effect", { name: scene.effect, colors: activeEffectColors });
        } else if (scene.whiteEffect && whiteEffectsMeta[scene.whiteEffect]) {
            setWhiteEffect(scene.whiteEffect);
        } else {
            sendColor();
        }
    }

    function deleteScene(id) {
        scenes = scenes.filter((s) => s.id !== id);
        saveScenesToStorage();
        renderScenes();
    }

    function renderScenes() {
        scenesEmpty.style.display = scenes.length ? "none" : "block";
        const existing = scenesRow.querySelectorAll(".scene-card");
        existing.forEach((el) => el.remove());
        scenes.forEach((s) => {
            const card = document.createElement("div");
            card.className = "scene-card";
            const previewColor = s.effect ? "linear-gradient(135deg, var(--accent), #6e40c9)" :
                `rgb(${Math.max(s.r, s.w * 0.7)}, ${Math.max(s.g, s.w * 0.7)}, ${Math.max(s.b, s.w * 0.6)})`;
            const meta = s.effect ? effectsMeta[s.effect]?.name || s.effect :
                s.whiteEffect ? "White: " + (whiteEffectsMeta[s.whiteEffect]?.name || s.whiteEffect) :
                `R${s.r} G${s.g} B${s.b} W${s.w}`;
            card.innerHTML = `
                <div class="scene-card-preview" style="background:${previewColor}"></div>
                <div class="scene-card-name">${esc(s.name)}</div>
                <div class="scene-card-meta">${esc(meta)}</div>
                <button class="scene-card-delete" title="Delete">&times;</button>
            `;
            card.addEventListener("click", (e) => {
                if (e.target.closest(".scene-card-delete")) return;
                recallScene(s);
            });
            card.querySelector(".scene-card-delete").addEventListener("click", () => deleteScene(s.id));
            scenesRow.appendChild(card);
        });
    }

    btnSaveScene.addEventListener("click", () => {
        const name = prompt("Scene name:", `Scene ${scenes.length + 1}`);
        if (!name) return;
        captureScene(name);
    });

    // ---- CUSTOM COLOR PRESETS ----
    let customPresets = loadCustomPresets();

    function loadCustomPresets() {
        try { return JSON.parse(localStorage.getItem("yeesite_custom_presets") || "[]"); }
        catch { return []; }
    }

    function saveCustomPresets() {
        localStorage.setItem("yeesite_custom_presets", JSON.stringify(customPresets));
    }

    function renderCustomPresets() {
        customPresetsEl.innerHTML = "";
        customPresets.forEach((p, i) => {
            const btn = document.createElement("button");
            btn.className = "custom-preset";
            btn.title = `Custom: R${p.r} G${p.g} B${p.b} W${p.w}`;
            if (p.w > 0 && (p.r + p.g + p.b) === 0) {
                btn.style.background = `rgb(${p.w}, ${p.w}, ${Math.round(p.w * 0.9)})`;
            } else {
                const mr = Math.min(255, p.r + p.w * 0.7);
                const mg = Math.min(255, p.g + p.w * 0.7);
                const mb = Math.min(255, p.b + p.w * 0.6);
                btn.style.background = `rgb(${mr}, ${mg}, ${mb})`;
            }
            btn.innerHTML = `<button class="cp-delete" title="Remove">&times;</button>`;
            btn.addEventListener("click", (e) => {
                if (e.target.closest(".cp-delete")) {
                    customPresets.splice(i, 1);
                    saveCustomPresets();
                    renderCustomPresets();
                    return;
                }
                sliderR.value = p.r; sliderG.value = p.g;
                sliderB.value = p.b; sliderW.value = p.w;
                updateColorDisplay();
                sendColor();
            });
            customPresetsEl.appendChild(btn);
        });
    }

    btnAddPreset.addEventListener("click", () => {
        colorPicker.value = rgbToHex(parseInt(sliderR.value), parseInt(sliderG.value), parseInt(sliderB.value));
        colorPicker.click();
    });

    // ---- EFFECT FAVORITES ----
    let effectFavs = loadEffectFavs();

    function loadEffectFavs() {
        try { return new Set(JSON.parse(localStorage.getItem("yeesite_effect_favs") || "[]")); }
        catch { return new Set(); }
    }

    function saveEffectFavs() {
        localStorage.setItem("yeesite_effect_favs", JSON.stringify([...effectFavs]));
    }

    function toggleEffectFav(key) {
        if (effectFavs.has(key)) effectFavs.delete(key);
        else effectFavs.add(key);
        saveEffectFavs();
    }

    // ---- PRESETS / LED BAR / EFFECTS ----

    const PRESETS = [
        { name: "Red",        r: 255, g: 0,   b: 0,   w: 0   },
        { name: "Green",      r: 0,   g: 255, b: 0,   w: 0   },
        { name: "Blue",       r: 0,   g: 0,   b: 255, w: 0   },
        { name: "White",      r: 0,   g: 0,   b: 0,   w: 255 },
        { name: "Warm White", r: 255, g: 160, b: 60,  w: 200 },
        { name: "Cyan",       r: 0,   g: 255, b: 255, w: 0   },
        { name: "Yellow",     r: 255, g: 255, b: 0,   w: 0   },
        { name: "Purple",     r: 180, g: 0,   b: 255, w: 0   },
        { name: "Orange",     r: 255, g: 100, b: 0,   w: 0   },
        { name: "Pink",       r: 255, g: 20,  b: 147, w: 0   },
    ];

    function buildLedBar() {
        rowTop.innerHTML = '<span class="led-row-label">T</span>';
        rowMid.innerHTML = '<span class="led-row-label">W</span>';
        rowBot.innerHTML = '<span class="led-row-label">B</span>';

        for (let col = 0; col < COLUMNS; col++) {
            const top = document.createElement("div");
            top.className = "led-zone";
            top.dataset.row = "top";
            top.dataset.col = col;
            rowTop.appendChild(top);

            const mid = document.createElement("div");
            mid.className = "led-zone white-zone";
            mid.dataset.row = "mid";
            mid.dataset.col = col;
            rowMid.appendChild(mid);

            const bot = document.createElement("div");
            bot.className = "led-zone";
            bot.dataset.row = "bot";
            bot.dataset.col = col;
            rowBot.appendChild(bot);
        }

        // Zone click handlers
        document.querySelectorAll(".led-zone").forEach((el) => {
            el.addEventListener("click", (e) => {
                const row = el.dataset.row;
                const col = parseInt(el.dataset.col);
                if (e.shiftKey) rangeSelect(row, col);
                else toggleZone(row, col, e.ctrlKey || e.metaKey);
            });
        });
    }

    function buildPresets() {
        presetsContainer.innerHTML = "";
        PRESETS.forEach((p, i) => {
            const btn = document.createElement("button");
            btn.className = "preset-btn";
            btn.title = `${p.name} [${(i + 1) % 10}]`;
            if (p.w > 0 && (p.r + p.g + p.b) === 0) {
                btn.style.background = `rgb(${p.w}, ${p.w}, ${Math.round(p.w * 0.9)})`;
            } else {
                const mr = Math.min(255, p.r + p.w * 0.7);
                const mg = Math.min(255, p.g + p.w * 0.7);
                const mb = Math.min(255, p.b + p.w * 0.6);
                btn.style.background = `rgb(${mr}, ${mg}, ${mb})`;
            }
            btn.addEventListener("click", () => {
                sliderR.value = p.r;
                sliderG.value = p.g;
                sliderB.value = p.b;
                sliderW.value = p.w;
                updateColorDisplay();
                sendColor();
            });
            presetsContainer.appendChild(btn);
        });
    }

    function makeEffectBtn(key, info, dataAttr, isActive, onToggle) {
        const btn = document.createElement("button");
        btn.className = "effect-btn";
        btn.dataset[dataAttr] = key;
        const star = document.createElement("button");
        star.className = "effect-fav" + (effectFavs.has(key) ? " is-fav" : "");
        star.textContent = effectFavs.has(key) ? "\u2605" : "\u2606";
        star.addEventListener("click", (e) => {
            e.stopPropagation();
            toggleEffectFav(key);
            star.classList.toggle("is-fav");
            star.textContent = effectFavs.has(key) ? "\u2605" : "\u2606";
        });
        btn.innerHTML = `${info.name}<span class="cat-tag">${info.category}</span>`;
        btn.appendChild(star);
        btn.addEventListener("click", () => onToggle(key));
        return btn;
    }

    function buildEffects(effectMap) {
        effectsMeta = effectMap;
        effectsGrid.innerHTML = "";
        const order = [
            "rainbow_chase", "color_cycle", "fire", "knight_rider",
            "police", "police_tb", "color_wipe", "wave", "meteor",
            "breathe", "sparkle", "twinkle", "theater_chase",
            "alternating", "gradient", "rainbow_breathe",
            "bounce", "plasma", "rain", "pulse", "heartbeat",
            "lightning", "strobe", "running_lights", "lava", "comet", "color_bounce",
        ];
        const keys = order.filter((k) => k in effectMap);
        const favKeys = keys.filter((k) => effectFavs.has(k));
        const restKeys = keys.filter((k) => !effectFavs.has(k));

        if (favKeys.length > 0) {
            const divider = document.createElement("div");
            divider.className = "effects-fav-divider";
            divider.textContent = "Favorites";
            effectsGrid.appendChild(divider);
            favKeys.forEach((key) => {
                effectsGrid.appendChild(makeEffectBtn(key, effectMap[key], "effect", activeEffect === key, (k) => {
                    if (activeEffect === k) stopRgbEffect();
                    else setEffect(k);
                }));
            });
            const divider2 = document.createElement("div");
            divider2.className = "effects-fav-divider";
            divider2.textContent = "All Effects";
            effectsGrid.appendChild(divider2);
        }

        restKeys.forEach((key) => {
            effectsGrid.appendChild(makeEffectBtn(key, effectMap[key], "effect", activeEffect === key, (k) => {
                if (activeEffect === k) stopRgbEffect();
                else setEffect(k);
            }));
        });
    }

    function buildWhiteEffects(wMap) {
        whiteEffectsMeta = wMap;
        whiteEffectsGrid.innerHTML = "";
        const order = [
            "w_breathe", "w_strobe", "w_chase", "w_twinkle", "w_sparkle",
            "w_pulse", "w_wave", "w_alternating", "w_gradient", "w_rain", "w_bounce",
        ];
        const keys = order.filter((k) => k in wMap);
        const favKeys = keys.filter((k) => effectFavs.has(k));
        const restKeys = keys.filter((k) => !effectFavs.has(k));

        if (favKeys.length > 0) {
            const divider = document.createElement("div");
            divider.className = "effects-fav-divider";
            divider.textContent = "Favorites";
            whiteEffectsGrid.appendChild(divider);
            favKeys.forEach((key) => {
                whiteEffectsGrid.appendChild(makeEffectBtn(key, wMap[key], "weffect", activeWhiteEffect === key, (k) => {
                    if (activeWhiteEffect === k) stopWhiteEffect();
                    else setWhiteEffect(k);
                }));
            });
            const divider2 = document.createElement("div");
            divider2.className = "effects-fav-divider";
            divider2.textContent = "All Effects";
            whiteEffectsGrid.appendChild(divider2);
        }

        restKeys.forEach((key) => {
            whiteEffectsGrid.appendChild(makeEffectBtn(key, wMap[key], "weffect", activeWhiteEffect === key, (k) => {
                if (activeWhiteEffect === k) stopWhiteEffect();
                else setWhiteEffect(k);
            }));
        });
    }

    function updateWhiteEffectButtons() {
        document.querySelectorAll("[data-weffect]").forEach((btn) => {
            btn.classList.toggle("active", btn.dataset.weffect === activeWhiteEffect);
        });
    }

    function hexToRgb(hex) {
        hex = hex.replace("#", "");
        return {
            r: parseInt(hex.substring(0, 2), 16) || 0,
            g: parseInt(hex.substring(2, 4), 16) || 0,
            b: parseInt(hex.substring(4, 6), 16) || 0,
        };
    }

    function rgbToHex(r, g, b) {
        return "#" + [r, g, b].map((v) => Math.max(0, Math.min(255, v)).toString(16).padStart(2, "0")).join("");
    }

    function renderEffectConfig() {
        if (!activeEffect || !effectsMeta[activeEffect]) {
            effectConfig.classList.remove("visible");
            effectConfig.innerHTML = "";
            return;
        }
        const meta = effectsMeta[activeEffect];
        const slots = meta.colors || [];
        if (slots.length === 0) {
            effectConfig.classList.remove("visible");
            effectConfig.innerHTML = "";
            return;
        }

        effectConfig.classList.add("visible");
        effectConfig.innerHTML = `<div class="effect-config-title">${esc(meta.name)} Colors</div><div class="effect-color-slots" id="effectColorSlots"></div>`;
        const container = effectConfig.querySelector("#effectColorSlots");

        slots.forEach((slot) => {
            const current = activeEffectColors[slot.key] || slot.default;
            const rgb = hexToRgb(current);
            const dim = activeEffectDimmers[slot.key] ?? 100;
            const card = document.createElement("div");
            card.className = "effect-color-slot";
            card.innerHTML = `
                <div class="effect-slot-header">
                    <span class="effect-slot-label">${esc(slot.label)}</span>
                    <input type="color" class="effect-slot-picker" value="${current}">
                </div>
                <div class="effect-slot-sliders">
                    <div class="effect-ch-row">
                        <span class="effect-ch-label ec-r">R</span>
                        <input type="range" min="0" max="255" value="${rgb.r}" data-ch="r">
                        <span class="effect-ch-val">${rgb.r}</span>
                    </div>
                    <div class="effect-ch-row">
                        <span class="effect-ch-label ec-g">G</span>
                        <input type="range" min="0" max="255" value="${rgb.g}" data-ch="g">
                        <span class="effect-ch-val">${rgb.g}</span>
                    </div>
                    <div class="effect-ch-row">
                        <span class="effect-ch-label ec-b">B</span>
                        <input type="range" min="0" max="255" value="${rgb.b}" data-ch="b">
                        <span class="effect-ch-val">${rgb.b}</span>
                    </div>
                    <div class="effect-ch-row effect-dimmer-row">
                        <span class="effect-ch-label ec-dim">%</span>
                        <input type="range" min="0" max="100" value="${dim}" data-ch="dim">
                        <span class="effect-ch-val">${dim}</span>
                    </div>
                </div>
            `;

            const picker = card.querySelector(".effect-slot-picker");
            const rgbSliders = card.querySelectorAll('.effect-ch-row:not(.effect-dimmer-row) input[type="range"]');
            const rgbVals = card.querySelectorAll('.effect-ch-row:not(.effect-dimmer-row) .effect-ch-val');
            const dimSlider = card.querySelector('.effect-dimmer-row input[type="range"]');
            const dimVal = card.querySelector('.effect-dimmer-row .effect-ch-val');
            rgbSliders.forEach((s) => setupSliderWheel(s, 5));
            setupSliderWheel(dimSlider, 2);

            function dimmedHex() {
                const d = parseInt(dimSlider.value) / 100;
                return rgbToHex(
                    Math.round(parseInt(rgbSliders[0].value) * d),
                    Math.round(parseInt(rgbSliders[1].value) * d),
                    Math.round(parseInt(rgbSliders[2].value) * d)
                );
            }

            function sendSlotUpdate() {
                activeEffectColors[slot.key] = dimmedHex();
                activeEffectDimmers[slot.key] = parseInt(dimSlider.value);
                if (!slotThrottle) {
                    slotThrottle = setTimeout(() => {
                        slotThrottle = null;
                        socket.emit("set_effect", { name: activeEffect, colors: activeEffectColors });
                    }, 30);
                }
            }

            let slotThrottle = null;

            rgbSliders.forEach((slider, i) => {
                slider.addEventListener("input", () => {
                    rgbVals[i].textContent = slider.value;
                    picker.value = rgbToHex(
                        parseInt(rgbSliders[0].value),
                        parseInt(rgbSliders[1].value),
                        parseInt(rgbSliders[2].value)
                    );
                    sendSlotUpdate();
                });
            });

            dimSlider.addEventListener("input", () => {
                dimVal.textContent = dimSlider.value;
                sendSlotUpdate();
            });

            picker.addEventListener("input", () => {
                const c = hexToRgb(picker.value);
                rgbSliders[0].value = c.r; rgbVals[0].textContent = c.r;
                rgbSliders[1].value = c.g; rgbVals[1].textContent = c.g;
                rgbSliders[2].value = c.b; rgbVals[2].textContent = c.b;
                sendSlotUpdate();
            });

            container.appendChild(card);
        });
    }

    // ---- UPDATE UI ----
    function updateColorDisplay() {
        const r = parseInt(sliderR.value);
        const g = parseInt(sliderG.value);
        const b = parseInt(sliderB.value);
        const w = parseInt(sliderW.value);
        $("#rVal").textContent = r;
        $("#gVal").textContent = g;
        $("#bVal").textContent = b;
        $("#wVal").textContent = w;
        $("#faderFillR").style.width = (r / 255 * 100) + "%";
        $("#faderFillG").style.width = (g / 255 * 100) + "%";
        $("#faderFillB").style.width = (b / 255 * 100) + "%";
        $("#faderFillW").style.width = (w / 255 * 100) + "%";
        colorPreview.style.backgroundColor = `rgb(${r}, ${g}, ${b})`;
        colorPicker.value = rgbToHex(r, g, b);
        const wBright = Math.round(w * 0.95);
        whitePreview.style.backgroundColor = `rgb(${wBright}, ${wBright}, ${Math.round(w * 0.88)})`;
    }

    function updateLedBar(display) {
        if (!display) return;
        const topZones = rowTop.querySelectorAll(".led-zone");
        const midZones = rowMid.querySelectorAll(".led-zone");
        const botZones = rowBot.querySelectorAll(".led-zone");

        for (let col = 0; col < COLUMNS; col++) {
            if (display.top && display.top[col]) {
                const t = display.top[col];
                topZones[col].style.backgroundColor = `rgb(${t.r}, ${t.g}, ${t.b})`;
            }
            if (display.middle && display.middle[col]) {
                const m = display.middle[col];
                const wv = m.w;
                midZones[col].style.backgroundColor = `rgb(${wv}, ${wv}, ${Math.round(wv * 0.92)})`;
            }
            if (display.bottom && display.bottom[col]) {
                const b = display.bottom[col];
                botZones[col].style.backgroundColor = `rgb(${b.r}, ${b.g}, ${b.b})`;
            }
        }
    }

    function updateEffectButtons() {
        document.querySelectorAll(".effect-btn[data-effect]").forEach((btn) => {
            btn.classList.toggle("active", btn.dataset.effect === activeEffect);
        });
    }


    // ---- COMMUNICATION ----
    function sendColor() {
        const r = parseInt(sliderR.value);
        const g = parseInt(sliderG.value);
        const b = parseInt(sliderB.value);
        const w = parseInt(sliderW.value);

        activeEffect = null;
        activeWhiteEffect = null;
        activeEffectColors = {};
        activeEffectDimmers = {};
        updateEffectButtons();
        updateWhiteEffectButtons();
        renderEffectConfig();

        if (selected.size > 0) {
            socket.emit("set_zones", selectionToServerPayload(r, g, b, w));
        } else {
            socket.emit("set_color", { r, g, b, w, fade_time: fadeTime });
        }
    }

    function setEffect(name) {
        activeEffect = name;
        activeEffectColors = {};
        activeEffectDimmers = {};
        const meta = effectsMeta[name];
        if (meta && meta.colors) {
            meta.colors.forEach((slot) => {
                activeEffectColors[slot.key] = slot.default;
                activeEffectDimmers[slot.key] = 100;
            });
        }
        updateEffectButtons();
        renderEffectConfig();
        socket.emit("set_effect", { name, colors: activeEffectColors });
    }

    function stopRgbEffect() {
        activeEffect = null;
        activeEffectColors = {};
        activeEffectDimmers = {};
        updateEffectButtons();
        renderEffectConfig();
        socket.emit("set_effect", { name: "" });
    }

    function setWhiteEffect(name) {
        activeWhiteEffect = name;
        updateWhiteEffectButtons();
        socket.emit("set_white_effect", { name });
    }

    function stopWhiteEffect() {
        activeWhiteEffect = null;
        updateWhiteEffectButtons();
        socket.emit("stop_white_effect", {});
    }

    function stopAll() {
        activeEffect = null;
        activeWhiteEffect = null;
        activeEffectColors = {};
        activeEffectDimmers = {};
        updateEffectButtons();
        updateWhiteEffectButtons();
        renderEffectConfig();
        sliderR.value = 0; sliderG.value = 0; sliderB.value = 0; sliderW.value = 0;
        updateColorDisplay();
        setSpeedUI(1.0);
        setWhiteSpeedUI(1.0);
        setRgbDimmerUI(100);
        setWhiteDimmerUI(100);
        fadeTime = 0;
        sliderFade.value = 0;
        fadeValEl.textContent = "0s";
        updateMasterSliderFills();
        syncKnobIndicator("rgbDim");
        syncKnobIndicator("whiteDim");
        socket.emit("stop", {});
    }

    // ---- SELECTION TOOLBAR ----
    selApply.addEventListener("click", () => sendColor());
    selClear.addEventListener("click", () => {
        selected.clear();
        updateSelectionUI();
    });
    selAll.addEventListener("click", () => {
        for (let c = 0; c < COLUMNS; c++) {
            selected.add(zoneKey("top", c));
            selected.add(zoneKey("mid", c));
            selected.add(zoneKey("bot", c));
        }
        updateSelectionUI();
    });
    selGroup.addEventListener("click", () => {
        if (selected.size === 0) return;
        const name = prompt("Group name:", `Group ${groups.length + 1}`);
        if (!name) return;
        createGroup(name, selected);
    });

    // ---- SPEED ----
    function sendSpeed() {
        const raw = parseInt(sliderSpeed.value);
        const spd = raw / 100;
        speedVal.textContent = spd.toFixed(1) + "\u00d7";
        socket.emit("set_speed", { value: spd });
    }
    function setSpeedUI(val) {
        const clamped = Math.max(0.1, Math.min(10.0, val));
        sliderSpeed.value = Math.round(clamped * 100);
        speedVal.textContent = clamped.toFixed(1) + "\u00d7";
        socket.emit("set_speed", { value: clamped });
    }
    sliderSpeed.addEventListener("input", sendSpeed);
    effectReset.addEventListener("click", () => {
        setSpeedUI(1.0);
        setRgbDimmerUI(100);
        sliderColorStrobeRate.value = 8;
        colorStrobeRateVal.textContent = 8;
        syncKnobIndicator("effectSpeed");
        syncKnobIndicator("rgbDim");
        syncKnobIndicator("colorStrobeRate");
        onColorStrobeRateInput();
    });

    // ---- WHITE SPEED ----
    function sendWhiteSpeed() {
        const raw = parseInt(sliderWSpeed.value);
        const spd = raw / 100;
        wSpeedVal.textContent = spd.toFixed(1) + "\u00d7";
        socket.emit("set_white_speed", { value: spd });
    }
    function setWhiteSpeedUI(val) {
        const clamped = Math.max(0.1, Math.min(10.0, val));
        sliderWSpeed.value = Math.round(clamped * 100);
        wSpeedVal.textContent = clamped.toFixed(1) + "\u00d7";
        socket.emit("set_white_speed", { value: clamped });
    }
    sliderWSpeed.addEventListener("input", sendWhiteSpeed);
    whiteEffectReset.addEventListener("click", () => {
        setWhiteSpeedUI(1.0);
        setWhiteDimmerUI(100);
        sliderWhiteStrobeRate.value = 8;
        whiteStrobeRateVal.textContent = 8;
        syncKnobIndicator("whiteSpeed");
        syncKnobIndicator("whiteDim");
        syncKnobIndicator("whiteStrobeRate");
        onWhiteStrobeRateInput();
    });


    // ---- EFFECT DIMMERS ----
    function sendRgbDimmer() {
        const val = parseInt(sliderRgbDim.value);
        rgbDimVal.textContent = val + "%";
        socket.emit("set_rgb_dimmer", { value: val / 100 });
    }
    function setRgbDimmerUI(val) {
        const v = Math.max(0, Math.min(100, Math.round(val)));
        sliderRgbDim.value = v;
        rgbDimVal.textContent = v + "%";
        socket.emit("set_rgb_dimmer", { value: v / 100 });
    }
    sliderRgbDim.addEventListener("input", sendRgbDimmer);

    function sendWhiteDimmer() {
        const val = parseInt(sliderWhiteDim.value);
        whiteDimVal.textContent = val + "%";
        socket.emit("set_white_dimmer", { value: val / 100 });
    }
    function setWhiteDimmerUI(val) {
        const v = Math.max(0, Math.min(100, Math.round(val)));
        sliderWhiteDim.value = v;
        whiteDimVal.textContent = v + "%";
        socket.emit("set_white_dimmer", { value: v / 100 });
    }
    sliderWhiteDim.addEventListener("input", sendWhiteDimmer);


    // ---- EVENT LISTENERS ----
    let colorThrottle = null;
    function onColorSliderInput() {
        updateColorDisplay();
        if (colorThrottle) return;
        colorThrottle = setTimeout(() => {
            colorThrottle = null;
            sendColor();
        }, 30);
    }
    sliderR.addEventListener("input", onColorSliderInput);
    sliderG.addEventListener("input", onColorSliderInput);
    sliderB.addEventListener("input", onColorSliderInput);
    sliderW.addEventListener("input", onColorSliderInput);

    colorPicker.addEventListener("input", () => {
        const c = hexToRgb(colorPicker.value);
        customPresets.push({ r: c.r, g: c.g, b: c.b, w: 0 });
        saveCustomPresets();
        renderCustomPresets();
        sliderR.value = c.r;
        sliderG.value = c.g;
        sliderB.value = c.b;
        updateColorDisplay();
        if (colorThrottle) return;
        colorThrottle = setTimeout(() => {
            colorThrottle = null;
            sendColor();
        }, 30);
    });


    btnBlackout.addEventListener("click", () => {
        isBlackout = !isBlackout;
        btnBlackout.classList.toggle("active", isBlackout);
        socket.emit("set_blackout", { active: isBlackout });
    });

    btnStop.addEventListener("click", stopAll);

    // ---- SOCKET EVENTS ----
    socket.on("connect", () => {
        statusDot.style.background = "var(--success)";
        statusText.textContent = "Connected";
        fetch("/api/state")
            .then((r) => r.json())
            .then((state) => {
                buildEffects(state.effects);
                if (state.white_effects) buildWhiteEffects(state.white_effects);
                sliderBright.value = Math.round(state.brightness * 100);
                $("#brightVal").textContent = Math.round(state.brightness * 100) + "%";
                isBlackout = state.blackout;
                btnBlackout.classList.toggle("active", isBlackout);
                activeEffect = state.effect;
                updateEffectButtons();
                renderEffectConfig();
                activeWhiteEffect = state.white_effect || null;
                updateWhiteEffectButtons();
                if (state.display) updateLedBar(state.display);
                if (state.color_strobe_rate != null) {
                    const r = Math.max(2, Math.min(20, Math.round(state.color_strobe_rate)));
                    sliderColorStrobeRate.value = r;
                    colorStrobeRateVal.textContent = r;
                    syncKnobIndicator("colorStrobeRate");
                }
                if (state.white_strobe_rate != null) {
                    const r = Math.max(2, Math.min(20, Math.round(state.white_strobe_rate)));
                    sliderWhiteStrobeRate.value = r;
                    whiteStrobeRateVal.textContent = r;
                    syncKnobIndicator("whiteStrobeRate");
                }
                if (state.effect_speed != null) {
                    sliderSpeed.value = Math.round(state.effect_speed * 100);
                    speedVal.textContent = state.effect_speed.toFixed(1) + "\u00d7";
                    syncKnobIndicator("effectSpeed");
                }
                if (state.white_effect_speed != null) {
                    sliderWSpeed.value = Math.round(state.white_effect_speed * 100);
                    wSpeedVal.textContent = state.white_effect_speed.toFixed(1) + "\u00d7";
                    syncKnobIndicator("whiteSpeed");
                }
                if (state.rgb_dimmer != null) {
                    sliderRgbDim.value = Math.round(state.rgb_dimmer * 100);
                    rgbDimVal.textContent = Math.round(state.rgb_dimmer * 100) + "%";
                }
                if (state.white_dimmer != null) {
                    sliderWhiteDim.value = Math.round(state.white_dimmer * 100);
                    whiteDimVal.textContent = Math.round(state.white_dimmer * 100) + "%";
                }
                if (state.brightness != null) {
                    sliderBright.value = Math.round(state.brightness * 100);
                    $("#brightVal").textContent = Math.round(state.brightness * 100) + "%";
                }
                ["rgbDim", "whiteDim"].forEach(syncKnobIndicator);
                updateMasterSliderFills();
            })
            .catch(() => {});
    });

    socket.on("disconnect", () => {
        statusDot.style.background = "var(--danger)";
        statusText.textContent = "Disconnected";
    });

    socket.on("frame", (display) => {
        updateLedBar(display);
    });

    // ---- SHORTCUTS OVERLAY ----
    const shortcutsOverlay = $("#shortcutsOverlay");
    const btnHelp = $("#btnHelp");
    const shortcutsClose = $("#shortcutsClose");

    function toggleShortcuts() {
        shortcutsOverlay.classList.toggle("visible");
    }
    btnHelp.addEventListener("click", toggleShortcuts);
    shortcutsClose.addEventListener("click", toggleShortcuts);
    shortcutsOverlay.addEventListener("click", (e) => {
        if (e.target === shortcutsOverlay) toggleShortcuts();
    });

    // ---- KEYBOARD SHORTCUTS ----
    function applyPreset(idx) {
        if (idx < 0 || idx >= PRESETS.length) return;
        const p = PRESETS[idx];
        sliderR.value = p.r;
        sliderG.value = p.g;
        sliderB.value = p.b;
        sliderW.value = p.w;
        updateColorDisplay();
        sendColor();
    }

    function adjustBrightness(delta) {
        let val = parseInt(sliderBright.value) + delta;
        val = Math.max(0, Math.min(100, val));
        sliderBright.value = val;
        $("#brightVal").textContent = val + "%";
        socket.emit("set_brightness", { value: val / 100 });
    }

    document.addEventListener("keydown", (e) => {
        if (e.target.tagName === "INPUT" && (e.target.type === "text" || e.target.type === "search")) return;
        if (shortcutsOverlay.classList.contains("visible") && e.key !== "?" && e.key !== "Escape") return;

        const key = e.key;

        if (key === "?" || key === "/") { e.preventDefault(); toggleShortcuts(); return; }
        if (key === "Escape") {
            if (shortcutsOverlay.classList.contains("visible")) { toggleShortcuts(); return; }
            e.preventDefault(); stopAll(); return;
        }

        const lower = key.toLowerCase();

        if (lower === "b") { e.preventDefault(); isBlackout = !isBlackout; btnBlackout.classList.toggle("active", isBlackout); socket.emit("set_blackout", { active: isBlackout }); return; }
        if (lower === "r") { e.preventDefault(); setSpeedUI(1.0); return; }
        if (key === "]") { e.preventDefault(); setSpeedUI(parseInt(sliderSpeed.value) / 100 + 0.5); return; }
        if (key === "[") { e.preventDefault(); setSpeedUI(parseInt(sliderSpeed.value) / 100 - 0.5); return; }

        if (lower === "a") {
            e.preventDefault();
            for (let c = 0; c < COLUMNS; c++) {
                selected.add(zoneKey("top", c));
                selected.add(zoneKey("mid", c));
                selected.add(zoneKey("bot", c));
            }
            updateSelectionUI();
            return;
        }
        if (lower === "d") { e.preventDefault(); selected.clear(); updateSelectionUI(); return; }
        if (key === "Enter" && selected.size > 0) { e.preventDefault(); sendColor(); return; }
        if (lower === "g" && selected.size > 0) {
            e.preventDefault();
            const name = prompt("Group name:", `Group ${groups.length + 1}`);
            if (name) createGroup(name, selected);
            return;
        }

        if (key === "ArrowUp") { e.preventDefault(); adjustBrightness(5); return; }
        if (key === "ArrowDown") { e.preventDefault(); adjustBrightness(-5); return; }
        if (key === "ArrowRight") { e.preventDefault(); setSpeedUI(parseInt(sliderSpeed.value) / 100 + 0.5); return; }
        if (key === "ArrowLeft") { e.preventDefault(); setSpeedUI(parseInt(sliderSpeed.value) / 100 - 0.5); return; }

        if (key >= "1" && key <= "9") { e.preventDefault(); applyPreset(parseInt(key) - 1); return; }
        if (key === "0") { e.preventDefault(); applyPreset(9); return; }
    });

    // ---- INIT ----
    buildLedBar();
    buildPresets();
    renderCustomPresets();
    updateColorDisplay();
    updateMasterSliderFills();
    renderGroups();
    renderScenes();
})();
