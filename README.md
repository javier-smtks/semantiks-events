# Semantiks Events

Public code, slides and runnable demos for the events Semantiks hosts and speaks at.

Upcoming and past meetups: **https://www.semantiks.com/events**

> This repo is public. Nothing here should contain Semantiks secrets, customer data, or anything you wouldn't put on a billboard.

## Events

| Event | Folder | Links |
| --- | --- | --- |
| MEXICO CITY: Agents In Production (LangChain Meetup, Mexico Tech Week) — 2026-10-29 | [`events/mcaip-291026`](./events/mcaip-291026) | [Luma](https://luma.com/mxtw-e354f23b) |

## Layout

```
events/
  <event-slug>/
    README.md       # Public guide attendees can follow
    ...             # Code, configs, examples
    NOTES.md        # Speaker notes — gitignored, not published
```

Each event folder is self-contained: its own virtual env, its own dependencies, its own setup instructions in its `README.md`.

## License

This repository is MIT-licensed — see [`LICENSE`](./LICENSE). Some event folders contain code derived from third-party MIT-licensed projects; where that's the case the upstream copyright notice and the list of our changes live in that folder's `NOTICE.md`.

## Contributing a new event

1. Create `events/<year>-<city>-<slug>/`.
2. Drop a `.gitignore` that excludes `NOTES.md` and `.env` so speaker-only material never leaks into a public commit.
3. Write a `README.md` an attendee could run on their laptop with nothing but the public info in it.
4. Link it from the table above and from https://www.semantiks.com/events.
