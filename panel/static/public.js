'use strict';
const $=(s,r=document)=>r.querySelector(s);
const NAME=$('meta[name=acc]').content;
const PM={ssh:{i:'terminal',n:'SSH'},vless:{i:'bolt',n:'VLESS'},vmess:{i:'diagram-project',n:'VMess'},trojan:{i:'shield-halved',n:'Trojan'}};
const SC={active:'ok',disabled:'off',expired:'bad',limit:'warn'};
const el=(t,a={},...k)=>{const e=document.createElement(t);for(const[x,v]of Object.entries(a)){if(x==='class')e.className=v;else if(x.startsWith('on'))e.addEventListener(x.slice(2),v);else if(v!==false&&v!=null)e.setAttribute(x,v===true?'':v)}for(const c of k.flat()){if(c==null||c===false)continue;e.append(c instanceof Node?c:document.createTextNode(String(c)))}return e};
const ic=(n,c='')=>el('i',{class:'fa-solid fa-'+n+(c?' '+c:'')});
const bytes=n=>{if(!n||n<0)return'0 B';const u=['B','KB','MB','GB','TB','PB'];const i=Math.min(Math.floor(Math.log(n)/Math.log(1024)),5);return(n/1024**i).toFixed(i?2:0)+' '+u[i]};
const dt=ts=>ts?new Date(ts*1000).toLocaleDateString('en-GB'):t('unlimited');
const left=ts=>{if(!ts)return t('unlimited');const d=Math.ceil((ts*1000-Date.now())/864e5);return d>0?t('days_n',d):t('ended')};
const meter=(p,c='')=>{const i=el('i');i.style.width=Math.max(0,Math.min(100,p))+'%';return el('div',{class:'meter '+c},i)};
const kv=(i,l,v)=>el('div',{class:'kv'},el('span',{},ic(i),l),el('b',{class:'ltr'},v));
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
const a=D,used=a.up+a.down,now=Date.now()/1000;
const tlsTag=a.proto==='ssh'?'80 + 443':a.tls==='both'?'TLS + 80':a.tls==='tls'?'TLS 443':'80';
const pc=a.quota?used/a.quota*100:0;
let vp=null;
if(a.expires&&a.created&&a.expires>a.created)vp=Math.max(0,Math.min(100,(a.expires-now)/(a.expires-a.created)*100));
box.replaceChildren(el('div',{class:'pub'},
el('div',{class:'pub-h'},
el('span',{class:'logo big'},ic(PM[a.proto]?PM[a.proto].i:'shield-halved')),
el('h2',{},a.name),
el('div',{class:'row'},el('span',{class:'pb p-'+a.proto},ic(PM[a.proto].i),PM[a.proto].n),el('span',{class:'muted sm'},tlsTag),el('span',{class:'pill '+SC[a.status]},t('st_'+a.status)))),
el('div',{class:'kv'},el('span',{},ic('wifi'),t('c_live')),el('span',{class:'live-row'},el('span',{class:'dot'+(a.active?' live':'')}),t(a.active?'live_on':'live_off'))),
kv('gauge-high',t('p_speed'),'↓ '+bytes(a.sp_down)+'/s  ↑ '+bytes(a.sp_up)+'/s'),
el('div',{class:'pub-sec'},
kv('chart-line',t('c_usage'),bytes(used)+' / '+(a.quota?bytes(a.quota):'∞')),
a.quota?meter(pc,pc>90?'bad':''):null,
a.quota?el('div',{class:'muted sm'},t('p_left_tr')+': '+bytes(Math.max(0,a.quota-used))+' · '+pc.toFixed(1)+'%'):el('div',{class:'muted sm'},t('unlimited')),
el('div',{class:'muted sm ltr'},'↓ '+bytes(a.down)+'  ↑ '+bytes(a.up))),
el('div',{class:'pub-sec'},
kv('clock',t('c_expiry'),dt(a.expires)),
vp!==null?meter(vp,vp<10?'bad':''):null,
el('div',{class:'muted sm'},t('p_validity')+': '+left(a.expires))),
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
