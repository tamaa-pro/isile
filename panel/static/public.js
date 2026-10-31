'use strict';
const $=(s,r=document)=>r.querySelector(s);
const NAME=$('meta[name=acc]').content;
const PM={sshws:{i:'terminal',n:'SSH WS'},sshssl:{i:'lock',n:'SSH SSL'},sshudp:{i:'tower-broadcast',n:'UDP Custom'},vless:{i:'bolt',n:'VLESS'},vmess:{i:'diagram-project',n:'VMess'},trojan:{i:'shield-halved',n:'Trojan'}};
const pk=a=>a.proto==='ssh'?(a.transport==='ssl'?'sshssl':a.transport==='udp'?'sshudp':'sshws'):a.proto;
const SC={active:'ok',disabled:'off',expired:'bad',limit:'warn'};
const el=(t,a={},...k)=>{const e=document.createElement(t);for(const[x,v]of Object.entries(a)){if(x==='class')e.className=v;else if(x.startsWith('on'))e.addEventListener(x.slice(2),v);else if(v!==false&&v!=null)e.setAttribute(x,v===true?'':v)}for(const c of k.flat()){if(c==null||c===false)continue;e.append(c instanceof Node?c:document.createTextNode(String(c)))}return e};
const ic=(n,c='')=>el('i',{class:'fa-solid fa-'+n+(c?' '+c:'')});
const bytes=n=>{if(!n||n<0)return'0 B';const u=['B','KB','MB','GB','TB','PB'];const i=Math.min(Math.floor(Math.log(n)/Math.log(1024)),5);return(n/1024**i).toFixed(i?2:0)+' '+u[i]};
const meter=(p,c='')=>{const i=el('i');i.style.width=Math.max(0,Math.min(100,p))+'%';return el('div',{class:'meter '+c},i)};
const loc=cc=>{if(!/^[A-Z]{2}$/.test(cc||''))return null;let n=cc;try{n=new Intl.DisplayNames([LANG],{type:'region'}).of(cc)||cc}catch(e){}const f=String.fromCodePoint(...[...cc].map(c=>127397+c.charCodeAt(0)));return el('div',{class:'kv'},el('span',{},ic('location-dot'),t('p_location')),el('b',{},f+' '+n))};
const kv=(i,l,v,c='ltr')=>el('div',{class:'kv'},el('span',{},ic(i),l),el('b',{class:c},v));
let D=null,NF=false,OFF=false;
function tools(){
const th=document.documentElement.dataset.theme;
$('#tools').replaceChildren(
el('button',{class:'icon-btn',title:t('s_language'),onclick:()=>{const v=LANG==='ar'?'en':'ar';try{localStorage.setItem('lang',v)}catch(e){}LANG=v;const d=document.documentElement;d.lang=v;d.dir=v==='ar'?'rtl':'ltr';tools();draw()}},ic('language')),
el('button',{class:'icon-btn',title:t('s_theme'),onclick:()=>{const v=document.documentElement.dataset.theme==='light'?'dark':'light';try{localStorage.setItem('theme',v)}catch(e){}document.documentElement.dataset.theme=v;tools()}},ic(th==='light'?'moon':'sun')))
}
function draw(){
document.title=NAME;
const box=$('#pub');
if(NF){box.replaceChildren(el('div',{class:'pub pub-nf'},ic('circle-exclamation'),el('div',{},t('p_not_found'))));return}
if(!D){box.replaceChildren(el('div',{class:'pub pub-nf'},ic('spinner','fa-spin')));return}
const a=D,K=pk(a),used=a.up+a.down,now=Date.now()/1000;
const tlsTag=tagOf(a);
const pc=a.quota?used/a.quota*100:0;
let vp=null;
if(a.expires&&a.created&&a.expires>a.created)vp=Math.max(0,Math.min(100,(a.expires-now)/(a.expires-a.created)*100));
box.replaceChildren(el('div',{class:'pub'},
el('div',{class:'pub-h'},
el('span',{class:'logo big'},ic(PM[K]?PM[K].i:'shield-halved')),
el('h2',{},a.name),
el('div',{class:'row'},el('span',{class:'pb p-'+K},ic(PM[K]?PM[K].i:'shield-halved'),PM[K]?PM[K].n:a.proto),el('span',{class:'muted sm'},tlsTag),el('span',{class:'pill '+SC[a.status]},t('st_'+a.status)))),
loc(a.cc),
el('div',{class:'kv'},el('span',{},ic('wifi'),t('c_live')),el('span',{class:'live-row'},el('span',{class:'dot'+(a.active?' live':'')}),t(a.active?'live_on':'live_off'))),
a.proto==='ssh'?kv('plug',t('c_conn'),a.conn+' / '+(a.conn_limit||'∞')):null,
kv('gauge-high',t('p_speed'),'↓ '+speed(a.sp_down)+'  ↑ '+speed(a.sp_up)),
el('div',{class:'pub-sec'},
kv('chart-line',t('c_usage'),bytes(used)+' / '+(a.quota?bytes(a.quota):'∞')),
a.quota?meter(pc,pc>90?'bad':''):null,
a.quota?el('div',{class:'muted sm'},t('p_left_tr')+': '+bytes(Math.max(0,a.quota-used))+' · '+pc.toFixed(1)+'%'):el('div',{class:'muted sm'},t('unlimited')),
el('div',{class:'muted sm ltr'},'↓ '+bytes(a.down)+'  ↑ '+bytes(a.up))),
el('div',{class:'pub-sec'},
kv('calendar-plus',t('c_created'),dt(a.created),'dtv'),
kv('clock',t('c_expiry'),dt(a.expires),'dtv'),
vp!==null?meter(vp,vp<10?'bad':''):null,
kv('hourglass-half',t('c_left'),left(a.expires),'')),
el('div',{class:'muted sm ctr'},OFF?t('p_offline'):t('p_auto'))))
}
async function load(){
try{
const r=await fetch('/api/public/'+encodeURIComponent(NAME),{credentials:'omit',cache:'no-store'});
if(r.status===404){NF=true;D=null}
else if(r.ok){D=await r.json();NF=false;OFF=false}
else OFF=true
}catch(e){OFF=true}
draw()
}
tools();draw();load();
setInterval(()=>{if(!document.hidden&&!NF)load()},5000);
