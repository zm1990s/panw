const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = v => String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const NS='http://www.w3.org/2000/svg';
const NODE_W=212,NODE_H=112,SERVICE_W=150,SERVICE_H=66;
const LEVELS={commercial:'已有授权 · 待接入',lab:'本地实验',partial:'部分替代',external:'需外部资源',license:'需授权',gap:'待规划'};
const STATUSES={planned:'待部署',deployed:'已部署',verified:'已验收'};
const KINDS={vm:'虚拟机',container:'容器',physical:'物理设备',router:'路由器',firewall:'防火墙',saas:'SaaS',external:'外部服务',service:'自定义服务'};
const EDGE_TYPES={traffic:'访问流量',identity:'身份与信任',telemetry:'日志与监测',control:'管理与编排',mirror:'流量镜像'};
const EDGE_COLORS={traffic:'#a28f54',identity:'#506b8c',telemetry:'#739384',control:'#85929c',mirror:'#a08b68'};
const EDGE_STYLES={line:'实线',dash:'虚线',dot:'点线'};
const EDGE_ROUTES={auto:'自动 · 左右优先',horizontal:'左右连接',vertical:'上下连接'};
const CUSTOM_ZONE_COLOR='#397881';
function allZones(data=project){return [...ZONES,...(data.customZones||[]).map(z=>({...z,subnet:z.description,w:470,h:188,cols:2,role:'support',custom:true}))];}
const hasResourceConfig=kind=>['vm','physical'].includes(kind);
const nodeSize=n=>n?.kind==='service'?{w:SERVICE_W,h:SERVICE_H}:{w:NODE_W,h:NODE_H};
const nodeBox=n=>({x:n.x,y:n.y,...nodeSize(n)});
const iconName=n=>n.kind==='service'?'Component':n.kind==='router'?'Router':n.kind==='firewall'?'BrickWallFire':n.kind==='container'?'Container':['external','saas'].includes(n.kind)?'Cloud':n.kind==='physical'?'Server':n.zone==='client'?'Monitor':n.zone==='ai'?'Bot':n.zone==='identity'?'KeyRound':n.zone==='edge'?'Shield':'Server';
function icon(name,size=16) {return `<svg class="icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${(ICONS[name]||ICONS.Server).map(([tag,a])=>`<${tag} ${Object.entries(a).map(([k,v])=>`${k}="${esc(v)}"`).join(' ')}/>`).join('')}</svg>`;}
function hydrateIcons(root=document) {root.querySelectorAll('[data-icon]').forEach(el=>{el.innerHTML=icon(el.dataset.icon);el.removeAttribute('data-icon');});}
function uid(prefix){return `${prefix}-${crypto.randomUUID?.()||Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)}`;}
function assert(ok,message){if(!ok)throw Error(message);}
function validate(raw) {
  assert(raw&&raw.schema==='zt-homelab'&&raw.version===1,'不支持的拓扑格式或版本');
  assert(raw.layoutVersion===undefined||[1,2,3].includes(raw.layoutVersion),'不支持的拓扑布局版本');
  assert(typeof raw.id==='string'&&raw.id.length<=160&&typeof raw.name==='string'&&raw.name.length<=100,'拓扑名称或标识无效');
  assert(Array.isArray(raw.nodes)&&raw.nodes.length<=500&&Array.isArray(raw.edges)&&raw.edges.length<=3000,'节点或连线数量无效');
  assert(Array.isArray(raw.coverage)&&raw.coverage.length===CATALOG.length,'能力映射不完整');
  const text=(v,max=16000)=>typeof v==='string'&&v.length<=max;
  const num=(v,max=10000000,min=0)=>Number.isFinite(v)&&v>=min&&v<=max;
  const color=v=>typeof v==='string'&&/^#[0-9a-f]{6}$/i.test(v);
  const zoneIds=new Set(ZONES.map(z=>z.id));
  if(raw.customZones!==undefined){
    assert(Array.isArray(raw.customZones)&&raw.customZones.length<=100,'自定义区域数量无效');
    for(const z of raw.customZones){assert(z&&text(z.id,160)&&/^zone-[\w-]+$/.test(z.id)&&!zoneIds.has(z.id)&&text(z.name,80)&&z.name.trim()&&text(z.description,500)&&color(z.color)&&num(z.x,50100,-50100)&&num(z.y,50100,-50100),'自定义区域无效');zoneIds.add(z.id);}
  }
  if(raw.zoneDetails!==undefined){
    assert(raw.zoneDetails&&typeof raw.zoneDetails==='object'&&!Array.isArray(raw.zoneDetails),'区域属性无效');
    for(const [id,detail] of Object.entries(raw.zoneDetails))assert(ZONES.some(z=>z.id===id)&&detail&&text(detail.name,80)&&detail.name.trim()&&text(detail.description,500)&&(detail.color===undefined||color(detail.color))&&(detail.x===undefined||num(detail.x,50100,-50100))&&(detail.y===undefined||num(detail.y,50100,-50100)),'区域标题、描述或颜色无效');
  }
  const ids=new Set();
  for(const n of raw.nodes){
    assert(text(n.id,160)&&/^[\w-]+$/.test(n.id)&&!ids.has(n.id),'节点 ID 无效或重复');ids.add(n.id);
    assert(zoneIds.has(n.zone)&&Object.hasOwn(KINDS,n.kind)&&Object.hasOwn(STATUSES,n.status),'节点分类无效');
    if(n.tags===undefined)n.tags=[];
    assert(text(n.name,100)&&n.name.trim()&&['os','ip','host','services','agents','purpose','verify','notes'].every(k=>text(n[k]))&&Array.isArray(n.tags)&&n.tags.length<=12&&n.tags.every(t=>text(t,24)&&t.trim()),'节点字段无效');
    assert(num(n.cpu,4096)&&num(n.ram,65536)&&num(n.disk)&&num(n.x,50000,-50000)&&num(n.y,50000,-50000)&&[1,2,3,4].includes(n.stage)&&typeof n.optional==='boolean','节点资源或位置无效');
  }
  const edgeIds=new Set();
  for(const e of raw.edges){if(e.style===undefined)e.style=['telemetry','mirror'].includes(e.type)?'dash':'line';if(e.route===undefined)e.route='auto';assert(text(e.id,160)&&/^[\w-]+$/.test(e.id)&&!edgeIds.has(e.id)&&ids.has(e.from)&&ids.has(e.to)&&e.from!==e.to&&Object.hasOwn(EDGE_TYPES,e.type)&&Object.hasOwn(EDGE_STYLES,e.style)&&Object.hasOwn(EDGE_ROUTES,e.route)&&['label','protocol','policy'].every(k=>text(e[k])),'连线引用或字段无效');edgeIds.add(e.id);}
  const capIds=new Set();
  for(const c of raw.coverage){assert(CATALOG.some(x=>x.id===c.id)&&!capIds.has(c.id)&&Array.isArray(c.nodes)&&c.nodes.every(id=>ids.has(id))&&new Set(c.nodes).size===c.nodes.length&&Object.hasOwn(LEVELS,c.level)&&text(c.implementation)&&text(c.acceptance),'能力映射无效');capIds.add(c.id);}
  assert(raw.settings&&num(raw.settings.hostCpu,4096,1)&&num(raw.settings.hostRam,65536,1)&&num(raw.settings.hostDisk,10000000,1)&&num(raw.settings.reserveRam,65536)&&raw.settings.reserveRam<raw.settings.hostRam,'宿主容量无效');
  assert(Array.isArray(raw.phaseNotes)&&raw.phaseNotes.length===4&&raw.phaseNotes.every(v=>text(v)),'实施计划无效');
  return structuredClone(raw);
}
const embedded=JSON.parse($('#saved-project').textContent);
let project=validate(upgradeTopologyLayout(validate(embedded||makeSeed())));
let startupNotice='';
function storageKey(){return `zt-homelab:v1:${project.id}`;}
try{
  const draft=localStorage.getItem(storageKey());
  if(draft){
    const data=validate(JSON.parse(draft));
    if(!data.layoutVersion||data.layoutVersion<2){
      try{localStorage.setItem(storageKey()+':before-layout-2',draft);}catch{}
      startupNotice='已迁移到三列主拓扑，并保留原有配置与验收状态。';
    }
    if (!embedded || !(Date.parse(embedded.updatedAt) > Date.parse(data.updatedAt))) project=validate(upgradeTopologyLayout(data));
  }
}catch{startupNotice='本地草稿不可用，已打开文件中的规划。';}
const ui={view:'topology',selected:new Set(),edge:null,cap:null,zone:null,hover:null,tool:'select',connectFrom:null,stage:'all',optional:true,query:'',edges:'traffic',capQuery:'',capLevel:'all',x:0,y:0,zoom:1,undo:[],redo:[],drag:null,snap:true,guides:[],leftCollapsed:false,rightCollapsed:false};
try{ui.snap=localStorage.getItem('zt-homelab:snap')!=='off';}catch{}
try{ui.leftCollapsed=localStorage.getItem('zt-homelab:left-panel')==='collapsed';ui.rightCollapsed=localStorage.getItem('zt-homelab:right-panel')==='collapsed';}catch{}
function toast(message){$('#toast').textContent=message;$('#toast').classList.add('visible');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('#toast').classList.remove('visible'),3200);}
function applyPanelState(){
  const w=$('#workspace');w.classList.toggle('left-collapsed',ui.leftCollapsed);w.classList.toggle('right-collapsed',ui.rightCollapsed);
  const left=$('#left-panel-toggle'),right=$('#right-panel-toggle');
  const leftLabel=ui.leftCollapsed?'展开左侧菜单':'折叠左侧菜单',rightLabel=ui.rightCollapsed?'展开右侧菜单':'折叠右侧菜单';
  left.setAttribute('aria-pressed',String(ui.leftCollapsed));left.setAttribute('aria-label',leftLabel);left.title=leftLabel;
  right.setAttribute('aria-pressed',String(ui.rightCollapsed));right.setAttribute('aria-label',rightLabel);right.title=rightLabel;
}
function persist(){project.updatedAt=new Date().toISOString();fileSave.error='';try{localStorage.setItem(storageKey(),JSON.stringify(project));fileSave.draftStored=true;}catch{fileSave.draftStored=false;}restoreSaveTarget();renderSaveState();updateUndo();}
function beforeChange(){ui.undo.push(JSON.stringify(project));if(ui.undo.length>60)ui.undo.shift();ui.redo=[];}
function mutate(fn,inspector=true){beforeChange();fn();persist();render(inspector);}
function updateUndo(){$('#undo-btn').disabled=!ui.undo.length;$('#redo-btn').disabled=!ui.redo.length;}
function historyStep(redo=false){const from=redo?ui.redo:ui.undo,to=redo?ui.undo:ui.redo;if(!from.length)return;to.push(JSON.stringify(project));project=JSON.parse(from.pop());clearSelection();persist();render();}
function node(id){return project.nodes.find(n=>n.id===id);}
function mixColor(color,white){return '#'+color.slice(1).match(/../g).map(hex=>Math.round(parseInt(hex,16)*(1-white)+255*white).toString(16).padStart(2,'0')).join('');}
function parseTags(value){return [...new Set(String(value).split(/[,，;；]+/).map(t=>t.trim()).filter(Boolean))].slice(0,12);}
function tagColor(tag){let h=0;for(const ch of String(tag))h=(h*31+ch.codePointAt(0))>>>0;return ['#3d6f9f','#367257','#81651b','#8b5f83','#7a6f32','#4c7688','#8a5b42','#596f99'][h%8];}
function tagChip(label,color,x,w){
  return `<g transform="translate(${x} 53)"><rect width="${w}" height="14" rx="3" fill="${mixColor(color,.86)}" stroke="${mixColor(color,.58)}"/><text class="node-text" x="${w/2}" y="7" font-size="7.5" font-weight="600" text-anchor="middle" dominant-baseline="central" style="fill:${color}">${esc(label)}</text></g>`;
}
function tagChips(tags=[]){
  const maxRight=198,gap=3,chips=[],defs=tags.map(t=>{const label=truncate(t,6);return {label,color:tagColor(t),w:Math.min(52,Math.max(24,13+[...label].length*6.4))};});
  let x=14,count=0;
  for(let i=0;i<defs.length;i++){
    const hidden=defs.length-i-1,moreW=hidden?Math.max(22,14+String(hidden).length*6):0,needed=defs[i].w+(hidden?gap+moreW:0);
    if(x+needed>maxRight)break;
    chips.push(tagChip(defs[i].label,defs[i].color,x,defs[i].w));x+=defs[i].w+gap;count++;
  }
  const hidden=defs.length-count;
  if(hidden){const label=`+${hidden}`,w=Math.max(22,14+[...label].length*6),color='#52606a';chips.push(tagChip(label,color,Math.min(x,maxRight-w),w));}
  return chips.join('');
}
function displayZone(z){const detail=project.zoneDetails?.[z.id],color=detail?.color??z.color,palette=detail?.color||z.custom?{color,fill:mixColor(color,.92),nodeFill:mixColor(color,.98),border:mixColor(color,.72),nodeBorder:mixColor(color,.60)}:{};return {...z,...palette,name:detail?.name??z.name,subnet:detail?.description??z.subnet,x:detail?.x??z.x,y:detail?.y??z.y};}
function updateZone(id,changes){const custom=project.customZones?.find(z=>z.id===id);if(custom){Object.assign(custom,changes);return;}const z=displayZone(ZONES.find(z=>z.id===id));project.zoneDetails??={};project.zoneDetails[id]={name:z.name,description:z.subnet,...project.zoneDetails[id],...changes};}
function emptyZoneVisible(z){return !project.nodes.some(n=>n.zone===z.id)&&(z.custom||project.zoneDetails?.[z.id]?.x!==undefined)&&ui.stage==='all'&&(!ui.query||[z.name,z.subnet].some(s=>s.toLowerCase().includes(ui.query.toLowerCase())));}
function zoneRects(nodes=visibleNodes(),includeEmpty=true){return allZones().map(displayZone).flatMap(z=>{const ns=nodes.filter(n=>n.zone===z.id);return ns.length?[{...z,...zoneBounds(ns)}]:includeEmpty&&emptyZoneVisible(z)?[z]:[];});}
function regionBox(id){const z=displayZone(allZones().find(z=>z.id===id)),ns=project.nodes.filter(n=>n.zone===id);return ns.length?zoneBounds(ns):{x:z.x,y:z.y,w:z.w,h:z.h};}
function rememberRegion(id){const b=regionBox(id);updateZone(id,{x:b.x,y:b.y});}
function visibleNodes(){const q=ui.query.toLowerCase();return project.nodes.filter(n=>(ui.stage==='all'||n.stage===Number(ui.stage))&&(ui.optional||!n.optional)&&(!q||[n.name,n.services,n.agents,n.ip,n.purpose,n.os,n.host,...(n.tags||[]),displayZone(allZones().find(z=>z.id===n.zone)).name,displayZone(allZones().find(z=>z.id===n.zone)).subnet].some(v=>v.toLowerCase().includes(q))));}
function matchingEdges(nodes=visibleNodes()){const ids=new Set(nodes.map(n=>n.id));return project.edges.filter(e=>ids.has(e.from)&&ids.has(e.to)&&(ui.edges==='all'||e.type===ui.edges));}
function clearSelection(){ui.selected.clear();ui.edge=null;ui.cap=null;ui.zone=null;ui.hover=null;ui.connectFrom=null;}
function totals(nodes){return nodes.filter(n=>n.kind==='vm').reduce((a,n)=>({cpu:a.cpu+n.cpu,ram:a.ram+n.ram,disk:a.disk+n.disk,count:a.count+1}),{cpu:0,ram:0,disk:0,count:0});}
function options(dict,value){return Object.entries(dict).map(([v,t])=>`<option value="${esc(v)}" ${v===String(value)?'selected':''}>${esc(t)}</option>`).join('');}
function fieldsForStage(){return Object.fromEntries(STAGES.map((s,i)=>[i+1,`${String(i+1).padStart(2,'0')} ${s}`]));}
function edgeDash(e){return e.style==='dot'?'1 6':e.style==='dash'?'5 5':'';}
function renderSidebar(){
  renderLegend();
  const nodes=visibleNodes();$('#node-list').innerHTML=allZones().map(displayZone).map(z=>{const ns=nodes.filter(n=>n.zone===z.id);return ns.length||emptyZoneVisible(z)?`<div class="list-zone"><i style="background:${z.color}"></i><span class="list-zone-name" title="${esc(z.name)}">${esc(z.name)}</span><small>${ns.length}</small><button data-edit-zone="${z.id}" title="编辑区域" aria-label="编辑${esc(z.name)}区域">${icon('Pencil')}</button></div>${ns.map(n=>`<button class="list-node ${ui.selected.has(n.id)?'selected':''}" data-node="${n.id}" title="${esc(n.name)}">${icon(iconName(n))}<span class="node-title">${esc(n.name)}<small>${n.kind==='vm'?`${n.cpu}C · ${n.ram} GiB`:esc(KINDS[n.kind])}${n.optional?' · 可选':''}</small></span><span class="status-dot" style="${n.status==='verified'?'background:#388765':n.status==='deployed'?'background:#3b82b6':''}"></span></button>`).join('')}`:'';}).join('')||'<div class="empty-result">无匹配节点</div>';
  const t=totals(nodes),s=project.settings;$('#capacity').innerHTML=`<div class="capacity-line"><span>当前范围 · VM 配额</span><strong>${t.count} 台</strong></div><div class="capacity-line"><span>内存</span><strong class="${t.ram+s.reserveRam>s.hostRam?'warning':''}">${t.ram} / ${s.hostRam} GiB</strong></div><progress max="${s.hostRam}" value="${Math.min(s.hostRam,t.ram+s.reserveRam)}"></progress><div>另预留 ${s.reserveRam} GiB 宿主内存</div><div>${t.cpu} vCPU / ${s.hostCpu} 物理核心</div><div>${t.disk} / ${s.hostDisk} GiB 虚拟磁盘</div>${t.ram+s.reserveRam>s.hostRam?'<div class="warning">内存超出参考容量，需分批启用</div>':''}`;
  $('#status-count').textContent=`${nodes.length} / ${project.nodes.length} 节点 · ${matchingEdges(nodes).length} 条可见连接`;
  $('#selection-status').textContent=ui.tool==='connect'?(ui.connectFrom?'选择目标节点':'选择连线起点'):ui.selected.size?`已固定选择 ${ui.selected.size} 个节点`:ui.edge?'已选择连线':'';
}
function pathFor(e){
  const a=node(e.from),b=node(e.to);let x1,y1,x2,y2,c1x,c1y,c2x,c2y;
  const as=nodeSize(a),bs=nodeSize(b),acx=a.x+as.w/2,acy=a.y+as.h/2,bcx=b.x+bs.w/2,bcy=b.y+bs.h/2,dx=bcx-acx,dy=bcy-acy;
  const separatedX=a.x+as.w<=b.x||b.x+bs.w<=a.x,separatedY=a.y+as.h<=b.y||b.y+bs.h<=a.y;
  const horizontal=e.route==='horizontal'||(e.route!=='vertical'&&(separatedX||(!separatedY&&Math.abs(dx)/Math.max(as.w,bs.w)>Math.abs(dy)/Math.max(as.h,bs.h))));
  if(horizontal){const right=dx>0;x1=a.x+(right?as.w:0);y1=a.y+as.h/2;x2=b.x+(right?0:bs.w);y2=b.y+bs.h/2;const bend=Math.max(6,Math.abs(x2-x1)*.45);c1x=x1+(right?bend:-bend);c2x=x2+(right?-bend:bend);c1y=y1;c2y=y2;}
  else {const down=dy>0;x1=a.x+as.w/2;y1=a.y+(down?as.h:0);x2=b.x+bs.w/2;y2=b.y+(down?0:bs.h);const bend=Math.max(6,Math.abs(y2-y1)*.4);c1x=x1;c2x=x2;c1y=y1+(down?bend:-bend);c2y=y2+(down?-bend:bend);}
  // Give aligned endpoints a gentle bow, keeping endpoint tangents normal to the node borders.
  if((horizontal&&Math.abs(y2-y1)<1)||(!horizontal&&Math.abs(x2-x1)<1)){
    const bow=Math.min(36,Math.max(4,Math.hypot(x2-x1,y2-y1)*.12));
    const mx=(x1+x2)/2+(horizontal?0:bow),my=(y1+y2)/2+(horizontal?bow:0);
    const hx=horizontal?(x2-x1)/4:0,hy=horizontal?0:(y2-y1)/4;
    return `M${x1},${y1} C${c1x},${c1y} ${mx-hx},${my-hy} ${mx},${my} C${mx+hx},${my+hy} ${c2x},${c2y} ${x2},${y2}`;
  }
  return `M${x1},${y1} C${c1x},${c1y} ${c2x},${c2y} ${x2},${y2}`;
}
function truncate(text,max){const chars=[...String(text)];return chars.length>max?chars.slice(0,max-1).join('')+'…':text;}
function nodeSvg(n,selected=true){
  const z=displayZone(allZones().find(z=>z.id===n.zone)),external=['external','saas'].includes(n.kind);
  if(n.kind==='service'){
    const statusColor=n.status==='verified'?'#368160':n.status==='deployed'?'#4386b0':'#a9b2b8',note=n.os||n.notes||'备注';
    return `<g class="graph-node service-node ${selected&&ui.selected.has(n.id)?'selected':''}" data-id="${n.id}" style="--node-accent:${z.color}" transform="translate(${n.x} ${n.y})" tabindex="0" role="button" aria-label="${esc(n.name)}"><title>${esc(n.name+'\n'+note)}</title><rect class="node-body" width="${SERVICE_W}" height="${SERVICE_H}" rx="6" fill="${z.nodeFill}" stroke="${z.nodeBorder}" stroke-width="1"/><rect x="0" y="13" width="3" height="26" rx="1" fill="${z.color}"/><g transform="translate(13 14)" color="${z.color}">${icon(iconName(n))}</g><text class="node-text" x="37" y="26" font-size="11.5" font-weight="600" style="fill:#172631">${esc(truncate(n.name,15))}</text><circle cx="${SERVICE_W-16}" cy="21" r="3" fill="${statusColor}"/><text class="node-text" x="14" y="48" font-size="9.5" style="fill:#344450">${esc(truncate(note,20))}</text></g>`;
  }
  const subtitle=n.kind==='saas'?'SaaS 云端服务':external?'外部控制面':n.kind==='router'?'路由器 / 三层转发':n.kind==='firewall'?'防火墙 / 安全策略':n.kind==='physical'?'物理宿主':`${n.cpu} vCPU   ${n.ram} GiB   ${n.disk} GiB`;
  const statusColor=n.status==='verified'?'#368160':n.status==='deployed'?'#4386b0':'#a9b2b8';
  const tags=n.tags||[],tagRow=tags.length?tagChips(tags):'',subY=tags.length?80:65,lineY=tags.length?88:78,ipY=tags.length?104:96;
  return `<g class="graph-node ${selected&&ui.selected.has(n.id)?'selected':''}" data-id="${n.id}" style="--node-accent:${z.color}" transform="translate(${n.x} ${n.y})" tabindex="0" role="button" aria-label="${esc(n.name)}"><title>${esc(n.name+'\n'+n.services+'\n'+n.agents+(tags.length?'\nTags: '+tags.join(', '):''))}</title><rect class="node-body" width="${NODE_W}" height="${NODE_H}" rx="6" fill="${z.nodeFill}" stroke="${z.nodeBorder}" stroke-width="1" ${n.optional||external?'stroke-dasharray="5 3"':''}/><rect x="0" y="13" width="3" height="27" rx="1" fill="${z.color}"/><g transform="translate(13 14)" color="${z.color}">${icon(iconName(n))}</g><text class="node-text" x="37" y="26" font-size="11.5" font-weight="600" style="fill:#172631">${esc(truncate(n.name,23))}</text><circle cx="196" cy="21" r="3" fill="${statusColor}"/><text class="node-text" x="14" y="45" font-size="9.5" style="fill:#344450">${esc(truncate(n.os,31))}</text>${tagRow}<text class="node-text" x="14" y="${subY}" font-size="10" font-weight="500">${esc(truncate(subtitle,tags.length?28:34))}</text><line x1="14" y1="${lineY}" x2="198" y2="${lineY}" stroke="${z.border}"/><text class="node-text" x="14" y="${ipY}" font-size="9.3" style="fill:#344450">${esc(truncate(n.ip||'待分配地址',30))}</text><text class="node-text" x="195" y="${ipY}" font-size="9" text-anchor="end" style="fill:#344450">${n.optional?'OPT':`0${n.stage}`}</text></g>`;
}
function fitZoneText(value,width,size,weight=400){
  const text=String(value).replace(/\s+/g,' '),ctx=fitZoneText.context??=(document.createElement('canvas').getContext('2d'));
  ctx.font=`${weight} ${size}px Arial, "PingFang SC", "Microsoft YaHei", sans-serif`;
  if(ctx.measureText(text).width<=width)return text;
  const chars=[...text];let low=0,high=chars.length;
  while(low<high){const mid=Math.ceil((low+high)/2);if(ctx.measureText(chars.slice(0,mid).join('')+'…').width<=width)low=mid;else high=mid-1;}
  return chars.slice(0,low).join('')+'…';
}
function zoneHeader(z,interactive){
  return `<g class="${interactive?'zone-handle':''}" data-zone-id="${z.id}" ${interactive?`tabindex="0" role="button" aria-label="编辑或移动${esc(z.name)}区域"`:''}><title>${esc(z.name+'\n'+z.subnet)}${interactive?'\n点击编辑；拖动移动；方向键微调，Shift 加速':''}</title><rect class="zone-handle-hit" x="${z.x+1}" y="${z.y+1}" width="${z.w-2}" height="52" rx="7" fill="transparent"/><circle cx="${z.x+17}" cy="${z.y+23}" r="3" fill="${z.color}"/><text class="zone-label" x="${z.x+28}" y="${z.y+27}" font-size="12" fill="#23384c" font-weight="600">${esc(fitZoneText(z.name,z.w-65,12,600))}</text><text class="zone-label" x="${z.x+15}" y="${z.y+44}" font-size="9" fill="#344450">${esc(fitZoneText(z.subnet,z.w-30,9))}</text>${interactive?`<g transform="translate(${z.x+z.w-29} ${z.y+15})" color="${z.color}">${icon('Move')}</g>`:''}</g>`;
}
function zoneBounds(nodes){const b=bounds(nodes);return {x:b.x+13,y:b.y-32,w:b.w-26,h:b.h+18};}
function graphContent(nodes,edges,includeZones=true,selected=true,includeEmptyZones=selected){
  const zones=zoneRects(nodes,includeEmptyZones);
  return `<defs>${Object.entries(EDGE_COLORS).map(([k,v])=>`<marker id="arrow-${k}" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L7,3 L0,6" fill="none" stroke="${v}" stroke-width="1.3"/></marker>`).join('')}</defs><g class="graph-world">${includeZones?zones.map(z=>`<g data-zone="${z.id}"><rect x="${z.x}" y="${z.y}" width="${z.w}" height="${z.h}" rx="8" fill="${z.fill}" stroke="${z.border}" stroke-dasharray="4 5"/></g>`).join(''):''}<g class="edges">${edges.map(e=>`<g class="graph-edge" data-edge="${e.id}"><title>${esc(e.label+' · '+EDGE_STYLES[e.style||'line']+' · '+e.protocol+'\n'+e.policy)}</title><path class="edge-hit" d="${pathFor(e)}"/><path class="edge-line" d="${pathFor(e)}" fill="none" stroke="${EDGE_COLORS[e.type]}" stroke-width="${selected&&ui.edge===e.id?2.8:1.4}" stroke-opacity=".7" stroke-linecap="round" ${edgeDash(e)?`stroke-dasharray="${edgeDash(e)}"`:''} marker-end="url(#arrow-${e.type})"/></g>`).join('')}</g>${includeZones?zones.map(z=>zoneHeader(z,selected)).join(''):''}<g class="nodes">${nodes.map(n=>nodeSvg(n,selected)).join('')}</g></g>`;
}
function updateTransform(){const world=$('#graph .graph-world');if(world)world.setAttribute('transform',`translate(${ui.x} ${ui.y}) scale(${ui.zoom})`);$('#zoom-value').textContent=Math.round(ui.zoom*100)+'%';}
function renderGraph(){const ns=visibleNodes();$('#graph').innerHTML=graphContent(ns,matchingEdges(ns));renderSnapGuides();updateTransform();applyFocus();$('#canvas').classList.toggle('pan',ui.tool==='pan');$('#canvas').classList.toggle('connect',ui.tool==='connect');$('#canvas').classList.toggle('dragging-zone',!!ui.drag?.zone);['select','pan','connect'].forEach(t=>$(`#${t}-tool`).classList.toggle('active',ui.tool===t));$('#snap-btn').classList.toggle('active',ui.snap);$('#snap-btn').setAttribute('aria-pressed',String(ui.snap));}
function applyFocus(){
  const base=new Set(ui.selected.size?ui.selected:ui.hover?[ui.hover]:[]);
  const e=project.edges.find(e=>e.id===ui.edge);if(e){base.add(e.from);base.add(e.to);}
  const related=new Set(base);project.edges.forEach(e=>{if(base.has(e.from)||base.has(e.to)){related.add(e.from);related.add(e.to);}});
  $$('#graph .graph-node').forEach(el=>el.classList.toggle('dimmed',!!base.size&&!related.has(el.dataset.id)));
  $$('#graph .graph-edge').forEach(el=>{const e=project.edges.find(e=>e.id===el.dataset.edge);el.classList.toggle('dimmed',!!base.size&&!base.has(e.from)&&!base.has(e.to));});
}
function bounds(nodes,zones=false){if(!nodes.length)return{x:0,y:0,w:700,h:500};let left=Math.min(...nodes.map(n=>n.x)),top=Math.min(...nodes.map(n=>n.y)),right=Math.max(...nodes.map(n=>n.x+nodeSize(n).w)),bottom=Math.max(...nodes.map(n=>n.y+nodeSize(n).h));if(zones)allZones().filter(z=>nodes.some(n=>n.zone===z.id)).forEach(z=>{left=Math.min(left,z.x);top=Math.min(top,z.y);right=Math.max(right,z.x+z.w);bottom=Math.max(bottom,z.y+z.h);});return {x:left-28,y:top-28,w:right-left+56,h:bottom-top+56};}
function paddedBox(box,pad=24){return{x:box.x-pad,y:box.y-pad,w:box.width+pad*2,h:box.height+pad*2};}
function fit(){if(ui.view!=='topology')return;const box=$('#graph .graph-world')?.getBBox(),b=box?.width?paddedBox(box):bounds(visibleNodes()),r=$('#canvas').getBoundingClientRect();ui.zoom=Math.max(.12,Math.min(1.15,(r.width-38)/b.w,(r.height-68)/b.h));ui.x=(r.width-b.w*ui.zoom)/2-b.x*ui.zoom;ui.y=(r.height-b.h*ui.zoom)/2-b.y*ui.zoom;updateTransform();}
function zoomAt(factor,cx,cy){const rect=$('#canvas').getBoundingClientRect();cx??=rect.width/2;cy??=rect.height/2;const next=Math.max(.12,Math.min(2.5,ui.zoom*factor)),ratio=next/ui.zoom;ui.x=cx-(cx-ui.x)*ratio;ui.y=cy-(cy-ui.y)*ratio;ui.zoom=next;updateTransform();}
function selectNode(id,add=false,focus=false){if(!node(id))return;if(!add)ui.selected.clear();if(add&&ui.selected.has(id))ui.selected.delete(id);else ui.selected.add(id);ui.edge=null;ui.cap=null;ui.zone=null;ui.hover=null;$('#inspector').classList.add('open');render();if(focus&&ui.view==='topology'){const n=node(id),s=nodeSize(n),r=$('#canvas').getBoundingClientRect();ui.zoom=Math.max(ui.zoom,.9);ui.x=r.width/2-(n.x+s.w/2)*ui.zoom;ui.y=r.height/2-(n.y+s.h/2)*ui.zoom;updateTransform();}}
function selectZone(id){if(!allZones().some(z=>z.id===id))return;clearSelection();ui.zone=id;$('#inspector').classList.add('open');render();}
function renderZone(){const z=displayZone(allZones().find(z=>z.id===ui.zone)),hasNodes=project.nodes.some(n=>n.zone===z.id);$('#inspector').innerHTML=`<div class="inspector-head"><div><div class="eyebrow">REGION</div><h2>区域属性</h2></div><button data-action="clear" aria-label="取消选择" title="取消选择">${icon('X')}</button></div><form id="zone-form" class="node-form" data-id="${z.id}" autocomplete="off">${formLabel('标题','name',z.name,'text','maxlength="80" required')}<label>描述<textarea name="description" maxlength="500">${esc(z.subnet)}</textarea></label><div><label for="zone-color">区域颜色</label><div class="zone-color-control"><input id="zone-color" name="color" type="color" value="${z.color}" aria-label="区域颜色"><input name="colorHex" value="${z.color}" pattern="#[0-9a-fA-F]{6}" maxlength="7" required aria-label="颜色十六进制"><button type="button" data-action="reset-zone-color" title="恢复默认颜色" aria-label="恢复默认颜色">${icon('RotateCcw')}</button></div></div><div class="form-actions"><button type="button" data-action="add-zone-node">${icon('Plus')}添加节点</button>${z.custom?`<button type="button" class="danger" data-action="delete-zone" title="${hasNodes?'先移出或删除区域内节点':'删除空区域'}" aria-label="删除空区域" ${hasNodes?'disabled':''}>${icon('Trash2')}</button>`:''}</div></form>`;}
function renderSummary(){
  const v=project.nodes.filter(n=>n.status==='verified').length,mapped=project.coverage.filter(c=>c.nodes.length).length,commercial=project.coverage.filter(c=>c.level==='commercial').length;
  $('#inspector').innerHTML=`<div class="inspector-head"><div><div class="eyebrow">PROJECT OVERVIEW</div><h2>部署概览</h2></div>${icon('Network')}</div><section class="inspector-section"><div class="summary-mark">${icon('Shield',24)}<strong>从架构到实验环境</strong></div><p class="summary-note">2 × Windows 11 · 2C / 4 GiB<br>1 × Ubuntu Desktop · 暂定 2C / 4 GiB<br>安全产品授权已具备</p><div class="summary-stats"><div><strong>${project.nodes.length}</strong><span>规划节点</span></div><div><strong>${mapped}</strong><span>已映射能力</span></div><div><strong>${v}</strong><span>已验收节点</span></div></div><div class="coverage-progress"><span style="width:${100*mapped/CATALOG.length}%"></span></div><p class="caption">${mapped} / ${CATALOG.length} 能力纳入规划，${commercial} 项采用已有授权方案。映射不代表部署完成。</p></section><section class="inspector-section"><h3>终端角色</h3><div class="mini-row"><span class="mini-index">01</span><div><strong>win11-managed</strong><p>XDR + 接入 Agent + 非二进制供应链治理</p></div></div><div class="mini-row"><span class="mini-index">02</span><div><strong>win11-validation</strong><p>安全浏览器、BYOD 与受管快照对照</p></div></div><div class="mini-row"><span class="mini-index">03</span><div><strong>ubuntu-dev</strong><p>开发工具、Linux Agent 与 MCP 调用</p></div></div></section><section class="inspector-section"><h3>分阶段建设</h3>${STAGES.map((s,i)=>`<div class="mini-row"><span class="mini-index">0${i+1}</span><div><strong>${s}</strong><p>${project.nodes.filter(n=>n.stage===i+1).length} 个规划节点</p></div></div>`).join('')}</section><section class="inspector-section"><p class="warning-note">Windows 11 的 4 GiB 内存较紧凑，安装多个 Agent 后需实测。服务器、云资源与容量仍为参考规划。</p></section>`;
}
function formLabel(label,name,value,type='text',extra=''){return `<label>${label}<input name="${name}" type="${type}" value="${esc(value)}" ${extra}></label>`;}
function textLabel(label,name,value){return `<label>${label}<textarea name="${name}" maxlength="16000">${esc(value)}</textarea></label>`;}
function renderInspector(){
  if(ui.zone){renderZone();return;}
  if(ui.cap){renderCapability();return;}
  const e=project.edges.find(e=>e.id===ui.edge);if(e){renderEdge(e);return;}
  const selected=[...ui.selected].map(node).filter(Boolean);
  if(!selected.length){renderSummary();return;}
  if(selected.length>1){const t=totals(selected);$('#inspector').innerHTML=`<div class="inspector-head"><div><div class="eyebrow">MULTIPLE SELECTION</div><h2>${selected.length} 个选中节点</h2></div><button data-action="clear" aria-label="取消选择">${icon('X')}</button></div><section class="inspector-section"><p class="summary-note">${t.cpu} vCPU · ${t.ram} GiB 内存 · ${t.disk} GiB 磁盘</p></section><div class="node-form"><button data-action="export-selected">${icon('Image')}导出选中节点</button><button data-action="delete" class="danger">${icon('Trash2')}删除选中节点</button></div>${selected.map(n=>`<div class="connection-list"><button class="connection-button" data-node="${n.id}">${esc(n.name)} ${icon('ChevronRight')}</button></div>`).join('')}`;return;}
  const n=selected[0],edges=project.edges.filter(e=>e.from===n.id||e.to===n.id);
  const service=n.kind==='service',zoneOptions=options(Object.fromEntries(allZones().map(displayZone).map(z=>[z.id,z.name])),n.zone);
  const details=service?formLabel('备注','os',n.os,'text','maxlength="300"'):`<div class="form-grid"><label>实施阶段<select name="stage">${options(fieldsForStage(),n.stage)}</select></label>${formLabel('部署位置 / 宿主','host',n.host,'text','maxlength="200"')}</div>${formLabel('备注','os',n.os,'text','maxlength="300"')}${formLabel('Tag','tags',(n.tags||[]).join(', '),'text','maxlength="300" placeholder="例如：核心, SaaS, Phase-1"')}${formLabel('IP / 网络地址','ip',n.ip,'text','maxlength="300"')}${hasResourceConfig(n.kind)?`<div class="form-grid triple">${formLabel('vCPU','cpu',n.cpu,'number','min="0" max="4096" step="1" required')}${formLabel('内存 GiB','ram',n.ram,'number','min="0" max="65536" step="0.25" required')}${formLabel('磁盘 GiB','disk',n.disk,'number','min="0" max="10000000" step="1" required')}</div>`:''}<label class="check-line"><input type="checkbox" name="optional" ${n.optional?'checked':''}>可选 / 按需启用</label><div class="form-heading">部署与验收</div>${textLabel('安装的服务 / 软件','services',n.services)}${textLabel('安装的 Agent','agents',n.agents)}${textLabel('实现的功能','purpose',n.purpose)}${textLabel('验收方法','verify',n.verify)}${textLabel('依赖 / 注意事项','notes',n.notes)}<div class="form-heading">关联原图能力</div><div class="cap-checks">${CATALOG.map(c=>`<label><input type="checkbox" data-cap-id="${c.id}" ${project.coverage.find(x=>x.id===c.id).nodes.includes(n.id)?'checked':''}>${esc(c.label)}</label>`).join('')}</div>`;
  $('#inspector').innerHTML=`<div class="inspector-head"><div><div class="eyebrow">${esc(KINDS[n.kind])} · ${esc(displayZone(allZones().find(z=>z.id===n.zone)).name)}</div><h2>节点属性</h2></div><button data-action="clear" aria-label="取消选择" title="取消选择">${icon('X')}</button></div><form class="node-form" id="node-form" data-id="${n.id}" autocomplete="off">${formLabel('名称','name',n.name,'text','maxlength="100" required')}<div class="form-grid"><label>类型<select name="kind">${options(KINDS,n.kind)}</select></label><label>状态<select name="status">${options(STATUSES,n.status)}</select></label></div><label>安全域<select name="zone">${zoneOptions}</select></label>${service?`<label>实施阶段<select name="stage">${options(fieldsForStage(),n.stage)}</select></label>`:''}${details}<div class="form-actions"><button type="button" data-action="duplicate">${icon('Copy')}复制</button><button type="button" data-action="connect">${icon('Cable')}连线</button><button type="button" data-action="delete" title="删除节点" aria-label="删除节点" class="danger">${icon('Trash2')}</button></div></form><div class="connection-list"><h3 style="margin-bottom:12px">连接 · ${edges.length}</h3>${edges.map(e=>`<button class="connection-button" data-edge="${e.id}"><span>${esc(e.label)}<small class="caption"> · ${esc(node(e.from===n.id?e.to:e.from)?.name)}</small></span>${icon('ChevronRight')}</button>`).join('')}</div>`;
}
function renderEdge(e){$('#inspector').innerHTML=`<div class="inspector-head"><div><div class="eyebrow">CONNECTION</div><h2>连接属性</h2></div><button data-action="clear" aria-label="取消选择">${icon('X')}</button></div><form id="edge-form" class="node-form" data-id="${e.id}">${formLabel('连接名称','label',e.label,'text','maxlength="300"')}<label>起点<select name="from">${options(Object.fromEntries(project.nodes.map(n=>[n.id,n.name])),e.from)}</select></label><label>终点<select name="to">${options(Object.fromEntries(project.nodes.map(n=>[n.id,n.name])),e.to)}</select></label><div class="form-grid"><label>连接类型<select name="type">${options(EDGE_TYPES,e.type)}</select></label><label>线型<select name="style">${options(EDGE_STYLES,e.style||'line')}</select></label></div><label>路由<select name="route">${options(EDGE_ROUTES,e.route||'auto')}</select></label>${textLabel('协议 / 端口','protocol',e.protocol)}${textLabel('策略 / 方向说明','policy',e.policy)}<button type="button" data-action="delete" class="danger">${icon('Trash2')}删除连接</button></form>`;}
function renderCapability(){const c=project.coverage.find(c=>c.id===ui.cap),m=CATALOG.find(m=>m.id===ui.cap);if(!c)return;$('#inspector').innerHTML=`<div class="inspector-head"><div><div class="eyebrow">${esc(m.group)}</div><h2>${esc(m.label)}</h2></div><button data-action="clear" aria-label="取消选择">${icon('X')}</button></div><form id="cap-form" data-id="${c.id}" class="node-form"><label>实施方案<select name="level">${options(LEVELS,c.level)}</select></label>${textLabel('部署方案','implementation',c.implementation)}${textLabel('验收标准','acceptance',c.acceptance)}<div class="form-heading">承载节点</div><div class="cap-checks">${project.nodes.map(n=>`<label><input type="checkbox" data-map-node="${n.id}" ${c.nodes.includes(n.id)?'checked':''}>${esc(n.name)}</label>`).join('')}</div></form><section class="inspector-section"><h3>原图能力范围</h3><p class="summary-note">${m.items.map(esc).join('<br>')}</p></section>`;}
function renderInventory(){const nodes=visibleNodes(),t=totals(nodes);$('#inventory-view').innerHTML=`<div class="view-heading"><div><h2>部署清单</h2><p>${t.count} 台 VM · ${t.cpu} vCPU · ${t.ram} GiB 内存 · ${t.disk} GiB 磁盘<br>VM 配额独立汇总；容器、路由器、防火墙和外部服务不计入宿主容量。</p></div><div class="view-actions"><button data-action="add-region">${icon('SquarePlus')}添加区域</button><button data-action="add">${icon('Plus')}新增节点</button></div></div><div class="table-wrap"><table><thead><tr><th>节点 / 位置</th><th>配置</th><th>服务 / Agent</th><th>功能与验收</th><th>状态</th></tr></thead><tbody>${nodes.map(n=>`<tr data-node="${n.id}"><td><strong>${esc(n.name)}</strong><small>${esc(n.ip)}</small><small>${esc(n.host)} · ${esc(KINDS[n.kind])}</small></td><td>${hasResourceConfig(n.kind)?`${n.cpu}C / ${n.ram} GiB<br>${n.disk} GiB`:'—'}<small>${esc(n.os)}</small></td><td class="long"><strong>${esc(n.services)}</strong><small>Agent · ${esc(n.agents)}</small></td><td class="long">${esc(n.purpose)}<small>验收 · ${esc(n.verify)}</small></td><td><span class="badge ${n.status}">${STATUSES[n.status]}</span><small>阶段 ${n.stage}${n.optional?' · 可选':''}</small></td></tr>`).join('')}</tbody></table>${!nodes.length?'<div class="empty-result">无匹配节点</div>':''}</div>`;}
function renderCoverage(){
  const visible=new Set(visibleNodes().map(n=>n.id));let rows=project.coverage.filter(c=>(ui.capLevel==='all'||c.level===ui.capLevel)&&(!ui.capQuery||[CATALOG.find(m=>m.id===c.id).label,c.implementation].some(v=>v.toLowerCase().includes(ui.capQuery.toLowerCase())))&&((ui.stage==='all'&&ui.optional&&!ui.query)||c.nodes.some(id=>visible.has(id))));
  const mapped=project.coverage.filter(c=>c.nodes.length).length,groups=[...new Set(CATALOG.map(m=>m.group))];
  $('#coverage-view').innerHTML=`<div class="view-heading"><div><h2>架构能力覆盖</h2><p>源自 zt-architect.html 的 ${CATALOG.length} 项能力 · 点击条目编辑部署方案与验收标准</p></div></div><div class="coverage-stats"><div class="stat-inline"><strong>${mapped}</strong>已映射</div><div class="stat-inline"><strong>${project.coverage.filter(c=>c.level==='commercial').length}</strong>已有授权</div><div class="stat-inline"><strong>${CATALOG.length-mapped}</strong>未映射</div><div class="stat-inline"><strong>${project.coverage.filter(c=>c.nodes.length&&c.nodes.every(id=>node(id)?.status==='verified')).length}</strong>承载节点已验收</div></div><div class="cap-search-row"><input id="cap-search" placeholder="搜索能力 / 方案" aria-label="搜索能力" value="${esc(ui.capQuery)}"><select id="cap-level-filter" aria-label="实施方案筛选"><option value="all">全部实施方案</option>${options(LEVELS,ui.capLevel)}</select></div><div class="table-wrap"><table><thead><tr><th>架构能力</th><th>实施方案</th><th>承载节点</th></tr></thead><tbody>${groups.map(g=>{const cs=rows.filter(c=>CATALOG.find(m=>m.id===c.id).group===g);return cs.length?`<tr><td colspan="3" class="coverage-group">${esc(g)}</td></tr>${cs.map(c=>`<tr data-cap="${c.id}"><td class="long"><strong>${esc(CATALOG.find(m=>m.id===c.id).label)}</strong><small>${c.id}</small></td><td class="long"><span class="badge ${c.level}">${LEVELS[c.level]}</span><br>${esc(c.implementation)}</td><td class="long">${c.nodes.map(id=>esc(node(id)?.name)).join('<br>')||'<span class="badge gap">未映射</span>'}</td></tr>`).join('')}`:'';}).join('')}</tbody></table>${rows.length?'':'<div class="empty-result">无匹配能力</div>'}</div>`;
}
function renderPhases(){const nodes=visibleNodes();$('#phases-view').innerHTML=`<div class="view-heading"><div><h2>分阶段实施</h2><p>记录建设顺序、资源需求与验收进度。容量为虚拟配额，阶段间保留的 VM 需累计计算。</p></div></div>${STAGES.map((s,i)=>{const ns=nodes.filter(n=>n.stage===i+1),t=totals(ns);return `<section class="phase"><div class="phase-head"><span>0${i+1}</span><h3>${s}</h3><span class="badge">${ns.filter(n=>n.status==='verified').length} / ${ns.length} 已验收</span></div><p class="caption" style="margin-bottom:8px">本阶段 ${t.count} 台 VM · ${t.cpu} vCPU · ${t.ram} GiB</p><textarea data-phase="${i}" aria-label="${s}实施说明" maxlength="16000">${esc(project.phaseNotes[i])}</textarea>${ns.map(n=>`<div class="phase-node"><button data-node="${n.id}">${icon(iconName(n))}${esc(n.name)}${n.optional?'<span class="mini-tag">可选</span>':''}</button><span class="node-resources">${n.kind==='vm'?`${n.cpu}C / ${n.ram} GiB`:KINDS[n.kind]}</span><select data-status-node="${n.id}" aria-label="${esc(n.name)}部署状态">${options(STATUSES,n.status)}</select></div>`).join('')}</section>`;}).join('')}`;}
function render(inspector=true){$('#project-name').value=project.name;$('#coverage-count').textContent=CATALOG.length;renderSidebar();renderGraph();if(inspector)renderInspector();if(ui.view==='inventory')renderInventory();if(ui.view==='coverage')renderCoverage();if(ui.view==='phases')renderPhases();updateUndo();}
function switchView(view){ui.view=view;$$('[data-view]').forEach(el=>el.classList.toggle('active',el.dataset.view===view));$$('.view').forEach(el=>el.classList.toggle('active',el.id===`${view}-view`));render();}
function setTool(tool){ui.tool=tool;ui.connectFrom=null;renderSidebar();renderGraph();}
function overlaps(a,b,gap=8){return a.x<b.x+b.w+gap&&a.x+a.w+gap>b.x&&a.y<b.y+b.h+gap&&a.y+a.h+gap>b.y;}
function freeNodePosition(id,excludeId,kind='vm'){const ns=project.nodes.filter(n=>n.zone===id&&n.id!==excludeId).map(nodeBox),z=regionBox(id),definition=allZones().find(z=>z.id===id),cols=definition.cols,size=nodeSize({kind}),stride=(definition.w-30-NODE_W)/Math.max(1,cols-1);for(let i=0;i<2505;i++){const candidate={x:Math.max(-50000,Math.min(50000,z.x+15+(i%cols)*stride)),y:Math.max(-50000,Math.min(50000,z.y+60+Math.floor(i/cols)*128)),...size};if(!ns.some(n=>overlaps(candidate,n)))return {x:candidate.x,y:candidate.y};}throw Error('区域内没有可用位置');}
function newNode(){if(!commitPendingEdits())return;if(project.nodes.length>=500){toast('最多支持 500 个节点');return;}const zone=ui.zone||node([...ui.selected][0])?.zone||'workload',n=seedNode(uid('n'),'new-vm',zone,'vm','Ubuntu 24.04 LTS','',2,4,40,3,'','','','');n.tags=[];Object.assign(n,freeNodePosition(zone));mutate(()=>project.nodes.push(n));ui.stage='all';$('#stage-filter').value='all';ui.query='';$('#search').value='';switchView('topology');selectNode(n.id,false,true);$('#node-form [name=name]')?.select();}
function newRegion(){
  if(!commitPendingEdits())return;if((project.customZones?.length||0)>=100){toast('最多支持 100 个自定义区域');return;}
  const boxes=allZones().map(z=>regionBox(z.id)),bottom=Math.max(0,...boxes.map(b=>b.y+b.h)),right=Math.max(0,...boxes.map(b=>b.x+b.w));
  let number=1;const names=new Set(allZones().map(z=>displayZone(z).name));while(names.has(`自定义区域 ${number}`))number++;
  const z={id:uid('zone'),name:`自定义区域 ${number}`,description:'',color:CUSTOM_ZONE_COLOR,x:bottom<49000?16:Math.min(49000,right+40),y:bottom<49000?bottom+40:20};
  mutate(()=>{project.customZones??=[];project.customZones.push(z);});ui.query='';ui.stage='all';$('#search').value='';$('#stage-filter').value='all';ui.tool='select';switchView('topology');selectZone(z.id);
  const r=$('#canvas').getBoundingClientRect();ui.zoom=Math.min(1,(r.width-48)/470,(r.height-48)/188);ui.x=r.width/2-(z.x+235)*ui.zoom;ui.y=r.height/2-(z.y+94)*ui.zoom;updateTransform();$('#zone-form [name=name]').select();
}
function deleteRegion(){const id=ui.zone;if(!project.customZones?.some(z=>z.id===id)||project.nodes.some(n=>n.zone===id))return;mutate(()=>{project.customZones=project.customZones.filter(z=>z.id!==id);clearSelection();});}
function duplicate(){const src=node([...ui.selected][0]);if(!src)return;const n=structuredClone(src);n.id=uid('n');n.name=truncate(`${src.name}-copy`,100);n.x+=26;n.y+=26;n.ip='';n.status='planned';mutate(()=>{project.nodes.push(n);project.coverage.forEach(c=>{if(c.nodes.includes(src.id))c.nodes.push(n.id);});});selectNode(n.id);}
function askDelete(){if(!ui.selected.size&&!ui.edge)return;$('#delete-message').textContent=ui.edge?'删除此连接？可使用撤销恢复。':`删除 ${ui.selected.size} 个节点及其连接？相关能力映射将移除这些节点，可使用撤销恢复。`;$('#delete-dialog').showModal();}
function removeSelected(){mutate(()=>{if(ui.edge)project.edges=project.edges.filter(e=>e.id!==ui.edge);else{new Set(project.nodes.filter(n=>ui.selected.has(n.id)).map(n=>n.zone)).forEach(id=>{if(!project.nodes.some(n=>n.zone===id&&!ui.selected.has(n.id)))rememberRegion(id);});project.nodes=project.nodes.filter(n=>!ui.selected.has(n.id));project.edges=project.edges.filter(e=>!ui.selected.has(e.from)&&!ui.selected.has(e.to));project.coverage.forEach(c=>c.nodes=c.nodes.filter(id=>!ui.selected.has(id)));}clearSelection();});}
function connectTo(id){ui.zone=null;if(!ui.connectFrom){ui.connectFrom=id;ui.selected=new Set([id]);render();return;}if(ui.connectFrom===id){toast('请选择另一个节点');return;}const from=ui.connectFrom;let e=project.edges.find(e=>e.from===from&&e.to===id&&e.type==='traffic');if(!e){e={id:uid('e'),from,to:id,type:'traffic',style:'line',label:'新连接',protocol:'HTTPS 443',policy:'待填写访问策略与允许范围'};mutate(()=>project.edges.push(e));}ui.tool='select';ui.connectFrom=null;ui.selected.clear();ui.edge=e.id;ui.edges='all';$('#edge-filter').value='all';render();$('#inspector').classList.add('open');}
function arrange(){mutate(()=>{const boxes=Object.fromEntries(allZones().map(z=>[z.id,regionBox(z.id)]));allZones().forEach(z=>{const ns=project.nodes.filter(n=>n.zone===z.id).sort((a,b)=>a.y-b.y||a.x-b.x||a.name.localeCompare(b.name));if(!ns.length)return;const box=boxes[z.id],cols=Math.max(1,Math.min(z.cols||2,ns.length)),span=Math.max(0,box.w-30-NODE_W),stride=cols>1?span/(cols-1):0;ns.forEach((n,i)=>{n.x=Math.max(-50000,Math.min(50000,box.x+15+(i%cols)*stride));n.y=Math.max(-50000,Math.min(50000,box.y+60+Math.floor(i/cols)*128));});});});fit();}
function filename(ext){return (project.name.replace(/[<>:"/\\|?*\x00-\x1f]/g,'-').trim()||'homelab')+'.'+ext;}
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1500);}
function saveJSON(){if(!commitPendingEdits())return;persist();download(new Blob([JSON.stringify(project,null,2)],{type:'application/json'}),filename('json'));toast('已导出拓扑 JSON');}
function saveHTML(){
  if(!commitPendingEdits())return;
  persist();const snapshot=structuredClone(project);snapshot.id=uid('homelab');
  download(new Blob([serializeHTML(snapshot)],{type:'text/html;charset=utf-8'}),filename('html'));toast('已下载 HTML 副本；原文件未被改写');
}
async function exportPNG(){
  const scope=$('#png-scope').value,ns=scope==='all'?project.nodes:scope==='selected'?project.nodes.filter(n=>ui.selected.has(n.id)):visibleNodes();
  if(!ns.length){toast('没有可导出的节点，请先选择节点');return;}
  const ids=new Set(ns.map(n=>n.id)),es=project.edges.filter(e=>ids.has(e.from)&&ids.has(e.to)&&(ui.edges==='all'||e.type===ui.edges));
  const includeEmptyZones=scope!=='selected',content=graphContent(ns,es,true,false,includeEmptyZones);
  const measure=document.createElementNS(NS,'svg');measure.style.cssText='position:fixed;left:-99999px;top:0;visibility:hidden';measure.innerHTML=content;document.body.append(measure);const b=paddedBox(measure.querySelector('.graph-world').getBBox());measure.remove();
  const scale=Math.min(2,12000/b.w,12000/b.h,Math.sqrt(32000000/(b.w*b.h)));
  const css='.node-text,.zone-label{font-family:Arial,SimHei,"Heiti SC","Microsoft YaHei",sans-serif;fill:#1d2b36}.edge-hit{stroke:none;fill:none}.icon{fill:none;stroke:currentColor;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}';
  const svg=`<svg xmlns="${NS}" width="${b.w}" height="${b.h}" viewBox="${b.x} ${b.y} ${b.w} ${b.h}"><style>${css}</style>${$('#png-transparent').checked?'':`<rect x="${b.x}" y="${b.y}" width="${b.w}" height="${b.h}" fill="#f7f9fa"/>`}${content}</svg>`;
  const url=URL.createObjectURL(new Blob([svg],{type:'image/svg+xml;charset=utf-8'}));$('#download-png').disabled=true;
  try {await document.fonts.ready;const img=new Image();await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=()=>reject(Error('SVG 图像渲染失败'));img.src=url;});const canvas=document.createElement('canvas');canvas.width=Math.ceil(b.w*scale);canvas.height=Math.ceil(b.h*scale);canvas.getContext('2d').drawImage(img,0,0,canvas.width,canvas.height);const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));assert(blob,'PNG 编码失败');download(blob,filename(`${scope}.png`));toast('PNG 已导出');}catch(error){toast(`导出失败：${error.message}`);}finally{URL.revokeObjectURL(url);$('#download-png').disabled=false;}
}

