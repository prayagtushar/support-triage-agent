# The voice path

Verified against `2484693` on 2026-09-05.

> **It shipped.** `deploy-api.sh` sets `VOICE_ENABLED=true` with all three cuts on:
> `VOICE_JUDGE_ASYNC`, `VOICE_STREAM_DRAFT`, `VOICE_FAST_DRAFTER`. Production runs the
> `fast_drafter` arm, so the 7.1s figure below is the configuration that is live, not a
> proposal. The drafter on the text path moved to `meta-llama/llama-3.3-70b-instruct` on
> 2026-09-04 for the same reason and is now the same model on both paths.

The text pipeline answers a ticket in about 22 seconds at p50 and 48 at p95. That is
fine, and the README says why: triage is asynchronous, so p95 bounds how long a ticket
waits before a human sees it, not how long anyone waits on a page.

Voice deletes the word asynchronous. The same agent, reached by speaking, has a person
sitting in silence for the whole of it. This document is what happened when the correct
text design was put behind a microphone, and what had to be given up to make it usable.

The metric throughout is **time to first audio**: from the caller finishing their
sentence to the first sound coming back. Not total time. A reply that starts in a second
and takes eight to finish is a conversation. One that starts in eight is a dead line.

## Status

Implemented and running end to end. **The four-arm comparison has been attempted twice
and has never completed.** Both attempts ran out of speech credit partway through, and
the quarantined run is in `api/evals/voice/invalid/` with its own note.

What survives is two arms on three golden tickets, measured while the account had credit:

| Arm | What changes | TTFA p50 | Spoke at all | n |
|---|---|---|---|---|
| `baseline` | The text pipeline unchanged, with a microphone on it. Judge inline, reply spoken once every node has finished. | 38.4s | **1 of 3** | 3 |
| `judge_async` | Cut A. The judge moves off the critical path. It still runs, still logs, still decides whether a human sees the turn. It stops standing between the question and the answer. | not measured | | |
| `stream_draft` | Cut A + B. Each sentence is spoken while the model writes the next. | not measured | | |
| `fast_drafter` | Cut A + B + C. The spoken reply is written by a non-reasoning model. | **7.1s** | 3 of 3 | 3 |

Three samples is a direction, not a result, and the two middle arms have never been
measured at all, so the individual contribution of moving the judge and of streaming
sentences is still unknown. What the numbers below do support is the drafter finding,
which was reproduced separately and does not depend on the benchmark.

Every number here was measured against live providers. Sample sizes are stated
throughout because most of them are three or one.

Run `make voice-bench` for all four arms over the full set. It is serial by design and
takes about 45 minutes.

## Why serial, and why the numbers are a floor

The benchmark runs one ticket at a time. The provider rate limiters are per process, so
running tickets concurrently makes them queue behind each other and the queueing lands
inside the measurement. `make eval` can be concurrent because it measures quality. This
cannot.

Each golden ticket is synthesised to speech once and cached, so every arm hears the same
audio and the comparison is fair. It is also cleaner than any real caller on a real
line: no crosstalk, no clipping, no traffic. **Every latency here is a floor.**

## What was actually measured

### Speech alone costs about 2.4 seconds

| Step | Latency | n |
|---|---|---|
| Text to speech, one sentence, `bulbul:v3` | 1463ms | 1 |
| Speech to text, one sentence, `saaras:v3` | 955ms | 1 |

The transcript came back exact, including "charged twice" and "last Tuesday". Both are
REST calls. Sarvam publishes WebSocket variants of each, and that is where this 2.4
seconds goes when someone needs it back.

This matters more than it looks. Before a single model runs, roughly two and a half
seconds of the budget is gone. A target under two seconds is not reachable on the REST
endpoints at all, no matter how fast the pipeline gets.

### The drafter, not the pipeline, is the problem

`sarvam-105b` reasons before it answers, and bills that reasoning as completion tokens.
The config has always said so. On the text path it costs nothing that matters. On a call
it is the whole game, because the reasoning is emitted before any speakable token, so
streaming cannot start early.

