"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

type Property = {
  id: string;
  external_ref: string;
  title: string;
  address_display: string;
  price: string;
  currency: string;
  bedrooms: number;
  area_m2: number;
  amenities: string;
};

type Message = { role: "assistant" | "caller"; text: string };
type Slot = { id: string; starts_at: string; ends_at: string };
type ActiveCall = { id: string; lead_id: string };

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const realtimeUrl = `${apiUrl.replace(/^http/, "ws")}/ws/qwen-realtime`;

function encodePcm(samples: Float32Array, inputRate: number): string {
  const ratio = inputRate / 16000;
  const length = Math.floor(samples.length / ratio);
  const pcm = new Int16Array(length);
  for (let index = 0; index < length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[Math.floor(index * ratio)]));
    pcm[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  const bytes = new Uint8Array(pcm.buffer);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

export default function Home() {
  const sessionId = useMemo(() => crypto.randomUUID(), []);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      text: "Hello, I’m Horizon Homes’ virtual assistant. This is a simulated AI conversation. Are you looking to rent or buy, and in which city?",
    },
  ]);
  const [properties, setProperties] = useState<Property[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Property | null>(null);
  const [slots, setSlots] = useState<Slot[]>([]);
  const [selectedSlot, setSelectedSlot] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [bookingStatus, setBookingStatus] = useState("");
  const [voiceStatus, setVoiceStatus] = useState<"idle" | "connecting" | "listening">(
    "idle",
  );
  const [liveCallerTranscript, setLiveCallerTranscript] = useState("");
  const [liveTranscript, setLiveTranscript] = useState("");
  const socketRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const inputContextRef = useRef<AudioContext | null>(null);
  const outputContextRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const transcriptRef = useRef("");
  const playbackTimeRef = useRef(0);
  const playbackSourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const callRef = useRef<ActiveCall | null>(null);
  const responseActiveRef = useRef(false);
  const speechStoppedAtRef = useRef<number | null>(null);
  const assistantLatencyRef = useRef<number | null>(null);

  async function ensureCall(mode: "browser_text" | "browser_voice") {
    if (callRef.current) return callRef.current;
    const response = await fetch(`${apiUrl}/api/calls`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: `${sessionId}-${Date.now()}`, mode }),
    });
    if (!response.ok) throw new Error(`Call API returned ${response.status}`);
    const call = (await response.json()) as ActiveCall;
    callRef.current = call;
    return call;
  }

  async function logTurn(
    speaker: "caller" | "assistant",
    text: string,
    options: { interrupted?: boolean; latency_ms?: number | null } = {},
  ) {
    const call = callRef.current;
    if (!call || !text.trim()) return;
    await fetch(`${apiUrl}/api/calls/${call.id}/turns`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ speaker, text: text.trim(), ...options }),
    });
  }

  function stopPlayback() {
    for (const source of playbackSourcesRef.current) {
      try {
        source.stop();
      } catch {
        // A source that already ended needs no further action.
      }
    }
    playbackSourcesRef.current.clear();
    playbackTimeRef.current = outputContextRef.current?.currentTime ?? 0;
  }

  function stopVoice() {
    stopPlayback();
    processorRef.current?.disconnect();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    void inputContextRef.current?.close();
    void outputContextRef.current?.close();
    socketRef.current?.close();
    processorRef.current = null;
    streamRef.current = null;
    inputContextRef.current = null;
    outputContextRef.current = null;
    socketRef.current = null;
    playbackTimeRef.current = 0;
    setLiveCallerTranscript("");
    setLiveTranscript("");
    const completedCall = callRef.current;
    if (completedCall) {
      void fetch(`${apiUrl}/api/calls/${completedCall.id}/complete`, { method: "POST" });
      callRef.current = null;
    }
    setVoiceStatus("idle");
  }

  // Cleanup must use the current media/socket refs and run only when this page unmounts.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => () => stopVoice(), []);

  function playPcm(base64Audio: string) {
    const context = outputContextRef.current;
    if (!context) return;
    const binary = atob(base64Audio);
    const samples = new Float32Array(Math.floor(binary.length / 2));
    for (let index = 0; index < samples.length; index += 1) {
      const low = binary.charCodeAt(index * 2);
      const high = binary.charCodeAt(index * 2 + 1);
      const value = (high << 8) | low;
      samples[index] = (value >= 0x8000 ? value - 0x10000 : value) / 0x8000;
    }
    const buffer = context.createBuffer(1, samples.length, 24000);
    buffer.copyToChannel(samples, 0);
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    playbackSourcesRef.current.add(source);
    source.onended = () => playbackSourcesRef.current.delete(source);
    const startsAt = Math.max(context.currentTime + 0.03, playbackTimeRef.current);
    source.start(startsAt);
    playbackTimeRef.current = startsAt + buffer.duration;
  }

  async function beginMicrophone(socket: WebSocket) {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    const context = new AudioContext();
    const outputContext = new AudioContext({ sampleRate: 24000 });
    const source = context.createMediaStreamSource(stream);
    const processor = context.createScriptProcessor(1024, 1, 1);
    processor.onaudioprocess = (event) => {
      if (socket.readyState !== WebSocket.OPEN) return;
      socket.send(
        JSON.stringify({
          type: "input_audio_buffer.append",
          audio: encodePcm(event.inputBuffer.getChannelData(0), context.sampleRate),
        }),
      );
    };
    source.connect(processor);
    processor.connect(context.destination);
    streamRef.current = stream;
    inputContextRef.current = context;
    outputContextRef.current = outputContext;
    processorRef.current = processor;
    setVoiceStatus("listening");
  }

  async function startVoice() {
    setError("");
    setVoiceStatus("connecting");
    let call: ActiveCall;
    try {
      call = await ensureCall("browser_voice");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to create call session");
      setVoiceStatus("idle");
      return;
    }
    const socket = new WebSocket(`${realtimeUrl}?call_id=${encodeURIComponent(call.id)}`);
    socketRef.current = socket;
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data);
      if (event.type === "session.updated") {
        void beginMicrophone(socket).catch((caught) => {
          setError(caught instanceof Error ? caught.message : "Microphone access failed");
          stopVoice();
        });
      } else if (event.type === "response.audio.delta") {
        if (assistantLatencyRef.current === null && speechStoppedAtRef.current !== null) {
          assistantLatencyRef.current = Math.round(
            performance.now() - speechStoppedAtRef.current,
          );
        }
        playPcm(event.delta);
      } else if (event.type === "response.created") {
        responseActiveRef.current = true;
        assistantLatencyRef.current = null;
      } else if (event.type === "input_audio_buffer.speech_stopped") {
        speechStoppedAtRef.current = performance.now();
      } else if (event.type === "input_audio_buffer.speech_started") {
        stopPlayback();
        setLiveCallerTranscript("");
        if (responseActiveRef.current && socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ type: "response.cancel" }));
        }
      } else if (
        event.type === "conversation.item.input_audio_transcription.delta"
      ) {
        setLiveCallerTranscript(`${event.text ?? ""}${event.stash ?? ""}`);
      } else if (event.type === "conversation.item.input_audio_transcription.completed") {
        const callerText = event.transcript ?? event.item?.content?.[0]?.transcript;
        setLiveCallerTranscript("");
        if (callerText) {
          setMessages((current) => [...current, { role: "caller", text: callerText }]);
          void logTurn("caller", callerText);
        }
      } else if (event.type === "conversation.item.input_audio_transcription.failed") {
        setLiveCallerTranscript("");
        setError("Qwen could not transcribe that audio; please try speaking again");
      } else if (event.type === "response.audio_transcript.delta") {
        transcriptRef.current += event.delta;
        setLiveTranscript(transcriptRef.current);
      } else if (event.type === "response.done") {
        if (transcriptRef.current) {
          const completed = transcriptRef.current;
          setMessages((current) => [...current, { role: "assistant", text: completed }]);
          void logTurn("assistant", completed, {
            latency_ms: assistantLatencyRef.current,
            interrupted: event.response?.status === "cancelled",
          });
          transcriptRef.current = "";
          setLiveTranscript("");
        }
        responseActiveRef.current = false;
      } else if (event.type === "proxy.tool_result") {
        if (event.name === "search_properties" && Array.isArray(event.output)) {
          setProperties(event.output);
        } else if (event.name === "book_viewing" && !event.output?.error) {
          setBookingStatus("Viewing confirmed by voice in the local demo.");
        }
      } else if (event.type === "proxy.error" || event.type === "error") {
        setError(event.message ?? event.error?.message ?? "Qwen realtime error");
        stopVoice();
      }
    };
    socket.onerror = () => {
      setError("Unable to connect to the Qwen realtime service");
      stopVoice();
    };
    socket.onclose = () => setVoiceStatus("idle");
  }

  async function chooseProperty(propertyRecord: Property) {
    setSelected(propertyRecord);
    setSelectedSlot("");
    setBookingStatus("");
    setError("");
    try {
      const response = await fetch(`${apiUrl}/api/properties/${propertyRecord.id}/slots`);
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      setSlots(await response.json());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load slots");
    }
  }

  async function bookViewing(event: FormEvent) {
    event.preventDefault();
    if (!selectedSlot || !name.trim() || !email.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const call = await ensureCall("browser_voice");
      const leadResponse = await fetch(`${apiUrl}/api/leads/${call.lead_id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          email: email.trim(),
          contact_consent_status: "declined",
        }),
      });
      if (!leadResponse.ok) throw new Error(`Lead API returned ${leadResponse.status}`);
      const bookingResponse = await fetch(`${apiUrl}/api/viewings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slot_id: selectedSlot,
          lead_id: call.lead_id,
          call_id: call.id,
          idempotency_key: `${sessionId}:${selectedSlot}`,
          confirmed: true,
        }),
      });
      if (!bookingResponse.ok) throw new Error(`Booking API returned ${bookingResponse.status}`);
      const booking = await bookingResponse.json();
      setBookingStatus(
        booking.confirmation_email_status === "sent"
          ? "An email was sent."
          : booking.confirmation_email_status === "simulated"
            ? "Viewing confirmed. The confirmation email was prepared in local mode."
            : "Viewing confirmed, but the confirmation email could not be sent.",
      );
      setSlots((current) => current.filter((slot) => slot.id !== selectedSlot));
      setSelectedSlot("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to book viewing");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <nav className="topNav" aria-label="Primary navigation">
        <Link className="brand" href="/" aria-label="Horizon Homes home">
          <span>H</span>
          <strong>Horizon Homes</strong>
        </Link>
      </nav>

      <header className="hero">
        <div className="heroCopy">
          <div className="topNav">
            <p className="eyebrow light">PRIVATE PROPERTY CONCIERGE</p>
            <span className="edition">Paris · France</span>
          </div>
          <h1>Find a place that feels distinctly yours.</h1>
          <p className="lede">
            Tell us what matters. Your AI concierge searches verified homes and
            arranges viewings in one conversation.
          </p>
          <div className="heroNotes" aria-label="Service highlights">
            <span>32 curated homes</span>
            <span>Instant availability</span>
            <span>Private by design</span>
          </div>
        </div>
      </header>

      <section className="workspace" aria-label="Conversation demo">
        <div className="conversation">
          <div className="status">
            <div className={voiceStatus === "listening" ? "voiceSignal active" : "voiceSignal"} aria-hidden="true">
              <i />
              <i />
              <i />
              <i />
            </div>
            <div className="statusCopy">
              <strong>{voiceStatus === "listening" ? "I’m listening" : "Property concierge"}</strong>
              <small>{voiceStatus === "listening" ? "Speak naturally — you can interrupt at any time" : "Begin by voice or write your request below"}</small>
            </div>
            <button
              className={voiceStatus === "idle" ? "voiceButton" : "voiceButton active"}
              onClick={voiceStatus === "idle" ? startVoice : stopVoice}
              disabled={voiceStatus === "connecting"}
            >
              {voiceStatus === "idle"
                ? "Start conversation"
                : voiceStatus === "connecting"
                  ? "Connecting…"
                  : "End conversation"}
            </button>
          </div>
          <div className="messages" aria-live="polite">
            {messages.map((message, index) => (
              <div className={`message ${message.role}`} key={`${message.role}-${index}`}>
                <strong>{message.role === "assistant" ? "Concierge" : "You"}</strong>
                <p>{message.text}</p>
              </div>
            ))}
            {liveCallerTranscript && (
              <div className="message caller live">
                <strong>You</strong>
                <p>{liveCallerTranscript}</p>
              </div>
            )}
            {liveTranscript && (
              <div className="message assistant live">
                <strong>Qwen</strong>
                <p>{liveTranscript}</p>
              </div>
            )}
          </div>
          <div className="voiceOnlyFooter">
            <span>Voice-only session</span>
            <p>Select “Start conversation” and speak naturally to begin.</p>
            {error && <p className="error">{error}. Is the API running?</p>}
          </div>
        </div>

        <aside>
          <div className="asideHeading">
            <div>
              <p className="eyebrow">YOUR SHORTLIST</p>
              <h2>{properties.length ? "Homes selected for you" : "A considered selection"}</h2>
            </div>
            <span>{String(properties.length).padStart(2, "0")}</span>
          </div>
          {properties.length === 0 ? (
            <div className="empty">
              <div className="emptyMonogram">HH</div>
              <p>Your tailored shortlist will appear here once we know where and how you want to live.</p>
            </div>
          ) : (
            properties.map((property) => (
              <article key={property.id}>
                <p className="reference">{property.external_ref}</p>
                <h2>{property.title}</h2>
                <p>{property.address_display}</p>
                <div className="facts">
                  <span>{property.bedrooms} beds</span>
                  <span>{property.area_m2} m²</span>
                </div>
                <p className="price">
                  {Number(property.price).toLocaleString()} {property.currency}
                </p>
                <button className="secondary" onClick={() => chooseProperty(property)}>
                  Explore viewing times
                </button>
              </article>
            ))
          )}
          {selected && (
            <form className="booking" onSubmit={bookViewing}>
              <p className="eyebrow">BOOK A VIEWING</p>
              <h2>{selected.title}</h2>
              <label htmlFor="slot">Available time</label>
              <select
                id="slot"
                value={selectedSlot}
                onChange={(event) => setSelectedSlot(event.target.value)}
                required
              >
                <option value="">Choose a time</option>
                {slots.map((slot) => (
                  <option value={slot.id} key={slot.id}>
                    {new Date(slot.starts_at).toLocaleString()}
                  </option>
                ))}
              </select>
              <label htmlFor="name">Your name</label>
              <input
                id="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Alex Martin"
                required
              />
              <label htmlFor="email">Email for confirmation</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="alex@example.com"
                autoComplete="email"
                required
              />
              <p className="consent">
                We’ll use this address only for your viewing confirmation. No marketing
                consent is recorded.
              </p>
              <button
                className={bookingStatus ? "confirmedButton" : undefined}
                disabled={busy || !selectedSlot || Boolean(bookingStatus)}
              >
                {bookingStatus ? "Confirmed" : "Confirm viewing"}
              </button>
              {bookingStatus && <p className="success">{bookingStatus}</p>}
            </form>
          )}
        </aside>
      </section>
    </main>
  );
}
