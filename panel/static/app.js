'use strict';
const $=(s,r=document)=>r.querySelector(s);
const csrf=$('meta[name=csrf]').content;
const VERSION=$('meta[name=version]').content;
const NS='http://www.w3.org/2000/svg';
const GB=1073741824;
const PM={sshws:{i:'terminal',n:'SSH WS'},sshssl:{i:'lock',n:'SSH SSL'},sshudp:{i:'tower-broadcast',n:'UDP Custom'},vless:{i:'bolt',n:'VLESS'},vmess:{i:'diagram-project',n:'VMess'},trojan:{i:'shield-halved',n:'Trojan'}};
const THEMES=[['blue','#6366f1','#06b6d4'],['red','#dc2626','#fb7185'],['green','#16a34a','#2dd4bf'],['purple','#8b5cf6','#e879f9'],['cyan','#0891b2','#22d3ee'],['orange','#ea580c','#fbbf24'],['pink','#db2777','#f472b6'],['gold','#d97706','#fde047'],['navy','#2563eb','#60a5fa'],['teal','#0d9488','#5eead4'],['lime','#84cc16','#d9f99d'],['fuchsia','#c026d3','#f0abfc'],['wine','#9f1239','#f43f5e'],['coffee','#a8734a','#e0b48a'],['slate','#94a3b8','#e2e8f0']];
const setTheme=v=>{try{localStorage.setItem('theme',v)}catch(e){}document.documentElement.dataset.theme=v};
const pk=a=>a.proto==='ssh'?(a.transport==='ssl'?'sshssl':a.transport==='udp'?'sshudp':'sshws'):a.proto;
const SIC={ok:'circle-check',off:'circle-minus',bad:'circle-xmark',warn:'triangle-exclamation'};
const SC={active:'ok',disabled:'off',expired:'bad',limit:'warn'};
const el=(t,a={},...k)=>{const e=document.createElement(t);for(const[x,v]of Object.entries(a)){if(x==='class')e.className=v;else if(x.startsWith('on'))e.addEventListener(x.slice(2),v);else if(v!==false&&v!=null)e.setAttribute(x,v===true?'':v)}for(const c of k.flat()){if(c==null||c===false)continue;e.append(c instanceof Node?c:document.createTextNode(String(c)))}return e};
const ic=(n,c='')=>el('i',{class:'fa-solid fa-'+n+(c?' '+c:'')});
const api=async(m,u,b)=>{const r=await fetch(u,{method:m,headers:{'Content-Type':'application/json','X-CSRF':csrf},body:b?JSON.stringify(b):undefined,credentials:'same-origin'});if(r.status===401){location.href='/login';throw new Error('unauthorized')}const j=await r.json().catch(()=>({}));if(!r.ok)throw Object.assign(new Error(j.error||'error'),{detail:j.detail});return j};
const spd=(u,d)=>'↓ '+speed(d)+'  ↑ '+speed(u);
const bytes=n=>{if(!n||n<0)return'0 B';const u=['B','KB','MB','GB','TB','PB'];const i=Math.min(Math.floor(Math.log(n)/Math.log(1024)),5);return(n/1024**i).toFixed(i?2:0)+' '+u[i]};
const upt=s=>{const d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);return(d?t('d_short',d)+' ':'')+t('h_short',h)+' '+t('m_short',m)};
const rnd=n=>{const c='abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789',a=new Uint32Array(n);crypto.getRandomValues(a);return Array.from(a,x=>c[x%c.length]).join('')};
const toast=m=>{const x=el('div',{class:'toast',popover:'manual'},m);document.body.append(x);try{x.showPopover()}catch(e){}setTimeout(()=>x.remove(),3500)};
const terr=e=>{if(e.message==='unauthorized')return;const k='e_'+e.message;const m=tx(k);toast(m!==k?m+(e.detail?': '+e.detail:''):(e.detail||e.message))};
const field=(l,i,h)=>el('label',{class:'f'},el('span',{},l),i,h?el('small',{class:'muted'},h):null);
const kv=(l,v,x)=>el('div',{class:'kv'},el('span',{},l),x?el('div',{class:'kv-v'},x,el('b',{class:'ltr'},v)):el('b',{class:'ltr'},v));
const SI={active:'circle-check',disabled:'ban',expired:'circle-xmark',limit:'triangle-exclamation'};
const sti=a=>el('span',{class:'sti '+SC[a.status],title:t('st_'+a.status)},ic(SI[a.status]||'circle'));
const copy=async v=>{try{await navigator.clipboard.writeText(v);toast(t('copied'))}catch{toast(t('copy_fail'))}};
const modal=(title,body,btns=[],cls='')=>{const d=el('dialog',{class:cls},el('div',{class:'dlg-h'},el('h3',{},title),el('button',{class:'icon-btn',title:t('close'),onclick:()=>d.close()},ic('xmark'))),el('div',{class:'dlg-b'},body),btns.length?el('div',{class:'dlg-f'},...btns):null);d.addEventListener('close',()=>d.remove());const cl=d.close.bind(d);d.close=()=>{if(!d.open||d.classList.contains('cl'))return;d.classList.add('cl');setTimeout(()=>cl(),170)};d.addEventListener('cancel',e=>{e.preventDefault();d.close()});document.body.append(d);d.showModal();return d};
const btn=(label,icon,f,c='')=>el('button',{class:'btn '+c,type:'button',onclick:f},icon?ic(icon):null,label?el('span',{},label):null);
const seg=(opts,val,on)=>{const box=el('div',{class:'seg'});const thumb=el('i',{class:'seg-i'});let btns=null;
const place=()=>{const b=box.querySelector('button.on');if(!box.offsetWidth)return;if(!b){thumb.style.opacity=0;return}thumb.style.opacity=1;thumb.style.width=b.offsetWidth+'px';thumb.style.height=b.offsetHeight+'px';thumb.style.transform='translate('+b.offsetLeft+'px,'+b.offsetTop+'px)'};
const draw=()=>{const same=btns&&btns.length===opts.length&&btns.every((x,i)=>x.dataset.v===String(opts[i].v));
if(!same){btns=opts.map((o,i)=>{const x=el('button',{type:'button',onclick:()=>{const q=opts[i];val=q.v;on(val);draw()}},o.i?ic(o.i):null,el('span',{},o.l));x.dataset.v=String(o.v);return x});box.replaceChildren(thumb,...btns)}
btns.forEach((x,i)=>{x.classList.toggle('on',opts[i].v===val);x.disabled=!!opts[i].dis;x.lastChild.textContent=opts[i].l});place()};
draw();new ResizeObserver(()=>{place();if(box.offsetWidth&&!thumb.classList.contains('rdy'))requestAnimationFrame(()=>thumb.classList.add('rdy'))}).observe(box);box.upd=(o2,v2)=>{opts=o2;val=v2;draw()};return box};
const clp=(n,shut)=>{const w=el('div',{class:'clp'+(shut?' shut':' done')},el('div',{class:'clp-i'},n));let tm;w.set=s=>{if(w.classList.contains('shut')===s)return;clearTimeout(tm);w.classList.remove('done');w.classList.toggle('shut',s);if(!s)tm=setTimeout(()=>w.classList.add('done'),480)};return w};
function dd(opts,val,on,mw=170,ph){
const lab=el('span',{class:'dd-l'});
const b=el('button',{type:'button',class:'dd-b'},lab,ic('chevron-down','dd-c'));
const wrap=el('div',{class:'dd'},b);
let pop=null,t0=0;
const dot=c=>{const d=el('span',{class:'sdot'});d.style.background=c;return d};
const set=v=>{val=v;const o=opts.find(o=>o.v===v);if(!o&&ph){lab.replaceChildren(ph);return}const x=o||opts[0];lab.replaceChildren(...(x.c?[dot(x.c)]:[]),x.l)};
function close(){if(!pop)return;const p=pop;pop=null;p.classList.add('out');setTimeout(()=>p.remove(),140);wrap.classList.remove('open');document.removeEventListener('mousedown',out,true);document.removeEventListener('keydown',key,true);document.removeEventListener('scroll',sc,true);window.removeEventListener('resize',close)}
function out(e){if(pop&&!pop.contains(e.target)&&!b.contains(e.target))close()}
function key(e){if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close()}}
function sc(e){if(pop&&!pop.contains(e.target)&&Date.now()-t0>150)close()}
b.addEventListener('click',()=>{
if(pop){close();return}
pop=el('div',{class:'dd-p',popover:'manual'},...opts.map(o=>el('button',{type:'button',class:'dd-o'+(o.v===val?' on':''),onclick:()=>{set(o.v);on(o.v);close()}},o.c?dot(o.c):o.i?ic(o.i):null,el('span',{},o.l),o.v===val?ic('check','dd-k'):null)));
t0=Date.now();wrap.append(pop);try{pop.showPopover()}catch(e){}wrap.classList.add('open');
const r=b.getBoundingClientRect();
pop.style.minWidth=Math.max(r.width,mw)+'px';
const w=pop.offsetWidth,h=pop.offsetHeight;
let left=r.left;if(left+w>innerWidth-8)left=innerWidth-8-w;
let top=r.bottom+6;if(top+h>innerHeight-8)top=Math.max(8,r.top-6-h);
pop.style.left=Math.max(8,left)+'px';pop.style.top=top+'px';
document.addEventListener('mousedown',out,true);document.addEventListener('keydown',key,true);document.addEventListener('scroll',sc,true);window.addEventListener('resize',close)
});
set(val);
return wrap
}

