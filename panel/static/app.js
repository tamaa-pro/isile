'use strict';
const $=(s,r=document)=>r.querySelector(s);
const csrf=$('meta[name=csrf]').content;
const LBL={ssh:'SSH + WebSocket',vless:'VLESS + WS + TLS',trojan:'Trojan + WS + TLS'};
const ST={active:'نشط',disabled:'معطّل',expired:'منتهي',limit:'تجاوز الحد'};
const GB=1073741824;
let ACC=[];
const el=(t,a={},...k)=>{const e=document.createElement(t);for(const[x,v]of Object.entries(a)){if(x==='class')e.className=v;else if(x.startsWith('on'))e.addEventListener(x.slice(2),v);else if(v!==false&&v!=null)e.setAttribute(x,v===true?'':v)}for(const c of k.flat()){if(c==null||c===false)continue;e.append(c instanceof Node?c:document.createTextNode(String(c)))}return e};
const api=async(m,u,b)=>{const r=await fetch(u,{method:m,headers:{'Content-Type':'application/json','X-CSRF':csrf},body:b?JSON.stringify(b):undefined,credentials:'same-origin'});if(r.status===401){location.href='/login';throw new Error('unauthorized')}const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(j.error||'خطأ');return j};
const bytes=n=>{if(!n)return'0 B';const u=['B','KB','MB','GB','TB'];const i=Math.min(Math.floor(Math.log(n)/Math.log(1024)),4);return(n/1024**i).toFixed(i?2:0)+' '+u[i]};
const dateTxt=t=>t?new Date(t*1000).toLocaleDateString('en-GB'):'مفتوح';
const left=t=>{if(!t)return'غير محدود';const d=Math.ceil((t*1000-Date.now())/864e5);return d>0?d+' يوم':'منتهي'};
const toast=m=>{const t=el('div',{class:'toast'},m);document.body.append(t);setTimeout(()=>t.remove(),3500)};
const field=(l,i)=>el('label',{class:'f'},el('span',{},l),i);
const copy=async v=>{try{await navigator.clipboard.writeText(v);toast('تم النسخ')}catch{toast('تعذر النسخ')}};
const modal=(title,body,btns=[])=>{const d=el('dialog',{},el('h3',{},title),body,el('div',{class:'row end'},...btns,el('button',{class:'btn',onclick:()=>d.close()},'إغلاق')));d.addEventListener('close',()=>d.remove());document.body.append(d);d.showModal();return d};
const card=(t,v)=>el('div',{class:'card'},el('b',{},t),el('span',{},v));
async function loadStats(){
const s=await api('GET','/api/stats');
const act=ACC.filter(a=>a.status==='active').length;
$('#stats').replaceChildren(
card('الحمل',s.load.map(x=>x.toFixed(2)).join(' / ')),
card('الذاكرة',bytes(s.mem_used)+' / '+bytes(s.mem_total)),
card('القرص',bytes(s.disk_used)+' / '+bytes(s.disk_total)),
card('مدة التشغيل',Math.floor(s.uptime/86400)+' يوم '+Math.floor(s.uptime%86400/3600)+' س'),
card('الحسابات',ACC.length+' ('+act+' نشط)'),
card('إجمالي الاستهلاك',bytes(ACC.reduce((t,a)=>t+a.up+a.down,0))),
el('div',{class:'card'},el('b',{},'الخدمات'),el('div',{class:'svc'},...Object.entries(s.services).map(([k,v])=>el('span',{class:'pill '+(v?'ok':'bad')},k)))))
}
const btn=(t,f,c='')=>el('button',{class:'btn sm '+c,onclick:f},t);
function row(a){
const used=a.up+a.down;
let bar=null;
if(a.quota){const i=el('i');i.style.width=Math.min(100,used/a.quota*100)+'%';bar=el('div',{class:'bar'},i)}
return el('tr',{},
el('td',{},a.name),
el('td',{},LBL[a.proto]),
el('td',{},el('span',{class:'pill '+a.status},ST[a.status])),
el('td',{},el('div',{},'↑ '+bytes(a.up)+'  ↓ '+bytes(a.down)),el('div',{class:'muted'},bytes(used)+' / '+(a.quota?bytes(a.quota):'∞')),bar),
el('td',{},el('div',{},dateTxt(a.expires)),el('div',{class:'muted'},left(a.expires))),
el('td',{class:'muted'},a.note),
el('td',{},el('div',{class:'acts'},btn('معلومات',()=>infoDlg(a.name)),btn('تعديل',()=>editDlg(a)),btn(a.manual?'تفعيل':'تعطيل',()=>patch(a.name,{manual:!a.manual})),btn('حذف',()=>del(a),'danger'))))
}
function render(){
const q=$('#q').value.trim().toLowerCase(),p=$('#pf').value,s=$('#sf').value;
const list=ACC.filter(a=>(!p||a.proto===p)&&(!s||a.status===s)&&(!q||a.name.includes(q)||a.note.toLowerCase().includes(q)));
$('#rows').replaceChildren(...(list.length?list.map(row):[el('tr',{},el('td',{colspan:7,class:'muted'},'لا توجد حسابات'))]))
}
async function refresh(){
try{ACC=await api('GET','/api/accounts');render();await loadStats()}catch(e){if(e.message!=='unauthorized')toast(e.message)}
}
async function patch(n,b,msg='تم'){
try{await api('PATCH','/api/accounts/'+n,b);toast(msg);await refresh();return true}catch(e){toast(e.message);return false}
}
async function del(a){
if(!confirm('حذف الحساب '+a.name+' نهائياً؟'))return;
try{await api('DELETE','/api/accounts/'+a.name);toast('تم الحذف');await refresh()}catch(e){toast(e.message)}
}
async function infoDlg(n){
try{
const r=await api('GET','/api/accounts/'+n+'/info');
modal('معلومات '+n,el('div',{},...r.items.map(i=>el('div',{class:'item'},el('span',{},i.label),el('textarea',{readonly:true,rows:i.rows||2,dir:'ltr'},i.value),el('button',{class:'btn sm',onclick:()=>copy(i.value)},'نسخ')))))
}catch(e){toast(e.message)}
}
function createDlg(){
const proto=el('select',{},...Object.entries(LBL).map(([k,v])=>el('option',{value:k},v)));
const name=el('input',{placeholder:'user1',maxlength:20,autocomplete:'off',dir:'ltr'});
const secret=el('input',{placeholder:'تلقائي',autocomplete:'off',dir:'ltr'});
const days=el('input',{type:'number',min:0,value:30});
const quota=el('input',{type:'number',min:0,step:'any',value:0});
const note=el('input',{maxlength:100});
const form=el('div',{class:'form'},field('البروتوكول',proto),field('اسم المستخدم',name),field('كلمة المرور / UUID (اختياري)',secret),field('الصلاحية بالأيام (0 = مفتوحة)',days),field('حد الترافيك GB (0 = مفتوح)',quota),field('ملاحظة',note));
const d=modal('حساب جديد',form,[el('button',{class:'btn pri',onclick:async()=>{
try{const r=await api('POST','/api/accounts',{proto:proto.value,name:name.value,secret:secret.value,days:+days.value,quota_gb:+quota.value,note:note.value});d.close();await refresh();infoDlg(r.name)}catch(e){toast(e.message)}
}},'إنشاء')])
}
function editDlg(a){
const secret=el('input',{placeholder:'اتركه فارغاً بدون تغيير',autocomplete:'off',dir:'ltr'});
const days=el('input',{type:'number',min:0,placeholder:'فارغ = بدون تغيير، 0 = مفتوح'});
const quota=el('input',{type:'number',min:0,step:'any',value:a.quota?+(a.quota/GB).toFixed(3):0});
const note=el('input',{maxlength:100,value:a.note});
const form=el('div',{class:'form'},field(a.proto==='vless'?'UUID جديد':'كلمة مرور جديدة',secret),field('الصلاحية من الآن بالأيام',days),field('حد الترافيك GB (0 = مفتوح)',quota),field('ملاحظة',note));
const d=modal('تعديل '+a.name,form,[
el('button',{class:'btn pri',onclick:async()=>{if(await patch(a.name,{secret:secret.value,days:days.value,quota_gb:quota.value,note:note.value}))d.close()}},'حفظ'),
el('button',{class:'btn',onclick:async()=>{if(await patch(a.name,{regen:true},'تم توليد سر جديد'))d.close()}},'توليد سر جديد'),
el('button',{class:'btn',onclick:async()=>{if(await patch(a.name,{reset:true},'تم تصفير الترافيك'))d.close()}},'تصفير الترافيك')])
}
function pwDlg(){
const o=el('input',{type:'password',autocomplete:'current-password'});
const n=el('input',{type:'password',autocomplete:'new-password'});
const d=modal('تغيير كلمة المرور',el('div',{class:'form'},field('الحالية',o),field('الجديدة (10 أحرف على الأقل)',n)),[el('button',{class:'btn pri',onclick:async()=>{
try{await api('POST','/api/password',{old:o.value,new:n.value});toast('تم التغيير');d.close()}catch(e){toast(e.message)}
}},'حفظ')])
}
$('#add').addEventListener('click',createDlg);
$('#pw').addEventListener('click',pwDlg);
$('#out').addEventListener('click',async()=>{try{await api('POST','/api/logout')}catch{}location.href='/login'});
for(const i of['#q','#pf','#sf'])$(i).addEventListener('input',render);
refresh();
setInterval(refresh,15000);
