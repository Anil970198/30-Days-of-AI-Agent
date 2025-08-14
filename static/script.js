// function ensureSessionId() {
//   const url = new URL(window.location.href);
//   let sid = url.searchParams.get("sessionId");
//   if (!sid) {
//     sid = (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now());
//     url.searchParams.set("sessionId", sid);
//     history.replaceState(null, "", url.toString());
//   }
//   return sid;
// }
// ensureSessionId(); // do it once on load

// // ---- Day 11 helpers ----

// // Unified fetch with timeout + JSON parse + non-OK handling
// async function safeFetch(url, opts = {}, label = "api", timeoutMs = 25000) {
//   const controller = new AbortController();
//   const timer = setTimeout(() => controller.abort(), timeoutMs);
//   try {
//     const res = await fetch(url, { ...opts, signal: controller.signal });
//     let data = {};
//     try { data = await res.json(); } catch {}
//     if (!res.ok) {
//       const msg = data?.error || data?.detail?.error || data?.detail || `Request failed: ${res.status}`;
//       throw new Error(`${label}: ${msg}`);
//     }
//     return data;
//   } catch (e) {
//     throw new Error(`${label}: ${e.message}`);
//   } finally {
//     clearTimeout(timer);
//   }
// }

// // Speak a local fallback without using any API
// function speakFallback(text) {
//   const line = text || "I'm having trouble connecting right now";
//   if ("speechSynthesis" in window) {
//     try {
//       const u = new SpeechSynthesisUtterance(line);
//       window.speechSynthesis.speak(u);
//       return;
//     } catch {}
//   }
//   try { new Audio("/static/fallback_im_trouble.mp3").play(); } catch {}
// }

// // Add x-debug-fail header if URL has ?fail=stt|llm|tts|agent
// function withDebugHeaders(opts = {}) {
//   const params = new URLSearchParams(location.search);
//   const fail = params.get("fail");
//   const headers = { ...(opts.headers || {}) };
//   if (fail) headers["x-debug-fail"] = fail;
//   return { ...opts, headers };
// }


// async function generateAudio() {
//   clearUIState();
//   const text = document.getElementById("inputText").value;
//   const audioPlayer = document.getElementById("audioPlayer");
//   const playerSection = document.getElementById("playerSection");
//   const errorDiv = document.getElementById("error");

//   if (!text.trim()) {
//     errorDiv.textContent = "Please enter some text.";
//     errorDiv.classList.remove("hidden");
//     playerSection.classList.add("hidden");
//     return;
//   }

//   try {
//     const data = await safeFetch(
//       "/generate-audio",
//       withDebugHeaders({
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         body: JSON.stringify({ text })
//       }),
//       "TTS (generate)"
//     );

//     if (data.audio_url) {
//       audioPlayer.src = data.audio_url;
//       playerSection.classList.remove("hidden");
//       errorDiv.classList.add("hidden");
//     } else {
//       errorDiv.textContent = "TTS (generate): No audio returned";
//       errorDiv.classList.remove("hidden");
//       playerSection.classList.add("hidden");
//       speakFallback();
//     }
//   } catch (err) {
//     errorDiv.textContent = err.message;
//     errorDiv.classList.remove("hidden");
//     playerSection.classList.add("hidden");
//     speakFallback();
//   }
// }


// // Echo Bot
// let mediaRecorder;
// let audioChunks = [];

// function startRecording() {
//   clearUIState();
//   const startBtn = document.querySelector('button[onclick="startRecording()"]');
//   const stopBtn  = document.getElementById("stopBtn");
//   document.getElementById("echoError").classList.add("hidden");

//   // disable Start, enable Stop to prevent double recording
//   if (startBtn) startBtn.disabled = true;
//   if (stopBtn)  stopBtn.disabled  = false;

//   navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
//     mediaRecorder = new MediaRecorder(stream);
//     audioChunks = [];

//     mediaRecorder.ondataavailable = e => {
//       if (e.data.size > 0) audioChunks.push(e.data);
//     };

