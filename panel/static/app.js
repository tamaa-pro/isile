'use strict';
const $=(s,r=document)=>r.querySelector(s);
const csrf=$('meta[name=csrf]').content;
const VERSION=$('meta[name=version]').content;
const NS='http://www.w3.org/2000/svg';
const GB=1073741824;
const PM={ssh:{i:'terminal',n:'SSH'},vless:{i:'bolt',n:'VLESS'},vmess:{i:'diagram-project',n:'VMess'},trojan:{i:'shield-halved',n:'Trojan'}};
const SC={active:'ok',disabled:'off',expired:'bad',limit:'warn'};
const el=(t,a={},...k)=>{const e=document.createElement(t);for(const[x,v]of Object.entries(a)){if(x==='class')e.className=v;else if(x.startsWith('on'))e.addEventListener(x.slice(2),v);else if(v!==false&&v!=null)e.setAttribute(x,v===true?'':v)}for(const c of k.flat()){if(c==null||c===false)continue;e.append(c instanceof Node?c:document.createTextNode(String(c)))}return e};
const ic=(n,c='')=>el('i',{class:'fa-solid fa-'+n+(c?' '+c:'')});
const api=async(m,u,b)=>{const r=await fetch(u,{method:m,headers:{'Content-Type':'application/json','X-CSRF':csrf},body:b?JSON.stringify(b):undefined,credentials:'same-origin'});if(r.status===401){location.href='/login';throw new Error('unauthorized')}const j=await r.json().catch(()=>({}));if(!r.ok)throw Object.assign(new Error(j.error||'error'),{detail:j.detail});return j};
const spd=(u,d)=>'↓ '+bytes(d)+'/s  ↑ '+bytes(u)+'/s';
const bytes=n=>{if(!n||n<0)return'0 B';const u=['B','KB','MB','GB','TB','PB'];const i=Math.min(Math.floor(Math.log(n)/Math.log(1024)),5);return(n/1024**i).toFixed(i?2:0)+' '+u[i]};
const dt=ts=>ts?new Date(ts*1000).toLocaleDateString('en-GB'):t('unlimited');
const left=ts=>{if(!ts)return t('unlimited');const d=Math.ceil((ts*1000-Date.now())/864e5);return d>0?t('days_n',d):t('ended')};
const upt=s=>{const d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);return(d?t('d_short',d)+' ':'')+t('h_short',h)+' '+t('m_short',m)};
const rnd=n=>{const c='abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789',a=new Uint32Array(n);crypto.getRandomValues(a);return Array.from(a,x=>c[x%c.length]).join('')};
const toast=m=>{const x=el('div',{class:'toast',popover:'manual'},m);document.body.append(x);try{x.showPopover()}catch(e){}setTimeout(()=>x.remove(),3500)};
const terr=e=>{if(e.message==='unauthorized')return;const k='e_'+e.message;const m=tx(k);toast(m!==k?m+(e.detail?': '+e.detail:''):(e.detail||e.message))};
const field=(l,i,h)=>el('label',{class:'f'},el('span',{},l),i,h?el('small',{class:'muted'},h):null);
const kv=(l,v,x)=>el('div',{class:'kv'},el('span',{},l),el('b',{class:'ltr'},v),x);
const copy=async v=>{try{await navigator.clipboard.writeText(v);toast(t('copied'))}catch{toast(t('copy_fail'))}};
const modal=(title,body,btns=[],cls='')=>{const d=el('dialog',{class:cls},el('div',{class:'dlg-h'},el('h3',{},title),el('button',{class:'icon-btn',title:t('close'),onclick:()=>d.close()},ic('xmark'))),el('div',{class:'dlg-b'},body),btns.length?el('div',{class:'dlg-f'},...btns):null);d.addEventListener('close',()=>d.remove());document.body.append(d);d.showModal();return d};
const btn=(label,icon,f,c='')=>el('button',{class:'btn '+c,type:'button',onclick:f},icon?ic(icon):null,label?el('span',{},label):null);
const seg=(opts,val,on)=>{const box=el('div',{class:'seg'});const draw=()=>box.replaceChildren(...opts.map(o=>el('button',{type:'button',class:o.v===val?'on':'',onclick:()=>{val=o.v;on(val);draw()}},o.i?ic(o.i):null,el('span',{},o.l))));draw();return box};
function dd(opts,val,on){
const lab=el('span',{class:'dd-l'});
const b=el('button',{type:'button',class:'dd-b'},lab,ic('chevron-down','dd-c'));
const wrap=el('div',{class:'dd'},b);
let pop=null;
const set=v=>{val=v;lab.textContent=(opts.find(o=>o.v===v)||opts[0]).l};
function close(){if(!pop)return;pop.remove();pop=null;wrap.classList.remove('open');document.removeEventListener('mousedown',out,true);document.removeEventListener('keydown',key,true);document.removeEventListener('scroll',sc,true);window.removeEventListener('resize',close)}
function out(e){if(pop&&!pop.contains(e.target)&&!b.contains(e.target))close()}
function key(e){if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close()}}
function sc(e){if(pop&&!pop.contains(e.target))close()}
b.addEventListener('click',()=>{
if(pop){close();return}
pop=el('div',{class:'dd-p'},...opts.map(o=>el('button',{type:'button',class:'dd-o'+(o.v===val?' on':''),onclick:()=>{set(o.v);on(o.v);close()}},o.i?ic(o.i):null,el('span',{},o.l),o.v===val?ic('check','dd-k'):null)));
wrap.append(pop);wrap.classList.add('open');
const r=b.getBoundingClientRect();
pop.style.minWidth=Math.max(r.width,170)+'px';
const w=pop.offsetWidth,h=pop.offsetHeight;
let left=r.left;if(left+w>innerWidth-8)left=innerWidth-8-w;
let top=r.bottom+6;if(top+h>innerHeight-8)top=Math.max(8,r.top-6-h);
pop.style.left=Math.max(8,left)+'px';pop.style.top=top+'px';
document.addEventListener('mousedown',out,true);document.addEventListener('keydown',key,true);document.addEventListener('scroll',sc,true);window.addEventListener('resize',close)
});
set(val);
return wrap
}
const chips=(vals,input)=>el('div',{class:'chips'},...vals.map(v=>el('button',{type:'button',class:'chip',onclick:()=>{input.value=v}},v===0?ic('infinity'):v)));
const meter=(p,c='')=>{const i=el('i');i.style.width=Math.max(0,Math.min(100,p))+'%';return el('div',{class:'meter '+c},i)};
const liveDot=on=>el('span',{class:'dot'+(on?' live':''),title:t(on?'live_on':'live_off')});
const badge=p=>el('span',{class:'pb p-'+p},ic(PM[p].i),PM[p].n);
const pill=(c,l)=>el('span',{class:'pill '+c},l);
function ask(msg,okLabel,onOk,o={}){
const d=modal(o.title||t('confirm'),el('div',{},el('p',{class:'ask'},msg),o.extra||null),[btn(okLabel,o.danger===false?'check':'triangle-exclamation',async()=>{if(await onOk()!==false)d.close()},o.danger===false?'pri':'dgr'),btn(t('cancel'),'xmark',()=>d.close())]);
return d
}
function overlay(msg){const o=el('div',{class:'ovl'},el('div',{class:'ovl-b'},ic('spinner','fa-spin ovl-i'),el('div',{class:'ovl-t'},msg)));document.body.append(o);return o}
function logDlg(log){modal(t('job_fail'),el('div',{},el('div',{class:'muted sm'},t('job_log')),el('pre',{class:'log'},log||'-')))}
async function runJob(url,body,msg,redirect){
try{await api('POST',url,body)}catch(e){terr(e);return}
const o=overlay(msg);
const t0=Date.now();
let fails=0;
const loop=async()=>{
try{
const j=await api('GET','/api/system/job');
fails=0;
if(j.state==='done'){o.remove();if(j.rc===0){toast(t('job_ok'));setTimeout(()=>location.reload(),900)}else logDlg(j.log);return}
if(j.state==='none'&&Date.now()-t0>20000){o.remove();location.reload();return}
}catch(e){fails++;if(redirect&&fails>=3){location.href=redirect;return}}
if(Date.now()-t0>600000){o.remove();return}
setTimeout(loop,2500)
};
setTimeout(loop,3000)
}
function spark(v,cls,max){const svg=document.createElementNS(NS,'svg');svg.setAttribute('viewBox','0 0 100 32');svg.setAttribute('preserveAspectRatio','none');svg.setAttribute('class','spark '+cls);if(v.length<2)return svg;const mx=max||Math.max(...v,1e-9);const pts=v.map((y,i)=>(i/(v.length-1)*100).toFixed(1)+','+(30-(Math.min(y,mx)/mx)*26).toFixed(1)).join(' ');const a=document.createElementNS(NS,'polygon');a.setAttribute('points','0,32 '+pts+' 100,32');a.setAttribute('class','sa');const l=document.createElementNS(NS,'polyline');l.setAttribute('points',pts);l.setAttribute('class','sl');svg.append(a,l);return svg}
const tile=(icon,col,title,value,sub,extra)=>el('div',{class:'tile'},el('div',{class:'tile-h'},el('span',{class:'ico '+col},ic(icon)),el('span',{class:'tile-t'},title)),el('div',{class:'tile-v'},value),sub?el('div',{class:'muted tile-s'},sub):null,extra);
const panel=(icon,title,...k)=>el('section',{class:'panel'},el('h3',{class:'panel-h'},ic(icon),title),...k);
let ACC=[],S=null,PREV=null,PAGE='dashboard',BUSY=false;
const H={cpu:[],ram:[],rx:[],tx:[]};
const F={q:'',p:'',s:''};
const push=(a,v)=>{a.push(v);if(a.length>60)a.shift()};
async function loadAcc(){ACC=await api('GET','/api/accounts')}
async function loadStats(){const s=await api('GET','/api/stats');if(PREV&&s.ts>PREV.ts){const d=s.ts-PREV.ts;push(H.rx,Math.max(0,(s.net_rx-PREV.net_rx)/d));push(H.tx,Math.max(0,(s.net_tx-PREV.net_tx)/d))}push(H.cpu,s.cpu);push(H.ram,s.mem_total?s.mem_used/s.mem_total*100:0);PREV=s;S=s}
function drawDash(){
const s=S,A=ACC;
const act=A.filter(a=>a.status==='active').length;
const up=A.reduce((x,a)=>x+a.up,0),dn=A.reduce((x,a)=>x+a.down,0);
const rx=H.rx.length?H.rx[H.rx.length-1]:0,tx=H.tx.length?H.tx[H.tx.length-1]:0;
const ramP=s.mem_total?s.mem_used/s.mem_total*100:0,diskP=s.disk_total?s.disk_used/s.disk_total*100:0;
const row1=el('div',{class:'grid g4'},
tile('microchip','c1',t('d_cpu'),s.cpu.toFixed(1)+'%',t('d_cores',s.cores)+' · '+t('d_load')+' '+s.load[0].toFixed(2),spark(H.cpu,'s1',100)),
tile('memory','c2',t('d_ram'),ramP.toFixed(1)+'%',bytes(s.mem_used)+' / '+bytes(s.mem_total),spark(H.ram,'s2',100)),
tile('hard-drive','c3',t('d_disk'),diskP.toFixed(1)+'%',bytes(s.disk_used)+' / '+bytes(s.disk_total),meter(diskP,diskP>90?'bad':'')),
tile('network-wired','c4',t('d_net'),el('span',{class:'ltr'},'↓ '+bytes(rx)+'/s'),'↑ '+bytes(tx)+'/s',spark(H.rx,'s4')),
portsTile(s.ports||[]));
const cap=s.cap_gb*GB,used=s.month_used,pc=cap?used/cap*100:0;
const trf=el('div',{class:'tile wide'},
el('div',{class:'tile-h'},el('span',{class:'ico c9'},ic('server')),el('span',{class:'tile-t'},t('d_server_traffic'))),
el('div',{class:'tw'},el('div',{class:'tile-v ltr'},bytes(used)+(cap?' / '+bytes(cap):'')),el('div',{class:'muted ltr'},'↓ '+bytes(s.month_rx)+'    ↑ '+bytes(s.month_tx))),
cap?meter(pc,pc>=95?'bad':pc>=80?'warnm':''):null,
el('div',{class:'muted tile-s'},cap?(used>=cap?t('d_cap_over'):t('d_cap_left',bytes(cap-used)))+' · '+pc.toFixed(1)+'%':t('d_no_cap')));
const row2=el('div',{class:'grid g4'},
tile('users','c5',t('d_accounts'),A.length,t('d_active_n',act)),
tile('chart-line','c7',t('d_traffic'),bytes(up+dn),'↑ '+bytes(up)+' · ↓ '+bytes(dn)),
tile('clock','c8',t('d_uptime'),upt(s.uptime),t('d_load')+' '+s.load.map(x=>x.toFixed(2)).join(' / ')));
const tot=Math.max(1,up+dn);
const byp=el('div',{class:'list'},...Object.keys(PM).map(p=>{const l=A.filter(a=>a.proto===p);const tr=l.reduce((x,a)=>x+a.up+a.down,0);return el('div',{class:'li'},el('div',{class:'li-h'},badge(p),el('b',{},l.length),el('span',{class:'muted'},bytes(tr))),meter(tr/tot*100,'m-'+p))}));
const top=[...A].sort((a,b)=>b.up+b.down-a.up-a.down).slice(0,5).filter(a=>a.up+a.down>0);
const topL=el('div',{class:'list'},...(top.length?top.map(a=>el('div',{class:'li'},el('div',{class:'li-h'},badge(a.proto),el('b',{},a.name),el('span',{class:'muted'},bytes(a.up+a.down))),meter((a.up+a.down)/(top[0].up+top[0].down)*100,'m-'+a.proto))):[el('div',{class:'empty'},t('d_none'))]));
const now=Date.now()/1000;
const exp=A.filter(a=>a.expires&&a.expires>now&&a.expires-now<7*86400).sort((a,b)=>a.expires-b.expires).slice(0,6);
const expL=el('div',{class:'list'},...(exp.length?exp.map(a=>el('div',{class:'li li-r'},badge(a.proto),el('b',{},a.name),el('span',{class:'muted'},left(a.expires)))):[el('div',{class:'empty'},t('d_none'))]));
const sv=el('div',{class:'svc'},...Object.entries(s.services).map(([k,v])=>el('span',{class:'pill '+(v?'ok':'bad')},ic(v?'circle-check':'circle-xmark'),k)));
$('#view').replaceChildren(row1,trf,row2,el('div',{class:'grid g2'},panel('diagram-project',t('d_by_proto'),byp),panel('ranking-star',t('d_top'),topL)),el('div',{class:'grid g2'},panel('hourglass-half',t('d_expiring'),expL),panel('server',t('d_services'),sv)))
}
function portsTile(P){
const on=P.filter(p=>p.listening).length,tot=P.filter(p=>p.enabled).length;
return tile('plug','c6',t('pt_title'),on+' / '+tot,t('pt_sub'),el('div',{class:'ports'},...P.map(p=>el('div',{class:'pt'},el('b',{class:'ltr'},p.port),el('span',{class:'muted'},t('pt_'+p.k)),pill(p.listening?'ok':p.enabled?'bad':'off',t(p.listening?'pt_listen':p.enabled?'pt_closed':'pt_off'))))))
}
function accRow(a){
const used=a.up+a.down;
const act=a.status==='active';
const tlsTag=a.tls==='both'?'TLS + 80':a.tls==='tls'?'TLS 443':'80';
return el('tr',{},
el('td',{},el('b',{},a.name),a.note?el('div',{class:'muted sm'},a.note):null),
el('td',{},badge(a.proto),el('div',{class:'muted sm'},tlsTag)),
el('td',{},pill(SC[a.status],t('st_'+a.status))),
el('td',{},el('span',{class:'live-row'},liveDot(act&&a.active)),act&&a.active?el('div',{class:'muted sm ltr'},spd(a.sp_up,a.sp_down)):null),
el('td',{class:'usage'},el('div',{class:'ltr'},'↑ '+bytes(a.up)+'  ↓ '+bytes(a.down)),el('div',{class:'muted sm ltr'},bytes(used)+' / '+(a.quota?bytes(a.quota):'∞')),a.quota?meter(used/a.quota*100,used/a.quota>.9?'bad':''):null),
el('td',{},el('div',{},dt(a.expires)),el('div',{class:'muted sm'},left(a.expires))),
el('td',{},el('div',{class:'acts'},
el('button',{class:'icon-btn',title:t('a_info'),onclick:()=>infoDlg(a.name)},ic('circle-info')),
el('button',{class:'icon-btn',title:t('a_edit'),onclick:()=>accDlg(a)},ic('pen-to-square')),
el('button',{class:'icon-btn',title:a.manual?t('a_enable'):t('a_disable'),onclick:()=>patch(a.name,{manual:!a.manual})},ic(a.manual?'circle-check':'ban')),
el('button',{class:'icon-btn danger',title:t('a_delete'),onclick:()=>del(a)},ic('trash')))))
}
function drawRows(){
const q=F.q.trim().toLowerCase();
const l=ACC.filter(a=>(!F.p||a.proto===F.p)&&(!F.s||a.status===F.s)&&(!q||a.name.includes(q)||a.note.toLowerCase().includes(q)));
const r=$('#rows');if(!r)return;
r.replaceChildren(...(l.length?l.map(accRow):[el('tr',{},el('td',{colspan:7,class:'empty'},t('a_empty')))]));
const c=$('#cnt');if(c)c.textContent=l.length+' / '+ACC.length
}
function viewAccounts(){
const q=el('input',{placeholder:t('a_search'),value:F.q});
q.addEventListener('input',()=>{F.q=q.value;drawRows()});
const p=dd([{v:'',l:t('a_all_protos'),i:'layer-group'},...Object.entries(PM).map(([k,v])=>({v:k,l:v.n,i:v.i}))],F.p,v=>{F.p=v;drawRows()});
const s=dd([{v:'',l:t('a_all_status'),i:'filter'},...Object.keys(SC).map(k=>({v:k,l:t('st_'+k)}))],F.s,v=>{F.s=v;drawRows()});
const tb=el('div',{class:'toolbar'},el('div',{class:'search'},ic('magnifying-glass'),q),p,s,el('span',{class:'muted',id:'cnt'}),btn(t('a_add'),'plus',()=>accDlg(),'pri'));
const th=['c_name','c_proto','c_status','c_live','c_usage','c_expiry','c_actions'].map(k=>el('th',{},t(k)));
$('#view').replaceChildren(tb,el('div',{class:'wrap'},el('table',{},el('thead',{},el('tr',{},th)),el('tbody',{id:'rows'}))));
drawRows()
}
async function patch(n,b,msg){
try{await api('PATCH','/api/accounts/'+n,b);toast(msg||t('done'));await loadAcc();if(PAGE==='accounts')drawRows();return true}catch(e){terr(e);return false}
}
function del(a){
ask(t('a_confirm_del',a.name),t('a_delete'),async()=>{
try{await api('DELETE','/api/accounts/'+a.name);toast(t('deleted'));await loadAcc();drawRows()}catch(e){terr(e);return false}
})
}
async function infoDlg(n){
try{
const r=await api('GET','/api/accounts/'+n+'/info');
const used=r.up+r.down;
const head=el('div',{class:'info-h'},
el('div',{class:'row'},badge(r.proto),pill(SC[r.status],t('st_'+r.status))),
el('div',{class:'kv'},el('span',{},ic('wifi'),t('c_live')),el('span',{class:'live-row'},liveDot(r.active),t(r.active?'live_on':'live_off'))),
r.active?el('div',{class:'kv'},el('span',{},ic('gauge-high'),t('p_speed')),el('b',{class:'ltr'},spd(r.sp_up,r.sp_down))):null,
el('div',{class:'kv'},el('span',{},ic('chart-line'),t('c_usage')),el('b',{class:'ltr'},bytes(used)+' / '+(r.quota?bytes(r.quota):'∞'))),
r.quota?meter(used/r.quota*100):null,
el('div',{class:'kv'},el('span',{},ic('calendar-plus'),t('c_created')),el('b',{},dt(r.created))),
el('div',{class:'kv'},el('span',{},ic('clock'),t('c_expiry')),el('b',{},dt(r.expires)+' · '+left(r.expires))));
const warn=(!r.tls_on&&r.tls!=='plain')?el('div',{class:'hint'},ic('triangle-exclamation'),t('i_tls_off')):null;
const items=r.items.map(i=>el('div',{class:'item'},el('div',{class:'item-h'},el('span',{},t('l_'+i.k)),el('button',{class:'icon-btn',title:t('copy'),onclick:()=>copy(i.value)},ic('copy'))),el('textarea',{readonly:true,rows:i.rows||2,dir:'ltr'},i.value)));
modal(t('i_title',n),el('div',{},head,warn,...items))
}catch(e){terr(e)}
}
async function accDlg(a){
if(!S){try{await loadStats()}catch(e){}}
const ed=!!a;
const tlsOn=!S||S.tls_on!==false;
const forced=!tlsOn&&!ed;
const st={kind:ed?(a.proto==='ssh'?'ssh':'v2'):'ssh',proto:ed?a.proto:'vless',tls:forced?'plain':ed?a.tls:'both'};
const name=el('input',{placeholder:'user1',maxlength:20,autocomplete:'off',dir:'ltr',value:ed?a.name:''});
if(ed)name.disabled=true;
const secret=el('input',{autocomplete:'off',dir:'ltr',placeholder:ed?t('f_keep'):t('f_auto')});
const days=el('input',{type:'number',min:0,placeholder:ed?t('f_keep'):'',value:ed?'':30});
const quota=el('input',{type:'number',min:0,step:'any',value:ed&&a.quota?+(a.quota/GB).toFixed(3):0});
const note=el('input',{maxlength:100,value:ed?a.note:''});
const genName=el('button',{type:'button',class:'icon-btn',title:t('f_gen'),onclick:()=>{name.value='u'+rnd(6).toLowerCase()}},ic('dice'));
const genSec=el('button',{type:'button',class:'icon-btn',title:t('f_gen'),onclick:()=>{secret.value=(st.kind==='v2'&&st.proto!=='trojan')?crypto.randomUUID():rnd(14)}},ic('dice'));
const kindSeg=seg([{v:'ssh',l:'SSH',i:'terminal'},{v:'v2',l:'V2Ray',i:'bolt'}],st.kind,v=>{st.kind=v;sync()});
const protoSeg=seg([{v:'vless',l:'VLESS',i:'bolt'},{v:'vmess',l:'VMess',i:'diagram-project'},{v:'trojan',l:'Trojan',i:'shield-halved'}],st.proto,v=>{st.proto=v;sync()});
const tlsSeg=seg([{v:'tls',l:t('tls_tls'),i:'lock'},{v:'plain',l:t('tls_plain'),i:'lock-open'},{v:'both',l:t('tls_both'),i:'layer-group'}],st.tls,v=>{st.tls=v});
const tlsHint=el('div',{class:'hint'},ic('triangle-exclamation'),t('tls_unavailable'));
const secLabel=el('span',{});
const boxProto=field(t('f_proto'),protoSeg);
const boxTls=field(t('f_tls'),tlsSeg,t('f_tls_hint'));
const boxKind=field(t('f_type'),kindSeg);
function sync(){
const v2=st.kind==='v2';
boxProto.hidden=!v2||ed;boxTls.hidden=forced;tlsHint.hidden=!forced;
secLabel.textContent=(v2&&st.proto!=='trojan')?t('f_uuid'):t('f_password')
}
const form=el('div',{class:'form'},
ed?null:boxKind,boxProto,boxTls,tlsHint,
field(t('f_name'),el('div',{class:'inp-row'},name,ed?null:genName)),
el('label',{class:'f'},secLabel,el('div',{class:'inp-row'},secret,genSec)),
el('div',{class:'two'},
el('div',{class:'f'},el('span',{},t('f_days')),days,chips(ed?[30,90,365,0]:[7,30,90,365,0],days)),
el('div',{class:'f'},el('span',{},t('f_quota')),quota,chips([5,10,50,100,0],quota))),
field(t('f_note'),note));
sync();
const d=modal(ed?t('a_edit_t',a.name):t('a_new'),form,[
btn(ed?t('save'):t('create'),ed?'floppy-disk':'plus',async()=>{
const b={secret:secret.value,days:days.value,quota_gb:quota.value,note:note.value,tls:st.tls};
try{
if(ed){await api('PATCH','/api/accounts/'+a.name,b);toast(t('done'));d.close();await loadAcc();drawRows()}
else{const proto=st.kind==='ssh'?'ssh':st.proto;const r=await api('POST','/api/accounts',{...b,proto,name:name.value});d.close();await loadAcc();drawRows();infoDlg(r.name)}
}catch(e){terr(e)}
},'pri'),
ed?btn(t('regen'),'rotate',async()=>{if(await patch(a.name,{regen:true},t('regen_done')))d.close()}):null,
ed?btn(t('reset_traffic'),'eraser',async()=>{if(await patch(a.name,{reset:true},t('reset_done')))d.close()}):null],'wide')
}
async function viewSettings(){
const s=await api('GET','/api/settings');
const th=document.documentElement.dataset.theme;
const o=el('input',{type:'password',autocomplete:'current-password'});
const n=el('input',{type:'password',autocomplete:'new-password'});
const c=el('input',{type:'password',autocomplete:'new-password'});
const savePw=async()=>{
if(n.value!==c.value){toast(t('s_mismatch'));return}
try{await api('POST','/api/password',{old:o.value,new:n.value});toast(t('s_changed'));o.value=n.value=c.value=''}catch(e){terr(e)}
};
const dom=el('input',{placeholder:'vpn.example.com',dir:'ltr',value:s.domain,autocomplete:'off'});
const mail=el('input',{placeholder:'you@example.com',dir:'ltr',autocomplete:'off'});
const res=el('div',{class:'kvs'});
const showDom=r=>res.replaceChildren(...[
kv(t('dm_current'),r.domain||t('dm_none')),
kv(t('dm_server_ip'),r.server_ip||'—'),
kv(t('dm_dns'),r.dns.length?r.dns.join(', '):'—',r.candidate?pill(r.match?'ok':'bad',r.match?t('dm_match'):t('dm_nomatch')):null),
kv(t('dm_cert'),r.cert?t('dm_cert_days',r.cert.days_left)+' ('+dt(r.cert.expires)+')':t('dm_cert_none')),
r.candidate&&!r.match?el('div',{class:'hint'},ic('triangle-exclamation'),t('dm_warn',r.candidate,r.server_ip||'—')):null].filter(Boolean));
const verify=async(quiet)=>{try{const r=await api('GET','/api/domain'+(dom.value.trim()?'?d='+encodeURIComponent(dom.value.trim().toLowerCase()):''));showDom(r);if(!quiet)toast(t('dm_checked'))}catch(e){terr(e)}};
verify(true);
const applyDom=()=>{
const d=dom.value.trim().toLowerCase();
if(!d){toast(t('e_bad_domain'));return}
ask(t('dm_confirm',d),t('confirm'),()=>{runJob('/api/domain',{domain:d,email:mail.value.trim()},t('dm_working'),'https://'+d+':2080/')},{danger:false})
};
let bv=s.cap_basis;
const basisDd=dd([{v:'total',l:t('basis_total')},{v:'out',l:t('basis_out')}],bv,v=>{bv=v});
const cap=el('input',{type:'number',min:0,step:'any',value:s.cap_gb});
const usedIn=el('input',{type:'number',min:0,step:'any',placeholder:+(s.month_used/GB).toFixed(2)});
const saveLim=async()=>{
try{await api('POST','/api/settings',{cap_gb:cap.value,cap_basis:bv,used_gb:usedIn.value});toast(t('lim_saved'));usedIn.value='';if(S)await loadStats()}catch(e){terr(e)}
};
const resetMonth=()=>ask(t('lim_reset_confirm'),t('lim_reset'),async()=>{try{await api('POST','/api/settings',{reset:true});toast(t('lim_saved'));if(S)await loadStats()}catch(e){terr(e);return false}});
const row=(icon,title,desc,b)=>el('div',{class:'srow'},el('span',{class:'ico c1'},ic(icon)),el('div',{class:'srow-t'},el('b',{},title),el('div',{class:'muted sm'},desc)),b);
const pw=el('input',{type:'password',autocomplete:'current-password',placeholder:t('sys_uninstall_pw')});
const doUninstall=()=>ask(t('sys_uninstall_confirm'),t('sys_uninstall'),async()=>{
try{await api('POST','/api/system/uninstall',{password:pw.value})}catch(e){terr(e);return false}
const ov=overlay(t('sys_w_uninstall'));
setTimeout(()=>ov.replaceChildren(el('div',{class:'ovl-b'},ic('circle-check','ovl-i ok-i'),el('div',{class:'ovl-t'},t('sys_removed')))),9000)
},{extra:pw});
$('#view').replaceChildren(el('div',{class:'grid g2'},
panel('palette',t('s_appearance'),el('div',{class:'form'},
field(t('s_theme'),seg([{v:'dark',l:t('theme_dark'),i:'moon'},{v:'light',l:t('theme_light'),i:'sun'}],th,v=>{localStorage.setItem('theme',v);document.documentElement.dataset.theme=v})),
field(t('s_language'),seg([{v:'en',l:'English',i:'language'},{v:'ar',l:'العربية',i:'language'}],LANG,setLang)))),
panel('key',t('s_security'),el('div',{class:'form'},field(t('s_cur'),o),field(t('s_new'),n,t('s_new_hint')),field(t('s_confirm'),c),btn(t('s_change'),'floppy-disk',savePw,'pri'))),
panel('globe',t('dm_title'),el('div',{class:'form'},res,field(t('dm_domain'),dom),field(t('dm_email'),mail),el('div',{class:'row'},btn(t('dm_apply'),'lock',applyDom,'pri'),btn(t('dm_verify'),'shield-halved',()=>verify(false))))),
panel('gauge-high',t('lim_title'),el('div',{class:'form'},
field(t('lim_cap'),cap,t('lim_cap_hint')),
field(t('lim_basis'),basisDd),
field(t('lim_used'),usedIn),
el('div',{class:'row'},btn(t('save'),'floppy-disk',saveLim,'pri'),btn(t('lim_reset'),'eraser',resetMonth)))),
panel('eye',t('pg_title'),el('div',{class:'form'},el('div',{class:'muted sm'},t('pg_desc')),seg([{v:'on',l:t('pg_on'),i:'eye'},{v:'off',l:t('pg_off'),i:'eye-slash'}],s.public_page?'on':'off',async v=>{try{await api('POST','/api/settings',{public_page:v==='on'});toast(t('pg_saved'))}catch(e){terr(e)}}))),
panel('screwdriver-wrench',t('sys_title'),el('div',{class:'kvs'},
kv(t('sys_version'),VERSION),
row('rotate-right',t('sys_restart'),t('sys_restart_desc'),btn('','power-off',()=>ask(t('sys_restart_confirm'),t('sys_restart'),()=>{runJob('/api/system/restart',null,t('sys_w_restart'))},{danger:false}))),
row('cloud-arrow-down',t('sys_update'),t('sys_update_desc'),btn('','cloud-arrow-down',()=>ask(t('sys_update_confirm'),t('sys_update'),()=>{runJob('/api/system/update',null,t('sys_w_update'))},{danger:false}))),
row('trash',t('sys_uninstall'),t('sys_uninstall_desc'),btn('','trash',doUninstall,'dgr'))))))
}
function setLang(v){
localStorage.setItem('lang',v);
const d=document.documentElement;d.lang=v;d.dir=v==='ar'?'rtl':'ltr';LANG=v;
shell();route()
}
const VIEWS={
dashboard:async()=>{await Promise.all([loadStats(),loadAcc()]);drawDash()},
accounts:async()=>{await loadAcc();viewAccounts()},
settings:async()=>{await viewSettings()}
};
function shell(){
document.title=t('app_title');
const link=(p,i)=>el('a',{href:'#/'+p,class:'nav-link','data-p':p,title:t('nav_'+p)},ic(i),el('span',{},t('nav_'+p)));
$('#nav').replaceChildren(link('dashboard','gauge-high'),link('accounts','users'));
$('#tools').replaceChildren(
el('button',{class:'nav-link keep',title:t('s_language'),onclick:()=>setLang(LANG==='ar'?'en':'ar')},ic('language'),el('span',{},t('lang_btn'))),
link('settings','gear'),
el('button',{class:'nav-link',title:t('logout'),onclick:async()=>{try{await api('POST','/api/logout')}catch{}location.href='/login'}},ic('right-from-bracket'),el('span',{},t('logout'))))
}
async function route(){
PAGE=location.hash.replace(/^#\//,'')||'dashboard';
if(!VIEWS[PAGE])PAGE='dashboard';
document.querySelectorAll('.nav-link').forEach(a=>a.classList.toggle('on',a.dataset.p===PAGE));
const v=$('#view');
v.replaceChildren(el('div',{class:'empty'},ic('spinner','fa-spin')));
v.classList.remove('enter');void v.offsetWidth;v.classList.add('enter');
try{await VIEWS[PAGE]()}catch(e){terr(e)}
}
async function tick(){
if(BUSY||document.hidden)return;
BUSY=true;
try{
if(PAGE==='dashboard'){await Promise.all([loadStats(),loadAcc()]);if(PAGE==='dashboard')drawDash()}
else if(PAGE==='accounts'){await loadAcc();if(PAGE==='accounts')drawRows()}
}catch(e){}
BUSY=false
}
window.addEventListener('hashchange',route);
shell();
route();
setInterval(tick,5000);
