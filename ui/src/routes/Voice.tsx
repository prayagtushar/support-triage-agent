import { useCallback, useEffect, useRef, useState } from "react";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const WS_URL = `${BASE.replace(/^http/, "ws")}/voice/ws`;

/**
 * What the benchmark measured, so the page is worth reading whether or not speech is
 * live. Three tickets per arm, against real providers, and the two middle arms were
 * never completed. docs/VOICE.md carries the caveats in full.
 */
const ARMS: readonly { arm: string; what: string; ttfa: string; spoke: string }[] = [
  {
    arm: "baseline",
    what: "The text pipeline with a microphone on it. Judge inline, reply spoken once every node has finished.",
    ttfa: "38.4s",
    spoke: "1 of 3",
  },
  {
    arm: "fast_drafter",
    what: "Judge off the critical path, sentences spoken as they are written, and a non-reasoning model writing the reply.",
    ttfa: "7.1s",
    spoke: "3 of 3",
  },
];

type Timings = {
  arm: string;
  transcript_ms: number | null;
  retrieved_ms: number | null;
  first_token_ms: number | null;
  first_audio_ms: number | null;
  reply_complete_ms: number | null;
  judged_ms: number | null;
  audio_chunks: number;
  errors: string[];
};

type Done = {
  timings: Timings;
  transcript: string;
  state: {
    draft?: string | null;
    route?: string | null;
    route_reason?: string | null;
    composite_confidence?: number | null;
    classification?: { intent?: string; urgency?: string } | null;
  };
};

/** What the caller heard, measured in the caller's browser rather than on the server. */
type Heard = { firstAudioMs: number | null; chunks: number };

const STAGES: Array<[keyof Timings, string]> = [
  ["transcript_ms", "speech recognised"],
  ["retrieved_ms", "cases retrieved"],
  ["first_token_ms", "first word written"],
  ["first_audio_ms", "first word spoken"],
  ["reply_complete_ms", "reply finished"],
  ["judged_ms", "judged and routed"],
];