Same prompt, same streaming client, `max_tokens=1024`:

| Drafter | First visible token | Completion tokens | Characters produced | n |
|---|---|---|---|---|
| `sarvam/sarvam-105b` | never | 1025 | **0** | 1 |
| `openrouter/meta-llama/llama-3.3-70b-instruct` | 1725ms | 48 | 240 | 1 |
| `openrouter/google/gemini-2.5-flash-lite` | 2312ms | 42 | 203 | 1 |

Read the first row again. It spent the entire token budget reasoning and produced no
reply at all. The text path catches this: `ModelOutputTruncated` fires, the router sends
the ticket to a human, and a reviewer sees what happened. On a call there is no reviewer
and no error, only silence, and then a person hanging up.

A wider budget does produce text. At `max_tokens=4096` the same prompt returned three
sentences after 761 completion tokens, with the first visible word at 6.2 seconds. Still
six seconds of nothing before streaming has anything to stream.

### The same finding, on the text path, with no microphone in it

The baseline arm above failed two of three tickets with
`sarvam-105b spent its 4096 token budget without producing content`. That looked like a
voice problem until the drafter was run on its own, on the original golden text, with no
speech anywhere. Both conditions below draft from identical cached classify and retrieve
output, so the only variable is the budget. All 60 golden tickets, 2026-09-03:

| `drafter_max_tokens` | Drafted | Produced nothing | Completion tokens on success |
|---|---|---|---|
| 4096, as shipped | 37 of 60 | **23 of 60 (38.3%)** | p50 3100, max 5261 |
| 8192 | 60 of 60 | 0 | p50 3424, p95 6136, max 7215 |

At 8192, 21 of 60 replies needed more than 4096 tokens, which is the same population as
the 23 failures. The shipped configuration was sitting on the boundary. Replies needing
more reasoning than that return empty, `ModelOutputTruncated` fires, and the router sends
the ticket to a human. Nothing errors, the queue keeps moving, and the system works
exactly as designed while producing no drafts.

This is the failure mode the README already describes in another form: *"Nothing failed.
The system just quietly stopped knowing anything."* Same shape, different cause. The
same eval run on 2026-08-01, same model and same 4096 budget, had **0 of 60** empty
drafts. The reasoning grew; the budget did not.

### The tight budget was the expensive one

The obvious objection to raising the ceiling is cost, and it is wrong. A truncated call
is billed for every token it reasoned with and returns nothing to show for it, and
because `draft_reply` returns no stats on failure, that spend is invisible to the cost
accounting:

| `drafter_max_tokens` | Usable drafts | Billed and counted | Billed but invisible | **Per usable draft** |
|---|---|---|---|---|
| 4096 | 37 | ₹2.039 | ₹1.507 | **₹0.0958** |
| 8192 | 60 | ₹3.947 | ₹0.000 | **₹0.0658** |

Total spend rises 11%. Output rises 62%. Cost per usable draft falls 31%.

**Resolved:** the budget is now 16384, not 8192, because the observed maximum at 8192 was
7215 and a ceiling 14% above the worst case seen is a ceiling that trips again. The
ceiling bills nothing on its own; only tokens actually generated are charged, so headroom
is close to free and truncation is not.

Changed in **two** places, which is the other half of the lesson. `app/config.py` holds
the default and `.env` holds the value that actually runs. The first attempt at
re-measuring this was labelled for 16384 and executed at 4096, because `.env` still said
4096 and nothing compared the two. Eval reports now record the budgets in force alongside
the models, so a label cannot silently disagree with its run again. In production the
same value comes from the Cloud Run environment, so `GET /policy` is the honest place to
read it.

**Not yet re-measured.** Every published metric in the README still dates from
2026-08-01 and was produced under the 4096 budget. The re-run is blocked: the Sarvam
account returned `402 No credits available` partway through, so `make eval`, `make gate`,
`make readme-metrics` and `make ui-evals` are all still outstanding.

So the largest single lever is not streaming. It is **not using a reasoning model to
write something a person is waiting to hear.** That is arm `fast_drafter`, and the
choice is a config change, which is the point of the settings design.