//     mediaRecorder.onstop = () => {
//       const audioBlob = new Blob(audioChunks, { type: mediaRecorder.mimeType || "audio/webm" });
//       const audioUrl = URL.createObjectURL(audioBlob);
//       document.getElementById("echoPlayer").src = audioUrl;
//       document.getElementById("echoSection").classList.remove("hidden");

//       const formData = new FormData();
//       const filename = `recording_${Date.now()}.webm`;
//       formData.append("file", audioBlob, filename);

//       const statusDiv = document.getElementById("echoStatus");
//       statusDiv.textContent = "⬆ Uploading...";
//       statusDiv.classList.remove("hidden");

//       fetch("/upload-audio", {
//         method: "POST",
//         body: formData
//       })
//         .then(res => res.json())
//         .then(data => {
//           if (data.filename) {
//             statusDiv.textContent = `✅ Uploaded: ${data.filename} (${data.size_kb} KB)`;
//           } else {
//             statusDiv.textContent = `❌ Upload failed: ${data.error || "Unknown error"}`;
//           }
//         })
//         .catch(err => {
//           statusDiv.textContent = "❌ Upload failed: " + err.message;
//         })
//         .finally(() => {
//           // ✅ auto-run the Day 9 bot AFTER upload kicks off
//           askBotFromRecording();

//           // re-enable Start, disable Stop
//           if (startBtn) startBtn.disabled = false;
//           if (stopBtn)  stopBtn.disabled  = true;
//         });
//     };

//     mediaRecorder.start();
//   }).catch(err => {
//     const echoError = document.getElementById("echoError");
//     echoError.textContent = "🎙 Microphone access denied.";
//     echoError.classList.remove("hidden");

//     // make sure buttons are in a sane state on failure
//     const startBtn = document.querySelector('button[onclick="startRecording()"]');
//     const stopBtn  = document.getElementById("stopBtn");
//     if (startBtn) startBtn.disabled = false;
//     if (stopBtn)  stopBtn.disabled  = true;
//   });
// }

// function stopRecording() {
//   const startBtn = document.querySelector('button[onclick="startRecording()"]');
//   const stopBtn  = document.getElementById("stopBtn");

//   if (mediaRecorder && mediaRecorder.state !== "inactive") {
//     // prevent spam-clicking Stop
//     if (stopBtn) stopBtn.disabled = true;

//     mediaRecorder.stop();

//     // release mic tracks
//     if (mediaRecorder.stream && mediaRecorder.stream.getTracks) {
//       mediaRecorder.stream.getTracks().forEach(track => track.stop());
//     }
//     // DO NOT re-enable Start here — we do it in onstop after upload kicks off
//   } else {
//     // if nothing to stop, ensure Start is enabled
//     if (startBtn) startBtn.disabled = false;
//     if (stopBtn)  stopBtn.disabled  = true;
//   }
// }

// async function transcribeRecording() {
//   if (audioChunks.length === 0) {
//     alert("Please record something first.");
//     return;
//   }

//   const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
//   const formData = new FormData();
//   const filename = `recording_${Date.now()}.webm`;
//   formData.append("file", audioBlob, filename);

//   const transcriptDiv = document.getElementById("transcriptionResult");
//   transcriptDiv.textContent = "🕐 Transcribing...";

//   try {
//     const data = await safeFetch(
//       "/transcribe/file",
//       withDebugHeaders({ method: "POST", body: formData }),
//       "STT"
//     );

//     if (data.transcript) {
//       transcriptDiv.textContent = "📝 " + data.transcript;
//     } else {
//       transcriptDiv.textContent = "❌ STT: No transcript returned";
//       speakFallback();
//     }
//   } catch (err) {
//     transcriptDiv.textContent = "❌ " + err.message;
//     speakFallback();
//   }
// }


// async function echoWithMurf(event) {
//   if (!audioChunks.length) {
//     alert("Please record something first.");
//     return;
//   }

//   const btn = event?.target;
//   if (btn) btn.disabled = true;

//   const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
//   const fd = new FormData();
//   fd.append("file", audioBlob, `recording_${Date.now()}.webm`);

//   const statusDiv = document.getElementById("echoStatus");
//   statusDiv.textContent = "🕐 Transcribing and generating voice...";
//   statusDiv.classList.remove("hidden");

