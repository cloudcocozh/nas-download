# Background Automation API

[中文](AUTOMATION.md) | [English](AUTOMATION_EN.md)

All endpoints are under `/api/v1` and require an existing login session. Tasks run in the NAS service; turning off the phone does not affect scheduling. No tasks are created or enabled by default, and no old containers or configurations are read.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET / POST | `/automations` | List / create tasks; returns `{ok,items}` / `{ok,item}` |
| GET / PATCH / DELETE | `/automations/{id}` | Read / update / disable and delete configuration (retaining audit and ownership records) |
| POST | `/automations/{id}/run` | `{request_id: UUID, dry_run: true}`; returns `{ok,run_id,status}`; the same UUID is not executed twice |
| POST | `/automations/{id}/stop` | Cancel execution and set `enabled=false` |
| GET | `/automations/{id}/logs?limit=50` | `{ok,items}`; recent runs and redacted results |
| GET | `/automations/{id}/owned` | `{ok,items}`; resources added by this task with persistent ownership evidence |
| GET / POST | `/automations/{id}/protections` | Permanent protection list / add `{info_hash,reason}` |
| DELETE | `/automations/{id}/protections/{info_hash}` | Remove explicit protection (other protections, including HR and unknown obligations, still apply) |
| GET | `/automation-runs/{run_id}` | `{ok,item}`, including status, timestamps and results |

Submit configuration fields directly when creating or updating a task. The returned `item` includes configuration, `next_run` (Unix seconds), `last_status`, `last_run_at` (Unix seconds, null before the first run), and `has_cookie/has_headers_json/has_request_body`; it does not return cookies, request headers or bodies. Empty authentication fields in PATCH preserve saved values. `kind` cannot change after creation. `run` defaults to a read-only dry run; actual execution requires enabling the task first. Once a stop is confirmed, no further write operations start; requests already sent finish or are recorded as uncertain. An HTTP request only registers a run; execution occurs in the background without waiting for the site's response.

Creation via `POST /automations` supports an optional `request_id: UUID`. Clients should retain the same UUID and identical request content for one creation, reusing them when the result is uncertain rather than creating again with another UUID. The same UUID and configuration return the public `item` receipt from the first creation; the same UUID with different configuration returns `409 REQUEST_ID_CONFLICT`. The receipt and task configuration are saved in the same SQLite transaction and survive service restarts; replaying the original request after task deletion does not recreate it. Older clients can still create without this field, but do not receive creation deduplication. PATCH does not use this creation receipt.

Run states: `queued`, `running`, `completed`, `failed`, `cancelled`, `interrupted`, `needs_review`. A run contains `id,automation_id,generation,dry_run,scheduled,status,created_at,started_at,finished_at,result`; `scheduled` is a read-only boolean distinguishing background scheduled runs from manual runs. Tasks initially have `last_status=idle`. `result.reason` describes the admission reason; the `result.retention` array records individual retention reasons and does not indicate that deletion has occurred. An `owned` object contains `automation_id,downloader_id,info_hash,task_id,marker,added_at,size,obligations,state`; `state` is `active/removed`.

## Configuration

Common fields: `name`, `kind`, `enabled=false`. Check-in and account checks use a daily randomized window in Beijing time: `window_start="08:00"`, `window_end="10:00"`. The chosen time is persisted in SQLite; a restart does not draw a new time. There is at most one actual check-in attempt per Beijing calendar day; uncertain results are not automatically retried.

Scheduled requests start only within `[window_start, window_end)` on the current calendar day. After downtime, recovery schedules today's window if it has not started, may catch up within the window, and schedules tomorrow's window if today's has ended; it never sends a missed morning task late at night. Queued scheduled tasks check again before execution; a missed window records `result.reason="outside_window"` without consuming that day's check-in ticket. Queues left by older versions with unknown origins are conservatively migrated under scheduled-window restrictions. An explicit user request for an actual “立即运行” (Run now) is manual and may execute outside the window, but remains subject to the one-ticket-per-day limit.