The judge is unaffected and stays where it is. Nothing is waiting on the judge once it
is off the critical path, so it can take as long as it needs to be right.

### Where the time actually goes

Three real turns on the `fast_drafter` arm, full pipeline, milliseconds from the moment
the caller stopped speaking.

| Ticket | transcript | retrieved | first token | **first audio** | reply done | judged |
|---|---|---|---|---|---|---|
| g001 | 1596 | 4793 | 5658 | **7135** | 10993 | 14082 |
| g002 | 1129 | 4171 | 4787 | **6215** | 11137 | 14063 |
| g003 | 710 | 8574 | 9375 | **12218** | 16834 | 18061 |

Four things this table says.

**Cut A is visible in the last two columns.** The caller stopped waiting somewhere
between 6.2 and 12.2 seconds. Judging and routing finished between 14.1 and 18.1. That
gap, 3 to 7 seconds, is work the caller never waited for and that still happened.

**Classify and retrieve are now the bottleneck.** They own everything between the
transcript and the first token: roughly 3 to 7 seconds, more than the drafter. Having
removed the reasoning drafter, the next cut is here rather than anywhere else, and
retrieving on a partial transcript is the obvious move.

**Speaking the first sentence costs 1.4 to 2.8 seconds after the first token exists.**
That is the text-to-speech round trip, and it is why the sentence-length question below
is not academic.

**None of this is yet a conversational latency.** The best turn was 6.2 seconds. A
caller talks over anything past about 2.5. The cuts implemented so far take a broken
38-second baseline to a slow but working 7, which is progress and is not the target.

## What streaming costs

Streaming the draft buys latency and gives up structure. The JSON schema cannot be
streamed, because nothing is speakable until the object closes, and the object closing
is the entire reply. So on the streamed arms the drafter returns prose, and three fields
go with the schema:

- **`citations`.** The retrieved cases are still recorded and still shown to a reviewer.
  Which sentence leaned on which case is gone. For a project whose review screen is
  built around citation markers, this is the most expensive thing on the list.
- **`is_safe_fallback`.** The router loses the drafter's own signal that it declined to
  answer, and has to infer it.
- **`used_language`.** Recoverable from the transcript's detected language, so this one
  is cheap.

The routing policy is unchanged. It reads a composite of judge, classifier and retrieval
signals, and it now reads one fewer of them.

## An open question the code does not answer

The sentence splitter merges a short opener into the sentence after it, so "Hi there."
does not become its own text-to-speech request. That is right for cost: a whole round
trip for a moment of audio.

It is also wrong for latency, and latency is the point. A human support agent opens with
"sure, let me check that" precisely because it buys thinking time while the caller hears
a voice. The merge deletes that move.

`tts_min_sentence_chars` exists so the trade can be measured instead of argued. It has
not been measured yet.

## What was deliberately not built

- Real phone calls, telephony, phone numbers. A browser microphone measures the same
  interval for a tenth of the work.
- Barge-in, where the caller interrupts mid-sentence.
- Multi-turn conversation memory. Each turn is a ticket.
- Speaker identification, wake words, noise handling.
- Streaming speech-to-text. It is the prerequisite for retrieving on a partial
  transcript, and worth adding once the numbers show retrieval is the next bottleneck.

## Where it lives

| Piece | Path |
|---|---|
| Speech endpoints, sentence splitting | `api/app/voice/speech.py` |
| One turn, timed at every boundary | `api/app/voice/turn.py` |
| WebSocket, one socket per turn | `api/app/routers/voice.py` |
| classify and retrieve only | `build_voice_graph` in `api/app/agent/graph.py` |
| Streaming completions | `TextStream` in `api/app/llm/client.py` |
| Benchmark | `api/scripts/voice_bench.py`, `make voice-bench` |
| Browser page | `ui/src/routes/Voice.tsx`, `/voice` |

The socket exists because the point is to deliver the first sentence of audio before the
last one exists. The 202-and-poll shape, which is right for text triage, would hide
exactly the interval being measured.
