"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

type CallSummary = {
  id: string;
  mode: string;
  status: string;
  disposition: string | null;
  started_at: string;
};

type CallDetail = CallSummary & {
  summary: string | null;
  booking_id: string | null;
  lead: { name: string | null; email: string | null; phone_e164: string | null };
  preferences: {
    city: string | null;
    transaction_type: string | null;
    budget_max: string | null;
    bedrooms_min: number | null;
  } | null;
  turns: Array<{
    id: string;
    speaker: string;
    text: string;
    interrupted: boolean;
    latency_ms: number | null;
  }>;
  tools: Array<{
    id: string;
    tool_name: string;
    status: string;
    latency_ms: number;
  }>;
  matches: Array<{
    rank: number;
    property: { id: string; external_ref: string; title: string; price: string; currency: string };
  }>;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function ReviewPage() {
  const [calls, setCalls] = useState<CallSummary[]>([]);
  const [selected, setSelected] = useState<CallDetail | null>(null);
  const [error, setError] = useState("");

  async function loadCalls(selectFirst = false) {
    try {
      const response = await fetch(`${apiUrl}/api/calls`);
      if (!response.ok) throw new Error(`API returned ${response.status}`);
      const data = await response.json();
      setCalls(data);
      if (data[0] && selectFirst) {
        const detailResponse = await fetch(`${apiUrl}/api/calls/${data[0].id}`);
        if (detailResponse.ok) setSelected(await detailResponse.json());
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load calls");
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${apiUrl}/api/calls`, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`API returned ${response.status}`);
        return response.json();
      })
      .then(async (data) => {
        setCalls(data);
        if (data[0]) {
          const detailResponse = await fetch(`${apiUrl}/api/calls/${data[0].id}`, {
            signal: controller.signal,
          });
          if (detailResponse.ok) setSelected(await detailResponse.json());
        }
      })
      .catch((caught) => {
        if (caught instanceof Error && caught.name !== "AbortError") setError(caught.message);
      });
    return () => controller.abort();
  }, []);

  async function selectCall(callId: string) {
    const response = await fetch(`${apiUrl}/api/calls/${callId}`);
    if (response.ok) setSelected(await response.json());
  }

  return (
    <main className="reviewPage">
      <nav className="topNav">
        <Link className="brand" href="/" aria-label="Horizon Homes home">
          <span>H</span>
          <strong>Horizon Homes</strong>
        </Link>
        <div className="navMeta">
          <Link className="navLink" href="/">← Concierge</Link>
          <button className="quietButton" onClick={() => void loadCalls()}>Refresh</button>
        </div>
      </nav>
      <header className="reviewHero">
        <div>
          <p className="eyebrow">CONCIERGE JOURNAL</p>
          <h1>Every conversation, beautifully accounted for.</h1>
        </div>
        <p className="lede">A clear record of preferences, recommendations, decisions, and arranged viewings.</p>
      </header>
      {error && <p className="error">{error}</p>}
      <section className="reviewGrid">
        <aside className="callList">
          {calls.length === 0 && <p>No calls recorded yet.</p>}
          {calls.map((call) => (
            <button
              className={selected?.id === call.id ? "callItem selected" : "callItem"}
              key={call.id}
              onClick={() => void selectCall(call.id)}
            >
              <strong>{call.mode.replace("browser_", "")}</strong>
              <span>{new Date(call.started_at).toLocaleString()}</span>
              <em>{call.disposition ?? call.status}</em>
            </button>
          ))}
        </aside>
        <div className="callDetail">
          {!selected ? (
            <div className="empty"><p>Select a call to inspect it.</p></div>
          ) : (
            <>
              <div className="reviewCards">
                <section>
                  <p className="eyebrow">LEAD</p>
                  <h2>{selected.lead.name ?? "Anonymous caller"}</h2>
                  <p>{selected.preferences?.transaction_type ?? "Intent not captured"}</p>
                  <p>{selected.preferences?.city ?? "City not captured"}</p>
                  <p>
                    {selected.preferences?.budget_max
                      ? `Budget up to €${Number(selected.preferences.budget_max).toLocaleString()}`
                      : "Budget not captured"}
                  </p>
                </section>
                <section>
                  <p className="eyebrow">OUTCOME</p>
                  <h2>{selected.booking_id ? "Viewing booked" : "Enquiry"}</h2>
                  <p>{selected.status}</p>
                  <p>{selected.summary ?? "Summary generated when the call ends."}</p>
                </section>
              </div>

              <section className="reviewSection">
                <p className="eyebrow">TRANSCRIPT</p>
                {selected.turns.length === 0 && <p>No completed turns captured.</p>}
                {selected.turns.map((turn) => (
                  <div className="transcriptTurn" key={turn.id}>
                    <strong>{turn.speaker}</strong>
                    <p>{turn.text}</p>
                    <small>
                      {turn.interrupted ? "Interrupted · " : ""}
                      {turn.latency_ms !== null ? `${turn.latency_ms} ms response latency` : ""}
                    </small>
                  </div>
                ))}
              </section>

              <section className="reviewSection">
                <p className="eyebrow">VERIFIED MATCHES</p>
                <div className="matchGrid">
                  {selected.matches.map((match) => (
                    <article key={match.property.id}>
                      <span>#{match.rank} · {match.property.external_ref}</span>
                      <h2>{match.property.title}</h2>
                      <p>{Number(match.property.price).toLocaleString()} {match.property.currency}</p>
                    </article>
                  ))}
                </div>
              </section>

              <section className="reviewSection">
                <p className="eyebrow">TOOL AUDIT</p>
                {selected.tools.map((tool) => (
                  <p className="toolRow" key={tool.id}>
                    <strong>{tool.tool_name}</strong>
                    <span>{tool.status} · {tool.latency_ms} ms</span>
                  </p>
                ))}
              </section>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
