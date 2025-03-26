# 关于

此 Tools 是适配 Dify 0.15 版本的 PANW AI Security Tools，适合于 Dify 企业版用户。



使用方法：

1. 在 Dify 安装目录下找到 `api/core/tools/provider/builtin`，然后将此文件夹放在 builtin 目录中。



示例如下：

```shell
[root@Dify palo_alto_networks_ai_security_api]# pwd
/root/dify/api/core/tools/provider/builtin/palo_alto_networks_ai_security_api

[root@Dify palo_alto_networks_ai_security_api]# ls -l
total 8
drwxr-xr-x. 2 root root   39 Mar 13 05:33 _assets
-rw-r--r--. 1 root root 1100 Mar 13 06:39 palo_alto_networks_ai_security_api.py
-rw-r--r--. 1 root root 2092 Mar 13 05:33 palo_alto_networks_ai_security_api.yaml
drwxr-xr-x. 2 root root   98 Mar 14 05:22 tools
```



2. 修改 Tools 清单

编辑此文件`api/core/tools/provider/_position.yaml`，在最后添加`- palo_alto_networks_ai_security_api`

示例如下：

```shell
[root@Dify dify]# cat api/core/tools/provider/_position.yaml
# 省略
- palo_alto_networks_ai_security_api
```



3. 构建镜像

在 dify 安装目录的 api 下，运行 `docker build . -t dify-api:v0.15.3-panw`封装镜像，取决于网络环境，此步骤可能消耗数分钟。

4. 修改`docker/docker-compose.yaml`文件中 API 服务的 image tag，然后 `docker compose up -d`启动容器。

```shell
[root@Dify docker]# cat docker-compose.yaml|grep -A4 -B4 panw

services:
  # API service
  api:
    image: dify-api:v0.15.5-panw
    restart: always
    environment:
      # Use the shared environment variables.
      <<: *shared-api-worker-env
```

