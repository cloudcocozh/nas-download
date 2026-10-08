# Standalone Sites and Search API

[中文](SITES.md) | [English](SITES_EN.md)

All endpoints use the service’s existing authentication, security request headers and error format, with the `/api/v1` prefix. The service does not depend on NAS-tools, import old accounts or credentials, search automatically, or perform automated torrent downloading/seeding automatically.

- `GET /sites` → `{ok,items:[{id,name,type,url,enabled,has_api_key}]}`.
- `POST /sites` → `{name,type:"mteam"|"torznab",url,api_key,enabled:true}`; returns `{ok,item}`. Maximum 16 sites. Saving only validates configuration; actual searches validate credentials.
- `PATCH /sites/:id` accepts the same configuration fields. An omitted or empty `api_key` preserves the original value. `DELETE /sites/:id` deletes connection configuration without changing download tasks.
- `POST /searches` → `{query,site_ids?:[id],page:1,limit:30}`; returns `{ok,search_id}`. Without site_ids, all enabled sites are searched. Only the specified single page is fetched per site; limit is 1–100.
- `GET /searches/:id?offset=0&limit=100` → `{ok,search_id,status:"running"|"completed"|"cancelled",items,total,site_totals:{site_id:total site matches},errors:[{site_id,code,error}],page,limit}`. total is the number of results fetched so far. For the next page, create another search with page incremented by one. Failed sites are explicitly listed in errors; failures must not appear as successful empty searches.
- `DELETE /searches/:id` → `{ok,status:"cancelled"}`. Stops accepting results immediately; HTTP requests already sent finish within at most 12 seconds. Clients stop polling. Cancel the previous search before creating a new one to prevent old results overwriting new results. At most four searches may run at once. Records remain valid for approximately ten minutes; only the device that created a search may read/cancel it.
- Result fields: `{id,site_id,site_name,name,subtitle,size,seeders,leechers,promotion,published}`. API keys, passkeys and download URLs containing credentials are not returned.
- `GET /sites/:sid/torrents/:tid` → `{ok,item}`. M-Team fetches details (description is plain text; the UI must display it with textContent). Torznab returns search entries within their ten-minute lifetime; expired entries return RESULT_EXPIRED/410.
- `POST /sites/:sid/torrents/:tid/download` → `{request_id:UUID,downloader_id,save_path?,paused?:false}` → `{ok,operation}`. The server fetches the torrent file and submits it to an existing downloader, reusing replay-prevention receipts; uncertain results must not be automatically retried. Downloading is an explicit user action, with no FREE filtering or automated downloading/seeding assumptions.

M-Team addresses are restricted to `https://api.m-team.cc/api` or `https://api.m-team.io/api`. Users create keys under access tokens in the site's control panel. Requests use x-api-key and fixed search/detail/genDlToken routes. Downloads allow only specified official HTTPS domains, without redirects. [Official documentation](https://wiki.m-team.cc/zh-tw/api).

For Torznab, enter the complete API path without query/username/password. Users can connect their own Jackett/Prowlarr deployments; sites such as HDFans are connected through their Torznab interfaces. This does not claim an unverified native HDFans API. Enter the key separately. Searches use t=search/q/offset/limit. Only results whose download URLs share the configured origin are accepted; redirects are not followed. [Specification](https://torznab.github.io/spec-1.3-draft/torznab/Specification-v1.3.html).

API keys and downloader passwords share Fernet encrypted storage and are not exposed in lists, logs or errors. Users may explicitly configure local Torznab endpoints; link-local, multicast, unspecified and metadata targets are prohibited. Validation is repeated for every network request. The entire service is administrator-only and does not provide an anonymous proxy.
