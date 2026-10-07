# 后台自动化 API

所有地址位于 `/api/v1`，要求现有登录会话。任务在 NAS 服务中运行，手机关闭不影响调度。默认不创建、不启用任何任务，不读取旧容器或旧配置。

## 接口

| 方法 | 路径 | 内容 |
|---|---|---|
| GET / POST | `/automations` | 列表 / 创建任务，返回 `{ok,items}` / `{ok,item}` |
| GET / PATCH / DELETE | `/automations/{id}` | 读取 / 更新 / 停用并删除配置（保留审计和归属记录） |
| POST | `/automations/{id}/run` | `{request_id: UUID, dry_run: true}`，返回 `{ok,run_id,status}`；同 UUID 不重复执行 |
| POST | `/automations/{id}/stop` | 取消运行并设置 `enabled=false` |
| GET | `/automations/{id}/logs?limit=50` | `{ok,items}`，最近运行与脱敏结果 |
| GET | `/automations/{id}/owned` | `{ok,items}`，本任务添加且有持久归属证据的资源 |
| GET / POST | `/automations/{id}/protections` | 永久保护列表 / 添加 `{info_hash,reason}` |
| DELETE | `/automations/{id}/protections/{info_hash}` | 取消显式保护（仍保留 HR、未知义务等其他保护） |
| GET | `/automation-runs/{run_id}` | `{ok,item}`，含状态、时间和结果 |

创建和更新直接提交配置字段。返回 `item` 包含配置、`next_run`（Unix 秒）、`last_status`、`last_run_at`（Unix 秒，未运行时 null）、`has_cookie/has_headers_json/has_request_body`；不返回 Cookie、请求头和正文。PATCH 空认证字段保留已保存值。`kind` 创建后不可修改。`run` 默认是只读预演；真实运行要求先启用任务。停止确认后不会发起后续写操作；已发出的请求会完成或记录为不确定。HTTP 请求只登记运行，后台执行，不等待站点响应。

创建 `POST /automations` 支持可选 `request_id: UUID`。客户端应为一次创建保留同一 UUID 和相同请求内容，结果不确定时复用，不能换 UUID 重新创建。同 UUID、同配置返回第一次创建的公开 `item` 回执；相同 UUID、不同配置返回 `409 REQUEST_ID_CONFLICT`。回执与任务配置在同一 SQLite 事务保存，服务重启后仍有效；任务删除后重放原请求不会重建。旧客户端不传此字段仍可创建，但不享有创建去重。PATCH 不使用这个创建回执。

运行状态：`queued`、`running`、`completed`、`failed`、`cancelled`、`interrupted`、`needs_review`。运行对象包含 `id,automation_id,generation,dry_run,scheduled,status,created_at,started_at,finished_at,result`；`scheduled` 是只读布尔值，区分后台计划与手动运行，任务初始 `last_status=idle`。`result.reason` 表达准入原因，`result.retention` 数组记录逐个保留原因，不表示已经删除。`owned` 对象为 `automation_id,downloader_id,info_hash,task_id,marker,added_at,size,obligations,state`；`state` 是 `active/removed`。

## 配置

公共字段：`name`、`kind`、`enabled=false`。签到和账户检查使用北京时间每日随机窗口 `window_start="08:00"`、`window_end="10:00"`，时间在 SQLite 中持久保存，重启不会重新抽签。每个北京时间自然日最多一个实际签到尝试；不确定结果不自动重试。

自动计划只在当前自然日的 `[window_start, window_end)` 内发起请求。停机后恢复：当前窗口前安排当天窗口，窗口内可补跑，窗口后安排次日窗口，绝不深夜补发早晨任务。已排队的自动任务在执行前再次检查；错过窗口时记录 `result.reason="outside_window"`，不占用当天签到票据。旧版本遗留的队列来源未知时，保守按自动计划窗口约束迁移。用户明确点击真实“立即运行”属于手动请求，可以在窗口外执行，仍受每日一次票据限制。

- `kind="hdfans_signin"`：`cookie` 必填，只访问固定 `https://hdfans.org/attendance.php`。成功、已签到、Cookie 失效、防护/验证码、未知页面分别记录。禁止重定向，不处理或绕过验证码。更换 Cookie 后翌日生效；当天失败须在站点人工核查。
- `kind="http_signin"`：自定义 HTTP 签到，无需先创建搜索站点。`signin_url` 为最终签到地址；`method=GET/POST`；`request_format=form/json/text`。`cookie`、`headers_json`、`request_body` 可选并加密保存，不回显。请求头使用 JSON 对象；form/json 正文使用 JSON 对象；GET 参数也填在正文栏，不能直接写进地址。`success_contains` 必填，`already_contains/failure_contains` 可空，`expected_status=200`。只有状态符合预期且正文匹配成功或已签到文字才确认成功；失败标志优先。公网要求 HTTPS；局域网 HTTP 须使用数字地址。禁止重定向、脚本、验证码处理及自动重试。需要动态 CSRF、网页登录流程或验证码的站点，尚不能用单次 HTTP 模板完成。预演不发送签到请求，只检查配置；真实验证会占用当天一次票据。
- `kind="mteam_check"`：`site_id` 指向 M-Team。只调用账户 API 检查连接与 VIP 到期时间；不实现网页登录、不宣称签到或保号。
- `kind="brush"`：`site_id`（M-Team 或 Torznab）、`downloader_id`、`save_path`（默认下载器默认路径）、`interval_minutes=10`（2–1440）；`concurrent=8`、`reserve_gib=100`、`capacity_gib=500`、`min_seeders=2`、`min_leechers=3`、`only_free=true`、`promotions=["FREE"]`、`observe_hours=6`、`low_upload_kib=32`、`auto_delete=false`、`delete_data=false`。所有下载器未完成任务（包括手动、暂停、排队）达到并发上限时，不再添加。容量按此任务持有种子的完整大小计算；磁盘预算扣除全部未完成任务剩余空间。优先下载人数，其次供需比；一次最多添加一个，避免堆积。