- `kind="hdfans_signin"`: `cookie` is required. Only the fixed `https://hdfans.org/attendance.php` endpoint is accessed. Success, already checked in, expired cookie, protection/CAPTCHA and unknown pages are recorded separately. Redirects are prohibited; CAPTCHAs are neither handled nor bypassed. A replacement cookie takes effect the following day; a failure today requires manual checking on the site.
- `kind="http_signin"`: Custom HTTP check-in, without first creating a search site. `signin_url` is the final check-in URL; `method=GET/POST`; `request_format=form/json/text`. Optional `cookie`, `headers_json` and `request_body` are encrypted at rest and never echoed. Headers use a JSON object; form/json bodies use a JSON object. Enter GET parameters in the body field too, rather than directly in the URL. `success_contains` is required; `already_contains/failure_contains` may be empty; `expected_status=200`. Success is confirmed only when the status matches expectations and the body matches success or already-checked-in text; failure markers take precedence. Public internet URLs require HTTPS; LAN HTTP requires a numeric address. Redirects, scripts, CAPTCHA handling and automatic retries are prohibited. Sites requiring dynamic CSRF, browser login flows or CAPTCHAs cannot yet be handled with a single HTTP template. A dry run sends no check-in request and only checks configuration; actual validation consumes that day's one ticket.
- `kind="mteam_check"`: `site_id` points to M-Team. Only the account API is called to check connectivity and VIP expiration; browser login is not implemented, and this does not claim to perform check-in or maintain account activity.
- `kind="brush"`: `site_id` (M-Team or Torznab), `downloader_id`, `save_path` (the downloader's default path by default), `interval_minutes=10` (2–1440); `concurrent=8`, `reserve_gib=100`, `capacity_gib=500`, `min_seeders=2`, `min_leechers=3`, `only_free=true`, `promotions=["FREE"]`, `observe_hours=6`, `low_upload_kib=32`, `auto_delete=false`, `delete_data=false`. No more tasks are added when all unfinished tasks in the selected downloader (including manual, paused and queued tasks) reach the concurrency limit. Capacity is calculated from the full sizes of torrents owned by this automation; the disk budget reserves remaining space for all unfinished tasks. Candidates prioritize leecher count, then the demand-to-supply ratio. At most one is added per run to prevent accumulation.

Non-FREE torrents are allowed only when `only_free=false`, `promotions` explicitly includes them, and the current M-Team API response returns `vip=true` with a verifiable future VIP expiration. Expiration, a missing value or a parsing failure automatically falls back to FREE; no torrent is added if less than one minute of VIP time remains at submission. Current promotion status is checked again before addition. This rule controls admission of new tasks only and does not guarantee exempt download traffic throughout the download. Torznab does not support allowing non-free torrents based on membership; only explicit `downloadvolumefactor=0` counts as FREE (download traffic exemption). Missing promotion information is not inferred as FREE. FREE candidates still require evidence of seeder and leecher counts.

qBittorrent's free-disk API covers only its actual default download directory, so automation `save_path` must match that directory; free space from another mount cannot substitute for it. Transmission uses the `free-space` API for the specified directory. Before addition, the budget is recalculated using the actual total size from torrent metadata, and free space is read a second time.

## Protection and Limitations

Before addition, torrent metadata is parsed for the info hash, existing downloader tasks are checked, and a UUID operation ticket is persisted; a unique tag associates the new task. Titles are not used for matching, existing tasks are not adopted, and a torrent with an existing hash is not added. Uncertain additions/deletions are never automatically resent, including after restart. The next run performs read-only verification: a late addition result is recorded only when the hash, unique tag and post-submission addition time all match; deletion is recorded only after confirming that the task no longer exists. Continued uncertainty blocks further additions to that downloader and records `needs_review`. Management is allowed only when the bound downloader task ID, hash, tag and addition time all match. Only torrents with a v1 info hash are supported; pure v2 metadata is rejected for automatic addition.

Upload efficiency uses persistent samples to calculate average upload speed over the last hour; a task is not removed without a complete window. Observation lasts at least six hours, and the download must already be complete. A task is retained when either current upload speed or the hourly average reaches `low_upload_kib`. `low_leechers=0` disables the population condition by default. When enabled, all Tracker leecher counts in the complete hourly sample must also be known and no higher than the threshold. Local peer connections are not treated as site-wide demand; Transmission tasks are retained when this evidence is unavailable. Paused, checking, queued, error, permanently protected or ownership-changed tasks are not removed for low speed. At most one task is removed per run. There is no total torrent count limit, but unfinished-task concurrency, capacity and actual free space still apply.

Users select `retention_policy` according to the site's actual rules: `unknown` (default; seeding obligations are unknown, so retain), `no_obligation` (the user confirms no additional seeding obligation), or `seed_hours_ratio` (both `min_seed_hours=72` and `min_ratio=1.0` must be met). The program does not decide whether a site has HR or whether VIP exempts seeding requirements. A snapshot of the rules is saved when each new task enters the pool; changing configuration does not remove protection from older tasks. Resources can be retained individually in the protection list.

Version 1.2 supports deleting data for removed tasks when both `auto_delete=true` and `delete_data=true`. New resources use a dedicated `<save path>/nd-brush/<automation ID>/<info hash>` directory, and their original file list is recorded. Before cleanup, downloader ownership, tags, addition time, path, filenames and sizes are checked, together with symlinks, hard links, mounts across filesystems, extra files and paths shared with other tasks in the same downloader. Any uncertainty causes retention. Data cleanup uses only the downloader's deletion API; NAS directories are not deleted directly. Older tasks without recorded evidence cannot be cleaned up automatically.

Full cleanup requires the service to inspect the same download directory read-only. The bundled downloader installation mode already sets this up:

```yaml
environment:
  ND_BRUSH_VERIFY_ROOT: /downloads
  ND_BRUSH_VERIFY_MOUNT: /managed-downloads
volumes:
  - /your-download-directory:/managed-downloads:ro
```

For an existing downloader, an administrator must configure a read-only verification mount of the same download data before enabling data deletion; the API explicitly rejects deletion without it. Directory mapping proves only the configured storage, not another disk or another NAS.

After deletion, both the downloader task and recorded files must be confirmed absent. Tasks and actual free disk space are then read again to decide whether to add a replacement. HTTP success or a torrent's nominal size is not treated as released space. An uncertain deletion retains its receipt; the next run verifies read-only, without repeating deletion or adding replacements. Retained-data mode continues to count the original disk usage. A previously fully cleaned-up torrent can re-enter the pool only when its current leecher count and demand-to-supply ratio are both better than at its previous admission; a fixed cooldown does not grant readmission.

SQLite WAL, in-process locking, a single-scheduler lease and a unique active-run constraint per task control concurrency. Runs left after restart are marked `interrupted`; uncertain writes and daily check-in tickets are retained. Loss of the scheduler lease stops further actions. Logs do not store cookies, API keys, torrent download URLs or original site response bodies.

## Verification

`python -m unittest discover -s tests -v` includes real local HTTP adapter tests and background-thread/SQLite tests covering asynchronous responses, offline phones, ownership after restart, duplicate UUIDs, concurrency quotas, VIP expiration fallback, promotion changes, disk budgets, unknown obligations, manual-task protection, low-efficiency sample windows and uncertain writes. Tests do not use real site cookies/API keys or run actual automated torrent downloading/seeding. Linux installer tests should run separately in Linux staging; they explicitly skip on Windows.

Rules come from the product's local conservative policy, not promises made by sites. On 2026-10-06, [M-Team official announcements](https://t.me/s/M_Team) were checked: the site had published 72-hour long-term seeding-rate and seven-day average seeding metrics. This is not proof of exemption from HR/seeding requirements. The [official FAQ](https://wiki.m-team.cc/zh-tw/faq) did not provide readable provisions during that access, so “no HR” or “VIP exempts all obligations” is not hard-coded.