hydrateIcons();
setupFileSaving();
function renderLegend(){$('.legend').innerHTML=['edge','identity','cnapp'].map((id,i)=>`<span><i style="background:${displayZone(allZones().find(z=>z.id===id)).color}"></i>${['接入','身份','运营'][i]}</span>`).join('')+'<span class="legend-outline">虚线 · 可选 / 外部</span>';}
document.addEventListener('click',event=>{
  const target=event.target.closest('button, [data-node], [data-cap], [data-edge]');if(!target)return;
  if(target.dataset.editZone){selectZone(target.dataset.editZone);return;}
  if(target.dataset.view){switchView(target.dataset.view);return;}
  if(target.dataset.node){selectNode(target.dataset.node,event.shiftKey||event.metaKey||event.ctrlKey,ui.view==='topology');return;}
  if(target.dataset.cap){clearSelection();ui.cap=target.dataset.cap;renderInspector();$('#inspector').classList.add('open');return;}
  if(target.dataset.edge&&target.closest('#inspector')){clearSelection();ui.edge=target.dataset.edge;render();return;}
  if(target.dataset.close){$('#'+target.dataset.close).close();return;}
  const action=target.dataset.action;
  if(action==='clear'){clearSelection();$('#inspector').classList.remove('open');render();}
  if(action==='delete')askDelete();if(action==='duplicate')duplicate();if(action==='add')newNode();if(action==='add-region')newRegion();
  if(action==='add-zone-node')newNode();if(action==='delete-zone')deleteRegion();
  if(action==='reset-zone-color'){const id=ui.zone;mutate(()=>{const custom=project.customZones?.find(z=>z.id===id);if(custom)custom.color=CUSTOM_ZONE_COLOR;else if(project.zoneDetails?.[id])delete project.zoneDetails[id].color;});}
  if(action==='connect'){ui.tool='connect';ui.connectFrom=[...ui.selected][0];switchView('topology');}
  if(action==='export-selected'){$('#png-scope').value='selected';$('#export-dialog').showModal();}
});
$('#inspector').addEventListener('submit',e=>e.preventDefault());
$('#inspector').addEventListener('change',event=>{
  const el=event.target,form=el.closest('form');if(!form)return;if(!el.checkValidity()){el.reportValidity();return;}
  if(form.id==='zone-form'){
    if(['color','colorHex'].includes(el.name)){const value=el.value.toLowerCase();if(!/^#[0-9a-f]{6}$/.test(value))return;const id=form.dataset.id;if(displayZone(allZones().find(z=>z.id===id)).color!==value)mutate(()=>updateZone(id,{color:value}),false);form.elements.color.value=value;form.elements.colorHex.value=value;return;}
    if(!['name','description'].includes(el.name))return;
    const z=displayZone(allZones().find(z=>z.id===form.dataset.id)),value=el.name==='name'?el.value.trim():el.value;
    if(el.name==='name'&&!value){toast('区域标题不能为空');el.value=z.name;return;}
    if(value===(el.name==='name'?z.name:z.subnet))return;
    mutate(()=>updateZone(z.id,{[el.name]:value}),false);
  } else if(form.id==='node-form'){
    const n=node(form.dataset.id);if(el.dataset.capId){mutate(()=>{const c=project.coverage.find(c=>c.id===el.dataset.capId);c.nodes=el.checked?[...new Set([...c.nodes,n.id])]:c.nodes.filter(id=>id!==n.id);},false);return;}
    if(!el.name)return;const val=el.name==='tags'?parseTags(el.value):el.type==='checkbox'?el.checked:['cpu','ram','disk','stage'].includes(el.name)?Number(el.value):el.value;
    if(el.name==='name'&&!String(val).trim()){toast('节点名称不能为空');el.value=n.name;return;}
    if(el.name==='tags')el.value=val.join(', ');
    mutate(()=>{if(el.name==='zone'&&val!==n.zone){const position=freeNodePosition(val,n.id);if(!project.nodes.some(other=>other.zone===n.zone&&other.id!==n.id))rememberRegion(n.zone);Object.assign(n,position);}n[el.name]=val;if(el.name==='kind'&&!hasResourceConfig(val)){n.cpu=0;n.ram=0;n.disk=0;}},false);
    if(el.name==='kind')renderInspector();
  } else if(form.id==='edge-form'){
    const e=project.edges.find(e=>e.id===form.dataset.id);if((el.name==='from'&&el.value===e.to)||(el.name==='to'&&el.value===e.from)){toast('起点与终点不能相同');renderInspector();return;}
    if(el.name)mutate(()=>e[el.name]=el.value,false);
  } else if(form.id==='cap-form'){
    const c=project.coverage.find(c=>c.id===form.dataset.id);mutate(()=>{if(el.dataset.mapNode)c.nodes=el.checked?[...new Set([...c.nodes,el.dataset.mapNode])]:c.nodes.filter(id=>id!==el.dataset.mapNode);else if(el.name)c[el.name]=el.value;},false);
  }
});
$('#project-name').addEventListener('change',e=>{const name=e.target.value.trim();if(!name){e.target.value=project.name;return;}mutate(()=>project.name=name,false);});
$('#search').addEventListener('input',e=>{ui.query=e.target.value;renderSidebar();renderGraph();if(ui.view==='inventory')renderInventory();if(ui.view==='coverage')renderCoverage();if(ui.view==='phases')renderPhases();});
$('#stage-filter').addEventListener('change',e=>{ui.stage=e.target.value;clearSelection();render();fit();});
$('#show-optional').addEventListener('change',e=>{ui.optional=e.target.checked;render();fit();});
$('#edge-filter').addEventListener('change',e=>{ui.edges=e.target.value;renderSidebar();renderGraph();});
$('#coverage-view').addEventListener('input',e=>{if(e.target.id==='cap-search'){const pos=e.target.selectionStart;ui.capQuery=e.target.value;renderCoverage();$('#cap-search').focus();$('#cap-search').setSelectionRange(pos,pos);}});
$('#coverage-view').addEventListener('change',e=>{if(e.target.id==='cap-level-filter'){ui.capLevel=e.target.value;renderCoverage();}});
$('#phases-view').addEventListener('change',e=>{if(e.target.dataset.phase!==undefined)mutate(()=>project.phaseNotes[Number(e.target.dataset.phase)]=e.target.value,false);if(e.target.dataset.statusNode)mutate(()=>node(e.target.dataset.statusNode).status=e.target.value);});
$('#add-btn').onclick=()=>newNode();$('#add-region-side-btn').onclick=newRegion;$('#save-btn').onclick=()=>saveTopology();$('#export-btn').onclick=()=>$('#export-dialog').showModal();$('#import-btn').onclick=()=>$('#import-file').click();
$('#left-panel-toggle').onclick=()=>{ui.leftCollapsed=!ui.leftCollapsed;try{localStorage.setItem('zt-homelab:left-panel',ui.leftCollapsed?'collapsed':'open');}catch{}applyPanelState();requestAnimationFrame(fit);};
$('#right-panel-toggle').onclick=()=>{ui.rightCollapsed=!ui.rightCollapsed;try{localStorage.setItem('zt-homelab:right-panel',ui.rightCollapsed?'collapsed':'open');}catch{}applyPanelState();requestAnimationFrame(fit);};
$('#download-json').onclick=saveJSON;$('#download-html').onclick=saveHTML;$('#download-png').onclick=exportPNG;
$('#import-file').addEventListener('change',async e=>{const file=e.target.files[0];if(!file)return;try{assert(file.size<=8000000,'文件超过 8 MB');const data=validate(upgradeTopologyLayout(validate(JSON.parse(await file.text()))));beforeChange();project=data;clearSelection();ui.query='';ui.stage='all';ui.optional=true;$('#search').value='';$('#stage-filter').value='all';$('#show-optional').checked=true;persist();render();fit();toast('拓扑已载入');}catch(error){toast(`未导入：${error.message}`);}finally{e.target.value='';}});
$('#delete-dialog').addEventListener('close',()=>{if($('#delete-dialog').returnValue==='delete')removeSelected();});
$('#settings-btn').onclick=()=>{const form=$('#settings-form');Object.entries(project.settings).forEach(([k,v])=>form.elements[k].value=v);$('#settings-dialog').showModal();};
$('#settings-form').addEventListener('submit',e=>{e.preventDefault();const values=Object.fromEntries(new FormData(e.target).entries());Object.keys(values).forEach(k=>values[k]=Number(values[k]));if(values.reserveRam>=values.hostRam){toast('宿主预留内存必须小于总内存');return;}mutate(()=>{project.settings=values;const host=node('pve');if(host){host.cpu=values.hostCpu;host.ram=values.hostRam;host.disk=values.hostDisk;}});$('#settings-dialog').close();});
$('#undo-btn').onclick=()=>historyStep();$('#redo-btn').onclick=()=>historyStep(true);$('#fit-btn').onclick=fit;$('#arrange-btn').onclick=arrange;
['select','pan','connect'].forEach(t=>$(`#${t}-tool`).onclick=()=>setTool(t));$('#zoom-in').onclick=()=>zoomAt(1.2);$('#zoom-out').onclick=()=>zoomAt(1/1.2);
$('#snap-btn').onclick=()=>{ui.snap=!ui.snap;ui.guides=[];try{localStorage.setItem('zt-homelab:snap',ui.snap?'on':'off');}catch{}renderGraph();};
$('#graph').addEventListener('pointerover',e=>{if(ui.selected.size||ui.edge||ui.drag)return;const n=e.target.closest('.graph-node');ui.hover=n?.dataset.id||null;applyFocus();});
$('#graph').addEventListener('pointerleave',()=>{ui.hover=null;applyFocus();});
$('#graph').addEventListener('pointerdown',e=>{
  if(ui.drag||(e.button!==0&&e.button!==1))return;const ng=e.target.closest('.graph-node'),eg=e.target.closest('.graph-edge'),zg=e.target.closest('.zone-handle');
  if(ui.tool==='connect'&&ng){connectTo(ng.dataset.id);e.preventDefault();return;}
  if(eg&&ui.tool!=='pan'&&e.button===0){clearSelection();ui.edge=eg.dataset.edge;render();$('#inspector').classList.add('open');return;}
  const pan=ui.tool==='pan'||e.button===1||!ng;
  if(zg&&ui.tool==='select'&&e.button===0){ui.hover=null;ui.drag={type:'nodes',zone:zg.dataset.zoneId,zoneBox:regionBox(zg.dataset.zoneId),startX:e.clientX,startY:e.clientY,positions:project.nodes.filter(n=>n.zone===zg.dataset.zoneId).map(n=>({id:n.id,x:n.x,y:n.y})),snapshot:JSON.stringify(project),moved:false};renderGraph();}
  else if(!pan){const add=e.shiftKey||e.ctrlKey||e.metaKey;if(add)selectNode(ng.dataset.id,true);else if(!ui.selected.has(ng.dataset.id))selectNode(ng.dataset.id);ui.drag={type:'nodes',startX:e.clientX,startY:e.clientY,positions:[...ui.selected].map(id=>({id,x:node(id).x,y:node(id).y})),snapshot:JSON.stringify(project),moved:false};}
  else ui.drag={type:'pan',startX:e.clientX,startY:e.clientY,x:ui.x,y:ui.y,moved:false,clear:!ng&&!eg};
  ui.guides=[];ui.drag.pointerId=e.pointerId;if(ui.drag.type==='nodes')ui.drag.alignment=dragAlignment(ui.drag);$('#graph').setPointerCapture(e.pointerId);e.preventDefault();
});
function movePositions(positions,dx,dy){
  if(!positions.length)return {dx:0,dy:0};
  // Clamp one shared delta so group spacing stays intact at the canvas limits.
  dx=Math.max(-50000-Math.min(...positions.map(p=>p.x)),Math.min(50000-Math.max(...positions.map(p=>p.x)),dx));
  dy=Math.max(-50000-Math.min(...positions.map(p=>p.y)),Math.min(50000-Math.max(...positions.map(p=>p.y)),dy));
  positions.forEach(p=>{const n=node(p.id);n.x=p.x+dx;n.y=p.y+dy;});
  return {dx,dy};
}
function dragAlignment(d){
  const visible=visibleNodes(),ids=new Set(d.positions.map(p=>p.id)),moving=visible.filter(n=>ids.has(n.id));
  if(d.zone){const rects=zoneRects(visible);return {moving:rects.find(z=>z.id===d.zone)||d.zoneBox,targets:rects.filter(z=>z.id!==d.zone)};}
  if(!moving.length)return null;
  const b=bounds(moving);
  return {moving:{x:b.x+28,y:b.y+28,w:b.w-56,h:b.h-56},targets:visible.filter(n=>!ids.has(n.id)).map(nodeBox)};
}
function moveRegion(d,dx,dy){const b=d.zoneBox,applied=d.positions.length?movePositions(d.positions,dx,dy):{dx:Math.max(-50000-b.x,Math.min(50000-b.x,dx)),dy:Math.max(-50000-b.y,Math.min(50000-b.y,dy))};updateZone(d.zone,{x:b.x+applied.dx,y:b.y+applied.dy});return applied;}
function alignmentMatch(moving,targets,axis,delta,threshold){
  const size=axis==='x'?'w':'h',other=axis==='x'?'y':'x',otherSize=axis==='x'?'h':'w';let best=null;
  for(const target of targets){
    const distance=Math.abs(moving[other]+moving[otherSize]/2-target[other]-target[otherSize]/2);
    for(const from of [0,.5,1])for(const to of [0,.5,1]){
      if((from===.5)!==(to===.5))continue;
      const value=target[axis]+target[size]*to,offset=value-(moving[axis]+moving[size]*from+delta),error=Math.abs(offset);
      if(error<=threshold&&(!best||error<best.error-1e-6||(Math.abs(error-best.error)<1e-6&&distance<best.distance)))best={offset,error,distance,value,from,target};
    }
  }
  return best;
}
function updateAlignedDrag(d,alt=false){
  let dx=d.dx,dy=d.dy;const a=d.alignment;ui.guides=[];
  // Match against fixed drag-start geometry; use screen pixels for consistent snapping at every zoom.
  const x=ui.snap&&!alt&&a?alignmentMatch({...a.moving,y:a.moving.y+dy},a.targets,'x',dx,7/ui.zoom):null;
  const y=ui.snap&&!alt&&a?alignmentMatch({...a.moving,x:a.moving.x+dx},a.targets,'y',dy,7/ui.zoom):null;
  const applied=d.zone?moveRegion(d,dx+(x?.offset||0),dy+(y?.offset||0)):movePositions(d.positions,dx+(x?.offset||0),dy+(y?.offset||0));d.applied=applied;
  if(a){const box={...a.moving,x:a.moving.x+applied.dx,y:a.moving.y+applied.dy},pad=12/ui.zoom;
    for(const [axis,match] of [['x',x],['y',y]]){if(!match)continue;const size=axis==='x'?'w':'h';if(Math.abs(box[axis]+box[size]*match.from-match.value)>1e-5)continue;
      ui.guides.push(axis==='x'?{x1:match.value,y1:Math.min(box.y,match.target.y)-pad,x2:match.value,y2:Math.max(box.y+box.h,match.target.y+match.target.h)+pad}:{x1:Math.min(box.x,match.target.x)-pad,y1:match.value,x2:Math.max(box.x+box.w,match.target.x+match.target.w)+pad,y2:match.value});
    }
  }
  renderGraph();
}
function renderSnapGuides(){
  if(!ui.guides.length)return;
  const layer=document.createElementNS(NS,'g');layer.setAttribute('class','snap-guides');layer.setAttribute('aria-hidden','true');
  for(const guide of ui.guides){const line=document.createElementNS(NS,'line');for(const [key,value] of Object.entries(guide))line.setAttribute(key,value);line.setAttribute('vector-effect','non-scaling-stroke');layer.append(line);}
  $('#graph .graph-world').append(layer);
}
$('#graph').addEventListener('pointermove',e=>{const d=ui.drag;if(!d||e.pointerId!==d.pointerId)return;const dx=e.clientX-d.startX,dy=e.clientY-d.startY;if(Math.abs(dx)+Math.abs(dy)>3)d.moved=true;if(!d.moved)return;if(d.type==='pan'){ui.x=d.x+dx;ui.y=d.y+dy;updateTransform();}else{d.dx=dx/ui.zoom;d.dy=dy/ui.zoom;updateAlignedDrag(d,e.altKey);}});
function endDrag(cancel=false){const d=ui.drag;if(!d)return;ui.drag=null;ui.guides=[];$('#graph .snap-guides')?.remove();$('#canvas').classList.remove('dragging-zone');if($('#graph').hasPointerCapture(d.pointerId))$('#graph').releasePointerCapture(d.pointerId);if(d.type==='nodes'&&d.moved){if(cancel)project=JSON.parse(d.snapshot);else if((d.zone&&(d.applied?.dx||d.applied?.dy))||d.positions.some(p=>node(p.id).x!==p.x||node(p.id).y!==p.y)){ui.undo.push(d.snapshot);if(ui.undo.length>60)ui.undo.shift();ui.redo=[];persist();}else project=JSON.parse(d.snapshot);render();}else if(d.zone&&!d.moved&&!cancel)selectZone(d.zone);else if(d.type==='pan'&&!d.moved&&d.clear&&!cancel){clearSelection();$('#inspector').classList.remove('open');render();}}
$('#graph').addEventListener('pointerup',e=>{if(e.pointerId===ui.drag?.pointerId)endDrag();});
['pointercancel','lostpointercapture'].forEach(type=>$('#graph').addEventListener(type,e=>{if(e.pointerId===ui.drag?.pointerId)endDrag(true);}));
$('#canvas').addEventListener('wheel',e=>{e.preventDefault();if(ui.drag)return;const r=e.currentTarget.getBoundingClientRect();zoomAt(Math.exp(-e.deltaY*.0015),e.clientX-r.left,e.clientY-r.top);},{passive:false});
$('#graph').addEventListener('keydown',e=>{
  if(ui.drag)return;
  const zone=e.target.closest('.zone-handle'),step=e.shiftKey?50:10,direction={ArrowLeft:[-step,0],ArrowRight:[step,0],ArrowUp:[0,-step],ArrowDown:[0,step]}[e.key];
  if(zone&&direction&&ui.tool==='select'&&!e.ctrlKey&&!e.metaKey&&!e.altKey){e.preventDefault();const id=zone.dataset.zoneId;mutate(()=>moveRegion({zone:id,zoneBox:regionBox(id),positions:project.nodes.filter(n=>n.zone===id)},...direction));$(`#graph .zone-handle[data-zone-id="${id}"]`).focus({preventScroll:true});return;}
  if(e.key==='Enter'||e.key===' '){if(zone&&ui.tool==='select'){e.preventDefault();selectZone(zone.dataset.zoneId);$('#zone-form [name=name]')?.focus();return;}const n=e.target.closest('.graph-node');if(n){e.preventDefault();ui.tool==='connect'?connectTo(n.dataset.id):selectNode(n.dataset.id,e.shiftKey);}}
});
document.addEventListener('keydown',e=>{
  if(ui.drag){if(e.key==='Escape')endDrag(true);else if(e.key==='Alt'&&ui.drag.type==='nodes'&&ui.drag.moved)updateAlignedDrag(ui.drag,true);e.preventDefault();return;}
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='s'){e.preventDefault();saveTopology();return;}
  if(e.target.matches('input,textarea,select')||$('dialog[open]'))return;
  if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='z'){e.preventDefault();historyStep(e.shiftKey);}
  if(e.key==='Escape'){clearSelection();setTool('select');$('#inspector').classList.remove('open');render();}
  if(e.key==='Delete'||e.key==='Backspace'){e.preventDefault();askDelete();}
});
document.addEventListener('keyup',e=>{if(e.key==='Alt'&&ui.drag?.type==='nodes'&&ui.drag.moved){e.preventDefault();updateAlignedDrag(ui.drag,false);}});
window.addEventListener('resize',()=>{if(ui.view==='topology')updateTransform();});
window.addEventListener('beforeunload',()=>{const el=document.activeElement;if(el?.closest('#inspector form')||el?.id==='project-name')el.dispatchEvent(new Event('change',{bubbles:true}));});
$('#stage-filter').value='all';$('#show-optional').checked=true;$('#edge-filter').value='traffic';$('#search').value='';$('#inspector').classList.remove('open');applyPanelState();
switchView('topology');persist();requestAnimationFrame(fit);if(startupNotice)toast(startupNotice);
