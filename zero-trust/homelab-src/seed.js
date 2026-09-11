const ZONES = [
  {id:'identity',name:'身份与设备信任',subnet:'全局信任配套 · VLAN 40',color:'#294a73',fill:'#edf2f8',nodeFill:'#fbfcfe',border:'#d6e0ec',nodeBorder:'#c3cfdf',x:16,y:20,w:1466,h:188,cols:5,role:'support'},
  {id:'client',name:'终端',subnet:'VLAN 20 / 25 / 60',color:'#506c86',fill:'#f0f3f6',nodeFill:'#fcfdfe',border:'#d7dfe6',nodeBorder:'#cbd5df',x:16,y:248,w:470,h:444,cols:2,role:'core'},
  {id:'edge',name:'网络与安全接入',subnet:'VLAN 30 · 分支 / SASE',color:'#81651b',fill:'#faf6e7',nodeFill:'#fffef8',border:'#e6debd',nodeBorder:'#d6c893',x:514,y:248,w:470,h:444,cols:2,role:'core'},
  {id:'workload',name:'应用与工作负载',subnet:'VLAN 50 · 私有应用 / K8S / 云 / SaaS',color:'#397881',fill:'#edf5f6',nodeFill:'#fbfdfd',border:'#d1e2e4',nodeBorder:'#bad2d5',x:1012,y:248,w:470,h:444,cols:2,role:'core'},
  {id:'cnapp',name:'CNAPP 云安全配套',subnet:'已有授权 · 云 API / 工作负载 / CI / AI 数据源',color:'#367257',fill:'#edf5f0',nodeFill:'#fbfdfb',border:'#d1e1d6',nodeBorder:'#bbd1c3',x:16,y:724,w:926,h:316,cols:4,role:'support'},
  {id:'ai',name:'AI 与安全分析配套',subnet:'AI 实验 VLAN 55 · 隔离分析 VLAN 90',color:'#79617e',fill:'#f4f1f6',nodeFill:'#fefcfe',border:'#dfd5e3',nodeBorder:'#d2c5d7',x:1012,y:724,w:470,h:188,cols:2,role:'support'},
  {id:'infra',name:'管理平面与恢复',subnet:'VLAN 10 · 10.10.10.0/24',color:'#647078',fill:'#f3f4f5',nodeFill:'#fdfdfd',border:'#dedfe1',nodeBorder:'#cdd2d6',x:1012,y:936,w:470,h:188,cols:2,role:'support'},
  {id:'ops',name:'安全运营与持续验证',subnet:'全局运营配套 · VLAN 70',color:'#367257',fill:'#edf5f0',nodeFill:'#fbfdfb',border:'#d1e1d6',nodeBorder:'#bbd1c3',x:16,y:1156,w:1466,h:188,cols:5,role:'support'}
];
const STAGES = ['基础网络','身份与终端','应用与运营','AI 与扩展'];
function seedNode(id,name,zone,kind,os,ip,cpu,ram,disk,stage,services,agents,purpose,verify,notes='',optional=false) {
  return {id,name,zone,kind,os,ip,cpu,ram,disk,stage,services,agents,purpose,verify,notes,tags:[],optional,status:'planned',host:['external','saas'].includes(kind)?'外部服务':kind==='physical'?'物理主机':'pve-01',x:0,y:0};
}
const SEED_NODES = [
  seedNode('win','win11-managed','client','vm','Windows 11 Pro / Evaluation','10.10.20.11',4,8,80,2,'Edge 管理策略；VS Code；测试用户 alice','Wazuh agent；Sysmon；osquery / Fleet；WireGuard 客户端（互斥选择商业接入 Agent）','托管办公终端；设备基线、事件采集、扩展白名单、远程接入','禁用终端 agent 后触发失联告警；用 EICAR 测试 AV；检查登录审计','启用虚拟 TPM 2.0 / UEFI；Windows 需许可。Wazuh 不等同于完整 EDR。'),
  seedNode('dev','ubuntu-dev','client','vm','Ubuntu 24.04 LTS','10.10.20.12',2,4,40,2,'VS Code；Git；Python / Node；开发用 MCP client','Wazuh agent；osquery；WireGuard；auditd','开发终端；包、IDE 扩展及 MCP 清单；最小权限开发','未知扩展被策略拒绝；依赖变更进入 SBOM；sudo 事件进入 SIEM'),
  seedNode('byod','byod-unmanaged','client','vm','Ubuntu Desktop / 浏览器','10.10.25.11',2,4,40,2,'Firefox；受限来宾用户','无管理 Agent','模拟第三方和非受管设备，仅经身份代理访问指定 Web 应用','访问获准 Web 应用成功；直接访问服务器 SSH 和管理网失败'),
  seedNode('iot','iot-sim','client','vm','Debian minimal','10.10.60.11',1,1,8,1,'Mosquitto client；模拟遥测程序','无终端 Agent；由网络探针观测','模拟无 Agent 的 IoT 设备，限制 DNS / NTP / MQTT 目的地址','向允许的 MQTT 服务发数据成功；访问身份和管理网被阻断','模拟 IoT，不代表真实 OT 协议覆盖。'),
  seedNode('branch','branch-router','client','router','OpenWrt x86','10.20.0.1',0,0,0,1,'WireGuard site-to-site；分支 10.20.0.0/24','Syslog 转发','模拟异地分支；通过独立隧道访问指定应用网段','分支到应用网可达；到管理 VLAN 10 不可达','使用独立虚拟交换机，避免与家庭 LAN 地址冲突。'),
  seedNode('fw','edge-fw','edge','firewall','OPNsense','10.10.30.1',0,0,0,1,'VLAN routing；NAT；WireGuard；Suricata IPS；IP denylist','Syslog；NetFlow exporter','所有实验 VLAN 三层网关；缺省拒绝跨域访问；远程与站点接入','每个 VLAN .1 为网关；从 BYOD 到管理网的 deny 记录进入 SIEM','WAN + VLAN trunk 至少两张 vNIC；IPS 吞吐需实测。不得桥接到公网。'),
  seedNode('dns','dns-filter','edge','vm','Debian 12','10.10.30.53',1,1,8,1,'Unbound；AdGuard Home；NTP','Wazuh agent；DNS query log','内部 *.lab.home.arpa 解析；域名拦截；统一时间同步','测试域名被阻断并产生日志；各 VM 时钟偏差小于 1 秒','DNS 列表过滤不等同于商业 DNS 隧道 / DGA 检测。'),
  seedNode('access','access-gateway','edge','vm','Ubuntu 24.04 LTS','10.10.30.10',2,2,20,2,'Pomerium；OIDC；反向代理；私有服务路由','Wazuh agent；OpenTelemetry collector','用身份感知代理发布 Web 应用；远程隧道由 edge-fw 提供','MFA 后 alice 可访问应用；contractor 被管理员路由拒绝','OIDC 代理只覆盖支持的协议，设备姿态联动需另行接入策略。'),
  seedNode('proxy','web-proxy','edge','vm','Debian 12','10.10.30.20',2,2,20,3,'Squid；PAC；域名 ACL；测试文件的 ClamAV 扫描','Wazuh agent；代理访问日志','显式代理与基础 URL 过滤；演示隔离测试内容的外发规则','PAC 引导 HTTP/S 流量到代理；禁用直连后验证策略不能绕过','HTTPS CONNECT 默认看不到正文；内容级 DLP 需要受信测试 CA、TLS 解密和额外集成。'),
  seedNode('sandbox','sandbox-lab','edge','vm','隔离分析 VM','10.10.90.10',4,8,80,4,'CAPE sandbox（可选）；隔离分析网 VLAN 90','行为采集器；无生产凭据','演示文件动态分析与结果关联','仅使用无害样本验证分析链路；确认到家庭 LAN / 管理网的流量被拒绝','需嵌套虚拟化与单独分析 guest，额外资源未计入；不提供全球威胁情报。',true),
  seedNode('idp','identity-01','identity','vm','Ubuntu 24.04 LTS','10.10.40.10',2,4,40,2,'Keycloak；PostgreSQL；OIDC / SAML；TOTP / WebAuthn','Wazuh agent；登录事件 webhook','员工、外包和 Agent 服务账号；SSO / MFA；短时令牌与 scope','MFA 强制；禁用用户后会话失效；Agent token 无管理员权限'),
  seedNode('ad','ad-lab','identity','vm','Windows Server Evaluation','10.10.40.11',2,4,60,2,'Active Directory DS；DNS；GPO；受限测试域','Wazuh agent；Sysmon；Windows 事件采集','域加入与 GPO；为身份检测提供 Windows 身份信号','失败登录和特权组变更进入 SOC；GPO 按 OU 生效','仅实验域；Windows 需授权；ITDR 规则和响应需自建。',true),
  seedNode('pam','bastion-01','identity','vm','Ubuntu 24.04 LTS','10.10.40.20',2,4,40,2,'Teleport Community / SSH CA；OIDC 依版本许可评估','Wazuh agent；会话录制','短期 SSH 证书、跳板接入、会话审计','直连 SSH 被拒；证书过期后不能登录；会话可回放','高级审批、企业 SSO、完整 JIT / ZSP 需确认版本与许可。'),
  seedNode('secrets','trust-services','identity','vm','Ubuntu 24.04 LTS','10.10.40.30',2,2,20,2,'OpenBao；SPIRE server；内部 CA','Wazuh agent；SPIRE agent（仅主机工作负载）','集中 Secret、轮转、工作负载身份；k3s 节点另装 SPIRE agent','SVID 自动轮转；应用只能读所属 Secret；审计事件进入日志'),
  seedNode('fleet','device-control','identity','vm','Ubuntu 24.04 LTS','10.10.40.40',2,2,30,2,'Fleet；osquery 管理；设备与扩展清单','Wazuh agent','设备健康查询与软件清单；扩展 / MCP 来源和权限评估','枚举 win / dev 设备清单；不合规状态发往策略 webhook','完整 MDM、非二进制行为检测、Koi 同类能力需要其他方案或商业许可。'),
  seedNode('kcp','k3s-control','workload','vm','Ubuntu 24.04 LTS','10.10.50.10',2,4,40,3,'k3s server；API audit；默认拒绝 NetworkPolicy','Wazuh agent；SPIRE agent；Falco（按内核兼容性安装）','Kubernetes 控制平面；RBAC 与审计','匿名 API 请求失败；限制 service account；审计日志进入 SOC','单控制节点无 HA；使用默认网络组件时先验证 NetworkPolicy 执行。'),
  seedNode('worker','k3s-worker','workload','vm','Ubuntu 24.04 LTS','10.10.50.11',4,8,100,3,'k3s agent；测试应用；MinIO；MQTT；测试数据集','Wazuh agent；SPIRE agent；Falco；Trivy Operator','容器运行时保护、镜像扫描、数据访问权限与服务身份','跨 namespace 非授权访问失败；Falco 测试事件进入 SOC','应用为容器共用此 VM 资源；MinIO 使用虚构敏感数据。'),
  seedNode('apps','private-apps','workload','vm','Ubuntu 24.04 LTS','10.10.50.20',2,4,50,3,'Gitea；测试 Web / API；内部文件服务','Wazuh agent；OpenTelemetry collector','私有业务资源；员工 / 承包商分权访问；审计数据源','OIDC 登录；外包用户无代码仓库管理权限；应用不可绕过网关直达'),
  seedNode('ci','build-security','workload','vm','Ubuntu 24.04 LTS','10.10.50.30',4,6,80,3,'Gitea runner；Trivy；Checkov；Gitleaks；Syft；Dependency-Track','Wazuh agent；runner 专用服务账号','代码、IaC、容器及 SBOM 检查；模型和 MCP 清单准入','含测试 Secret 或高危依赖的提交阻断；生成 SBOM 和审计记录','扫描器集成需 CI job；供应链网关与行为防护仅局部模拟。'),
  seedNode('cloud','cloud-account','workload','external','可选 AWS / Azure / GCP 测试账号','独立云 VPC',0,0,0,4,'只读审计角色；云审计日志；测试 bucket / workload','可选云 Agent；优先 API 扫描','真实 CSPM / CIEM / CDR 需要云资源与审计信号','在自有测试资源上发现公开存储配置；撤销后告警恢复','仅规划；存在云资源费用，尚未创建账号或资源。',true),
  seedNode('ai','ai-lab','ai','vm','Ubuntu 24.04 LTS','10.10.55.10',4,8,80,4,'LiteLLM；测试 Agent；受限 MCP server；Qdrant；Presidio；garak','Wazuh agent；OpenTelemetry collector；短期工具 token','LLM 统一入口、MCP 授权、合成敏感数据过滤、AI 测试与向量库隔离','提示词泄漏测试；只读 Agent 写操作拒绝；Qdrant 不对客户端公开','默认使用外部模型 API（可能计费）；本地大模型 GPU / VRAM 未计入；防注入不保证完全有效。'),
  seedNode('saas','saas-test-tenant','ai','external','SaaS 开发 / 测试租户','Internet · HTTPS',0,0,0,4,'独立测试租户；API 日志；受限 OAuth app','无主机 Agent；只读 API connector','演示 SaaS 审计、Agent scope、API 数据扫描','只读 token 不能写入；事件通过连接器关联到 SOC','CASB、租户限制与安全浏览器需商业服务或专项集成。',true),
  seedNode('sase','sase-subscription','ai','external','可选商业 SASE / 云安全订阅','Internet · VPN / HTTPS',0,0,0,4,'MU / RN / SC；安全浏览器；CDSS；可选 AI / CNAPP 服务','厂商接入与防护 Agent，按实际许可安装','补充商业 SASE、云沙箱、DLP、CASB、ATP Plus 等原生能力','取得订阅并完成接入后，逐项验收策略、Agent 与日志','本节点为授权占位；添加节点不代表已购买、启用或完成验证。',true),
  seedNode('wazuh','security-manager','ops','vm','Ubuntu 24.04 LTS','10.10.70.10',4,8,100,3,'Wazuh manager / indexer / dashboard','Agent 1514/TCP；注册 1515/TCP（限时开放）','统一终端 / 身份 / 网络日志、FIM、基线和关联告警','测试事件能关联设备与账号；限制注册范围；验证索引保留策略','实验规模参考资源，实际按 EPS / 保留天数调整；不是完整商业 XDR。'),
  seedNode('sensor','network-sensor','ops','vm','Ubuntu 24.04 LTS','10.10.70.20',4,8,100,3,'Zeek；Suricata IDS；镜像流量分析','日志 shipper','通过 SPAN / 虚拟交换机镜像观察流量与 IoT 行为','产生测试流量后看到 DNS / TLS 元数据；丢包率达标','独立管理 vNIC + 无 IP 镜像 vNIC；镜像需在物理或虚拟交换机配置。',true),
  seedNode('soc','soc-workflows','ops','vm','Ubuntu 24.04 LTS','10.10.70.30',4,6,60,3,'Shuffle；TheHive（评估许可）；OpenCTI / 情报按需','Wazuh agent；webhook connector','事件调查、剧本编排、风险排序、人工批准的响应；AI 辅助摘要','测试告警触发工单；隔离动作先审批；记录回滚结果','集成和凭据需配置；不默认运行自治封禁；情报平台附加资源按需增加。'),
  seedNode('scanner','posture-scanner','ops','vm','Ubuntu 24.04 LTS','10.10.70.40',4,8,60,3,'Greenbone；Prowler；kube-bench；Presidio；授权资产清单','Wazuh agent；云只读角色','漏洞、云配置、权限及合成敏感数据扫描；图谱关联实验','扫描范围仅自有实验网；修复测试漏洞后告警关闭','DSPM / 攻击路径 / AI-SPM 为多工具与人工关联，非完整商业引擎。'),
  seedNode('monitor','experience-monitor','ops','vm','Ubuntu 24.04 LTS','10.10.70.50',2,2,20,1,'Prometheus；Grafana；Blackbox exporter；Uptime Kuma','Node exporter；端到端合成探测','持续验证 DNS / 登录 / 应用可用性；DEM 基础替代','从终端与网关两侧比较探测；断开隧道后告警','探测目标与告警路由需配置，不提供真实用户全链路商业 DEM。'),
  seedNode('pve','pve-01','infra','physical','Proxmox VE','10.10.10.10',16,128,2000,1,'vmbr0 管理；vmbr1 VLAN-aware trunk；隔离 WAN bridge','Node exporter；Syslog','承载 VM；快照、网络分区与配额管理','管理 UI 只允许管理员网段；验证 VLAN 不泄漏；预留宿主内存','参考硬件：16 核 / 128 GiB / 2 TB SSD / 双网口；vCPU 可超配，内存按需分批启用。'),
  seedNode('backup','backup-01','infra','vm','Proxmox Backup Server','10.10.10.20',2,2,200,1,'PBS；定时备份；离线 / 异机副本；Ansible 配置仓库','Node exporter；Syslog','恢复演练、配置基线与审计证据留存','随机恢复一台 VM 并校验服务；备份凭据不能访问业务数据','同宿主 PBS 只用于演练，无法抵御宿主整体故障；实际副本应位于独立设备。')
];
function placeSeed(nodes) {
  const height=id=>{const z=ZONES.find(z=>z.id===id);return 60+Math.max(1,Math.ceil(nodes.filter(n=>n.zone===id).length/z.cols))*128;};
  const coreY=20+height('identity')+40;
  const supportY=coreY+Math.max(...['client','edge','workload'].map(height))+32;
  const infraY=supportY+height('ai')+24;
  const opsY=Math.max(supportY+height('cnapp'),infraY+height('infra'))+32;
  const ys={identity:20,client:coreY,edge:coreY,workload:coreY,cnapp:supportY,ai:supportY,infra:infraY,ops:opsY};
  ZONES.forEach(z=>{
    const stride=(z.w-30-212)/Math.max(1,z.cols-1);
    nodes.filter(n=>n.zone===z.id).forEach((n,i)=>{n.x=z.x+15+(i%z.cols)*stride;n.y=ys[z.id]+60+Math.floor(i/z.cols)*128;});
  });
}
placeSeed(SEED_NODES);
const SEED_EDGES = [];
function link(from,to,type,label,protocol,policy) { SEED_EDGES.push({id:`e-${SEED_EDGES.length+1}`,from,to,type,label,protocol,policy}); }
link('win','fw','traffic','远程接入','WireGuard UDP 51820','仅访问获准网段；生产可替换厂商隧道');
link('dev','fw','traffic','受管终端接入','WireGuard UDP 51820','按角色限制网络访问');
link('byod','access','traffic','受限 Web','HTTPS 443','仅 OIDC 身份代理发布的 Web 应用');
link('branch','fw','traffic','分支隧道','WireGuard UDP 51820','仅分支 10.20.0.0/24 到业务白名单');
link('iot','fw','traffic','IoT 出口','DNS / NTP / MQTT','仅固定目的地，禁止到管理域');
link('fw','access','traffic','应用入口','HTTPS 443','仅网关对外发布端口');
link('fw','dns','traffic','受控解析','UDP/TCP 53；NTP UDP 123','只允许内部 DNS / NTP');
link('dev','proxy','traffic','PAC 代理','TCP 3128','禁止旁路直接 HTTP/S 出口');
link('access','apps','traffic','私有服务','HTTPS 443','仅允许代理来源访问应用');
link('access','worker','traffic','容器应用','HTTPS 443','仅指定 ingress');
link('access','idp','identity','身份认证','OIDC / HTTPS 443','校验 issuer / audience / MFA');
link('win','ad','identity','域身份','DNS / Kerberos / LDAP(S) / SMB / RPC','按 AD 官方端口矩阵限制到 DC；不向公网发布');
link('dev','pam','identity','运维入口','SSH 3022 / HTTPS 443（部署后确认）','短期证书与会话录制');
link('pam','apps','identity','管理会话','SSH 22','仅批准的主机和角色');
link('secrets','worker','identity','工作负载信任','SPIRE TCP 8081；OpenBao 8200/TLS','图示信任关系；agent 主动访问服务端；按 workload 限权');
link('kcp','worker','control','集群控制','API 6443；kubelet 10250；集群网络端口','仅节点网段；参照实际 k3s 网络后端');
link('ci','worker','control','受控发布','HTTPS 443 / API 6443','CI 专用 namespace 与 service account');
link('apps','ai','traffic','AI API','HTTPS 443','统一 LLM / MCP 网关；按用户 quota / scope');
link('ai','idp','identity','Agent 令牌','OIDC / HTTPS 443','独立 client、最小 scope、短 TTL');
link('ai','saas','traffic','受限工具调用','HTTPS 443','独立测试租户，禁止共享管理员 token');
link('fw','sase','traffic','可选 SASE 接入','IPsec UDP 500/4500；ESP 按需','仅完成订阅与隧道配置后启用');
link('scanner','cloud','control','云只读扫描','Cloud API / HTTPS 443','只读审计角色');
link('fw','sensor','mirror','SPAN 镜像','L2 mirror · 无 IP','交换机复制流量，探针不在转发路径');
['win','dev','idp','fleet','worker','ai','fw','sensor','proxy','ad'].forEach(id=>link(id,'wazuh','telemetry','安全遥测',id==='fw'?'Syslog TLS 6514（经中继）':'Agent TCP 1514 / HTTPS collector','只允许指定采集源；Syslog 来源需中继标准化'));
link('wazuh','soc','telemetry','告警联动','Webhook HTTPS 443','验签与幂等；响应需审批');
link('soc','ai','control','AI 辅助调查','HTTPS 443','去敏上下文；只读工具；保留人审');
link('monitor','access','telemetry','合成体验探测','HTTPS 443','专用低权限测试账号');
link('pve','backup','control','备份','PBS HTTPS 8007','专用最小权限备份身份');