//   try {
//     const data = await safeFetch(
//       "/tts/echo",
//       withDebugHeaders({ method: "POST", body: fd }),
//       "Echo"
//     );

//     if (data.audio_url) {
//       const player = document.getElementById("murfPlayer");
//       player.src = data.audio_url;
//       document.getElementById("murfSection").classList.remove("hidden");

//       const transcriptDiv = document.getElementById("transcriptionResult");
//       if (transcriptDiv) transcriptDiv.textContent = "📝 " + (data.text || "");

//       statusDiv.textContent = "✅ Ready";
//       player.play().catch(() => {});
//     } else {
//       statusDiv.textContent = "❌ Echo: No audio returned";
//       speakFallback();
//     }
//   } catch (e) {
//     statusDiv.textContent = "❌ " + e.message;
//     speakFallback();
//   } finally {
//     if (btn) btn.disabled = false;
//   }
// }


// // helper: play multiple audio files back-to-back in a single <audio>
// async function playSequential(urls, audioEl, onDone) {
//   if (!urls || !urls.length || !audioEl) {
//     if (typeof onDone === "function") onDone();
//     return;
//   }
//   let i = 0;
//   const playNext = () => {
//     if (i >= urls.length) {
//       if (typeof onDone === "function") onDone();
//       return;
//     }
//     audioEl.src = urls[i++];
//     audioEl.play().catch(() => {});
//   };
//   audioEl.onended = playNext;
//   playNext();
// }


// async function askBotFromRecording(event) {
//   if (!audioChunks.length) {
//     alert("Please record something first.");
//     return;
//   }

//   const btn = event?.target;
//   if (btn) btn.disabled = true;

//   const statusDiv = document.getElementById("botStatus");
//   statusDiv.textContent = "🕐 Thinking… (transcribing → LLM → voice)";
//   statusDiv.classList.remove("hidden");

//   try {
//     const sid = ensureSessionId();
//     const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
//     const fd = new FormData();
//     fd.append("file", audioBlob, `recording_${Date.now()}.webm`);

//     const data = await safeFetch(
//       `/agent/chat/${sid}`,
//       withDebugHeaders({ method: "POST", body: fd }),
//       "Agent"
//     );

//     if (data.audio_url || (Array.isArray(data.audio_urls) && data.audio_urls.length)) {
//       const botPlayer = document.getElementById("botPlayer");
//       document.getElementById("botSection").classList.remove("hidden");

//       // show transcript
//       const transcriptDiv = document.getElementById("transcriptionResult");
//       if (transcriptDiv && data.text) transcriptDiv.textContent = "📝 " + data.text;

//       // show assistant text
//       const llmTextEl = document.getElementById("llmText");
//       const llmTextSection = document.getElementById("llmTextSection");
//       const echoStatus = document.getElementById("echoStatus");
//       if (data.llm_text) {
//         if (llmTextEl && llmTextSection) {
//           llmTextEl.textContent = data.llm_text;
//           llmTextSection.classList.remove("hidden");
//         } else if (echoStatus) {
//           echoStatus.textContent = "💬 " + data.llm_text;
//           echoStatus.classList.remove("hidden");
//         }
//       }

//       // render chat history if present
//       if (Array.isArray(data.history)) renderHistory(data.history);

//       const urls = Array.isArray(data.audio_urls) && data.audio_urls.length
//         ? data.audio_urls
//         : [data.audio_url];

//       await playSequential(urls, botPlayer, () => {
//         startRecording(); // 🔁 auto-start mic after playback
//       });

//       statusDiv.textContent = "✅ Reply ready";
//     } else {
//       statusDiv.textContent = "❌ Agent: No audio returned";
//       speakFallback();
//     }
//   } catch (e) {
//     statusDiv.textContent = "❌ " + e.message;
//     speakFallback();
//   } finally {
//     if (btn) btn.disabled = false;
//   }
// }

// function clearUIState() {
//   // Stop any playing audio
//   ["audioPlayer", "echoPlayer", "murfPlayer", "botPlayer"].forEach(id => {
//     const el = document.getElementById(id);
//     if (el) {
//       el.pause?.();
//       el.src = "";
//     }
//   });

