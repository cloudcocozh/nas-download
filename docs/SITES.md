# 独立站点与搜索 API

所有接口采用 PLAN.md 的认证、安全请求头、错误格式和 `/api/v1` 前缀。服务不依赖 NAS-tools，不导入旧账号或凭据，不自动搜索、不自动刷流。

- `GET /sites` → `{ok,items:[{id,name,type,url,enabled,has_api_key}]}`。
- `POST /sites` → `{name,type:"mteam"|"torznab",url,api_key,enabled:true}`；返回 `{ok,item}`。最多 16 个。保存仅校验配置，真实搜索才验证凭据。
- `PATCH /sites/:id` 同配置字段，省略或空 `api_key` 保留原值。`DELETE /sites/:id` 删除接入配置，不修改下载任务。
- `POST /searches` → `{query,site_ids?:[id],page:1,limit:30}`；返回 `{ok,search_id}`。无 site_ids 搜索全部已启用站点，每站仅获取指定一页，limit 1–100。
- `GET /searches/:id?offset=0&limit=100` → `{ok,search_id,status:"running"|"completed"|"cancelled",items,total,site_totals:{site_id:站点匹配总数},errors:[{site_id,code,error}],page,limit}`。total 是当前已获取结果数；下一页重新创建 search，page 加一。失败站点明确进入 errors，不能把故障显示为空搜索成功。
- `DELETE /searches/:id` → `{ok,status:"cancelled"}`。立即停止接纳结果，已发出的 HTTP 请求最多 12 秒收尾；客户端停止轮询。新搜索前取消旧搜索，避免旧结果覆盖新结果。最多四个运行中的搜索；记录约十分钟有效，仅创建该搜索的设备可读取/取消。
- 结果字段 `{id,site_id,site_name,name,subtitle,size,seeders,leechers,promotion,published}`；不返回 API 密钥、passkey、带凭据下载 URL。
- `GET /sites/:sid/torrents/:tid` → `{ok,item}`。M-Team 获取详情（description 为纯文本，UI 必须 textContent 展示）；Torznab 返回十分钟内搜索条目，过期返回 RESULT_EXPIRED/410。
- `POST /sites/:sid/torrents/:tid/download` → `{request_id:UUID,downloader_id,save_path?,paused?:false}` → `{ok,operation}`。服务端获取种子文件后提交已有下载器，沿用防重放回执；uncertain 禁止自动重试。下载为用户主动操作，没有免费筛选或刷流假设。

M-Team 地址仅 `https://api.m-team.cc/api` 或 `https://api.m-team.io/api`，密钥由用户在站点控制台的存取令牌处创建。使用 x-api-key、固定 search/detail/genDlToken 路由；下载只允许指定官方 HTTPS 域名，无重定向。官方说明：https://wiki.m-team.cc/zh-tw/api 。

Torznab 地址填完整 API 路径，不能带 query/用户名/密码。可接用户自行部署的 Jackett/Prowlarr，因此 HDFans 等站点通过其 Torznab 接入；没有冒充未经验证的原生 HDFans API。密钥单独输入。搜索使用 t=search/q/offset/limit；只接收下载 URL 与配置同源的结果，不跟随重定向。标准：https://torznab.github.io/spec-1.3-draft/torznab/Specification-v1.3.html 。

API 密钥与下载器密码共用 Fernet 加密存储，不在列表、日志或错误中输出。配置允许用户显式指定本地 Torznab，禁止链路本地/组播/未指定/元数据目标；每次网络请求重新校验。整个服务仅管理员访问，不提供匿名代理。
