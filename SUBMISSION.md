# Door Interpreter — submission pack

Accessibility doorbell for a deaf or hard-of-hearing resident. A ring becomes a high-contrast alert, the live door picture, the visitor's words as text, and one plain sentence about what is there. People are not identified.

## Text description

Door Interpreter is a new Ring app. The server receives a doorbell or motion event from a signed webhook, from Playground event polling, or from a built-in simulator. The same alert path updates a high-contrast page that flashes and vibrates.

Watch the door opens a receive-only H264 WebRTC session. The browser builds the offer. The server posts it to Ring's WHEP endpoint and deletes the session when the view ends. Visitor audio from that stream is transcribed on the Mac and shown as a caption. What is there classifies a snapshot, from Ring's image API or from the live frame, into one sentence: a package, a vehicle, an animal, a person, or a clear doorway. The sentence is chosen from a fixed list, so a classifier label can never become someone's name.

## How to run

See the README. Judges: `sh scripts/demo.sh`, open http://localhost:8000, press Simulate: Doorbell, then Watch the door if `RING_ACCESS_TOKEN` is set.

## Product feedback — Ring Partner API

Used for device discovery, WHEP live video, image snapshot download, and the documented webhook signature. The Playground token and the synthetic Doorbell Pro were enough to prove discovery and a live H264 session.

What worked: `GET /v1/devices?include=status,capabilities,location,configurations` returned an online Doorbell Pro with AVC video, snapshot support, and end-to-end encryption off. A receive-only H264 offer to `/v1/devices/{id}/media/streaming/whep/sessions` returned 201, the peer connection reached `connected`, and `DELETE` on the session URL returned 200.

What needs work: a normal browser offer (VP8) gets `500 INTERNAL_ERROR` with no codec detail. A bad token gets an empty 401. The synthetic device's event history is empty, and image download has no recording to return. Doorbells cannot play a spoken reply. The hello-world sample adds a `sendrecv` audio track, which this device does not accept as a way to talk back.

Onboarding: the Playground token is the short path and lasts about 30 minutes. Webhooks are not available on that token. The docs are clear once you are on the WHEP and snapshot pages. I would build on this API again, because the live stream and the device model are real, and the gaps above are specific.

## Friction log

1. **Task:** Open a live view from the Playground doorbell with a browser WebRTC offer.
   **Steps:** Create a peer connection, add a receive-only video track, post the SDP to the WHEP session endpoint.
   **Expected:** An SDP answer, or a 4xx that names the missing codec.
   **Actual:** `500 INTERNAL_ERROR`. The offer contained only VP8. The device capabilities list AVC.
   **Severity:** High. The sample and a default browser both lead with VP8.
   **Workaround:** Offer H264 only, every track `recvonly`. That returns 201 and connects.
   **Suggestion:** Reject an unsupported codec with 415 and `detail` naming AVC, and say so next to the sample that uses a default offer.

2. **Task:** Call `GET /v1/devices` with a Playground token that Ring will not accept.
   **Steps:** Send `Authorization: Bearer` and the token.
   **Expected:** 401 with `UNAUTHORIZED` and a detail, matching the error format used by image download.
   **Actual:** 401 and an empty body. No `WWW-Authenticate` header.
   **Severity:** Medium.
   **Workaround:** Treat any 401 as "generate a new Playground token."
   **Suggestion:** Use the same `errors[]` body as the rest of the API.

3. **Task:** Poll event history and download a snapshot for the Playground device.
   **Steps:** `GET /v1/history/devices/{id}/events` and `POST /v1/devices/{id}/media/image/download` with `latest_in_range`.
   **Expected:** A synthetic ding or a still, since the device is online and advertised as a doorbell.
   **Actual:** History is `data: []`. There is no recording to snapshot. The live WHEP session still connects.
   **Severity:** High for an event-driven demo.
   **Workaround:** Simulate the ring in the app, and take the scene sentence from the live frame.
   **Suggestion:** Add a Playground control that emits `button_press` and stores one snapshot.

4. **Task:** Speak a reply through the doorbell after reading the caption.
   **Steps:** Read the media and chime docs, then the device capabilities.
   **Expected:** A way to play generated speech on the doorbell, as two-way audio would imply.
   **Actual:** Streams are receive-only. `audio.supported_actions` is null. Playback exists for chimes.
   **Severity:** High if the product is a conversation. Not a bug once the docs are read. The hello-world sample still adds `sendrecv` audio.
   **Workaround:** Show captions and do not promise a spoken reply.
   **Suggestion:** Mark talkback unsupported on the live-video page, and change the sample's audio transceiver to `recvonly`.

## Demo video (under 3 minutes)

Record the screen with the mic off. No music. English.

1. Open the page. Say what it is: a doorbell a deaf resident can read.
2. Press Simulate: Doorbell. The alert flashes. That is the event.
3. Press Watch the door. The Playground doorbell picture appears. Point at the network log: one POST to the WHEP session, H264, then DELETE when it ends.
4. Play a short spoken line at the computer mic only if the stream's own audio is silent. The caption line fills with the words.
5. Press What is there. One sentence appears. Say that it does not name the person.
6. Stop before 3:00. Lead with the caption, not the setup.

## Open Source mini

- Project repo: this GitHub repo
- Contribution URL: the commit that adds the live view, captions, and scene line
- License: MIT, already in `LICENSE`
- What: a new project. It calls the Ring Partner API at runtime, turns the door into text, and refuses to identify people.

## Still needs the account holder

- Request the $150 AWS credits before Wed 22 Oct 2026, 3:00 AM PHT. Confirm which of the two published forms is current.
- Upload the demo video as a public YouTube or Vimeo link.
- Submit the Devpost form with this description, the feedback, and the friction log.
