"use client";

import { useEffect, useRef, useState } from "react";
import { API_BASE_URL } from "@/lib/config";

type SavedTake = { blob: Blob; filename: string; duration: number; mimeType: string; savedAt: number };
type DonorCandidate = { ledger_id: number; ledger_name: string; contact_person?: string | null; mobile?: string | null; score: number; method: string };
type RecordingSummary = {
  recording_id: string; event_id: string; original_filename: string; size: number;
  progress_status: string; background_job_status: string; uploaded_at: string;
  transcript?: string | null;
  extracted_json?: { name?: string; event?: string; amount?: number; amount_type?: string } | null;
  matching_candidates?: DonorCandidate[] | null;
  last_error?: string | null;
};
type Phase = "ready" | "recording" | "paused" | "review" | "uploading" | "uploaded";
const DB_NAME = "aadeshsmart-audio";
const STORE = "pending-recordings";

function openAudioDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
async function saveTake(take: SavedTake) {
  const db = await openAudioDb();
  await new Promise<void>((resolve, reject) => { const tx = db.transaction(STORE, "readwrite"); tx.objectStore(STORE).put(take, "latest"); tx.oncomplete = () => resolve(); tx.onerror = () => reject(tx.error); });
  db.close();
}
async function loadTake(): Promise<SavedTake | null> {
  const db = await openAudioDb();
  const value = await new Promise<SavedTake | null>((resolve, reject) => { const req = db.transaction(STORE).objectStore(STORE).get("latest"); req.onsuccess = () => resolve(req.result || null); req.onerror = () => reject(req.error); });
  db.close(); return value;
}
async function clearTake() {
  const db = await openAudioDb();
  await new Promise<void>((resolve, reject) => { const tx = db.transaction(STORE, "readwrite"); tx.objectStore(STORE).delete("latest"); tx.oncomplete = () => resolve(); tx.onerror = () => reject(tx.error); });
  db.close();
}

const mimeChoices = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/aac", "audio/ogg;codecs=opus", "audio/ogg"];
function supportedMime() { return typeof MediaRecorder !== "undefined" ? mimeChoices.find((type) => MediaRecorder.isTypeSupported(type)) || "" : ""; }
function uploadMime(type: string) { return (type.split(";")[0] || "application/octet-stream").trim().toLowerCase(); }
function formatTime(seconds: number) { return `${Math.floor(seconds / 60).toString().padStart(2, "0")}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`; }
function extension(type: string) { return type.includes("mp4") || type.includes("aac") ? "m4a" : type.includes("ogg") ? "ogg" : "webm"; }
function stageLabel(status: string) {
  const labels: Record<string, string> = { uploaded: "Uploaded", transcribing: "Transcribing audio", transcribed: "Transcription completed", extracting: "Extracting details", extracted: "Extraction completed", matching: "Finding donor matches", matched: "Matching completed" };
  return labels[status] || "Processing";
}
function processingLabel(recording: RecordingSummary) {
  if (recording.background_job_status === "failed") {
    const failures: Record<string, string> = { uploaded: "Transcription failed", transcribing: "Transcription failed", transcribed: "Extraction failed", extracting: "Extraction failed", extracted: "Processing failed after extraction", matching: "Donor matching failed", matched: "Finalization failed" };
    return failures[recording.progress_status] || "Processing failed";
  }
  if (recording.background_job_status === "success") return stageLabel(recording.progress_status);
  if (recording.background_job_status === "not_started") return "Uploaded";
  return stageLabel(recording.progress_status);
}
function amountTypeLabel(value?: string) { return value === "man" ? "Man" : value === "rupees" ? "Rupees" : "—"; }
function matchingMessage(recording: RecordingSummary) {
  if (recording.matching_candidates?.length) return "";
  if (recording.progress_status === "matching" && recording.background_job_status === "failed") return "Donor matching failed.";
  if (recording.progress_status === "matching" && recording.background_job_status === "in_progress") return "Finding donor matches…";
  if (recording.background_job_status === "success" && recording.progress_status === "matched") return "No matching donor found.";
  if (recording.progress_status === "matched") return "Matching completed.";
  if (recording.progress_status === "extracted") return "Donor matching has not started.";
  if (recording.background_job_status === "failed") return "Donor matching has not started; extraction did not complete.";
  return "Donor matching is waiting for extracted details.";
}