//   // Clear all status/error/text areas
//   ["error", "echoError", "echoStatus", "botStatus", "transcriptionResult"].forEach(id => {
//     const el = document.getElementById(id);
//     if (el) {
//       el.textContent = "";
//       el.classList.add("hidden");
//     }
//   });

//   // Clear LLM text section if it exists
//   const llmTextEl = document.getElementById("llmText");
//   if (llmTextEl) llmTextEl.textContent = "";
//   const llmTextSection = document.getElementById("llmTextSection");
//   if (llmTextSection) llmTextSection.classList.add("hidden");

//   // Hide audio sections
//   ["playerSection", "echoSection", "murfSection", "botSection"].forEach(id => {
//     const el = document.getElementById(id);
//     if (el) el.classList.add("hidden");
//   });
// }

// function renderHistory(items) {
//   const box = document.getElementById("chatMessages");
//   if (!box) return;
//   box.innerHTML = "";
//   (items || []).forEach(m => {
//     const div = document.createElement("div");
//     div.className = "msg " + (m.role || ""); // <-- add class for styling
//     const who = m.role === "user" ? "🧑" : "🤖";
//     div.textContent = `${who} ${m.role}: ${m.content}`;
//     box.appendChild(div);
//   });
// }

// document.getElementById("resetSessionBtn")?.addEventListener("click", () => {
//   const url = new URL(window.location.href);
//   url.searchParams.delete("sessionId");
//   history.replaceState(null, "", url.toString());
//   ensureSessionId();
//   renderHistory([]);
// });




// -------------------- Session --------------------
function ensureSessionId() {
  const url = new URL(window.location.href);
  let sid = url.searchParams.get("sessionId");
  if (!sid) {
    sid = (crypto && crypto.randomUUID) ? crypto.randomUUID() : String(Date.now());
    url.searchParams.set("sessionId", sid);
    history.replaceState(null, "", url.toString());
  }
  return sid;
}
ensureSessionId();

// -------------------- Helpers --------------------
async function safeFetch(url, opts = {}, label = "api", timeoutMs = 25000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...opts, signal: controller.signal });
    let data = {};
    try { data = await res.json(); } catch {}
    if (!res.ok) {
      const msg = data?.error || data?.detail?.error || data?.detail || `Request failed: ${res.status}`;
      throw new Error(`${label}: ${msg}`);
    }
    return data;
  } catch (e) {
    throw new Error(`${label}: ${e.message}`);
  } finally {
    clearTimeout(timer);
  }
}

function withDebugHeaders(opts = {}) {
  const params = new URLSearchParams(location.search);
  const fail = params.get("fail");
  const headers = { ...(opts.headers || {}) };
  if (fail) headers["x-debug-fail"] = fail;
  return { ...opts, headers };
}

function speakFallback(text) {
  const line = text || "I'm having trouble connecting right now";
  if ("speechSynthesis" in window) {
    try {
      const u = new SpeechSynthesisUtterance(line);
      window.speechSynthesis.speak(u);
      return;
    } catch {}
  }
  try { new Audio("/static/fallback_im_trouble.mp3").play(); } catch {}
}

function renderHistory(items) {
  const box = document.getElementById("chatMessages");
  if (!box) return;
  box.innerHTML = "";
  (items || []).forEach(m => {
    const div = document.createElement("div");
    div.className = "msg " + (m.role || "");
    const who = m.role === "user" ? "🧑" : "🤖";
    div.textContent = `${who} ${m.role}: ${m.content}`;
    box.appendChild(div);
  });
}

async function playSequential(urls, audioEl, onDone) {
  if (!urls || !urls.length || !audioEl) {
    if (typeof onDone === "function") onDone();
    return;
  }
  let i = 0;
  const playNext = () => {
    if (i >= urls.length) {
      if (typeof onDone === "function") onDone();
      return;
    }
    audioEl.src = urls[i++];
    audioEl.play().catch(() => {});
  };
  audioEl.onended = playNext;
  playNext();
}

