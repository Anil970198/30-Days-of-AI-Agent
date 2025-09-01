// Session management
function ensureSessionId() {
    const url = new URL(window.location.href);
    let sid = url.searchParams.get("sessionId");
    if (!sid) {
        sid = crypto?.randomUUID?.() || Date.now().toString();
        url.searchParams.set("sessionId", sid);
        history.replaceState(null, "", url.toString());
    }
    return sid;
}

const SESSION_ID = ensureSessionId();

// API helper
async function apiCall(url, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 25000);
    
    try {
        const response = await fetch(url, { ...options, signal: controller.signal });
        let data = {};
        try { data = await response.json(); } catch {}
        
        if (!response.ok) {
            throw new Error(data?.error || `Request failed: ${response.status}`);
        }
        return data;
    } finally {
        clearTimeout(timer);
    }
}

// UI elements
const $ = (sel) => document.querySelector(sel);
const statusDiv = $("#status");
const recordBtn = $("#recordToggle");
const botPlayer = $("#botPlayer");
const llmText = $("#llmText");
const llmTextSection = $("#llmTextSection");
const chatMessages = $("#chatMessages");

// UI functions
function setStatus(msg, isError = false) {
    if (!statusDiv) return;
    statusDiv.textContent = msg || "";
    statusDiv.classList.toggle("hidden", !msg);
    statusDiv.classList.toggle("error", !!isError);
}

function setRecordingUI(recording) {
    if (!recordBtn) return;
    recordBtn.classList.toggle("recording", recording);
    const label = recordBtn.querySelector(".micLabel");
    if (label) label.textContent = recording ? "Stop Recording" : "Start Recording";
}

function renderHistory(history) {
    if (!chatMessages) return;
    chatMessages.innerHTML = "";
    (history || []).forEach(msg => {
        const div = document.createElement("div");
        div.className = "msg " + (msg.role || "");
        const emoji = msg.role === "user" ? "🧑" : "🤖";
        div.textContent = `${emoji} ${msg.role}: ${msg.content}`;
        chatMessages.appendChild(div);
    });
}

// Recording state
const STATE = { IDLE: "idle", RECORDING: "recording", PROCESSING: "processing", PLAYING: "playing" };
let appState = STATE.IDLE;
let mediaRecorder = null;
let audioChunks = [];

// Recording functions
async function startRecording() {
    if (appState !== STATE.IDLE) return;
    
    setStatus("Listening…");
    appState = STATE.RECORDING;
    setRecordingUI(true);
    
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];
        
        mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = e => {
            if (e.data.size > 0) audioChunks.push(e.data);
        };
        
        mediaRecorder.onstop = () => {
            stream.getTracks().forEach(track => track.stop());
            sendToAgent();
        };
        
        mediaRecorder.start();
    } catch (error) {
        appState = STATE.IDLE;
        setRecordingUI(false);
        setStatus("Microphone access denied", true);
    }
}

function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        setStatus("Processing…");
        appState = STATE.PROCESSING;
        setRecordingUI(false);
        mediaRecorder.stop();
    }
}

// Main agent pipeline
async function sendToAgent() {
    try {
        const formData = new FormData();
        const audioBlob = new Blob(audioChunks, { type: mediaRecorder?.mimeType || "audio/webm" });
        
        formData.append("file", audioBlob, `recording_${Date.now()}.webm`);
        formData.append("web_search", $("#webSearchToggle")?.checked ? "true" : "false");  // 🆕 ADD WEB SEARCH FLAG
        formData.append("concise", "false");
        
        const data = await apiCall(`/agent/chat/${SESSION_ID}`, {
            method: "POST",
            body: formData
        });
        
        // Update UI
        if (data.history) renderHistory(data.history);
        
        if (data.llm_text && llmText && llmTextSection) {
            llmText.textContent = data.llm_text;
            llmTextSection.classList.remove("hidden");
        }
        
        // Play audio
        if (data.audio_url) {
            appState = STATE.PLAYING;
            setStatus("Speaking…");
            botPlayer.src = data.audio_url;
            
            try {
                await botPlayer.play();
                botPlayer.onended = () => {
                    appState = STATE.IDLE;
                    setStatus("Ready");
                    startRecording(); // Auto-continue
                };
            } catch {
                appState = STATE.IDLE;
                setStatus("Ready");
            }
        } else {
            appState = STATE.IDLE;
            setStatus("No audio returned", true);
        }
        
    } catch (error) {
        appState = STATE.IDLE;
        setStatus(error.message, true);
    }
}

// Event listeners
if (recordBtn) {
    recordBtn.addEventListener("click", () => {
        if (appState === STATE.IDLE) startRecording();
        else if (appState === STATE.RECORDING) stopRecording();
    });
}

// Configuration
const configDialog = $("#configDialog");
const configBtn = $("#configBtn");

if (configBtn) configBtn.addEventListener("click", () => configDialog.showModal());

$("#closeCfg")?.addEventListener("click", () => configDialog.close());

$("#saveCfg")?.addEventListener("click", async () => {
    const config = {
        murf: $("#cfgMurf")?.value?.trim() || "",
        aai: $("#cfgAAI")?.value?.trim() || "",
        gemini: $("#cfgGemini")?.value?.trim() || "",
        weather: $("#cfgWeather")?.value?.trim() || "",
        search: $("#cfgSearch")?.value?.trim() || "",        // 🆕 ADD SEARCH KEY
        persona: $("#cfgPersona")?.value || "neutral"
    };
    
    try {
        await apiCall(`/config/${SESSION_ID}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(config)
        });
        
        const status = $("#cfgStatus");
        if (status) {
            status.textContent = "✅ Saved";
            status.classList.remove("hidden");
            setTimeout(() => status.classList.add("hidden"), 1500);
        }
    } catch (error) {
        const status = $("#cfgStatus");
        if (status) {
            status.textContent = "❌ " + error.message;
            status.classList.remove("hidden");
        }
    }
});


// Reset session
$("#resetSessionBtn")?.addEventListener("click", () => {
    const url = new URL(window.location.href);
    url.searchParams.delete("sessionId");
    history.replaceState(null, "", url.toString());
    location.reload();
});

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    setStatus("Ready to start");
});