function Waterfall({ timings }: { timings: Timings }) {
  const total = Math.max(
    ...STAGES.map(([key]) => (timings[key] as number | null) ?? 0),
    1,
  );
  const spoken = timings.first_audio_ms;

  return (
    <div className="space-y-1.5">
      {STAGES.map(([key, label]) => {
        const at = timings[key] as number | null;
        if (at == null) return null;
        const isSpoken = key === "first_audio_ms";
        return (
          <div key={key} className="flex items-center gap-3 text-xs">
            <span className="w-36 shrink-0 text-ink-3">{label}</span>
            <span className="relative h-3 flex-1 rounded-[2px] bg-paper-2">
              <span
                className={`absolute inset-y-0 left-0 rounded-[2px] ${
                  isSpoken ? "bg-teal-fill" : "bg-rule"
                }`}
                style={{ width: `${(at / total) * 100}%` }}
              />
              {/* Where the caller stops waiting. Every bar past it is work they never felt. */}
              {spoken != null && (
                <span
                  aria-hidden
                  className="absolute inset-y-[-2px] w-px bg-teal"
                  style={{ left: `${(spoken / total) * 100}%` }}
                />
              )}
            </span>
            <span
              className={`w-16 shrink-0 text-right tabular-nums ${
                isSpoken ? "font-semibold text-ink" : "text-ink-3"
              }`}
            >
              {(at / 1000).toFixed(1)}s
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function Voice() {
  const [recording, setRecording] = useState(false);
  const [status, setStatus] = useState("Press and hold, or click to start and click to stop.");
  const [transcript, setTranscript] = useState("");
  const [done, setDone] = useState<Done | null>(null);
  const [heard, setHeard] = useState<Heard>({ firstAudioMs: null, chunks: 0 });
  const [error, setError] = useState<string | null>(null);
  // The API knows whether speech is funded and switched on. Asking it beats guessing,
  // and beats asking someone for a microphone on the way to an error.
  const [live, setLive] = useState<boolean | null>(null);

  useEffect(() => {
    fetch(`${BASE}/voice/config`)
      .then((r) => r.json())
      .then((c) => setLive(Boolean(c.enabled)))
      .catch(() => setLive(false));
  }, []);

  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const stopped = useRef<number>(0);
  const queue = useRef<Promise<void>>(Promise.resolve());

  useEffect(() => () => recorder.current?.stream.getTracks().forEach((t) => t.stop()), []);

  /** Plays clips strictly in order. Two sentences arriving together must not overlap. */
  const enqueue = useCallback((wavB64: string) => {
    queue.current = queue.current.then(
      () =>
        new Promise<void>((resolve) => {
          const audio = new Audio(`data:audio/wav;base64,${wavB64}`);
          audio.onended = () => resolve();
          audio.onerror = () => resolve();
          void audio.play().then(() => {
            setHeard((h) => ({
              // The server's number stops at the socket. This one includes the network
              // and the browser, which is the part the caller actually sits through.
              firstAudioMs: h.firstAudioMs ?? Math.round(performance.now() - stopped.current),
              chunks: h.chunks + 1,
            }));
          });
        }),
    );
  }, []);

  const send = useCallback(
    (blob: Blob) => {
      const socket = new WebSocket(WS_URL);
      socket.binaryType = "arraybuffer";
      socket.onopen = () => void blob.arrayBuffer().then((buf) => socket.send(buf));
      socket.onerror = () => setError("Could not reach the voice endpoint.");
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "transcript") {
          setTranscript(message.text);
          setStatus("Thinking.");
        } else if (message.type === "audio") {
          setStatus("Answering.");
          enqueue(message.wav_b64);
        } else if (message.type === "error") {
          setError(message.message);
          setStatus("Stopped.");
        } else if (message.type === "done") {
          setDone(message);
          setStatus("Done.");
        }
      };
    },
    [enqueue],
  );

  const start = useCallback(async () => {
    setError(null);
    setDone(null);
    setTranscript("");
    setHeard({ firstAudioMs: null, chunks: 0 });
    chunks.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const media = new MediaRecorder(stream);
      media.ondataavailable = (event) => chunks.current.push(event.data);
      media.onstop = () => {
        // The clock starts the moment the caller stops talking, not when the socket
        // opens. Anything measured after this point is time they are already waiting.
        stopped.current = performance.now();
        stream.getTracks().forEach((track) => track.stop());
        send(new Blob(chunks.current, { type: media.mimeType }));
      };
      media.start();
      recorder.current = media;
      setRecording(true);
      setStatus("Listening.");
    } catch {
      setError("No microphone. The browser refused access, or there is no input device.");
    }
  }, [send]);

  const stop = useCallback(() => {
    recorder.current?.stop();
    setRecording(false);
    setStatus("Sending.");
  }, []);

  return (
    <div className="max-w-3xl space-y-8">
      <header className="space-y-2">
        <h1 className="text-lg font-semibold tracking-tight">Voice</h1>
        <p className="prose-human text-sm text-ink-2">
          The same agent and the same routing rules, reached by speaking instead of typing.
          The text pipeline takes about 22 seconds to answer. That is fine for a queue and
          hopeless on a call. What I measure below is the gap between you finishing your
          sentence and hearing the first word back.
        </p>
      </header>

      {live === false ? (
        <div
          role="status"
          className="rounded-[2px] border border-mustard/40 bg-mustard-bg px-3 py-2 text-xs text-mustard"
        >
          <span className="font-medium">Speech is switched off on this deployment.</span>{" "}
          <span className="prose-human">
            Speech to text and text to speech are the only part of this system that runs on
            a paid Indic speech account, and it has no credit. Rather than hand you a button
            that asks for a microphone and then fails, here is what the benchmark measured
            while the account was funded.
          </span>
        </div>
      ) : (
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={recording ? stop : start}
            disabled={live === null}
            className={`rounded-[2px] px-4 py-2 text-sm font-medium transition-opacity hover:opacity-90 disabled:opacity-50 ${
              recording ? "bg-rust text-paper" : "bg-teal text-paper"
            }`}
          >
            {recording ? "Stop" : "Start talking"}
          </button>
          <span className="text-sm text-ink-3">{status}</span>
        </div>
      )}

      {live === false && (
        <section className="space-y-3">
          <h2 className="eyebrow">time to first audio</h2>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[34rem] text-left text-xs">
              <thead className="text-ink-3">
                <tr className="border-b border-rule">
                  <th className="pb-1.5 font-normal">arm</th>
                  <th className="pb-1.5 font-normal">what changes</th>
                  <th className="pb-1.5 text-right font-normal">p50</th>
                  <th className="pb-1.5 text-right font-normal">spoke at all</th>
                </tr>
              </thead>
              <tbody>
                {ARMS.map((a) => (
                  <tr key={a.arm} className="border-b border-rule align-top">
                    <td className="py-2 pr-3 font-mono text-ink">{a.arm}</td>
                    <td className="prose-human py-2 pr-3 text-ink-2">{a.what}</td>
                    <td className="py-2 pl-3 text-right tabular-nums text-ink">{a.ttfa}</td>
                    <td className="py-2 pl-3 text-right tabular-nums text-ink-2">{a.spoke}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="prose-human text-xs text-ink-3">
            Three tickets per arm, so this is a direction rather than a result, and two
            further arms were never completed. The finding that survives is the drafter:
            a reasoning model spends its whole budget thinking before it emits a word
            anyone can say, which on a call is silence. Swapping it for a non-reasoning
            model is a config change, and it is most of the 38.4 to 7.1 second gap. The
            measurements, including the ones that failed, are in{" "}
            <code className="text-ink-2">docs/VOICE.md</code>.
          </p>
        </section>
      )}

      {error && (
        <p className="rounded-[2px] border border-rust bg-paper-2 px-3 py-2 text-sm text-ink">
          {error}
        </p>
      )}

      {transcript && (
        <section className="space-y-1">
          <h2 className="text-xs uppercase tracking-wide text-ink-3">Heard</h2>
          <p className="text-sm text-ink">{transcript}</p>
        </section>
      )}

      {done?.state.draft && (
        <section className="space-y-1">
          <h2 className="text-xs uppercase tracking-wide text-ink-3">Said</h2>
          <p className="prose-human text-sm text-ink">{done.state.draft}</p>
        </section>
      )}

      {done && (
        <section className="space-y-4">
          <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
            <span className="text-sm text-ink-3">
              arm <span className="font-mono text-ink">{done.timings.arm}</span>
            </span>
            {done.state.route && (
              <span className="text-sm text-ink-3">
                routed to <span className="font-mono text-ink">{done.state.route}</span>
              </span>
            )}
            {heard.firstAudioMs != null && (
              <span className="text-sm text-ink-3">
                you waited{" "}
                <span className="font-semibold text-ink tabular-nums">
                  {(heard.firstAudioMs / 1000).toFixed(1)}s
                </span>
              </span>
            )}
            {done.timings.audio_chunks > 1 && (
              <span className="text-sm text-ink-3">
                spoken in{" "}
                <span className="text-ink tabular-nums">{done.timings.audio_chunks}</span> pieces
              </span>
            )}
          </div>

          <Waterfall timings={done.timings} />

          <p className="prose-human text-xs text-ink-3">
            The server's clock stops at the socket; yours includes the network and the browser,
            so the two disagree by the amount the deployment costs. Bars past the marked line
            are work you never waited for.
          </p>
        </section>
      )}
    </div>
  );
}