// -------------------- State --------------------
const STATE = { IDLE: "idle", RECORDING: "recording", PROCESSING: "processing", PLAYING: "playing" };
let appState = STATE.IDLE;

let mediaRecorder = null;
let audioChunks = [];

// Elements
const recordToggle = document.getElementById("recordToggle");
const statusDiv = document.getElementById("status");
const botPlayer = document.getElementById("botPlayer");
const llmText = document.getElementById("llmText");
const llmTextSection = document.getElementById("llmTextSection");

// -------------------- UI updates --------------------
function setStatus(msg, isError = false) {
  if (!statusDiv) return;
  statusDiv.textContent = msg || "";
  statusDiv.classList.toggle("hidden", !msg);
  statusDiv.classList.toggle("error", !!isError);
}

function setRecordingUI(on) {
  recordToggle.classList.toggle("recording", !!on);
  const label = recordToggle.querySelector(".micLabel");
  if (label) label.textContent = on ? "Stop Recording" : "Start Recording";
}

function resetUI() {
  setStatus("");
  if (llmText) llmText.textContent = "";
  if (llmTextSection) llmTextSection.classList.add("hidden");
  if (botPlayer) {
    botPlayer.pause?.();
    botPlayer.src = "";
    botPlayer.classList.add("hidden");
  }
}

// -------------------- Recording --------------------
async function startRecording() {
  resetUI();
  setStatus("Listening…", false);
  appState = STATE.RECORDING;
  setRecordingUI(true);

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream);

    mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
    mediaRecorder.onstop = () => {
      stream.getTracks().forEach(t => t.stop());
      sendToAgent();
    };

    mediaRecorder.start();
  } catch (e) {
    appState = STATE.IDLE;
    setRecordingUI(false);
    setStatus("Microphone access denied.", true);
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    setStatus("Processing…", false);
    appState = STATE.PROCESSING;
    setRecordingUI(false);
    mediaRecorder.stop();
  }
}

// -------------------- Agent Pipeline --------------------
async function sendToAgent() {
  try {
    const sid = ensureSessionId();
    const fd = new FormData();
    const audioBlob = new Blob(audioChunks, { type: mediaRecorder?.mimeType || "audio/webm" });
    fd.append("file", audioBlob, `recording_${Date.now()}.webm`);

    const data = await safeFetch(
      `/agent/chat/${sid}`,
      withDebugHeaders({ method: "POST", body: fd }),
      "Agent"
    );

    // history
    if (Array.isArray(data.history)) renderHistory(data.history);

    // assistant text
    if (data.llm_text && llmText && llmTextSection) {
      llmText.textContent = data.llm_text;
      llmTextSection.classList.remove("hidden");
    }

    // audio
    const urls = Array.isArray(data.audio_urls) && data.audio_urls.length
      ? data.audio_urls
      : (data.audio_url ? [data.audio_url] : []);

    if (urls.length) {
      appState = STATE.PLAYING;
      setStatus("Speaking…");
      botPlayer.classList.remove("hidden");
      await playSequential(urls, botPlayer, () => {
        // Auto-loop: return to idle and re-arm mic
        appState = STATE.IDLE;
        setStatus("Ready");
        startRecording(); // auto-start next turn
      });
    } else {
      appState = STATE.IDLE;
      setStatus("No audio returned.", true);
      speakFallback();
    }
  } catch (e) {
    appState = STATE.IDLE;
    setStatus(e.message, true);
    speakFallback();
  }
}

// -------------------- Toggle Control --------------------
recordToggle.addEventListener("click", () => {
  if (appState === STATE.IDLE) return startRecording();
  if (appState === STATE.RECORDING) return stopRecording();
  // If processing/playing, ignore tap to avoid races
});

// -------------------- Reset Session --------------------
document.getElementById("resetSessionBtn")?.addEventListener("click", () => {
  const url = new URL(window.location.href);
  url.searchParams.delete("sessionId");
  history.replaceState(null, "", url.toString());
  ensureSessionId();
  renderHistory([]);
  resetUI();
  appState = STATE.IDLE;
  setRecordingUI(false);
  setStatus("Session reset.");
});
