# 本地模型服务外网访问说明

## 当前已接入方案

当前已经为本地模型服务接入了 **Cloudflare Quick Tunnel**，适合立即联调，不需要公网服务器。

- 本地模型地址：`http://127.0.0.1:54862`
- 当前公网地址：`https://acute-sections-proven-schools.trycloudflare.com`
- 健康检查：`https://acute-sections-proven-schools.trycloudflare.com/health`
- 主接口：`POST https://acute-sections-proven-schools.trycloudflare.com/v1/chat/completions`

## 一键启动

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_public_model_tunnel_windows.ps1
```

启动后会输出一个 `https://*.trycloudflare.com` 地址，并写入：

- `logs/cloudflared_quick_tunnel_url.txt`
- `logs/cloudflared_quick_tunnel.err.log`

## 一键停止

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\stop_public_model_tunnel_windows.ps1
```

## 适用场景

- 另一个后端服务不在同一局域网
- 需要快速打通本地模型调用
- 当前以联调、开发、测试为主

## 当前方案的限制

Cloudflare 官方明确说明：

- Quick Tunnel 主要用于快速试验
- 没有可用性保证
- 生产环境建议改为 **Named Tunnel**

如果后面要长期稳定使用，建议升级为以下正式方案之一：

## 更正式的可选方案

### 1. Cloudflare Named Tunnel

适合：

- 你有 Cloudflare 账号
- 最好有自己的域名
- 需要长期稳定地址

优点：

- 地址固定
- 更适合正式环境
- 可以继续叠加 Cloudflare Access 做鉴权

### 2. ngrok

适合：

- 你想快速拿到稳定公网地址
- 愿意注册账号并配置 `authtoken`

优点：

- 上手简单
- 对 HTTP 接口调试友好

### 3. frp

适合：

- 你自己有公网服务器
- 想完全自控

优点：

- 灵活
- 性能和转发策略可控

缺点：

- 需要你自己维护公网机器

## 当前建议

现阶段建议继续使用：

- Quick Tunnel 做联调

后续如果你们要长期给异地服务调用，再切到：

- Cloudflare Named Tunnel

## 官方文档

- Cloudflare Tunnel 下载：<https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/>
- Cloudflare Quick Tunnel：<https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/>
- Cloudflare Named Tunnel：<https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/>
- ngrok 文档：<https://ngrok.com/docs>