非 FREE 仅在 `only_free=false`、`promotions` 显式选择且 M-Team API 当次返回 `vip=true` 和可验证的未来 VIP 到期时间时允许；到期、未返回或解析失败自动回落 FREE，提交时剩余 VIP 时间不足一分钟也不添加。新增前重新核实当前促销。此规则仅控制新任务准入，不承诺下载全过程免流量。Torznab 不支持以会员身份放开非免费；只有明确 `downloadvolumefactor=0` 才视为免费，缺失促销信息不推断免费。免费候选仍须有做种人数/下载人数证据。

qBittorrent 的空闲磁盘接口只覆盖其真正默认下载目录，因此自动化 `save_path` 必须与 qBittorrent 的默认目录一致；不能拿另一个挂载的剩余空间代替。Transmission 使用指定目录的 `free-space` 接口。新增前按种子元数据实际总大小重算预算，并第二次读取空间。

## 保护与限制

新增前解析种子信息哈希，核查下载器已有任务，再持久登记 UUID 操作票据，以唯一标签关联新任务。不使用标题匹配，不接管原有任务；相同哈希已有任务不添加。不确定新增/删除不会自动重发，也不会通过重启绕过。下次运行只读核验：只有哈希、唯一标签和提交后添加时间全部吻合，才补记迟到的新增结果；删除则只能通过确认任务已不存在补记。仍不确定时阻止该下载器继续新增，记录 `needs_review`。绑定后的下载器任务编号、哈希、标签与添加时间全部匹配才允许管理。仅支持具有 v1 信息哈希的种子；纯 v2 元数据拒绝自动添加。

上传效率用持久样本计算最近一小时平均上传速度；缺少完整窗口不淘汰。至少观察六小时，且必须已经下载完成。当前上传或小时均速达到 `low_upload_kib` 时保留。`low_leechers=0` 默认关闭人数条件，开启后还要求完整一小时样本中的 Tracker 下载人数均已知且不高于阈值；不把本机连接人数当作全站需求，Transmission 无此人数证据时保留。暂停、校验、排队、错误、永久保护、归属变化的任务不会按低速清理。每轮最多淘汰一个，没有总种子数量上限，仍受未完成并发、容量与真实剩余空间约束。

`retention_policy` 由用户按站点实际规则选择：`unknown`（默认，保种义务未知，保留）、`no_obligation`（用户确认没有额外保种义务）、`seed_hours_ratio`（同时满足 `min_seed_hours=72` 和 `min_ratio=1.0`）。程序不替用户判断站点是否有 HR 或 VIP 是否豁免保种。规则在每个新任务入池时保存快照；更改配置不会解除旧任务的保护。可以在保护名单中单独保留资源。

1.2 支持 `auto_delete=true` 且 `delete_data=true` 时清理已淘汰任务的数据。新增资源使用 `<保存路径>/nd-brush/<自动任务编号>/<信息哈希>` 专属目录，并登记原始文件清单。清理前核查下载器归属、标签、添加时间、路径、文件名与大小，并检查符号链接、硬链接、跨盘挂载、多余文件及同下载器其他任务共享的路径；有一项不确定就保留。只通过下载器的删除接口清理数据，不直接删除 NAS 目录。旧任务缺少登记证据时不能自动清理。

完整清理要求服务能只读查看同一下载目录。内置下载器的安装模式已设置：

```yaml
environment:
  ND_BRUSH_VERIFY_ROOT: /downloads
  ND_BRUSH_VERIFY_MOUNT: /managed-downloads
volumes:
  - /你的实际下载目录:/managed-downloads:ro
```

接入现有下载器时，需要管理员把其下载目录配置为相同数据的只读验证挂载，再启用删除数据；未配置时接口明确拒绝。目录映射只能证明配置的存储，不能为另一块盘或另一台 NAS 提供证明。

删除后同时确认下载器任务已消失、登记文件已消失，再重新读取任务和真实剩余磁盘空间，决定是否补种。不会把 HTTP 成功、种子标称大小当作已释放空间。不确定删除保留回执，下一轮只读核验，禁止重复删除和继续补种。保留数据模式仍计入原占用。以前已完整清理的种子可以重新入池，但要求当前下载人数及供需比都优于上次入池，不按固定冷却时间放行。

SQLite WAL、进程内锁、单调度器租约、每任务唯一活动运行约束负责并发。重启后遗留运行标为 `interrupted`，未确定的写操作和每日签到票据保留。调度租约丢失时停止后续动作。日志不保存 Cookie、API Key、种子下载 URL 或站点响应原文。

## 验证

`python -m unittest discover -s tests -v`：包括真实本地 HTTP 适配器测试与后台线程/SQLite 测试，覆盖异步响应、离线手机场景、重启后归属、重复 UUID、并发配额、VIP 到期回落、促销变化、磁盘预算、未知义务、人工任务保护、低效样本窗口和不确定写操作。测试不使用真实站点 Cookie/API Key，不运行真实刷流。Linux 安装脚本测试应在 Linux staging 单独运行，Windows 下会明确跳过。

规则来源于产品本地保守策略，并非站点承诺。2026-10-06 核查 [M-Team 官方公告](https://t.me/s/M_Team)：官方已发布 72 小时长期做种率与 7 天平均保种指标；这不构成免除 HR/保种要求的证明。[官方 FAQ](https://wiki.m-team.cc/zh-tw/faq) 未向本次访问提供可读取条文，故不硬编码“无 HR”或“VIP 免除全部义务”。
