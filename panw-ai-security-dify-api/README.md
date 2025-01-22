# About

This is a simple Dify API-based extension that can provide LLM input and output security using Palo Alto AI Runtime Security.

For more detailes please see:

- [API-based Extension](https://docs.dify.ai/advanced/extension/api_based_extension) in [Dify](https://dify.ai/)

- [AI Runtime Security: API Intercept Overview](https://docs.paloaltonetworks.com/ai-runtime-security/activation-and-onboarding/ai-runtime-security-api-intercept-overview)



# How to Use

This project needs to run on Cloudflare, so please prepare a Cloudflare account in advance.

The general process:

- Prerequisites: Install npm and wrangler (Cloudflare's CLI plugin)
- Download the project files, modify the **Token** in `wrangler.toml` and the **Key** and **Profile** in `src/index.ts`
- Deploy the project to Cloudflare

## Prerequisites

**Install wrangler:**

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



Keep everything else unchanged for now.

## Debug

Run the following commands for local debugging:

```shell
cd panw-ai-security-dify-api
npm install
npm run dev
```

## Deploy to Cloudflare

Run the following commands to deploy to Cloudflare:

```shell
cd panw-ai-security-dify-api
npm install
# When running the following command for the first time, it will automatically open the system's default browser for Cloudflare authentication. After authentication is complete, it will display "Successfully logged in." Then the system will automatically deploy the Workers
npm run deploy
```
