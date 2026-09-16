# bibles

The discovery layer for Bible content (text today; audio, video, and
pictures over time) published across four independent sources — plus,
soon, some texts published here for the first time. This repo doesn't
host all the content itself; it publishes a compact index of what exists
and how the pieces relate, so a client doesn't have to independently
discover and reconcile each source. Full detail on each: **[`doc/sources.md`](doc/sources.md)**.

- **DBT** — [Digital Bible Platform / Bible Brain](https://www.digitalbibleplatform.com/),
  published by [Faith Comes By Hearing](https://www.faithcomesbyhearing.com/).
  The largest catalog here, with the broadest published audio.
  **Requires your own API key** to fetch actual verse text/audio from
  DBT's own API — the only one of the four sources with that requirement.
- **PKF** — the packaged Bible format published by
  [`se-regional-pwa`](https://cdn.bibel.wiki/pkf/) — real audio, text, and
  versification data per language. No API key needed.
- **helloAO** — [bible.helloao.org](https://bible.helloao.org/), a free
  Bible API and content source. No API key needed.
- **openbible** — [Biblica](https://www.biblica.com/)'s Open Bible
  catalog, published via [openbible-api-1.biblica.com](https://openbible-api-1.biblica.com/).
  No API key needed.

**Using this data in your own app?** Start at **[`doc/README.md`](doc/README.md)**.

**Working on the publish pipeline itself?** Start at **[`pipeline/README.md`](pipeline/README.md)**.
