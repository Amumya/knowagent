# 标注工作表（由 cite_helper.py 生成）

> 用法：每条候选下方是原文片段。请在 CSV 里补 `question` / `answer_keypoints` /
> `kp_keywords` / `gold_span_ids`，并把要点对应的原文行复制到 `gold_spans/<qid>.txt`。

---

## (未编号) · multi_hop

- 来源文档：`en/latest/plugins/openid-connect.md`
- 候选章节：No Session State Found
- 该文档引用了：`../deployment-modes.md|../plugin-develop.md|../terminology/secret.md|../tutorials/keycloak-oidc.md`  ← 多跳题的第二跳候选
- 正文字数：2944

**原文（openid-connect.md，从第 481 行起）**

```markdown
 481| ### No Session State Found
 482| 
 483| If you encounter a `500 internal server error` with the following message in the log when working with [authorization code flow](#authorization-code-flow), there could be a number of reasons.
 484| 
 485| ```text
 486| the error request to the redirect_uri path, but there's no session state found
 487| ```
 488| 
 489| #### 1. Misconfigured Redirection URI
 490| 
 491| A common misconfiguration is to configure the `redirect_uri` the same as the URI of the Route. When a user initiates a request to visit the protected resource, the request directly hits the redirection URI with no session cookie in the request, which leads to the no session state found error.
 492| 
 493| To properly configure the redirection URI, make sure that the `redirect_uri` matches the Route where the Plugin is configured, without being fully identical. For instance, a correct configuration would be to configure `uri` of the Route to `/api/v1/*` and the path portion of the `redirect_uri` to `/api/v1/redirect`.
 494| 
 495| You should also ensure that the `redirect_uri` includes the scheme, such as `http` or `https`.
 496| 
 497| It is recommended to set `redirect_uri` to an absolute URL (scheme and host). When it is left unset or set to a relative path, the host is assembled from request headers, so a forged `Host` or `Forwarded` header can point the redirect URI at an attacker-controlled host. An absolute `redirect_uri` bypasses header-based host assembly entirely.
 498| 
 499| #### 2. Missing Session Secret
 500| 
 501| If you deploy APISIX in the [standalone mode](../deployment-modes.md#standalone-mode), make sure that `session.secret` is configured.
 502| 
 503| User sessions are stored in browser as cookies and encrypted with session secret. The secret is automatically generated and saved to etcd if no secret is configured through the `session.secret` attribute. However, in standalone mode, etcd is no longer the configuration center. Therefore, you should explicitly configure `session.secret` for this Plugin in the YAML configuration center `apisix.yaml`.
 504| 
 505| #### 3. Cookie Not Sent or Absent
 506| 
 507| Check if the [`SameSite`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Set-Cookie#samesitesamesite-value) cookie attribute is properly set (i.e. if your application needs to send the cookie cross sites) to see if this could be a factor that prevents the cookie being saved to the browser's cookie jar or being sent from the browser.
 508| 
 509| #### 4. Upstream Sent Too Big Header
 510| 
 511| If you have NGINX sitting in front of APISIX to proxy client traffic, see if you observe the following error in NGINX's `error.log`:
 512| 
 513| ```text
 514| upstream sent too big header while reading response header from upstream
 515| ```
 516| 
 517| If so, try adjusting `proxy_buffers`, `proxy_buffer_size`, and `proxy_busy_buffers_size` to larger values.
 518| 
 519| Another option is to configure the `session_contents` attribute to adjust which data to store in session. For instance, you can set `session_contents.access_token` to `true`.
 520| 
 521| #### 5. Invalid Client Secret
 522| 
 523| Verify if `client_secret` is valid and correct. An invalid `client_secret` would lead to an authentication failure and no token shall be returned and stored in session.
 524| 
 525| #### 6. PKCE IdP Configuration
 526| 
 527| If you are enabling PKCE with the authorization code flow, make sure you have configured the IdP client to use PKCE. For example, in Keycloak, you should configure the PKCE challenge method in the client's advanced settings:
 528| 
 529| ![PKCE IdP Configuration](https://static.api7.ai/uploads/2026/04/21/YhDIbbBO_8-pkce-idp-configuration.webp)
```

---

## (未编号) · multi_hop

- 来源文档：`en/latest/grpc-proxy.md`
- 候选章节：Example
- 该文档引用了：`certificate.md`  ← 多跳题的第二跳候选
- 正文字数：1850

**原文（grpc-proxy.md，从第 32 行起）**

```markdown
  32| ### Example
  33| 
  34| #### create proxying gRPC route
  35| 
  36| Here's an example, to proxying gRPC service by specified route:
  37| 
  38| * attention: the `scheme` of the route's upstream must be `grpc` or `grpcs`.
  39| * attention: APISIX use TLS‑encrypted HTTP/2 to expose gRPC service, so need to [config SSL certificate](certificate.md)
  40| * attention: APISIX also support to expose gRPC service with plaintext HTTP/2, which does not rely on TLS, usually used to proxy gRPC service in intranet environment
  41| * the grpc server example：[grpc_server_example](https://github.com/api7/grpc_server_example)
  42| 
  43| :::note
  44| You can fetch the `admin_key` from `config.yaml` and save to an environment variable with the following command:
  45| 
  46| ```bash
  47| admin_key=$(yq '.deployment.admin.admin_key[0].key' conf/config.yaml | sed 's/"//g')
  48| ```
  49| 
  50| :::
  51| 
  52| ```shell
  53| curl http://127.0.0.1:9180/apisix/admin/routes/1 -H "X-API-KEY: $admin_key" -X PUT -d '
  54| {
  55|     "methods": ["POST", "GET"],
  56|     "uri": "/helloworld.Greeter/SayHello",
  57|     "upstream": {
  58|         "scheme": "grpc",
  59|         "type": "roundrobin",
  60|         "nodes": {
  61|             "127.0.0.1:50051": 1
  62|         }
  63|     }
  64| }'
  65| ```
  66| 
  67| #### testing HTTP/2 with TLS‑encrypted
  68| 
  69| Invoking the route created before：
  70| 
  71| ```shell
  72| $ grpcurl -insecure -import-path /pathtoprotos  -proto helloworld.proto  -d '{"name":"apisix"}' 127.0.0.1:9443 helloworld.Greeter.SayHello
  73| {
  74|   "message": "Hello apisix"
  75| }
  76| ```
  77| 
  78| > grpcurl is a CLI tool, similar to curl, that acts as a gRPC client and lets you interact with a gRPC server. For installation, please check out the official [documentation](https://github.com/fullstorydev/grpcurl#installation).
  79| 
  80| This means that the proxying is working.
  81| 
  82| #### testing HTTP/2 with plaintext
  83| 
  84| By default, the APISIX only listens to `9443` for TLS‑encrypted HTTP/2. You can support HTTP/2 with plaintext via the `node_listen` section under `apisix` in `conf/config.yaml`:
  85| 
  86| ```yaml
  87| apisix:
  88|     node_listen:
  89|         - port: 9080
  90|         - port: 9081
  91|     enable_http2: true
```