export default function RecordingsPage() {
  const [phase, setPhase] = useState<Phase>("ready");
  const [take, setTake] = useState<SavedTake | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [recordings, setRecordings] = useState<RecordingSummary[]>([]);
  const [listError, setListError] = useState("");
  const [retryingIds, setRetryingIds] = useState<string[]>([]);
  const [retryErrors, setRetryErrors] = useState<Record<string, string>>({});
  const [restored, setRestored] = useState(false);
  const [playbackUrl, setPlaybackUrl] = useState("");
  const [micSupported, setMicSupported] = useState(false);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  useEffect(() => { let active = true; loadTake().then((saved) => { if (active && saved) { setTake(saved); setElapsed(saved.duration); setPhase("review"); setRestored(true); } }).catch(() => { if (active) setError("Saved audio could not be restored from this browser."); }); return () => { active = false; }; }, []);
  useEffect(() => { setMicSupported(Boolean(navigator.mediaDevices && typeof MediaRecorder !== "undefined")); }, []);
  async function refreshRecordings() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/recordings`);
      if (!response.ok) throw new Error("Could not load recordings");
      setRecordings(await response.json()); setListError("");
    } catch { setListError("Confirmed recordings could not be loaded. Check your connection and refresh."); }
  }
  async function retryRecording(recordingId: string) {
    setRetryErrors((current) => ({ ...current, [recordingId]: "" }));
    setRetryingIds((current) => current.includes(recordingId) ? current : [...current, recordingId]);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/recordings/${recordingId}/retry`, { method: "POST" });
      if (!response.ok) {
        let message = "Could not retry processing. Please try again.";
        try { const body = await response.json(); if (typeof body.detail === "string") message = body.detail; } catch { /* use default */ }
        throw new Error(message);
      }
      await refreshRecordings();
    } catch (cause) {
      setRetryErrors((current) => ({ ...current, [recordingId]: cause instanceof Error ? cause.message : "Could not retry processing. Please try again." }));
    } finally {
      setRetryingIds((current) => current.filter((id) => id !== recordingId));
    }
  }
  useEffect(() => {
    void refreshRecordings();
    const interval = window.setInterval(() => { void refreshRecordings(); }, 5000);
    return () => window.clearInterval(interval);
  }, []);
  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); streamRef.current?.getTracks().forEach((track) => track.stop()); }, []);
  useEffect(() => { if (!take) { setPlaybackUrl(""); return; } const url = URL.createObjectURL(take.blob); setPlaybackUrl(url); return () => URL.revokeObjectURL(url); }, [take]);

  async function startRecording() {
    setError(""); setElapsed(0);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") { setError("Audio recording is not supported in this browser. Try a current Safari or Chrome browser over HTTPS."); return; }
    const mimeType = supportedMime();
    if (!mimeType) { setError("This browser does not support a compatible audio recording format."); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const recorder = new MediaRecorder(stream, { mimeType });
      recorderRef.current = recorder; chunksRef.current = [];
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onerror = () => setError("Recording stopped because the microphone reported an error.");
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop()); streamRef.current = null;
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || mimeType });
        const duration = Math.max(1, Math.floor((Date.now() - startedAtRef.current) / 1000));
        const saved = { blob, filename: `event-recording-${Date.now()}.${extension(blob.type)}`, duration, mimeType: blob.type || mimeType, savedAt: Date.now() };
        setElapsed(duration); setTake(saved); setPhase("review");
        try { await saveTake(saved); } catch { setError("Recording is ready, but this browser could not save a recovery copy. Keep this page open until upload succeeds."); }
      };
      startedAtRef.current = Date.now(); recorder.start(1000); setPhase("recording");
      timerRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000)), 500);
    } catch (cause) {
      const name = cause instanceof DOMException ? cause.name : "";
      setError(name === "NotAllowedError" || name === "SecurityError" ? "Microphone access was blocked. Allow microphone access in your browser settings and try again." : "Could not start the microphone. Check that it is connected and available.");
    }
  }
  function stopRecording() { if (timerRef.current) clearInterval(timerRef.current); timerRef.current = null; if (recorderRef.current && recorderRef.current.state !== "inactive") recorderRef.current.stop(); }
  function togglePause() {
    const recorder = recorderRef.current;
    if (!recorder) return;
    if (recorder.state === "recording" && recorder.pause) {
      recorder.pause();
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = null;
      setPhase("paused");
    } else if (recorder.state === "paused" && recorder.resume) {
      recorder.resume();
      startedAtRef.current = Date.now() - elapsed * 1000;
      timerRef.current = setInterval(() => setElapsed(Math.floor((Date.now() - startedAtRef.current) / 1000)), 500);
      setPhase("recording");
    }
  }
  async function discard() { if (phase === "recording") { recorderRef.current?.stop(); } setTake(null); setPhase("ready"); setElapsed(0); setError(""); try { await clearTake(); } catch { /* local cleanup is best effort */ } }
  async function upload() {
    if (!take) return;
    setError(""); setProgress(0); setPhase("uploading");
    const form = new FormData(); form.append("event_id", `event-${crypto.randomUUID()}`); form.append("operator_identifier", `volunteer-${crypto.randomUUID().slice(0, 8)}`);
    // MediaRecorder commonly reports a codec parameter (for example, audio/webm;codecs=opus).
    // The API validates the base media type and the filename extension, so send that base type.
    const file = new File([take.blob], take.filename, { type: uploadMime(take.mimeType || take.blob.type) });
    form.append("file", file, take.filename);
    const xhr = new XMLHttpRequest(); xhr.open("POST", `${API_BASE_URL}/api/v1/recordings`);
    xhr.upload.onprogress = (event) => { if (event.lengthComputable) setProgress(Math.round((event.loaded / event.total) * 100)); };
    xhr.onerror = () => { setError("Upload failed. Your recording is saved on this device; check your connection and retry."); setPhase("review"); };
    xhr.onabort = () => { setError("Upload was interrupted. Your recording is saved on this device; retry when ready."); setPhase("review"); };
    xhr.onload = async () => {
      if (xhr.status < 200 || xhr.status >= 300) { let message = "The server could not accept this recording."; try { const body = JSON.parse(xhr.responseText); message = typeof body.detail === "string" ? body.detail : message; } catch { /* use default */ } setError(message); setPhase("review"); return; }
      try { JSON.parse(xhr.responseText); await clearTake(); setTake(null); setElapsed(0); setPhase("uploaded"); setProgress(100); setRestored(false); void refreshRecordings(); window.setTimeout(() => setPhase((current) => current === "uploaded" ? "ready" : current), 1500); } catch { setError("The recording uploaded, but the server response could not be read. Check the recordings list before retrying."); setPhase("review"); }
    };
    xhr.send(form);
  }

  const processedCount = recordings.filter((recording) => recording.background_job_status === "success").length;
  const needsAttentionCount = recordings.filter((recording) => recording.background_job_status === "failed").length;
  return <main className="workspace-page">
    <header className="page-heading">
      <div><span className="eyebrow">Shree Pantnagar Sangh</span>
      <p>શ્રી ઘાટકોપર જૈન શ્વે. મુ તપા. સંઘ, ચિંતામણી પાર્શ્વનાથ જિનાલય પંતનગર  </p>
      <h2>Aadesh Announcements </h2>
      </div>
      <div className="workspace-stats" aria-label="Recording summary"><div><strong>{recordings.length}</strong><span>Listed</span></div><div><strong>{processedCount}</strong><span>Processed</span></div><div><strong>{needsAttentionCount}</strong><span>Needs attention</span></div></div>
    </header>
    <section className="recordings-section" aria-labelledby="recordings-title">
      <div className="section-title"><div><h2 id="recordings-title">Recent Announcements</h2><p>Transcripts, extracted details and donor matches.</p></div><span className="record-count">{recordings.length}</span></div>
      {listError && <p className="list-error" role="alert">{listError}</p>}
      {!listError && recordings.length === 0 ? <div className="recordings-empty">Your recordings will appear here after upload.</div> : <div className="recordings-list">{recordings.map((item, index) => {
        const candidates = item.matching_candidates || [];
        const extracted = item.extracted_json;
        const failed = item.background_job_status === "failed";
        const status = processingLabel(item);
        const retrying = retryingIds.includes(item.recording_id);
        const extractionFailure = failed && ["transcribed", "extracting"].includes(item.progress_status);
        const transcriptionFailure = failed && ["uploaded", "transcribing"].includes(item.progress_status);
        return <article className="recording-card" key={item.recording_id}>
          <div className="recording-card-top"><div className="recording-identity"><span>RECORDING {String(recordings.length - index).padStart(2, "0")}</span><strong>#{item.recording_id.slice(0, 8)}</strong><time dateTime={item.uploaded_at}>{new Date(item.uploaded_at).toLocaleString()}</time></div><div className="recording-card-actions"><span className={`status-badge ${failed ? "status-failed" : item.background_job_status === "success" ? "status-success" : ""}`}>{status}</span>{failed && <button className="retry-button" onClick={() => void retryRecording(item.recording_id)} disabled={retrying}>{retrying ? "Retrying…" : "Retry"}</button>}</div></div>
          {failed && item.last_error && <p className="processing-error"><strong>{status}.</strong> {item.last_error}</p>}
          <section className="recording-details" aria-label="Extracted information">
            <div className="detail-field"><span>Donor</span><strong>{extracted?.name || (transcriptionFailure ? "Transcription failed" : extractionFailure ? "Extraction failed" : "Pending")}</strong></div>
            <div className="detail-field"><span>Amount</span><strong>{extracted?.amount != null ? `${extracted.amount.toLocaleString()}${extracted.amount_type ? ` ${amountTypeLabel(extracted.amount_type)}` : ""}` : (extractionFailure || transcriptionFailure) ? "Unavailable" : "Pending"}</strong></div>
            <div className="detail-field"><span>Event / Seva</span><strong>{extracted?.event || (extractionFailure || transcriptionFailure ? "Unavailable" : "Pending")}</strong></div>
          </section>
          <section className="matching-section" aria-label="Donor matching"><div className="subsection-heading"><strong>Donor matches</strong>{candidates.length > 0 && <span>{candidates.length} candidates</span>}</div>{candidates.length > 0 ? <div className="candidate-list">{candidates.map((candidate) => <div className="candidate-row" key={`${item.recording_id}-${candidate.ledger_id}`}><div><strong>{candidate.ledger_name}</strong><span>{candidate.contact_person || "Contact unavailable"}{candidate.mobile ? ` · ${candidate.mobile}` : ""}</span></div><span className="match-score">{Math.round(candidate.score * 100)}%</span></div>)}</div> : <p className="matching-message">{matchingMessage(item)}</p>}</section>
          {item.transcript?.trim() ? <details className="transcript-details"><summary>Gujarati transcript</summary><p lang="gu">{item.transcript}</p></details> : <div className="transcript-pending"><span>Gujarati transcript</span><p>{transcriptionFailure ? "Transcription could not be completed." : "Transcript will appear when transcription is complete."}</p></div>}
          {retryErrors[item.recording_id] && <p className="retry-error" role="alert">{retryErrors[item.recording_id]}</p>}
        </article>;
      })}</div>}
    </section>
    <section className={`recording-dock ${phase !== "ready" ? "is-expanded" : "is-compact"}`} aria-labelledby="record-title">
      <div className="dock-header"><div><span className={`mic-indicator ${micSupported ? "available" : "unavailable"}`} />{micSupported ? "Microphone ready" : "Microphone unavailable"}</div><div><span className={`dock-status ${phase === "recording" ? "live" : phase === "paused" ? "paused" : ""}`}>{phase === "ready" ? "Ready" : phase === "recording" ? "Recording" : phase === "paused" ? "Paused" : phase === "review" ? "Review" : phase === "uploading" ? "Uploading" : "Uploaded"}</span><span className="dock-timer" aria-live="polite">{formatTime(elapsed)}</span></div></div>
      {phase !== "ready" && <div className={`dock-meter ${phase === "recording" ? "active" : ""}`}><span /></div>}
      {(phase === "recording" || phase === "paused") && <div className="dock-actions">{phase === "recording" ? <button className="dock-secondary" onClick={togglePause}>Ⅱ Pause</button> : <button className="dock-secondary" onClick={togglePause}>▶ Resume</button>}<button className="dock-stop" onClick={stopRecording}>■ Stop &amp; preview</button></div>}
      {phase === "ready" && <button className="dock-record" onClick={startRecording} disabled={!micSupported}><span>●</span> Record announcement</button>}
      {phase === "review" && take && <div className="dock-review"><audio controls preload="metadata" src={playbackUrl} aria-label="Recording preview"/><div className="dock-review-meta">{take.filename} · {formatTime(take.duration)} · {Math.max(1, Math.round(take.blob.size / 1024))} KB</div>{restored && <span className="saved-note">Recovered from this device</span>}<div className="dock-actions"><button className="dock-secondary" onClick={discard}>Discard</button><button className="dock-record" onClick={upload}>Confirm &amp; upload</button></div></div>}
      {phase === "uploading" && <div className="dock-upload"><progress value={progress} max="100" aria-label="Upload progress"/><span>{progress}% uploaded</span></div>}
      {phase === "uploaded" && <p className="dock-success" role="status">✓ Recording uploaded and added to recent recordings.</p>}
      {error && <p role="alert" className="recorder-error">{error}</p>}
    </section>
  </main>;
}