const parseDT=(s,base)=>{
s=String(s).trim().replace(/[٠-٩]/g,c=>c.charCodeAt(0)-1632).replace(/[۰-۹]/g,c=>c.charCodeAt(0)-1776);
const m=s.match(/^(\d{4})[\/.\-](\d{1,2})[\/.\-](\d{1,2})(?:\s*[-–,T]?\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|ص|م)?)?$/i);
if(!m)return null;
const y=+m[1],mo=+m[2],d=+m[3];
let h=base.getUTCHours(),mi=base.getUTCMinutes();
if(m[4]!==undefined){
h=+m[4];mi=m[5]!==undefined?+m[5]:0;
if(m[6]){if(h<1||h>12)return null;h=h%12+(/pm|م/i.test(m[6])?12:0)}else if(h>23)return null;
if(mi>59)return null
}
const r=new Date(Date.UTC(y,mo-1,d,h,mi,0,0));
return r.getUTCFullYear()===y&&r.getUTCMonth()===mo-1&&r.getUTCDate()===d?r:null
};
function dtField(init,onChange){
const input=el('input',{dir:'ltr',autocomplete:'off',placeholder:'YYYY/MM/DD - hh:mm '+t('pm'),value:init?fmtDT(init):''});
let cur=init?new Date(init):null,vw=new Date(cur||W(Date.now())),open=false;
vw.setUTCDate(1);
const panel=el('div',{class:'cal'});const cw=clp(panel,true);
const toggle=el('button',{type:'button',class:'icon-btn',title:t('cal_open'),onclick:()=>{open=!open;toggle.classList.toggle('on',open);if(open)draw();cw.set(!open)}},ic('calendar-days'));
const wrap=el('div',{class:'dtf'},el('div',{class:'inp-row'},input,toggle),cw);
const rtl=LANG==='ar';
const mk=(y,m,d,h=0,mi=0)=>new Date(Date.UTC(y,m,d,h,mi,0,0));
const setCur=(d,keep)=>{cur=d;if(d){vw=mk(d.getUTCFullYear(),d.getUTCMonth(),1)}if(!keep)input.value=d?fmtDT(d):'';input.classList.remove('bad');onChange&&onChange(cur);if(open)draw()};
function draw(){
const loc=(rtl?'ar':'en')+'-u-nu-latn';
const mon=new Intl.DateTimeFormat(loc,{month:'long',timeZone:'UTC'}).format(vw);
const ws=rtl?6:0,today=W(Date.now());
const first=mk(vw.getUTCFullYear(),vw.getUTCMonth(),1);
const lead=(first.getUTCDay()-ws+7)%7;
const days=[];
for(let i=0;i<42;i++)days.push(mk(vw.getUTCFullYear(),vw.getUTCMonth(),1-lead+i));
const same=(x,y)=>y&&x.getUTCFullYear()===y.getUTCFullYear()&&x.getUTCMonth()===y.getUTCMonth()&&x.getUTCDate()===y.getUTCDate();
const wd=Array.from({length:7},(_,i)=>new Intl.DateTimeFormat(loc,{weekday:'short',timeZone:'UTC'}).format(mk(2024,0,7+(ws+i)%7)));
const nav=(n,icn,k)=>el('button',{type:'button',class:'icon-btn',title:t(k),onclick:()=>{vw=mk(vw.getUTCFullYear(),vw.getUTCMonth()+n,1);draw();const g=panel.querySelector('.cal-g');if(g&&g.animate)g.animate([{opacity:0,transform:'translateX('+(n*(rtl?-1:1)*16)+'px)'},{opacity:1,transform:'none'}],{duration:240,easing:'cubic-bezier(.22,1,.36,1)'})}},ic(icn));
const grid=el('div',{class:'cal-g'},
...wd.map(w=>el('span',{class:'cal-w'},w)),
...days.map(d=>el('button',{type:'button',class:'cal-d'+(d.getUTCMonth()!==vw.getUTCMonth()?' o':'')+(same(d,today)?' td':'')+(same(d,cur)?' on':''),onclick:()=>{const b=cur||W(Date.now());setCur(mk(d.getUTCFullYear(),d.getUTCMonth(),d.getUTCDate(),b.getUTCHours(),b.getUTCMinutes()))}},d.getUTCDate())));
const b=cur||W(Date.now());
const h12=b.getUTCHours()%12||12,pm=b.getUTCHours()>=12;
const upd=(h,mi,p)=>{const x=cur?new Date(cur):new Date(b);x.setUTCHours((h%12)+(p?12:0),mi,0,0);if(!cur){x.setUTCFullYear(b.getUTCFullYear(),b.getUTCMonth(),b.getUTCDate())}setCur(x)};
const hd=dd(Array.from({length:12},(_,i)=>({v:i+1,l:p2(i+1)})),h12,v=>upd(v,b.getUTCMinutes(),pm),78);
const md=dd(Array.from({length:60},(_,i)=>({v:i,l:p2(i)})),b.getUTCMinutes(),v=>upd(h12,v,pm),78);
const ap=seg([{v:false,l:t('am')},{v:true,l:t('pm')}],pm,v=>upd(h12,b.getUTCMinutes(),v));
panel.dir=rtl?'rtl':'ltr';
panel.replaceChildren(
el('div',{class:'cal-h'},nav(-1,rtl?'chevron-right':'chevron-left','cal_prev'),el('b',{class:'cal-t'},mon+' '+vw.getUTCFullYear()),nav(1,rtl?'chevron-left':'chevron-right','cal_next')),
grid,
el('div',{class:'tm'},hd,el('b',{},':'),md,ap))
}
input.addEventListener('input',()=>{
const v=input.value.trim();
if(!v){cur=null;input.classList.remove('bad');onChange&&onChange(null);if(open)draw();return}
const d=parseDT(v,cur||W(Date.now()));
if(d){cur=d;vw=mk(d.getUTCFullYear(),d.getUTCMonth(),1);input.classList.remove('bad');onChange&&onChange(cur);if(open)draw()}else input.classList.add('bad')
});
input.addEventListener('blur',()=>{if(cur&&!input.classList.contains('bad'))input.value=fmtDT(cur)});
return{el:wrap,set:d=>setCur(d),get:()=>{const v=input.value.trim();if(!v)return{ok:true,d:null};const d=parseDT(v,cur||W(Date.now()));return d?{ok:true,d}:{ok:false}}}
}
const dchips=(vals,f)=>el('div',{class:'chips'},...vals.map(n=>el('button',{type:'button',class:'chip',onclick:()=>{if(!n){f.set(null);return}const d=W(Date.now());d.setUTCSeconds(0,0);d.setUTCDate(d.getUTCDate()+n);f.set(d)}},n===0?ic('infinity'):t('d_short',n))));
const chips=(vals,input)=>el('div',{class:'chips'},...vals.map(v=>el('button',{type:'button',class:'chip',onclick:()=>{input.value=v}},v===0?ic('infinity'):v)));
const meter=(p,c='')=>{const i=el('i');i.style.width=Math.max(0,Math.min(100,p))+'%';return el('div',{class:'meter '+c},i)};
const liveDot=on=>el('span',{class:'dot'+(on?' live':''),title:t(on?'live_on':'live_off')});
const connPill=a=>{const L=a.conn_limit;return el('span',{class:'pill ltr '+(a.conn>0?(L&&a.conn>=L?'warn':'ok'):'off')},ic('plug'),a.conn+' / '+(L||'∞'))};
const badge=p=>el('span',{class:'pb p-'+p},ic(PM[p].i),PM[p].n);
const sw=(on,f)=>{const b=el('button',{type:'button',class:'sw'+(on?' on':''),role:'switch','aria-checked':String(!!on),onclick:()=>{on=!on;b.classList.toggle('on',on);b.setAttribute('aria-checked',String(on));f(on)}},el('i'));return b};
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
const TR={open:false,mode:'both',sel:null,el:null,days:null,upd:null};
try{const m=localStorage.getItem('trmode');if(m==='down'||m==='up'||m==='both')TR.mode=m}catch(e){}
const axB=n=>{if(!n||n<=0)return'0';const u=['B','KB','MB','GB','TB','PB'];const i=Math.min(Math.floor(Math.log(n)/Math.log(1024)),5);return+(n/1024**i).toFixed(1)+' '+u[i]};
const NICE=[1,2,3,4,5,6,8,10,20,30,40,50,60,80,100,200,300,400,500,600,800,1000,1024];
const niceMax=v=>{if(!(v>0))return 1048576;const i=Math.min(Math.floor(Math.log(v)/Math.log(1024)),5),u=1024**i,x=v/u;return(NICE.find(n=>n>=x)||1024)*u};
const monthName=D=>{try{return new Intl.DateTimeFormat((LANG==='ar'?'ar':'en')+'-u-nu-latn',{month:'long',timeZone:'UTC'}).format(Date.UTC(D.y,D.m-1,15))}catch(e){return String(D.m)}};
function coresGrid(s){
const P=s.core_pct||[];
if(!P.length)return null;
return el('div',{class:'cores'},...P.map((p,i)=>el('div',{class:'core'},el('div',{class:'core-h'},el('span',{},t('d_core',i+1)),el('b',{class:'ltr'},p.toFixed(0)+'%')),meter(p,p>90?'bad':p>70?'warnm':''))))
}
function trafficTile(s){
if(TR.el){TR.upd(s);return TR.el}
let cols=[];
const val=el('div',{class:'tile-v ltr'}),rt=el('div',{class:'muted ltr'});
const mI=el('i'),mEl=el('div',{class:'meter',hidden:true},mI);
const note=el('div',{class:'muted tile-s'});
const tile=el('div',{class:'tile wide tt'+(TR.open?' open':'')});
const btnT=el('button',{type:'button',class:'icon-btn tt-btn'+(TR.open?' on':''),title:t('ch_toggle'),'aria-label':t('ch_toggle'),'aria-expanded':String(TR.open),onclick:()=>{TR.open=!TR.open;tile.classList.toggle('open',TR.open);btnT.classList.toggle('on',TR.open);btnT.setAttribute('aria-expanded',String(TR.open))}},ic('chart-simple'));
const title=el('b',{class:'tc-t'});
const modeSeg=seg([{v:'down',l:t('ch_down'),i:'arrow-down'},{v:'up',l:t('ch_up'),i:'arrow-up'},{v:'both',l:t('ch_both'),i:'arrows-up-down'}],TR.mode,v=>{TR.mode=v;try{localStorage.setItem('trmode',v)}catch(e){}paint()});
const ay1=el('span',{}),ay2=el('span',{});
const colsBox=el('div',{class:'tc-cols'});
const infoD=el('b',{}),infoV=el('div',{class:'tc-iv'});
const pickDay=d=>{if(TR.sel===d)return;TR.sel=d;info()};
const hit=e=>{const x=document.elementFromPoint(e.clientX,e.clientY);const c=x&&x.closest?x.closest('.col'):null;if(c&&colsBox.contains(c))pickDay(+c.dataset.d)};
colsBox.addEventListener('pointerdown',hit);
colsBox.addEventListener('pointermove',e=>{if(e.pointerType==='mouse'||e.buttons)hit(e)});
function mk(dim){
cols=[];
for(let i=0;i<dim;i++){
const day=i+1,g=el('i',{class:'sgd'}),u=el('i',{class:'sgu'}),bars=el('div',{class:'bars'},g,u);
bars.style.setProperty('--i',i);
const c=el('button',{type:'button',class:'col'+(day===1||day%5===0?' k':''),'data-d':day,onfocus:()=>pickDay(day),onclick:()=>{TR.sel=day;info()}},el('div',{class:'cb'},bars),el('span',{class:'dl'},day));
cols.push({el:c,bars,d:g,u})
}
colsBox.replaceChildren(...cols.map(c=>c.el))
}
function info(){
const D=TR.days;if(!D)return;
const day=Math.max(1,Math.min(TR.sel||D.today,D.dim)),fut=day>D.today;
const rx=D.rx[day-1]||0,tx=D.tx[day-1]||0;
cols.forEach((c,i)=>c.el.classList.toggle('sel',i+1===day));
infoD.textContent=day+' '+monthName(D);
infoV.replaceChildren(...(fut?[el('span',{class:'muted'},t('ch_future'))]:[
el('span',{class:'ltr'},el('i',{class:'lgd d'}),'↓ '+bytes(rx)),
el('span',{class:'ltr'},el('i',{class:'lgd u'}),'↑ '+bytes(tx)),
el('b',{class:'ltr'},bytes(rx+tx))]))
}
function paint(){
const D=TR.days;if(!D)return;
if(cols.length!==D.dim)mk(D.dim);
const m=TR.mode,V=[];let mx=0;
for(let i=0;i<D.dim;i++){const d=m==='up'?0:(D.rx[i]||0),u=m==='down'?0:(D.tx[i]||0);V.push([d,u]);if(d+u>mx)mx=d+u}
const nm=niceMax(mx);
ay1.textContent=axB(nm);ay2.textContent=axB(nm/2);
title.textContent=monthName(D)+' '+D.y;
cols.forEach((c,i)=>{
const[d,u]=V[i],tot=d+u,day=i+1;
c.bars.style.height=(tot/nm*100)+'%';
c.bars.classList.toggle('nz',tot>0);
c.d.style.flexGrow=d;c.u.style.flexGrow=u;
c.el.classList.toggle('fut',day>D.today);
c.el.classList.toggle('today',day===D.today);
c.el.title=day+' '+monthName(D)+(day>D.today?'':' · '+bytes(tot))
});
info()
}
TR.upd=s=>{
const cap=s.cap_gb*GB,used=s.month_used,pc=cap?used/cap*100:0;
val.textContent=bytes(used)+(cap?' / '+bytes(cap):'');
rt.textContent='↓ '+bytes(s.month_rx)+'    ↑ '+bytes(s.month_tx);
mEl.hidden=!cap;
mEl.className='meter '+(pc>=95?'bad':pc>=80?'warnm':'');
mI.style.width=Math.max(0,Math.min(100,pc))+'%';
note.textContent=cap?(used>=cap?t('d_cap_over'):t('d_cap_left',bytes(cap-used)))+' · '+pc.toFixed(1)+'%':t('d_no_cap');
if(s.days){TR.days=s.days;paint()}
};
tile.append(
el('div',{class:'tile-h'},el('span',{class:'ico c9'},ic('server')),el('span',{class:'tile-t'},t('d_server_traffic')),btnT),
el('div',{class:'tw'},val,rt),mEl,note,
el('div',{class:'tc'},el('div',{class:'tc-in'},el('div',{class:'tc-box'},
el('div',{class:'tc-top'},title,modeSeg),
el('div',{class:'tc-plot'},el('div',{class:'tc-ax'},ay1,ay2,el('span',{},'0')),el('div',{class:'tc-area'},el('div',{class:'tc-lines'},el('i'),el('i'),el('i')),colsBox)),
el('div',{class:'tc-info'},infoD,infoV)))));
TR.el=tile;
TR.upd(s);
return tile
}

