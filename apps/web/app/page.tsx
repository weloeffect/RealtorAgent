"use client";

import { FormEvent, useMemo, useState } from "react";

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

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const sessionId = useMemo(() => crypto.randomUUID(), []);
  const [input, setInput] = useState("");
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
  const [bookingStatus, setBookingStatus] = useState("");

  async function sendMessage(event: FormEvent) {
    event.preventDefault();
    const message = input.trim();
    if (!message || busy) return;
    setMessages((current) => [...current, { role: "caller", text: message }]);
    setInput("");
    setBusy(true);
    setError("");
    try {
      const response = await fetch(`${apiUrl}/api/conversations/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message }),
      });
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      const data = await response.json();
      setMessages((current) => [...current, { role: "assistant", text: data.reply }]);
      setProperties(data.properties);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to reach the API");
    } finally {
      setBusy(false);
    }
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
    if (!selectedSlot || !name.trim() || busy) return;
    setBusy(true);
    setError("");
    try {
      const leadResponse = await fetch(`${apiUrl}/api/leads`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), contact_consent_status: "declined" }),
      });
      if (!leadResponse.ok) throw new Error(`Lead API returned ${leadResponse.status}`);
      const lead = await leadResponse.json();
      const bookingResponse = await fetch(`${apiUrl}/api/viewings`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slot_id: selectedSlot,
          lead_id: lead.id,
          idempotency_key: `${sessionId}:${selectedSlot}`,
          confirmed: true,
        }),
      });
      if (!bookingResponse.ok) throw new Error(`Booking API returned ${bookingResponse.status}`);
      setBookingStatus("Viewing confirmed in the local demo.");
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
      <header>
        <p className="eyebrow">LOCAL MOCKED MVP</p>
        <h1>Find a place worth coming home to.</h1>
        <p className="lede">
          Test the structured enquiry flow with synthetic listings. Try “I want to rent
          a two-bedroom in Paris under 3,000.”
        </p>
      </header>

      <section className="workspace" aria-label="Conversation demo">
        <div className="conversation">
          <div className="status"><span /> Concierge available</div>
          <div className="messages" aria-live="polite">
            {messages.map((message, index) => (
              <div className={`message ${message.role}`} key={`${message.role}-${index}`}>
                <strong>{message.role === "assistant" ? "Concierge" : "You"}</strong>
                <p>{message.text}</p>
              </div>
            ))}
          </div>
          <form onSubmit={sendMessage}>
            <label htmlFor="message">Your reply</label>
            <div className="inputRow">
              <input
                id="message"
                value={input}
                onChange={(event) => setInput(event.target.value)}
                placeholder="Tell me what you’re looking for…"
              />
              <button disabled={busy}>{busy ? "Searching…" : "Send"}</button>
            </div>
            {error && <p className="error">{error}. Is the API running?</p>}
          </form>
        </div>

        <aside>
          <div className="asideHeading">
            <p className="eyebrow">MATCHES</p>
            <span>{properties.length}</span>
          </div>
          {properties.length === 0 ? (
            <div className="empty">
              <p>Matching homes will appear here once we know your city and intent.</p>
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
                  View times
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
              <p className="consent">
                By confirming, you request this viewing. No marketing consent is recorded.
              </p>
              <button disabled={busy || !selectedSlot}>Confirm viewing</button>
              {bookingStatus && <p className="success">{bookingStatus}</p>}
            </form>
          )}
        </aside>
      </section>
    </main>
  );
}