// Coverage describes a plan, not deployed or equivalent product functionality.
const COVERAGE_PLAN = {};
function covers(ids,nodes,level,implementation,acceptance) { ids.split(' ').forEach(id => COVERAGE_PLAN[id]={nodes:nodes.split(' '),level,implementation,acceptance}); }
covers('m-emp m-contractor','idp win byod','lab','员工 / 管理员 / contractor 独立用户与角色；终端分别访问','对同一应用验证不同角色权限');
covers('m-aiagent m-agtreg m-mcpauth','ai idp','partial','Agent registry 用显式清单与 OIDC client；工具代理校验 scope 并审计','未注册 client / 越权工具调用被拒绝');
covers('m-endpointdev m-byod m-iot','win dev byod iot','lab','分别部署受管、非受管和无 Agent 设备','按类别验证允许与拒绝的访问路径');
covers('m-sso','idp','lab','Keycloak OIDC / SAML + MFA；账号生命周期演练','MFA、禁用用户、角色切换验收');
covers('m-pam','pam','partial','短时证书与会话录制；高级 JIT 审批按版本补充','证书过期与非授权 SSH 均失败');
covers('m-device','fleet win dev idp','partial','设备清单与基线查询；姿态到身份策略需 webhook 集成','设备不合规后测试策略拒绝或降权');
covers('m-epm m-xdr','win dev wazuh soc','partial','系统 AV + Wazuh + Sysmon；跨源规则与人工批准响应','受控测试事件关联到终端 / 用户，响应留审计');
covers('m-nbsc m-swmesh','fleet ci dev','partial','扩展 / MCP 清单、白名单、SBOM 与依赖扫描','未知扩展或高风险依赖准入被阻断；行为检测另需引擎');
covers('m-spiffe m-wcert','secrets worker','lab','SPIRE SVID 与 OpenBao；通过工作负载身份读取 Secret','短期凭据轮转；跨服务越权失败');
covers('m-itdr','ad idp wazuh soc','partial','域 / IdP 登录与权限变更日志关联，自建身份检测规则','失败登录及特权组修改触发事件；不宣称完整票据攻击防御');
covers('m-remote m-branch m-campus','fw branch win','lab','WireGuard 远程 / 站点隧道；VLAN 模拟园区分区','受限网段可达且禁止跨域横向访问');
covers('m-sase-mu m-sase-rn m-sase-sc','fw access branch sase','partial','WireGuard + 身份代理模拟访问路径；原生 MU / RN / SC 需订阅','本地路径与商业订阅路径分别验收');
covers('m-sase-ep','proxy byod','lab','Squid + PAC；域名 ACL 与访问审计','代理流量被记录，旁路出口被阻断');
covers('m-sase-browser','byod sase','license','安全企业浏览器需要独立授权；普通浏览器只能测试身份代理','拿到许可后验证剪贴板、下载与隔离策略');
covers('m-atp m-ipdef','fw sensor','partial','Suricata 规则与 IP denylist；不等同于 AI 增强商业防护','无害测试规则匹配，阻断事件进入 SOC');
covers('m-awf','sandbox sase','partial','可选本地隔离沙箱；云信誉、全球情报与 ML 需订阅','文件分析报告回传；确认沙箱网络隔离');
covers('m-aurl m-adns','dns proxy','partial','DNS / URL 列表和域名 ACL；实时信誉、DGA 检测需额外引擎','列表内测试域名被阻断并产生可检索日志');
covers('m-devsec','iot sensor fleet','partial','网络元数据识别 + 资产台账 + 限制 VLAN','无 Agent 设备可被发现且无法访问身份域');
covers('m-edlp','proxy ai sase','partial','合成敏感数据和 Presidio 演示；统一通道 / TLS 内容检查待集成','只在已集成内容检查的测试路径验收，不推断全域 DLP');
covers('m-saas-sec m-ngcasb m-saas-agent','saas ai sase','license','只读测试租户 API 演练；完整 CASB / SaaS Agent 治理需商业授权与连接器','验证租户权限、API 扫描与工具行为日志');
covers('m-ai-access m-llmgw m-mcpgw m-rtsec','ai idp','partial','LiteLLM 路由 / 配额 + 受限 MCP + 自定义过滤与审计','限制模型、调用 scope、合成数据泄漏与注入回归测试');
covers('m-atpp','sase','license','保留商业能力占位；开源 IPS 不等价于 Frontier AI 漏洞发现和自动防护生成','获取相应授权后按厂商文档验证补偿控制与情报能力');
covers('m-internet','fw dns proxy','lab','受控 NAT 出口、DNS 与代理','非授权直接出口失败，合法流量成功');
covers('m-saas','saas','external','独立 SaaS 测试租户','OIDC / OAuth 访问与审计事件验收');
covers('m-cloud','cloud kcp worker','external','k3s 提供本地容器实验；真实云另需自有账号','本地网络策略和云 API 扫描分别验收');
covers('m-dc','apps pve','lab','本地私有应用 / VM / 文件服务','通过网关访问，直连受限');
covers('m-modelsec m-skillsec','ci ai','partial','模型 / 工具来源与哈希清单，静态扫描及准入规则','来源未知模型或超 scope 工具被拒；不等同于完整后门检测');
covers('m-redteam','ai','lab','garak 与人工评测集，仅测自有 AI 应用','保存提示词注入、越权、泄漏测试报告');
covers('m-policy','backup fw kcp','partial','Ansible / Git 管理配置与 NetworkPolicy；统一审批流程','变更可审计且可回滚；跨工具冲突校验需额外实现');
covers('m-alert m-log m-xsiam','wazuh sensor soc','partial','Wazuh 索引与规则、网络日志、SOC 事件关联','测试告警能从设备追溯到原始日志与处置记录');
covers('m-compliance','wazuh scanner backup','partial','基线扫描、证据与备份保留；用于实验验证而非合规认证','基线差异可追踪，恢复与证据导出成功');
covers('m-xpanse m-expomgmt m-attackpath','scanner soc','partial','自有资产枚举、漏洞扫描，手动结合网络 / IAM 图排序','仅授权资产；验证一条暴露路径及修复前后变化');
covers('m-xsoar','soc','lab','Shuffle 事件编排与人工审批响应','告警自动建单，隔离需批准且能回滚');
covers('m-agentix','soc ai','partial','只读 AI 调查摘要与受限工具调用','无自主封禁权限；摘要能追溯证据');
covers('m-cspm m-ciem m-cdr','scanner cloud wazuh','external','Prowler + 云审计 + 最小权限角色；真实云信号需外部账号','配置、权限和云事件各至少一个测试案例');
covers('m-dspm','scanner worker','partial','扫描 MinIO 中合成敏感数据并关联访问策略','发现测试敏感对象与过度开放权限；非完整 DSPM');
covers('m-cwpp','worker kcp ci','partial','Falco + Trivy Operator + 主机 Agent','异常运行时行为与高危镜像告警进入 SOC');
covers('m-aspm','ci apps','partial','代码 / Secret / IaC / SBOM 的 CI 检查，关联部署版本','高风险构建被门禁拒绝，修复后通过');
covers('m-aispm','ai scanner','partial','AI / 向量库清单、模型 API 配置与测试数据访问策略检查','发现公开模型端点或向量库权限配置问题');
covers('v-appid v-contentid','fw proxy sensor','partial','流量元数据、协议分类与规则检测；不等价于厂商专有识别引擎','应用 / 内容规则的可见性与 TLS 限制逐项确认');
covers('v-userid v-deviceid','idp fleet access','partial','OIDC 身份 + 设备清单，通过策略接口关联','策略决策日志包含测试用户和设备标识');
covers('v-dem','monitor win dev','partial','从终端与网关侧合成探测登录 / DNS / HTTP','隧道、应用、DNS 故障分别出现可区分告警');
const CNAPP_MODULES = [
  {id:'cnapp-cspm',cap:'m-cspm',name:'CSPM 云安全态势',targets:['cloud','kcp'],services:'Cortex Cloud / Prisma Cloud CSPM；云账号 API 连接器；配置合规策略',agents:'云只读审计角色；通常无须安装主机 Agent',purpose:'持续发现云资源错误配置，评估基线并关联 K8S 配置风险',verify:'在自有测试账号中发现一处受控错误配置；修复后告警关闭'},
  {id:'cnapp-dspm',cap:'m-dspm',name:'DSPM 数据安全态势',targets:['cloud','worker'],services:'DSPM 数据源连接器；敏感数据分类；访问权限关联',agents:'受支持的数据存储连接器；扫描身份按需授予读取权限',purpose:'发现测试存储中的合成敏感数据、影子数据和过度访问',verify:'发现合成敏感对象并定位过度开放策略；MinIO 需确认连接器兼容性'},
  {id:'cnapp-ciem',cap:'m-ciem',name:'CIEM 云权限治理',targets:['cloud','idp'],services:'云 IAM 权限采集；有效权限分析；最小权限建议',agents:'云 IAM 只读角色；身份目录集成按需配置',purpose:'识别过度授权的用户、角色与机器身份，评估最小权限',verify:'测试角色的冗余权限被发现；撤销冗余权限后应用仍能完成预定操作'},
  {id:'cnapp-cwpp',cap:'m-cwpp',name:'CWPP 工作负载保护',targets:['worker','kcp','apps'],services:'工作负载保护控制面；镜像 / 主机漏洞与运行时策略',agents:'在受支持的 VM / K8S 节点部署 Defender 或对应 Agent，按当前版本支持矩阵选择',purpose:'统一保护 VM 与容器，结合镜像漏洞、运行时行为和微隔离',verify:'测试镜像风险和无害运行时事件进入控制台；验证策略阻断与例外'},
  {id:'cnapp-cdr',cap:'m-cdr',name:'CDR 云检测响应',targets:['cloud','soc'],services:'云审计日志连接器；检测规则；响应剧本集成',agents:'云审计日志 / 事件流；响应账号单独授权',purpose:'识别云端身份与资源异常，关联事件并执行经审批的响应',verify:'受控云 API 异常触发事件；响应需人审且具备回滚记录'},
  {id:'cnapp-attackpath',cap:'m-attackpath',name:'攻击路径分析',targets:['cloud','worker','cnapp-cspm','cnapp-ciem','cnapp-cwpp'],services:'云风险图谱；暴露面 / IAM / 漏洞关联；修复路径排序',agents:'复用 CSPM、CIEM、CWPP 信号；无需独立主机 Agent',purpose:'将公开入口、过度权限和工作负载漏洞关联成可验证的攻击路径',verify:'建立一条受控测试路径，修复关键节点后验证路径消失'},
  {id:'cnapp-aspm',cap:'m-aspm',name:'ASPM 应用安全态势',targets:['ci','apps'],services:'代码 / IaC / 镜像 / SBOM 连接器；CI 安全门禁',agents:'仓库应用与 CI 扫描 job；仅向所需仓库授权',purpose:'把代码风险、构建制品与运行时应用关联，阻断高风险发布',verify:'含测试 Secret 或高危依赖的构建被阻断；修复后发布通过'},
  {id:'cnapp-aispm',cap:'m-aispm',name:'AI-SPM AI 安全态势',targets:['ai','cloud'],services:'AI 模型端点 / 数据管道 / 向量库清单；AI 配置与数据访问策略',agents:'受支持的云 AI API / 数据源连接器；自建组件通过资产清单补充',purpose:'发现 AI 工作负载、模型端点、训练 / RAG 数据与向量库配置风险',verify:'发现公开 AI 端点或过度开放向量库权限；修复后重新评估'}
];
function upgradeNetworkApplianceKinds(data){
  const router=data.nodes.find(n=>n.id==='branch');
  if(router){router.kind='router';router.cpu=0;router.ram=0;router.disk=0;}
  const firewall=data.nodes.find(n=>n.id==='fw');
  if(firewall){firewall.kind='firewall';firewall.cpu=0;firewall.ram=0;firewall.disk=0;}
  data.nodes.filter(n=>['router','firewall'].includes(n.kind)).forEach(n=>{n.cpu=0;n.ram=0;n.disk=0;});
  return data;
}
function upgradeTopologyLayout(data) {
  const version=data.layoutVersion||1;
  if(version>=2){data.layoutVersion=3;return upgradeNetworkApplianceKinds(data);}
  const placements={branch:['client','edge'],saas:['ai','workload'],sase:['ai','edge'],sandbox:['edge','ai']};
  Object.entries(placements).forEach(([id,[from,to]])=>{const n=data.nodes.find(n=>n.id===id);if(n?.zone===from)n.zone=to;});
  const added=new Map();
  CNAPP_MODULES.forEach(m=>{
    let id=m.id,suffix=2;
    while(data.nodes.some(n=>n.id===id))id=m.id+'-'+suffix++;
    const n=seedNode(id,m.name,'cnapp','external','CNAPP · 已有授权','云控制台 / HTTPS',0,0,0,4,m.services,m.agents,m.purpose,m.verify,'同一 CNAPP 租户内的配套能力，不新增独立 VM；具体 SKU、连接器支持与开通状态以现有租户为准。');
    n.host='共享 CNAPP 云控制面';data.nodes.push(n);added.set(m.id,id);
    const c=data.coverage.find(c=>c.id===m.cap);
    if(c)c.nodes=[...new Set([...c.nodes.filter(id=>id!=='sase'),n.id])];
  });
  function addEdge(from,to,type,label,protocol,policy){
    if(!data.nodes.some(n=>n.id===from)||!data.nodes.some(n=>n.id===to))return;
    let id=`e-${from}-${to}`,suffix=2;while(data.edges.some(e=>e.id===id))id=`e-${from}-${to}-${suffix++}`;
    data.edges.push({id,from,to,type,label,protocol,policy});
  }
  CNAPP_MODULES.forEach(m=>m.targets.forEach(target=>addEdge(added.get(m.id),added.get(target)||target,'control',m.name+' 关联','HTTPS 443 / 厂商支持的采集接口','逻辑管控与数据源关联；实际连接发起方向依连接器确定，私网 Agent 主动向云端连接；按最小权限授权')));
  addEdge(added.get('cnapp-cdr'),'wazuh','telemetry','云检测事件汇聚','API / Webhook HTTPS 443','通过本地连接器拉取或授权的转发接口接入，不向公网暴露日志服务');
  placeSeed(data.nodes);data.layoutVersion=3;
  return upgradeNetworkApplianceKinds(data);
}
function makeSeed() {
  const nodes=structuredClone(SEED_NODES);
  Object.assign(nodes.find(n=>n.id==='win'),{name:'win11-managed',cpu:2,ram:4,agents:'Cortex XDR agent；Prisma Access Agent 或 GlobalProtect（二选一）；Koi 端点组件（核实当前支持版本）',services:'Windows 11 Pro；受管 Edge；测试员工 alice',notes:'用户确定配置：2 vCPU / 4 GiB。开启 vTPM 2.0 / UEFI；Windows 11 guest CPU 需满足支持条件。4 GiB 为紧凑配置，Agent 安装后检查内存、启动时间与浏览器响应；建议可扩到 8 GiB。不要并装多套实时 EDR。'});
  Object.assign(nodes.find(n=>n.id==='byod'),{name:'win11-validation',os:'Windows 11 Pro',cpu:2,ram:4,disk:80,services:'Prisma Browser；普通浏览器对照；外包测试用户 bob',agents:'默认不装企业接入 / EDR Agent，模拟 BYOD；另建受管快照测试 Cortex XDR + 接入 Agent',purpose:'第二台 Windows 对照机：非受管 / 受管快照分别验证设备姿态、安全浏览器、DLP 和第三方访问',verify:'普通浏览器到受限应用被拒；Prisma Browser 获准会话禁止指定下载 / 复制；受管快照单独验证设备姿态',notes:'用户确定配置：2 vCPU / 4 GiB；vTPM 2.0 / UEFI。非受管和受管状态分开测试，不同时宣称 BYOD 与完整设备信任。'});
  Object.assign(nodes.find(n=>n.id==='dev'),{os:'Ubuntu Desktop 24.04 LTS',agents:'Cortex XDR for Linux（核实发行版 / 内核支持）；GlobalProtect Linux / Prisma Access Agent（按当前支持矩阵二选一）；osquery（按需）',notes:'Ubuntu 暂按 2 vCPU / 4 GiB 规划，可编辑；浏览器 / IDE 扩展和 MCP 工具治理根据 Koi 实际 Linux 支持情况配置。不要并装多套实时 EDR。'});
  Object.assign(nodes.find(n=>n.id==='sase'),{name:'licensed-security-cloud',optional:false,os:'已有授权 · 控制台待接入',services:'Prisma Access / Browser；CDSS（ATP / ATP Plus / WildFire / URL / DNS / DLP / CASB）；Cortex XDR / XSIAM；Cortex Cloud / Prisma Cloud；Prisma AIRS',purpose:'用户已有授权的商业安全控制面；具体租户、服务地址和已开通 SKU 在此登记',verify:'逐项确认租户已开通功能；接入三台终端与实验网；验证策略命中与日志返回',notes:'授权由用户确认已有。此处仍是部署规划，具体 SKU、OS 支持矩阵与区域可用性须以实际租户为准；尚未登录或配置服务。'});
  const coverage=CATALOG.map(c=>({id:c.id,...structuredClone(COVERAGE_PLAN[c.id]||{nodes:[],level:'gap',implementation:'待规划',acceptance:''})}));
  const commercial={
    'm-epm':'Cortex XDR agent：实时终端防护与漏洞风险管理；策略从租户下发',
    'm-xdr':'Cortex XDR / XSIAM：关联终端、网络和云信号，配置调查与响应',
    'm-nbsc':'Koi Security：核实 Windows / Linux 支持后部署端点组件，治理扩展 / 包 / MCP',
    'm-sase-mu':'Prisma Access Agent 或 GlobalProtect：受管 Windows / Ubuntu 远程接入，按 OS 支持矩阵部署',
    'm-sase-ep':'Prisma Access Explicit Proxy：将 PAC 和代理策略下发给测试浏览器',
    'm-sase-browser':'Prisma Browser：在 win11-validation 配置浏览器身份、下载和剪贴板策略',
    'm-sase-rn':'Prisma Access Remote Networks：实验边界与分支建立 IPSec 接入',
    'm-sase-sc':'Prisma Access Service Connection：通过实验边界发布私有应用网段，避免重叠路由',
    'm-atp':'Advanced Threat Prevention：在 SASE / NGFW 策略启用威胁防护配置文件',
    'm-atpp':'Advanced Threat Prevention Plus：核对租户功能开通并验证漏洞防护策略 / 情报',
    'm-awf':'Advanced WildFire：配置文件转发与分析日志，用安全测试样本验收',
    'm-aurl':'Advanced URL Filtering：分类策略与信誉判定；验证解密 / 非解密路径',
    'm-adns':'Advanced DNS Security：配置 DNS 检测策略与日志',
    'm-ipdef':'Advanced IP Defense：确认已开通功能，配置威胁策略与事件检索',
    'm-devsec':'Device Security：接入网络资产与 IoT 元数据并配置分段策略',
    'm-swmesh':'软件供应链网关：结合实际授权服务与 Koi / 端侧清单，配置包与扩展准入',
    'm-edlp':'Enterprise DLP：合成敏感数据测试上传、下载与内容外发，按实际解密和通道覆盖验收',
    'm-saas-sec':'SaaS Security：连接独立 SaaS 测试租户并验证 API / Inline 扫描',
    'm-ngcasb':'NG-CASB：配置租户限制、应用策略与测试数据扫描',
    'm-ai-access':'AI Access Security：识别 GenAI 应用并配置 Prompt / Response 数据策略',
    'm-rtsec':'Prisma AIRS：将自有 AI 应用接入运行时检查并保留回归测试集',
    'm-modelsec':'模型安全扫描：按实际 AI 安全授权接入模型来源与准入流程',
    'm-skillsec':'MCP / Skill 安全：按实际授权工具扫描与准入接口接入 CI',
    'm-redteam':'Prisma AIRS Red Teaming：对自有 AI 应用进行测试并保存报告',
    'm-saas-agent':'SaaS Agent Security：接入测试租户，验证 Agent 清单 / 权限 / 行为审计',
    'm-xsiam':'Cortex XSIAM：接入终端、身份与网络数据源，验证跨域事件关联',
    'm-xsoar':'Cortex XSOAR：配置工单和人工审批剧本，验证响应与回滚',
    'm-agentix':'Cortex AgentiX：按租户已开通功能配置只读调查和人审工具权限',
    'm-cspm':'Cortex Cloud / Prisma Cloud：连接自有云账号并检查配置基线',
    'm-dspm':'DSPM：授权测试数据源，发现合成敏感数据与过度访问',
    'm-ciem':'CIEM：采集云 IAM，验证冗余权限与最小权限建议',
    'm-cwpp':'云工作负载防护：按当前版本在 k3s / VM 安装受支持的 Defender / Agent',
    'm-cdr':'CDR：接入自有云审计事件并验证检测与响应规则',
    'm-attackpath':'攻击路径分析：关联云配置、工作负载和 IAM，验证一条受控暴露路径',
    'm-aspm':'ASPM：接入代码仓库、CI 与镜像，配置风险准入门禁',
    'm-aispm':'AI-SPM：接入云 AI 工作负载与向量库清单，验证配置和数据权限风险',
    'v-appid':'在 SASE / NGFW 策略中按 App-ID 验证应用识别与访问控制',
    'v-userid':'将身份用户组关联至 SASE 策略和流量日志',
    'v-deviceid':'采集设备身份与姿态，在策略中验证受管 / 非受管差异',
    'v-contentid':'启用威胁、文件、URL 与内容检查配置，按解密可见性验收',
    'v-dem':'启用授权中的 DEM / ADEM，并在受支持终端安装相应组件，测试应用体验'
  };
  coverage.forEach(c=>{if(commercial[c.id]){c.level='commercial';c.implementation=commercial[c.id];c.nodes=[...new Set([...c.nodes,'sase'])];}});
  const edges=structuredClone(SEED_EDGES);
  edges.forEach(e=>{
    if(['win','dev'].includes(e.from)&&e.to==='fw'){e.to='sase';e.label='商业 SASE 接入';e.protocol='GlobalProtect TCP 443 / UDP 4501；Prisma Access Agent 按版本核对';e.policy='使用已授权租户、身份认证和设备姿态，限制应用访问';}
    if(['win','dev'].includes(e.from)&&e.to==='wazuh'){e.to='sase';e.label='Cortex XDR 遥测';e.protocol='HTTPS 443';e.policy='Agent 向 Cortex 租户上报，放行当前租户文档要求的 FQDN';}
  });
  edges.push({id:'e-browser-sase',from:'byod',to:'sase',type:'traffic',label:'安全浏览器接入',protocol:'HTTPS 443',policy:'Prisma Browser 身份和内容策略；普通浏览器作对照'});
  edges.push({id:'e-sase-log',from:'sase',to:'wazuh',type:'telemetry',label:'云端日志关联',protocol:'API HTTPS 443 / 支持的日志转发协议',policy:'逻辑日志方向；本地 connector 主动拉取并标准化，需专项集成；不开放 SIEM 公网端口'});
  edges.push({id:'e-sase-private',from:'sase',to:'fw',type:'traffic',label:'私有服务连接',protocol:'IPsec UDP 500/4500',policy:'Service Connection 通过边界路由到私有应用白名单；与 RN 路由分别规划'});
  return upgradeTopologyLayout({schema:'zt-homelab',version:1,id:'homelab-reference-v1',name:'Zero Trust Homelab',updatedAt:new Date().toISOString(),settings:{hostCpu:16,hostRam:128,hostDisk:2000,reserveRam:12},nodes,edges,coverage,phaseNotes:['先建立 VLAN / DNS / NTP / 管理边界与恢复；服务器容量暂用参考值。','部署两台 2C / 4 GiB Windows 11 与 Ubuntu Desktop，接入已授权安全服务并验证 Agent 和姿态策略。','接入业务、k3s 与日志；商业云控制面优先，本地 SOC / 扫描器可作为对照实验。','接入 AI / 云测试资源与已有授权服务；逐项记录验收结果，未验证能力保持规划状态。']});
}