function drawDash(){
const s=S,A=ACC;
const act=A.filter(a=>a.status==='active').length;
const up=A.reduce((x,a)=>x+a.up,0),dn=A.reduce((x,a)=>x+a.down,0);
const rx=H.rx.length?H.rx[H.rx.length-1]:0,tx=H.tx.length?H.tx[H.tx.length-1]:0;
const ramP=s.mem_total?s.mem_used/s.mem_total*100:0,diskP=s.disk_total?s.disk_used/s.disk_total*100:0;
const row1=el('div',{class:'grid'},
tile('microchip','c1',t('d_cpu'),s.cpu.toFixed(1)+'%',t('d_cores',s.cores)+' · '+t('d_load')+' '+s.load[0].toFixed(2),[spark(H.cpu,'s1',100),coresGrid(s)]),
tile('memory','c2',t('d_ram'),ramP.toFixed(1)+'%',bytes(s.mem_used)+' / '+bytes(s.mem_total),spark(H.ram,'s2',100)),
tile('hard-drive','c3',t('d_disk'),diskP.toFixed(1)+'%',bytes(s.disk_used)+' / '+bytes(s.disk_total),meter(diskP,diskP>90?'bad':'')),
tile('network-wired','c4',t('d_net'),el('span',{class:'ltr'},'↓ '+speed(rx)),'↑ '+speed(tx),spark(H.rx,'s4')),
portsTile(s.ports||[]));
const trf=trafficTile(s);
const row2=el('div',{class:'grid'},
tile('users','c5',t('d_accounts'),A.length,t('d_active_n',act)+' · '+t('d_conn_n',A.reduce((x,a)=>x+(a.conn||0),0))),
tile('chart-line','c7',t('d_traffic'),bytes(up+dn),'↑ '+bytes(up)+' · ↓ '+bytes(dn)),
tile('clock','c8',t('d_uptime'),upt(s.uptime),t('d_load')+' '+s.load.map(x=>x.toFixed(2)).join(' / ')));
const tot=Math.max(1,up+dn);
const byp=el('div',{class:'list'},...Object.keys(PM).map(p=>{const l=A.filter(a=>pk(a)===p);const tr=l.reduce((x,a)=>x+a.up+a.down,0);return el('div',{class:'li'},el('div',{class:'li-h'},badge(p),el('b',{},l.length),el('span',{class:'muted'},bytes(tr))),meter(tr/tot*100,'m-'+p))}));
const top=[...A].sort((a,b)=>b.up+b.down-a.up-a.down).slice(0,5).filter(a=>a.up+a.down>0);
const topL=el('div',{class:'list'},...(top.length?top.map(a=>el('div',{class:'li'},el('div',{class:'li-h'},badge(pk(a)),el('b',{},a.name),el('span',{class:'muted'},bytes(a.up+a.down))),meter((a.up+a.down)/(top[0].up+top[0].down)*100,'m-'+pk(a)))):[el('div',{class:'empty'},t('d_none'))]));
const now=Date.now()/1000;
const exp=A.filter(a=>a.expires&&a.expires>now&&a.expires-now<7*86400).sort((a,b)=>a.expires-b.expires).slice(0,6);
const expL=el('div',{class:'list'},...(exp.length?exp.map(a=>el('div',{class:'li li-r'},badge(pk(a)),el('b',{},a.name),el('span',{class:'muted'},left(a.expires)))):[el('div',{class:'empty'},t('d_none'))]));
const sv=el('div',{},el('div',{class:'svc'},...Object.entries(s.services).map(([k,v])=>{const z=typeof v==='string'?v:(v?'ok':'warn');return el('span',{class:'pill '+z,title:t('svc_'+z)},ic(SIC[z]),k)})),el('div',{class:'muted sm svc-lg'},t('svc_legend')));
const rest=[row2,el('div',{class:'grid'},panel('diagram-project',t('d_by_proto'),byp),panel('ranking-star',t('d_top'),topL)),el('div',{class:'grid'},panel('hourglass-half',t('d_expiring'),expL),panel('server',t('d_services'),sv))];
const v=$('#view');
if(trf.parentNode===v){while(v.firstChild!==trf)v.firstChild.remove();while(trf.nextSibling)trf.nextSibling.remove();v.insertBefore(row1,trf);v.append(...rest)}
else v.replaceChildren(row1,trf,...rest)
}
function portsTile(P){
const on=P.filter(p=>p.listening).length,tot=P.filter(p=>p.enabled).length;
return tile('plug','c6',t('pt_title'),on+' / '+tot,t('pt_sub'),el('div',{class:'ports'},...P.map(p=>el('div',{class:'pt'},el('b',{class:'ltr'},p.port),el('span',{class:'muted'},t('pt_'+p.k)),pill(p.listening?'ok':p.enabled?'bad':'off',t(p.listening?'pt_listen':p.enabled?'pt_closed':'pt_off'))))))
}
function accRow(a){
const used=a.up+a.down;
const act=a.status==='active';
const tlsTag=tagOf(a);
return el('tr',{},
el('td',{},el('b',{},sti(a),a.name),a.note?el('div',{class:'muted sm'},a.note):null),
el('td',{},badge(pk(a)),el('div',{class:'muted sm'},tlsTag)),
el('td',{},el('span',{class:'live-row'},liveDot(act&&a.active),a.proto==='ssh'?connPill(a):null),act&&a.active?el('div',{class:'muted sm ltr'},spd(a.sp_up,a.sp_down)):null),
el('td',{class:'usage'},el('div',{class:'ltr'},'↑ '+bytes(a.up)+'  ↓ '+bytes(a.down)),el('div',{class:'muted sm ltr'},bytes(used)+' / '+(a.quota?bytes(a.quota):'∞')),a.quota?meter(used/a.quota*100,used/a.quota>.9?'bad':''):null),
el('td',{},el('div',{class:'dtv'},dt(a.expires)),el('div',{class:'muted sm'},left(a.expires))),
el('td',{},el('div',{class:'acts'},
el('button',{class:'icon-btn',title:t('a_info'),onclick:()=>infoDlg(a.name)},ic('circle-info')),
el('button',{class:'icon-btn',title:t('a_edit'),onclick:()=>accDlg(a)},ic('pen-to-square')),
el('button',{class:'icon-btn',title:a.manual?t('a_enable'):t('a_disable'),onclick:()=>patch(a.name,{manual:!a.manual})},ic(a.manual?'circle-check':'ban')),
el('button',{class:'icon-btn danger',title:t('a_delete'),onclick:()=>del(a)},ic('trash')))))
}
function drawRows(){
const q=F.q.trim().toLowerCase();
const l=ACC.filter(a=>(!F.p||pk(a)===F.p)&&(!F.s||a.status===F.s)&&(!q||a.name.includes(q)||a.note.toLowerCase().includes(q)));
const r=$('#rows');if(!r)return;
r.replaceChildren(...(l.length?l.map(accRow):[el('tr',{},el('td',{colspan:6,class:'empty'},t('a_empty')))]));
const c=$('#cnt');if(c)c.textContent=l.length+' / '+ACC.length
}
function viewAccounts(){
const q=el('input',{placeholder:t('a_search'),value:F.q});
q.addEventListener('input',()=>{F.q=q.value;drawRows()});
const p=dd([{v:'',l:t('a_all_protos'),i:'layer-group'},...Object.entries(PM).map(([k,v])=>({v:k,l:v.n,i:v.i}))],F.p,v=>{F.p=v;drawRows()});
const s=dd([{v:'',l:t('a_all_status'),i:'filter'},...Object.keys(SC).map(k=>({v:k,l:t('st_'+k)}))],F.s,v=>{F.s=v;drawRows()});
const tb=el('div',{class:'toolbar'},el('div',{class:'search'},ic('magnifying-glass'),q),p,s,el('span',{class:'muted',id:'cnt'}),btn(t('a_add'),'plus',()=>accDlg(),'pri'));
const th=['c_name','c_proto','c_live','c_usage','c_expiry','c_actions'].map(k=>el('th',{},t(k)));
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
el('div',{class:'row'},badge(pk(r)),pill(SC[r.status],t('st_'+r.status))),
el('div',{class:'kv'},el('span',{},ic('wifi'),t('c_live')),el('span',{class:'live-row'},liveDot(r.active),t(r.active?'live_on':'live_off'))),
r.proto==='ssh'?el('div',{class:'kv'},el('span',{},ic('plug'),t('c_conn')),el('b',{class:'ltr'},r.conn+' / '+(r.conn_limit||'∞'))):null,
r.active?el('div',{class:'kv'},el('span',{},ic('gauge-high'),t('p_speed')),el('b',{class:'ltr'},spd(r.sp_up,r.sp_down))):null,
el('div',{class:'kv'},el('span',{},ic('chart-line'),t('c_usage')),el('b',{class:'ltr'},bytes(used)+' / '+(r.quota?bytes(r.quota):'∞'))),
r.quota?meter(used/r.quota*100):null,
el('div',{class:'kv'},el('span',{},ic('calendar-plus'),t('c_created')),el('b',{class:'dtv'},dt(r.created))),
el('div',{class:'kv'},el('span',{},ic('clock'),t('c_expiry')),el('b',{class:'dtv'},dt(r.expires))),
el('div',{class:'kv'},el('span',{},ic('hourglass-half'),t('c_left')),el('b',{},left(r.expires))),
r.note?el('div',{class:'note-b'},el('span',{},ic('note-sticky'),t('f_note')),el('div',{class:'note-t'},r.note)):null);
const warn=(!r.tls_on&&r.tls!=='plain')?el('div',{class:'hint'},ic('triangle-exclamation'),t('i_tls_off')):null;
const items=r.items.map(i=>el('div',{class:'item'},el('div',{class:'item-h'},el('span',{},t('l_'+i.k)),el('div',{class:'acts'},i.k==='page'?el('a',{class:'icon-btn',href:i.value,target:'_blank',rel:'noopener noreferrer',title:t('open'),'aria-label':t('open')},ic('arrow-up-right-from-square')):null,el('button',{class:'icon-btn',title:t('copy'),onclick:()=>copy(i.value)},ic('copy')))),el('textarea',{readonly:true,rows:i.rows||2,dir:'ltr'},i.value)));
modal(t('i_title',n),el('div',{},head,warn,...items))
}catch(e){terr(e)}
}
async function accDlg(a){
if(!S){try{await loadStats()}catch(e){}}
const ed=!!a;
const tlsOn=!S||S.tls_on!==false;
const forced=!tlsOn&&!ed;
const st={kind:ed?(a.proto==='ssh'?'ssh':'v2'):'ssh',proto:ed?a.proto:'vless',transport:ed&&a.proto==='ssh'?(a.transport||'ws'):'ws',tls:forced?'plain':ed?a.tls:'both'};
const name=el('input',{placeholder:'user1',maxlength:20,autocomplete:'off',dir:'ltr',value:ed?a.name:''});
if(ed)name.disabled=true;
const secret=el('input',{autocomplete:'off',dir:'ltr',placeholder:ed?t('f_keep'):t('f_auto')});
const org=ed&&a.expires?W(a.expires*1000):null;
if(org)org.setUTCSeconds(0,0);
const startD=ed?org:(()=>{const n=W(Date.now());n.setUTCSeconds(0,0);return n})();
const expF=dtField(startD);
const quota=el('input',{type:'number',min:0,step:'any',value:ed&&a.quota?+(a.quota/GB).toFixed(3):0});
const connLim=el('input',{type:'number',min:0,max:1000,step:1,value:ed?(a.conn_limit||0):0});
const connHint=el('small',{class:'muted'});
const note=el('input',{maxlength:100,value:ed?a.note:''});
const genName=el('button',{type:'button',class:'icon-btn',title:t('f_gen'),onclick:()=>{name.value='u'+rnd(6).toLowerCase()}},ic('dice'));
const genSec=el('button',{type:'button',class:'icon-btn',title:t('f_gen'),onclick:()=>{secret.value=(st.kind==='v2'&&st.proto!=='trojan')?crypto.randomUUID():rnd(14)}},ic('dice'));
let CB=null;
try{const r=await api('GET','/api/components');CB={};r.combos.forEach(x=>{CB[x.k]=x})}catch(e){}
const av=k=>!CB||!!(CB[k]&&CB[k].avail);
const V2P=['vless','vmess','trojan'];
const baseOf=(kind,proto,tr)=>kind==='v2'?proto:(tr==='ssl'?'sshssl':tr==='udp'?'sshudp':'sshws');
const orgBase=ed?baseOf(a.proto==='ssh'?'ssh':'v2',a.proto,a.transport):'';
const isUdp=()=>st.kind==='ssh'&&st.transport==='udp';
const kindOk=k=>ed||(k==='ssh'?['sshws:tls','sshws:plain','sshssl:tls','sshssl:plain','sshudp:udp']:V2P.flatMap(p=>[p+':tls',p+':plain'])).some(av);
const protoOk=p=>(ed&&a.proto===p)||av(p+':tls')||av(p+':plain');
const trOk=x=>{if(ed&&a.proto==='ssh'&&a.transport===x)return true;if(x==='udp')return av('sshudp:udp');const b=x==='ssl'?'sshssl':'sshws';return av(b+':tls')||av(b+':plain')};
const tlsOk=m=>{const b=baseOf(st.kind,st.proto,st.transport);if(ed&&b===orgBase&&a.tls===m)return true;return m==='both'?av(b+':tls')&&av(b+':plain'):av(b+':'+m)};
const kindOpts=()=>[{v:'ssh',l:'SSH',i:'terminal',dis:!kindOk('ssh')},{v:'v2',l:'V2Ray',i:'bolt',dis:!kindOk('v2')}];
const protoOpts=()=>[{v:'vless',l:'VLESS',i:'bolt'},{v:'vmess',l:'VMess',i:'diagram-project'},{v:'trojan',l:'Trojan',i:'shield-halved'}].map(o=>({...o,dis:!protoOk(o.v)}));
const trOpts=()=>[{v:'ws',l:t('tr_ws'),i:'globe'},{v:'ssl',l:t('tr_ssl'),i:'lock'},{v:'udp',l:t('tr_udp'),i:'tower-broadcast'}].map(o=>({...o,dis:!trOk(o.v)}));
const tlsOpts=()=>[{v:'tls',l:t('tls_tls'),i:'lock'},{v:'plain',l:t('tls_plain'),i:'lock-open'},{v:'both',l:t('tls_both'),i:'layer-group'}].map(o=>({...o,dis:!tlsOk(o.v)}));
const selKeys=()=>{if(st.kind==='v2'||!isUdp()){const b=baseOf(st.kind,st.proto,st.transport);return(st.tls==='both'?['tls','plain']:[st.tls]).map(m=>b+':'+m)}return['sshudp:udp']};
const kindSeg=seg(kindOpts(),st.kind,v=>{st.kind=v;sync()});
const protoSeg=seg(protoOpts(),st.proto,v=>{st.proto=v;sync()});
const tlsSeg=seg(tlsOpts(),st.tls,v=>{st.tls=v});tlsSeg.classList.add('s3');
const transportSeg=seg(trOpts(),st.transport,v=>{st.transport=v;sync()});
const tlsHint=el('div',{class:'hint'},ic('triangle-exclamation'),t('tls_unavailable'));
const unav=el('div',{class:'hint'},ic('circle-info'),t('f_unavail_hint'));
const secLabel=el('span',{});
const boxProto=field(t('f_proto'),protoSeg);
const tlsHintTxt=el('small',{class:'muted'},t('f_tls_hint'));
const boxTls=el('label',{class:'f'},el('span',{},t('f_tls')),tlsSeg,tlsHintTxt);
const boxTransport=field(t('f_transport'),transportSeg,t('f_transport_hint'));
const boxKind=field(t('f_type'),kindSeg);
const boxConn=el('div',{class:'f'},el('span',{},t('f_conn_limit')),connLim,chips([1,2,3,5,0],connLim),connHint);
const cProto=clp(boxProto,true),cTransport=clp(boxTransport,true),cTls=clp(boxTls,true),cTlsHint=clp(tlsHint,true),cUnav=clp(unav,true),cConn=clp(boxConn,true);
function sync(){
if(!ed){
if(!kindOk(st.kind))st.kind=kindOk('ssh')?'ssh':'v2';
if(st.kind==='v2'&&!protoOk(st.proto))st.proto=V2P.find(protoOk)||st.proto;
if(st.kind==='ssh'&&!trOk(st.transport))st.transport=['ws','ssl','udp'].find(trOk)||st.transport;
if(isUdp())st.tls='plain';
else if(!forced&&!tlsOk(st.tls))st.tls=['both','plain','tls'].find(tlsOk)||st.tls
}
const v2=st.kind==='v2',udp=isUdp();
kindSeg.upd(kindOpts(),st.kind);protoSeg.upd(protoOpts(),st.proto);transportSeg.upd(trOpts(),st.transport);tlsSeg.upd(tlsOpts(),st.tls);
cProto.set(!v2||ed);cTransport.set(v2);cTls.set(forced||udp);cTlsHint.set(!forced||udp);
cUnav.set(!(CB&&((!ed&&kindOpts().some(o=>o.dis))||(v2&&protoOpts().some(o=>o.dis))||(!v2&&trOpts().some(o=>o.dis))||(!(forced||udp)&&tlsOpts().some(o=>o.dis)))));
tlsHintTxt.textContent=t(!v2&&st.transport==='ssl'?'f_tls_hint_ssl':'f_tls_hint');
cConn.set(v2);connHint.textContent=t('f_conn_limit_ssh');
secLabel.textContent=(v2&&st.proto!=='trojan')?t('f_uuid'):t('f_password')
}
const form=el('div',{class:'form'},
ed?null:boxKind,cProto,cTransport,cTls,cTlsHint,cUnav,
field(t('f_name'),el('div',{class:'inp-row'},name,ed?null:genName)),
el('label',{class:'f'},secLabel,el('div',{class:'inp-row'},secret,genSec)),
el('div',{class:'f'},el('span',{},t('f_days')),expF.el,dchips([7,30,90,365,0],expF),el('small',{class:'muted'},t('f_exp_hint'))),
el('div',{class:'f'},el('span',{},t('f_quota')),quota,chips([5,10,50,100,0],quota)),
cConn,
field(t('f_note'),note));
sync();
const d=modal(ed?t('a_edit_t',a.name):t('a_new'),form,[
btn(ed?t('save'):t('create'),ed?'floppy-disk':'plus',async()=>{
const x=expF.get();
if(!x.ok){toast(t('e_bad_date'));return}
if(!ed&&CB&&!selKeys().every(av)){toast(t('e_combo_disabled'));return}
const b={secret:secret.value,quota_gb:quota.value,conn_limit:st.kind==='v2'?0:connLim.value,note:note.value,tls:st.tls,transport:st.transport};
if(!ed||(x.d?x.d.getTime():0)!==(org?org.getTime():0))b.expires=x.d?Math.floor(U(x.d)/1000):0;
try{
if(ed){await api('PATCH','/api/accounts/'+a.name,b);toast(t('done'));d.close();await loadAcc();drawRows()}
else{const proto=st.kind==='ssh'?'ssh':st.proto;const r=await api('POST','/api/accounts',{...b,proto,name:name.value});d.close();await loadAcc();drawRows();infoDlg(r.name)}
}catch(e){terr(e)}
},'pri'),
ed?btn(t('regen'),'rotate',async()=>{if(await patch(a.name,{regen:true},t('regen_done')))d.close()}):null,
ed?btn(t('reset_traffic'),'eraser',async()=>{if(await patch(a.name,{reset:true},t('reset_done')))d.close()}):null],'wide')
}
function dlLog(k){const x=el('a',{href:'/api/logs/'+k+'/download'});document.body.append(x);x.click();x.remove()}
async function clearLog(k,after){
ask(t('lg_confirm',t('lg_'+k)),t('lg_clear'),async()=>{try{await api('POST','/api/logs/'+k+'/clear');toast(t('lg_cleared'));if(after)await after()}catch(e){terr(e);return false}})
}
async function logDlgView(k,after){
const pre=el('pre',{class:'log big'},'...');
const load=async()=>{try{const r=await api('GET','/api/logs/'+k+'?n=500');pre.textContent=r.text||t('lg_empty');pre.scrollTop=pre.scrollHeight}catch(e){terr(e)}};
const d=modal(t('lg_'+k),pre,[btn(t('lg_refresh'),'rotate',load),btn(t('lg_download'),'download',()=>dlLog(k)),btn(t('lg_clear'),'eraser',()=>clearLog(k,async()=>{await load();if(after)await after()}),'dgr')],'wide');
await load()
}
function portsBox(){
const box=el('div',{class:'form cols'},el('div',{class:'empty'},ic('spinner','fa-spin')));
let ins={},cur={};
const save=()=>{
const b={};let ch=false;
for(const k in ins){const v=parseInt(ins[k].value,10);if(!(v>=1&&v<=65535)){toast(t('e_bad_port'));return}b[k]=v;if(v!==cur[k])ch=true}
if(!ch){toast(t('pp_nochange'));return}
const go=b.panel&&b.panel!==cur.panel?location.protocol+'//'+location.hostname+':'+b.panel+'/':undefined;
ask(t('pp_confirm'),t('save'),()=>{runJob('/api/ports',b,t('pp_working'),go)},{danger:false})
};
const fill=async()=>{
try{
const r=await api('GET','/api/ports');
ins={};cur={};
const rows=r.ports.map(p=>{
if(!p.editable)return field(t('pt_'+p.k),el('input',{value:p.port,dir:'ltr',disabled:true}),t('pp_ssh_hint'));
const i=el('input',{type:'number',min:'1',max:'65535',value:p.port,dir:'ltr',inputmode:'numeric'});
ins[p.k]=i;cur[p.k]=p.port;
return field(t('pt_'+p.k),i,p.k==='http'&&r.tls?t('pp_tls_hint'):null)
});
box.replaceChildren(el('div',{class:'muted sm'},t('pp_desc')),...rows,el('small',{class:'muted'},t('pp_internal',r.internal.join(' '))),el('div',{class:'row'},btn(t('save'),'floppy-disk',save,'pri')))
}catch(e){terr(e)}
};
fill();
return box
}
function compsBox(){
const ML={tls:t('cb_tls'),plain:t('cb_plain'),udp:t('cb_udp')};
const V2R=['vless','vmess','trojan'].flatMap(p=>['tls','plain'].map(m=>[p,m]));
const BL=[
{c:'wsbridge',i:'terminal',n:'SSH WebSocket',d:'cb_ws_desc',rows:[['sshws','tls'],['sshws','plain']]},
{c:'sshssl',i:'lock',n:'SSH SSL',d:'cb_ssl_desc',rows:[['sshssl','tls'],['sshssl','plain']]},
{c:'udpcustom',i:'tower-broadcast',n:'UDP Custom',d:'cb_udp_desc',rows:[['sshudp','udp']]},
{c:'xray',i:'bolt',n:'Xray',d:'cb_xray_desc',rows:V2R}];
const box=el('div',{class:'kvs cols xl'},el('div',{class:'empty'},ic('spinner','fa-spin')));
let R=null;
const fill=async()=>{
try{R=await api('GET','/api/components');box.replaceChildren(el('div',{class:'muted sm'},t('cb_desc')),...BL.map(draw),el('div',{class:'muted sm'},t('svc_legend')))}catch(e){terr(e)}
};
const doInstall=b=>{
if(b.c==='udpcustom'){
const cb=el('input',{type:'checkbox'});
const ex=el('div',{class:'udpw'},el('ul',{},...['udp_warn_1','udp_warn_2','udp_warn_3','udp_warn_4'].map(k=>el('li',{},t(k)))),el('label',{class:'chk'},cb,el('span',{},t('udp_ack'))));
ask(t('udp_warn_lead'),t('cb_install'),()=>{if(!cb.checked){toast(t('udp_ack_needed'));return false}return runJob('/api/components/udpcustom/install',{ack:true},t('cb_w_install'))},{title:t('udp_warn_title'),extra:ex})
}else ask(t('cb_install_confirm',b.n),t('cb_install'),()=>runJob('/api/components/'+b.c+'/install',{},t('cb_w_install')),{danger:false})
};
const doRemove=(b,cm)=>ask(t('cb_uninstall_confirm',b.n,t('cb_accounts',cm.accounts)),t('cb_uninstall'),()=>runJob('/api/components/'+b.c+'/uninstall',{},t('cb_w_uninstall')));
function draw(b){
const cm=R.comps[b.c],CBm=Object.fromEntries(R.combos.map(x=>[x.k,x])),busy=R.busy;
const enabledN=b.rows.filter(([p,m])=>CBm[p+':'+m].enabled).length;
const act=cm.removable?(cm.installed?btn('','trash',()=>doRemove(b,cm),'dgr'):btn(t('cb_install'),'download',()=>doInstall(b),'pri')):null;
if(act&&busy)act.disabled=true;
const rows=b.rows.map(([p,m])=>{
const x=CBm[p+':'+m];
const s=sw(x.enabled,v=>{
const send=async()=>{try{await api('POST','/api/components/combo',{key:x.k,enabled:v});toast(t('done'))}catch(e){terr(e)}await fill()};
if(!v&&enabledN===1&&cm.removable&&cm.installed&&cm.accounts>0){const d=ask(t('cb_off_confirm',b.n,t('cb_accounts',cm.accounts)),t('confirm'),async()=>{await send()});d.addEventListener('close',fill)}
else send()
});
if(!cm.installed||busy)s.disabled=true;
return el('div',{class:'cbrow'},el('div',{class:'srow-t'},el('b',{},(b.c==='xray'?PM[p].n+' · ':'')+ML[m]),x.why==='no_tls'?el('div',{class:'muted sm'},ic('triangle-exclamation'),' '+t('cb_no_tls')):null),s)
});
const info=[];
if(b.c==='udpcustom'){
if(!cm.installed)info.push(el('div',{class:'hint'},ic('triangle-exclamation'),t('udp_warn_1')));
else{info.push(el('div',{class:'muted sm'},t('udp_portl')+': ',el('b',{class:'ltr'},cm.port)));
if(cm.info&&cm.info.url)info.push(el('div',{class:'muted sm brk'},t('udp_src')+': ',el('span',{class:'ltr'},cm.info.url)));
if(cm.info&&cm.info.sha256)info.push(el('div',{class:'muted sm brk'},t('udp_sha')+': ',el('span',{class:'ltr'},cm.info.sha256)))}
}
return el('div',{class:'cbk'},
el('div',{class:'cbh'},el('span',{class:'ico c1'},ic(b.i)),el('div',{class:'cbt'},el('b',{},b.n),el('span',{class:'pill '+cm.state,title:t('svc_'+cm.state)},ic(SIC[cm.state]),t('svc_'+cm.state))),act),
el('div',{class:'muted sm cbd'},t(b.d)),
...info,el('div',{class:'cbrows'},...rows))
}
fill();
return box
}
async function viewSettings(){
const s=await api('GET','/api/settings');
const vw=document.documentElement.dataset.view==='desktop'?'desktop':'mobile';
const o=el('input',{type:'password',autocomplete:'current-password'});
const n=el('input',{type:'password',autocomplete:'new-password'});
const c=el('input',{type:'password',autocomplete:'new-password'});
const savePw=async()=>{
if(n.value!==c.value){toast(t('s_mismatch'));return}
try{await api('POST','/api/password',{old:o.value,new:n.value});toast(t('s_changed'));o.value=n.value=c.value=''}catch(e){terr(e)}
};
const dom=el('input',{placeholder:'vpn.example.com',dir:'ltr',value:s.domain,autocomplete:'off'});
const mail=el('input',{placeholder:'you@example.com',dir:'ltr',autocomplete:'off'});
const res=el('div',{class:'kvs cols full box'});
const showDom=r=>res.replaceChildren(...[
kv(t('dm_current'),r.domain||t('dm_none')),
kv(t('dm_server_ip'),r.server_ip||'—'),
kv(t('dm_dns'),r.dns.length?r.dns.join(', '):'—',r.candidate?pill(r.match?'ok':'bad',r.match?t('dm_match'):t('dm_nomatch')):null),
kv(t('dm_cert'),r.cert?t('dm_cert_days',r.cert.days_left)+' ('+dtd(r.cert.expires)+')':t('dm_cert_none')),
r.candidate&&!r.match?el('div',{class:'hint'},ic('triangle-exclamation'),t('dm_warn',r.candidate,r.server_ip||'—')):null].filter(Boolean));
const verify=async(quiet)=>{try{const r=await api('GET','/api/domain'+(dom.value.trim()?'?d='+encodeURIComponent(dom.value.trim().toLowerCase()):''));showDom(r);if(!quiet)toast(t('dm_checked'))}catch(e){terr(e)}};
verify(true);
const applyDom=()=>{
const d=dom.value.trim().toLowerCase();
if(!d){toast(t('e_bad_domain'));return}
ask(t('dm_confirm',d),t('confirm'),()=>{runJob('/api/domain',{domain:d,email:mail.value.trim()},t('dm_working'),'https://'+d+':'+location.port+'/')},{danger:false})
};
let bv=s.cap_basis;
const basisDd=dd([{v:'total',l:t('basis_total')},{v:'out',l:t('basis_out')}],bv,v=>{bv=v});
const cap=el('input',{type:'number',min:0,step:'any',value:s.cap_gb});
const usedIn=el('input',{type:'number',min:0,step:'any',placeholder:+(s.month_used/GB).toFixed(2)});
const saveLim=async()=>{
try{await api('POST','/api/settings',{cap_gb:cap.value,cap_basis:bv,used_gb:usedIn.value});toast(t('lim_saved'));usedIn.value='';if(S)await loadStats()}catch(e){terr(e)}
};
const resetMonth=()=>ask(t('lim_reset_confirm'),t('lim_reset'),async()=>{try{await api('POST','/api/settings',{reset:true});toast(t('lim_saved'));if(S)await loadStats()}catch(e){terr(e);return false}});
const themeBox=el('div',{class:'dc'});
const drawTheme=()=>{const cur=document.documentElement.dataset.theme;
themeBox.replaceChildren(
field(t('s_theme'),seg([{v:'dark',l:t('theme_dark'),i:'moon'},{v:'gray',l:t('theme_gray'),i:'circle-half-stroke'},{v:'light',l:t('theme_light'),i:'sun'}],cur,v=>{setTheme(v);drawTheme()})),
field(t('s_color_theme'),dd(THEMES.map(x=>({v:x[0],l:t('th_'+x[0]),c:'linear-gradient(135deg,'+x[1]+','+x[2]+')'})),THEMES.some(x=>x[0]===cur)?cur:'',v=>{setTheme(v);drawTheme()},210,t('theme_choose'))))};
drawTheme();
const row=(icon,title,desc,b)=>el('div',{class:'srow'},el('span',{class:'ico c1'},ic(icon)),el('div',{class:'srow-t'},el('b',{},title),el('div',{class:'muted sm'},desc)),b);
const pw=el('input',{type:'password',autocomplete:'current-password',placeholder:t('sys_uninstall_pw')});
const doUninstall=()=>ask(t('sys_uninstall_confirm'),t('sys_uninstall'),async()=>{
try{await api('POST','/api/system/uninstall',{password:pw.value})}catch(e){terr(e);return false}
const ov=overlay(t('sys_w_uninstall'));
setTimeout(()=>ov.replaceChildren(el('div',{class:'ovl-b'},ic('circle-check','ovl-i ok-i'),el('div',{class:'ovl-t'},t('sys_removed')))),9000)
},{extra:pw});
let tzR=s.tz_region,tzU=!!s.tz_utc;
const tzNames=(s.tz_list&&s.tz_list.length?s.tz_list:[]).slice();
if(!tzNames.includes(tzR))tzNames.unshift(tzR);
const saveTz=async b=>{try{await api('POST','/api/settings',b);TZ=tzU?'UTC':tzR;toast(t('lim_saved'))}catch(e){terr(e)}};
const tzDd=dd(tzNames.map(n=>({v:n,l:n})),tzR,v=>{tzR=v;saveTz({tz:v})},260);
const tzBox=el('div',{class:'tzbox'},tzDd);
const tzApply=()=>{tzBox.classList.toggle('dis',tzU);tzDd.querySelector('.dd-b').disabled=tzU};
tzApply();
const tzSw=sw(tzU,v=>{tzU=v;tzApply();saveTz({tz_utc:v})});
const pwr=el('input',{type:'password',autocomplete:'current-password',placeholder:t('sys_uninstall_pw')});
const doReset=()=>ask(t('sys_reset_confirm'),t('sys_reset'),async()=>{
try{await api('POST','/api/system/reset',{password:pwr.value})}catch(e){terr(e);return false}
toast(t('sys_reset_done'));setTimeout(()=>location.reload(),900)
},{extra:pwr});
const bn=el('textarea',{rows:5,maxlength:2000,dir:'auto',placeholder:t('bn_ph')});
bn.value=s.banner||'';
const saveBn=async(v)=>{try{await api('POST','/api/settings',{banner:v});if(v==='')bn.value='';toast(t('bn_saved'))}catch(e){terr(e)}};
const lgBox=el('div',{class:'kvs cols lg'},el('div',{class:'empty'},ic('spinner','fa-spin')));
const fillLogs=async()=>{
try{
const r=await api('GET','/api/logs');
lgBox.replaceChildren(...(r.items.length?r.items.map(i=>el('div',{class:'srow'},el('span',{class:'ico c2'},ic(i.kind==='file'?'file-lines':'scroll')),el('div',{class:'srow-t'},el('b',{},t('lg_'+i.id)),el('div',{class:'muted sm'},i.kind==='file'?bytes(i.size):t('lg_journal'))),el('div',{class:'acts'},
el('button',{class:'icon-btn',title:t('lg_open'),onclick:()=>logDlgView(i.id,fillLogs)},ic('eye')),
el('button',{class:'icon-btn',title:t('lg_download'),onclick:()=>dlLog(i.id)},ic('download')),
el('button',{class:'icon-btn danger',title:t('lg_clear'),onclick:()=>clearLog(i.id,fillLogs)},ic('eraser'))))):[el('div',{class:'empty'},t('lg_none'))]),el('div',{class:'muted sm'},t('lg_unit_note')))
}catch(e){terr(e)}
};
fillLogs();
$('#view').replaceChildren(el('div',{class:'stack'},
panel('palette',t('s_appearance'),el('div',{class:'form cols lg'},
themeBox,
field(t('s_language'),seg([{v:'en',l:'English',i:'language'},{v:'ar',l:'العربية',i:'language'}],LANG,setLang)),
field(t('s_speed'),seg([{v:'bytes',l:t('spu_bytes')},{v:'bits',l:t('spu_bits')}],SPU,v=>{setSpu(v);toast(t('done'))}),t('s_speed_hint')),
field(t('s_view'),seg([{v:'mobile',l:t('view_mobile'),i:'mobile-screen'},{v:'desktop',l:t('view_desktop'),i:'desktop'}],vw,v=>{try{localStorage.setItem('view',v)}catch(e){}location.reload()}),t('s_view_hint')),
el('div',{class:'f'},el('span',{},t('s_tz')),tzBox,el('div',{class:'kv'},el('span',{},t('s_tz_utc')),tzSw),el('small',{class:'muted'},t('s_tz_hint'))))),
panel('key',t('s_security'),el('div',{class:'form cols'},field(t('s_cur'),o),field(t('s_new'),n,t('s_new_hint')),field(t('s_confirm'),c),el('div',{class:'row'},btn(t('s_change'),'floppy-disk',savePw,'pri')))),
panel('globe',t('dm_title'),el('div',{class:'form cols'},res,field(t('dm_domain'),dom),field(t('dm_email'),mail),el('div',{class:'row'},btn(t('dm_apply'),'lock',applyDom,'pri'),btn(t('dm_verify'),'shield-halved',()=>verify(false))))),
panel('plug',t('pp_title'),portsBox()),
panel('puzzle-piece',t('cb_title'),compsBox()),
panel('gauge-high',t('lim_title'),el('div',{class:'form cols'},
field(t('lim_cap'),cap,t('lim_cap_hint')),
field(t('lim_basis'),basisDd),
field(t('lim_used'),usedIn),
el('div',{class:'row'},btn(t('save'),'floppy-disk',saveLim,'pri'),btn(t('lim_reset'),'eraser',resetMonth)))),
panel('eye',t('pg_title'),el('div',{class:'form'},el('div',{class:'muted sm'},t('pg_desc')),seg([{v:'on',l:t('pg_on'),i:'eye'},{v:'off',l:t('pg_off'),i:'eye-slash'}],s.public_page?'on':'off',async v=>{try{await api('POST','/api/settings',{public_page:v==='on'});toast(t('pg_saved'))}catch(e){terr(e)}}))),
panel('bullhorn',t('bn_title'),el('div',{class:'form'},el('div',{class:'muted sm'},t('bn_desc')),bn,el('div',{class:'row'},btn(t('save'),'floppy-disk',()=>saveBn(bn.value),'pri'),btn(t('bn_clear'),'eraser',()=>saveBn(''))))),
panel('file-lines',t('lg_title'),el('div',{class:'form'},el('div',{class:'muted sm'},t('lg_desc')),lgBox)),
panel('screwdriver-wrench',t('sys_title'),el('div',{class:'kvs cols sys lg'},
kv(t('sys_version'),VERSION),
latestRow(),
row('rotate-right',t('sys_restart'),t('sys_restart_desc'),btn('','power-off',()=>ask(t('sys_restart_confirm'),t('sys_restart'),()=>{runJob('/api/system/restart',null,t('sys_w_restart'))},{danger:false}))),
row('cloud-arrow-down',t('sys_update'),t('sys_update_desc'),btn('','cloud-arrow-down',()=>ask(t('sys_update_confirm'),t('sys_update'),()=>{runJob('/api/system/update',null,t('sys_w_update'))},{danger:false}))),
row('broom',t('sys_reset'),t('sys_reset_desc'),btn('','broom',doReset,'dgr')),
row('trash',t('sys_uninstall'),t('sys_uninstall_desc'),btn('','trash',doUninstall,'dgr'))))))
}
const RAW='https://raw.githubusercontent.com/tamaa-pro/isile/refs/heads/main/panel/VERSION';
const fetchLatest=async()=>{try{const r=await fetch(RAW+'?t='+Date.now(),{cache:'no-store',credentials:'omit',referrerPolicy:'no-referrer'});if(!r.ok)throw 0;const v=(await r.text()).trim().split('\n')[0].trim();if(!/^[0-9A-Za-z .+_-]{1,32}$/.test(v))throw 0;return{latest:v}}catch(e){return api('GET','/api/system/latest')}};
function latestRow(){
const b=el('b',{class:'ltr'},'…');
const g=el('div',{class:'kv-v'},b);
const d=el('div',{class:'kv'},el('span',{},t('sys_latest')),g);
fetchLatest().then(r=>{b.textContent=r.latest;g.prepend(r.latest===VERSION?pill('ok',t('sys_uptodate')):pill('warn',t('sys_new')))}).catch(()=>{b.textContent=t('sys_latest_err')});
return d}
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
TR.el=null;
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
