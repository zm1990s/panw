# 关于

这是一个简单的基于 Dify API 的扩展，它使用 Palo Alto Networks 的 AI Runtime Security 为 LLM 提供输入和输出安全。

更多详细信息请参见：

- [API-based Extension](https://docs.dify.ai/advanced/extension/api_based_extension) in [Dify](https://dify.ai/)

- [AI Runtime Security: API Intercept Overview](https://docs.paloaltonetworks.com/ai-runtime-security/activation-and-onboarding/ai-runtime-security-api-intercept-overview)



# 如何使用

本项目需要需要运行在 Cloudflare 中，因此请提前准备好 Cloudflare 账户。



大致的流程：

- 前提条件：安装 npm、wrangler（Cloudflare 的 CLI 插件）
- 下载项目文件，修改`wrangler.toml`中的 Token 以及`src/index.ts`中的 Key 和 Profile
- 将项目部署到 Cloudflare

## 前提条件

**安装 weangler：**

```shell
npm install wrangler --save-dev
```

```shell
npm WARN deprecated sourcemap-codec@1.4.8: Please use @jridgewell/sourcemap-codec instead
npm WARN deprecated rollup-plugin-inject@3.0.2: This package has been deprecated and is no longer maintained. Please use @rollup/plugin-inject.

added 68 packages, and audited 71 packages in 48s

11 packages are looking for funding
  run `npm fund` for details

found 0 vulnerabilities
```

其他暂时保持不变。

## 本地部署调试

运行下列命令进行本地调试：

```shell
cd panw-ai-security-dify-api
npm install
npm run dev
```

## 部署到 Cloudflare

运行下列命令进行部署到 Cloudflare：

```shell
cd panw-ai-security-dify-api
npm install
# 在首次运行下列命令时，会自动打开系统默认浏览器进行 Cloudflare 认证，认证完成后会显示 Successfully logged in。然后系统会自动部署 Workers
npm run deploy
```

