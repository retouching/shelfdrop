# 0015. The journal of the events, posted on Discord
Status: Accepted
Date: 2026-10-21

## Context
Decided by the user on 2026-10-21 (plan section 3, point 7): each event of shelfdrop (a send, the end of a download, a placement, a file to place, a retry, a failure, a sign-in...) goes to the webhook of Discord the user already has, as an embed, with a color per type (the Radix palette of the site). 22 volumes sent are one message, not 22: the events of one batch are grouped for 30 seconds. A webhook takes 30 messages a minute; a message that fails 3 times is dropped and logged, and never holds up a download nor a placement. Each type can be switched off. No secret, no URL of a tracker with its key, never the name typed for a sign-in refused.

## Decision
- An event is a row of `events`: its type, its group, its facts (JSON), a picture, the state of its message (`pending`, `sent`, `skipped`, `dropped`) and its attempts. Every process records its events (`Journal.record`, on a session of its own, from the threadpool); the domains receive it through a protocol of their own (`AuthEvents`, `DownloadEvents`).
- The API alone posts them (`JournalSender`, a singleton run by its lifespan): every 5 seconds, the batches (one type, one group) whose first event is 30 seconds old, 5 messages a look at most, each one embed (`shelfdrop.journal.embeds`, pure), with its cover joined in a `multipart/form-data` body. A `429` waits the `retry_after` of Discord, a minute at most, and keeps the batch; any other failure counts an attempt, the third drops it.
- The picture is kept with its event (the bytes, JPEG, PNG or WebP, 8 MB at most): the API that posts it may not see the files of the process that recorded it.
- The webhook is the secret `discord.webhook` (imported once from `SHELFDROP_DISCORD_WEBHOOK`), the types on are `discord.events.<type>`, read at each look; the title links to `SHELFDROP_PUBLIC_URL`.
- The events of now: `sent`, `failed` (`not_received`) and `retry` (with its result) at the end of a send; `downloaded` (an automatic download complete) and `to_place` (a manual one) once, by whichever process completes it first (`DownloadRepository.mark_completed` returns the ids it changed); `login`, a sign-in, or the attempts refused from one address past the throttle.

## Rejected alternatives
- A message per event: 22 volumes would be 22 messages, and the 30 messages a minute of a webhook would go at once.
- The post in the process of the event (the worker of the placement): two processes would share the limit of one webhook without knowing it.
- The cover by its path: the API does not see the library.

## Consequences
- A message comes 30 seconds at least after its first event.
- A batch that keeps getting a `429` keeps its events pending until Discord takes them.
