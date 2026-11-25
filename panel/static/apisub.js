'use strict';
/* isile 1.9.7: "API and subscription" card of the settings page, the configs window, and the subscription switch of the account dialog.
   Loaded after i18n.js and before app.js; it only uses the helpers of app.js when a function runs. Backend: apisub.py */
Object.assign(I18N.ar,{
ap_title:'API ورابط الاشتراك',ap_desc:'يتيح لتطبيق VPN خاص أو لأي تطبيق يدعم رابط الاشتراك جلب كونفيجات حسابات محددة بالإعدادات التي تختارها هنا، فلا تكفي بيانات الحساب وحدها (TLS وPayload وSNI وغيرها).',
ap_on:'تفعيل API',ap_on_hint:'مغلق افتراضياً. عند التفعيل يُولَّد رابط من رابط اللوحة يتبعه هاش، ويمكن توليد أكثر من رابط.',
ap_keys:'روابط API',ap_add:'إضافة API',ap_rename:'تسمية',ap_regen:'رابط جديد',ap_regen_confirm:'سيتوقف الرابط القديم عن العمل فوراً وتحتاج التطبيقات إلى الرابط الجديد. متابعة؟',
ap_del:'حذف',ap_del_confirm:'حذف رابط API هذا نهائياً؟',ap_name:'اسم الرابط',ap_hits:'{0} طلب',ap_never:'لم يُستخدم بعد',ap_cfgs:'{0} كونفيج',ap_off_key:'متوقف',
ap_secret:'الرابط سرّي: من يملكه يقرأ بيانات الحسابات المرسلة عبره. يعيد JSON، وللقائمة فقط أضف ‎?format=raw‎ إلى آخره.',
ap_ctl:'التحكم بما يُرسل',ap_ctl_hint:'اختر الحسابات والإعدادات التي تصل إلى التطبيق، ولكل كونفيج خيار الإرسال عبر API أو الاشتراك أو كليهما.',
sb_title:'رابط الاشتراك',sb_on:'تفعيل رابط الاشتراك',sb_hint:'التفعيل هنا يفتح خيار الاشتراك في نافذة إنشاء الحساب فقط. ولا يُصدر الرابط شيئاً قبل أن تُنشأ كونفيجات لذلك الحساب وتُضبط على الإرسال عبر الاشتراك.',
sb_count:'{0} حساب مفعّل له الاشتراك',
cd_title:'ما يُرسل عبر API والاشتراك',cd_add:'إضافة كونفيج',cd_empty:'لا توجد كونفيجات بعد. أضف كونفيجاً من أحد الحسابات.',cd_pick:'اختر الحساب',cd_pick_none:'لا توجد حسابات مدعومة. يدعم التطبيق: SSH (WS وSSL وDirect وVayDNS وSlowDNS) وV2Ray (WS وgRPC وXHTTP).',
cd_search:'بحث عن حساب',cd_new:'كونفيج جديد من {0}',cd_edit:'تعديل الكونفيج',cd_save:'حفظ',cd_dup:'نسخ الكونفيج',cd_del:'حذف',cd_del_confirm:'حذف هذا الكونفيج؟',cd_copy:'نسخ الرابط',
cd_label:'اسم الكونفيج',cd_label_hint:'الاسم الذي يظهر في التطبيق. يمكن إنشاء عدة كونفيجات من الحساب نفسه.',cd_delivery:'الإرسال',cd_apis:'روابط API المستلمة',cd_apis_hint:'بدون اختيار = كل روابط API',
cd_reset:'إعادة الكل للتلقائي',cd_link:'الرابط الناتج',cd_auto:'تلقائي',cd_inactive:'الحساب غير نشط فلا يُرسل',cd_no_delivery:'لا يُرسل',
dl_none:'لا شيء',dl_api:'API',dl_sub:'اشتراك',dl_both:'الاثنان',
g_id:'الهوية',g_conn:'الاتصال',g_ws:'WebSocket',g_payload:'Payload والبروكسي',g_tls:'TLS',g_net:'الشبكة',g_dns:'نفق DNS',g_dnsadv:'خيارات DNS المتقدمة',g_adv:'متقدم',
cf_label:'الاسم',cf_locked:'قفل الكونفيج',cf_host:'العنوان (Host)',cf_port:'المنفذ',cf_ws:'WebSocket',cf_wsPath:'مسار WebSocket',cf_wsHost:'ترويسة Host',cf_payloadOn:'تفعيل Payload',cf_payload:'Payload',
cf_proxyHost:'بروكسي بعيد (Remote Proxy)',cf_proxyPort:'منفذ البروكسي',cf_tls:'TLS',cf_sni:'SNI',cf_tlsVersion:'إصدار TLS',cf_insecure:'السماح بشهادة غير موثوقة',
cf_dnsTransport:'نقل DNS',cf_dnsResolver:'المحلّل (Resolver)',cf_dnsRecord:'نوع السجل',cf_dnsListen:'المستمع المحلي',cf_dnsCompat:'توافق dnstt',cf_dnsIdle:'idle-timeout (ث)',cf_dnsKeepalive:'keepalive (ث)',
cf_dnsUdpTimeout:'udp-timeout (مللي ث)',cf_dnsOpenStream:'open-stream-timeout (ث)',cf_dnsWorkers:'udp-workers',cf_dnsRps:'rps',cf_dnsMaxQname:'max-qname-len',cf_dnsMaxLabels:'max-num-labels',cf_dnsClientId:'clientid-size',
cf_dnsUtls:'بصمة TLS (utls)',cf_dnsLogLevel:'مستوى السجل',cf_dnsExtra:'خيارات إضافية',cf_network:'الشبكة (Network)',cf_serviceName:'اسم خدمة gRPC',cf_mux:'Mux',cf_fingerprint:'بصمة TLS',cf_alpn:'ALPN',
cf_flow:'Flow',cf_encryption:'Encryption',cf_alterId:'alterId',cf_vmessScy:'تشفير VMess',
ch_locked:'يخفي محتوى الكونفيج داخل التطبيق ويمنع تعديله ومشاركته',ch_host:'غيّره مثلاً إلى نطاق CDN أو عنوان آخر. الفارغ = نطاق اللوحة',ch_port:'الفارغ = المنفذ الافتراضي حسب TLS',
ch_payload:'الوسوم: [host] [port] [host_port] [crlf]',ch_proxyHost:'اتركه فارغاً لعدم استعمال بروكسي',ch_sni:'الفارغ = نطاق اللوحة',ch_dnsResolver:'مثل 8.8.8.8:53 أو dns.google:853 أو https://dns.google/dns-query',
ch_dnsListen:'مثل 7000 أو 127.0.0.1:7000، والفارغ = تلقائي',ch_mux:'يصل التطبيق عبر JSON فقط، ولا يحمله الرابط',ch_dnsExtra:'خيارات تُمرَّر للمحرك كما هي',
e_api_bad_field:'قيمة غير صالحة',e_api_unsupported:'هذا الحساب غير مدعوم في التطبيق',e_too_many:'تم بلوغ الحد الأقصى',
sub_f:'رابط الاشتراك',sub_f_on:'تفعيل رابط الاشتراك لهذا الحساب',sub_f_hint:'لا يُصدر الرابط شيئاً حتى تُنشأ كونفيجات من هذا الحساب وتُضبط على الإرسال عبر الاشتراك.',sub_f_na:'غير متاح لـ UDP Custom وV2Ray عبر DNS',sub_f_cfgs:'{0} كونفيج عبر الاشتراك',
l_sub_link:'رابط الاشتراك'});
Object.assign(I18N.en,{
ap_title:'API & subscription',ap_desc:'Lets a private VPN app, or any app that supports subscription links, fetch the configs of chosen accounts with the settings you pick here, because the account credentials alone are not enough (TLS, payload, SNI and more).',
ap_on:'Enable API',ap_on_hint:'Off by default. When enabled, a link is generated from the panel URL followed by a hash, and you can generate more than one.',
ap_keys:'API links',ap_add:'Add API',ap_rename:'Rename',ap_regen:'New link',ap_regen_confirm:'The old link stops working immediately and apps need the new one. Continue?',
ap_del:'Delete',ap_del_confirm:'Delete this API link permanently?',ap_name:'Link name',ap_hits:'{0} requests',ap_never:'Never used',ap_cfgs:'{0} configs',ap_off_key:'Paused',
ap_secret:'The link is secret: anyone who has it can read the account data sent through it. It returns JSON; add ?format=raw to get only the list of links.',
ap_ctl:'Control what is sent',ap_ctl_hint:'Choose the accounts and settings that reach the app. Each config can be sent through the API, the subscription, both or neither.',
sb_title:'Subscription link',sb_on:'Enable subscription link',sb_hint:'Enabling it here only unlocks the subscription switch in the create-account window. The link returns nothing until configs are made from that account and set to be sent through the subscription.',
sb_count:'{0} accounts with subscription enabled',
cd_title:'What is sent through the API and subscription',cd_add:'Add config',cd_empty:'No configs yet. Add one from an account.',cd_pick:'Choose the account',cd_pick_none:'No supported accounts. The app supports SSH (WS, SSL, Direct, VayDNS, SlowDNS) and V2Ray (WS, gRPC, XHTTP).',
cd_search:'Search accounts',cd_new:'New config from {0}',cd_edit:'Edit config',cd_save:'Save',cd_dup:'Duplicate config',cd_del:'Delete',cd_del_confirm:'Delete this config?',cd_copy:'Copy link',
cd_label:'Config name',cd_label_hint:'The name shown in the app. You can make several configs from the same account.',cd_delivery:'Delivery',cd_apis:'Receiving API links',cd_apis_hint:'None selected = every API link',
cd_reset:'Reset everything to auto',cd_link:'Resulting link',cd_auto:'auto',cd_inactive:'Account is not active, so it is not sent',cd_no_delivery:'Not sent',
dl_none:'None',dl_api:'API',dl_sub:'Subscription',dl_both:'Both',
g_id:'Identity',g_conn:'Connection',g_ws:'WebSocket',g_payload:'Payload & proxy',g_tls:'TLS',g_net:'Network',g_dns:'DNS tunnel',g_dnsadv:'Advanced DNS options',g_adv:'Advanced',
cf_label:'Name',cf_locked:'Lock the config',cf_host:'Address (Host)',cf_port:'Port',cf_ws:'WebSocket',cf_wsPath:'WebSocket path',cf_wsHost:'Host header',cf_payloadOn:'Enable payload',cf_payload:'Payload',
cf_proxyHost:'Remote proxy',cf_proxyPort:'Proxy port',cf_tls:'TLS',cf_sni:'SNI',cf_tlsVersion:'TLS version',cf_insecure:'Allow untrusted certificate',
cf_dnsTransport:'DNS transport',cf_dnsResolver:'Resolver',cf_dnsRecord:'Record type',cf_dnsListen:'Local listener',cf_dnsCompat:'dnstt compatibility',cf_dnsIdle:'idle-timeout (s)',cf_dnsKeepalive:'keepalive (s)',
cf_dnsUdpTimeout:'udp-timeout (ms)',cf_dnsOpenStream:'open-stream-timeout (s)',cf_dnsWorkers:'udp-workers',cf_dnsRps:'rps',cf_dnsMaxQname:'max-qname-len',cf_dnsMaxLabels:'max-num-labels',cf_dnsClientId:'clientid-size',
cf_dnsUtls:'TLS fingerprint (utls)',cf_dnsLogLevel:'Log level',cf_dnsExtra:'Extra flags',cf_network:'Network',cf_serviceName:'gRPC service name',cf_mux:'Mux',cf_fingerprint:'TLS fingerprint',cf_alpn:'ALPN',
cf_flow:'Flow',cf_encryption:'Encryption',cf_alterId:'alterId',cf_vmessScy:'VMess cipher',
ch_locked:'Hides the config content inside the app and blocks editing and sharing',ch_host:'Change it to a CDN domain or another address, for example. Empty = the panel domain',ch_port:'Empty = the default port for the TLS setting',
ch_payload:'Tags: [host] [port] [host_port] [crlf]',ch_proxyHost:'Leave empty for no proxy',ch_sni:'Empty = the panel domain',ch_dnsResolver:'Such as 8.8.8.8:53, dns.google:853 or https://dns.google/dns-query',
ch_dnsListen:'Such as 7000 or 127.0.0.1:7000; empty = automatic',ch_mux:'Reaches the app through JSON only; a link cannot carry it',ch_dnsExtra:'Flags passed to the engine as they are',
e_api_bad_field:'Invalid value',e_api_unsupported:'This account is not supported by the app',e_too_many:'Limit reached',
sub_f:'Subscription link',sub_f_on:'Enable the subscription link for this account',sub_f_hint:'The link returns nothing until configs are made from this account and set to be sent through the subscription.',sub_f_na:'Not available for UDP Custom and V2Ray over DNS',sub_f_cfgs:'{0} configs via subscription',
l_sub_link:'Subscription link'});
const APS={snap:null};
const apNum=(n)=>n.toLocaleString(LANG==='ar'?'ar-u-nu-latn':'en');
const apAgo=ts=>{if(!ts)return t('ap_never');try{return fmtD(W(ts*1000))}catch(e){return String(ts)}};
const DL_OPTS=()=>[{v:'none',l:t('dl_none'),i:'ban'},{v:'api',l:t('dl_api'),i:'plug'},{v:'sub',l:t('dl_sub'),i:'rss'},{v:'both',l:t('dl_both'),i:'layer-group'}];
const apPost=async(u,b,m='POST')=>{const s=await api(m,u,b);if(s&&s.keys)APS.snap=s;return s};
/* ---------- settings card ---------- */
function apiCard(){
const body=el('div',{class:'form'});
const box=sec('plug',t('ap_title'),body);
const draw=()=>{
const s=APS.snap;
if(!s){body.replaceChildren(el('div',{class:'empty'},ic('spinner','fa-spin')));return}
const apiSw=sw(s.api_on,async v=>{try{await apPost('/api/apicfg/settings',{api_on:v});toast(t('done'))}catch(e){terr(e)}draw()});
const subSw=sw(s.sub_on,async v=>{try{await apPost('/api/apicfg/settings',{sub_on:v});toast(t('done'))}catch(e){terr(e)}draw()});
const keys=s.api_on?el('div',{class:'stack ap-keys'},...s.keys.map(k=>keyRow(k)),el('div',{class:'row'},btn(t('ap_add'),'plus',async()=>{try{await apPost('/api/apicfg/keys',{});draw()}catch(e){terr(e)}}),btn(t('ap_ctl'),'sliders',()=>configsDlg(draw),'pri')),el('div',{class:'hint'},ic('circle-info'),t('ap_secret'))):null;
const nSub=s.accounts.filter(a=>a.sub).length;
body.replaceChildren(...[
el('div',{class:'muted sm'},t('ap_desc')),
el('div',{class:'f'},el('div',{class:'kv'},el('span',{},t('ap_on')),apiSw),el('small',{class:'muted'},t('ap_on_hint'))),
keys,
el('div',{class:'ap-sep'}),
el('div',{class:'f'},el('div',{class:'kv'},el('span',{},t('sb_on')),subSw),el('small',{class:'muted'},t('sb_hint')),s.sub_on?el('small',{class:'muted'},t('sb_count',nSub)):null),
s.sub_on&&!s.api_on?el('div',{class:'row'},btn(t('ap_ctl'),'sliders',()=>configsDlg(draw),'pri')):null].filter(Boolean))};
const keyRow=k=>{
const url=el('input',{readonly:true,dir:'ltr',value:k.url});
const en=sw(k.enabled,async v=>{try{await apPost('/api/apicfg/keys/'+k.id,{enabled:v},'PATCH');toast(t('done'))}catch(e){terr(e)}draw()});
const rn=()=>{const inp=el('input',{maxlength:40,value:k.name,placeholder:t('ap_name')});const d=modal(t('ap_rename'),field(t('ap_name'),inp),[btn(t('save'),'floppy-disk',async()=>{try{await apPost('/api/apicfg/keys/'+k.id,{name:inp.value},'PATCH');d.close();draw()}catch(e){terr(e)}},'pri')])};
return el('div',{class:'ap-key'+(k.enabled?'':' off')},
el('div',{class:'ap-key-h'},el('b',{},k.name||'API'),el('span',{class:'muted sm'},t('ap_cfgs',k.configs)+' · '+(k.hits?t('ap_hits',apNum(k.hits))+' · '+apAgo(k.last):t('ap_never'))),en),
el('div',{class:'inp-row'},url,el('button',{class:'icon-btn',title:t('copy'),onclick:()=>copy(k.url)},ic('copy')),
el('button',{class:'icon-btn',title:t('ap_rename'),onclick:rn},ic('pen')),
el('button',{class:'icon-btn',title:t('ap_regen'),onclick:()=>ask(t('ap_regen_confirm'),t('ap_regen'),async()=>{try{await apPost('/api/apicfg/keys/'+k.id,{regen:true},'PATCH');draw()}catch(e){terr(e);return false}},{danger:false})},ic('rotate')),
el('button',{class:'icon-btn danger',title:t('ap_del'),onclick:()=>ask(t('ap_del_confirm'),t('ap_del'),async()=>{try{await apPost('/api/apicfg/keys/'+k.id+'/delete',{});draw()}catch(e){terr(e);return false}})},ic('trash'))))};
draw();
api('GET','/api/apicfg').then(s=>{APS.snap=s;draw()}).catch(terr);
return box}
/* ---------- configs window ---------- */
function configsDlg(onClose){
const list=el('div',{class:'stack cfgs'});
const draw=()=>{
const s=APS.snap;
const rows=s.configs.map(c=>cfgRow(c,s));
list.replaceChildren(...(rows.length?rows:[el('div',{class:'empty'},t('cd_empty'))]))};
const cfgRow=(c,s)=>{
const dl=dd(DL_OPTS(),c.delivery,async v=>{try{await apPost('/api/apicfg/configs/'+c.id,{delivery:v},'PATCH');toast(t('done'))}catch(e){terr(e)}draw()},150);
return el('div',{class:'cfg-i'+(c.status!=='active'?' off':'')},
el('div',{class:'cfg-t'},el('b',{},c.label),el('div',{class:'muted sm ltr'},c.account+' · '+c.type+' · '+c.host+':'+c.port),
c.status!=='active'?el('div',{class:'muted sm'},ic('triangle-exclamation'),' '+t('cd_inactive')):null,
c.delivery==='none'?el('div',{class:'muted sm'},t('cd_no_delivery')):null),
el('div',{class:'cfg-a'},dl,
el('button',{class:'icon-btn',title:t('cd_edit'),onclick:()=>cfgForm(c.account,c,draw)},ic('pen')),
el('button',{class:'icon-btn',title:t('cd_dup'),onclick:async()=>{try{await apPost('/api/apicfg/configs',{account:c.account,label:'',delivery:c.delivery,apis:c.apis,settings:c.settings});draw()}catch(e){terr(e)}}},ic('clone')),
el('button',{class:'icon-btn danger',title:t('cd_del'),onclick:()=>ask(t('cd_del_confirm'),t('cd_del'),async()=>{try{await apPost('/api/apicfg/configs/'+c.id+'/delete',{});draw()}catch(e){terr(e);return false}})},ic('trash'))))};
const d=modal(t('cd_title'),el('div',{class:'stack'},el('div',{class:'muted sm'},t('ap_ctl_hint')),list),[btn(t('cd_add'),'plus',()=>pickAccount(draw),'pri'),btn(t('close'),'xmark',()=>d.close())],'xl');
d.addEventListener('close',()=>{if(onClose)onClose()});
draw();
api('GET','/api/apicfg').then(s=>{APS.snap=s;draw()}).catch(terr)}
function pickAccount(done){
const s=APS.snap;
const q=el('input',{placeholder:t('cd_search'),autocomplete:'off',dir:'ltr'});
const box=el('div',{class:'stack cfg-pick'});
const paint=()=>{const f=q.value.trim().toLowerCase();const a=s.accounts.filter(x=>!f||x.name.includes(f));
box.replaceChildren(...(a.length?a.map(x=>el('button',{type:'button',class:'cfg-pk',onclick:()=>{d.close();cfgForm(x.name,null,done)}},el('b',{class:'ltr'},x.name),el('span',{class:'pill'},x.proto==='ssh'?'SSH · '+x.transport.toUpperCase():x.proto.toUpperCase()+' · '+x.transport.toUpperCase()),x.status!=='active'?pill('off',t('st_'+x.status)):null)):[el('div',{class:'empty'},t('cd_pick_none'))]))};
q.addEventListener('input',paint);paint();
const d=modal(t('cd_pick'),el('div',{class:'stack'},s.accounts.length>6?q:null,box),[btn(t('cancel'),'xmark',()=>d.close())])}
/* ---------- config editor ---------- */
const GROUPS=['id','conn','ws','payload','net','tls','dns','dnsadv','adv'];
const COLLAPSED={dnsadv:1,adv:1};
async function cfgForm(account,cfg,done){
let F;
try{F=await api('GET','/api/apicfg/fields/'+account)}catch(e){terr(e);return}
const s=APS.snap;
const st={ov:Object.assign({},cfg?cfg.settings:{}),label:cfg?cfg.label:'',delivery:cfg?cfg.delivery:'api',apis:cfg?cfg.apis.slice():[]};
let prof=F.profile;
const ctl={};          // key -> {box, input, kind}
const linkBox=el('textarea',{readonly:true,rows:4,dir:'ltr'});
const msg=el('div',{class:'muted sm'});
const lab=el('input',{maxlength:40,value:st.label,placeholder:account,autocomplete:'off'});
lab.addEventListener('input',()=>{st.label=lab.value;queue()});
const holder=(k)=>String(prof[k]===undefined||prof[k]===''||prof[k]===false?'':prof[k]);
const mkField=f=>{
const k=f.k;let inp,kind=f.t;
const hint=I18N[LANG]['ch_'+k]?t('ch_'+k):'';
if(k==='label')return null;
if(f.t==='bool'){
inp=sw(!!prof[k],v=>{st.ov[k]=v;queue()});
const box=el('div',{class:'f cfg-f cfg-sw'},el('div',{class:'kv'},el('span',{},t('cf_'+k)),inp),hint?el('small',{class:'muted'},hint):null);
ctl[k]={box,inp,kind,f};return box}
if(f.t==='select'){
inp=el('select',{dir:'ltr'},...f.opts.map(o=>el('option',{value:o},o===''?t('cd_auto'):o)));
inp.value=st.ov[k]!==undefined?st.ov[k]:(prof[k]===undefined?'':prof[k]);
inp.addEventListener('change',()=>{st.ov[k]=inp.value;queue()})}
else if(f.t==='area'){
inp=el('textarea',{rows:3,dir:'ltr',maxlength:f.mx||1500,placeholder:holder(k)});inp.value=st.ov[k]||'';
inp.addEventListener('input',()=>{if(inp.value==='')delete st.ov[k];else st.ov[k]=inp.value;queue()})}
else{
inp=el('input',{dir:'ltr',autocomplete:'off',maxlength:f.mx||253,placeholder:holder(k)||t('cd_auto')});if(f.t==='int'){inp.setAttribute('inputmode','numeric')}
inp.value=st.ov[k]!==undefined?st.ov[k]:'';
inp.addEventListener('input',()=>{const v=inp.value.trim();if(v==='')delete st.ov[k];else st.ov[k]=v;queue()})}
const box=el('label',{class:'f cfg-f'},el('span',{},t('cf_'+k)),inp,hint?el('small',{class:'muted'},hint):null);
ctl[k]={box,inp,kind,f};return box};
const lockF=F.fields.find(f=>f.k==='locked');
const secs={};
for(const g of GROUPS){secs[g]=el('div',{class:'cfg-g-b'})}
secs.id.append(field(t('cd_label'),lab,t('cd_label_hint')));
for(const f of F.fields){const b=mkField(f);if(b)secs[f.g].append(b)}
const grp=g=>{
if(!secs[g].children.length)return null;
const h=el('div',{class:'cfg-g-h'},t('g_'+g));
if(COLLAPSED[g]){secs[g].hidden=true;const tg=el('button',{class:'btn adv-t',type:'button','aria-expanded':'false'},ic('sliders'),el('span',{},t('g_'+g)),ic('chevron-down','adv-c'));
tg.addEventListener('click',()=>{secs[g].hidden=!secs[g].hidden;tg.classList.toggle('on',!secs[g].hidden);tg.setAttribute('aria-expanded',String(!secs[g].hidden))});
return el('div',{class:'cfg-g'},tg,secs[g])}
return el('div',{class:'cfg-g'},h,secs[g])};
const dlSeg=seg(DL_OPTS(),st.delivery,v=>{st.delivery=v;showApis()});
const apiBox=el('div',{class:'f'},el('span',{},t('cd_apis')),el('div',{class:'chips'}),el('small',{class:'muted'},t('cd_apis_hint')));
const showApis=()=>{
const on=(st.delivery==='api'||st.delivery==='both')&&s.keys.length>1;
apiBox.hidden=!on;
const c=apiBox.querySelector('.chips');
c.replaceChildren(...s.keys.map(k=>{const sel=st.apis.includes(k.id);return el('button',{type:'button',class:'chip'+(sel?' on':''),onclick:()=>{st.apis=st.apis.includes(k.id)?st.apis.filter(x=>x!==k.id):st.apis.concat(k.id);showApis()}},k.name||'API')}))};
const refresh=async()=>{
try{
const r=await api('POST','/api/apicfg/preview',{account,label:st.label,settings:st.ov});
prof=r.profile;linkBox.value=r.link;msg.textContent='';msg.classList.remove('bad');
for(const[k,c]of Object.entries(ctl)){
const f=c.f;let show=true;
if(f.when)for(const[wk,vals]of Object.entries(f.when)){if(!vals.includes(prof[wk]))show=false}
c.box.hidden=!show;
if(f.t==='bool'){if(st.ov[k]===undefined){c.inp.classList.toggle('on',!!prof[k]);c.inp.setAttribute('aria-checked',String(!!prof[k]))}}
else if(f.t==='select'){if(st.ov[k]===undefined)c.inp.value=prof[k]===undefined?'':prof[k]}
else if(!c.inp.matches(':focus')||c.inp.value===''){c.inp.placeholder=holder(k)||t('cd_auto')}}
}catch(e){msg.classList.add('bad');msg.textContent=(tx('e_'+e.message)!=='e_'+e.message?t('e_'+e.message):e.message)+(e.detail?': '+(I18N[LANG]['cf_'+e.detail]?t('cf_'+e.detail):e.detail):'')}};
let tm=null;const queue=()=>{clearTimeout(tm);tm=setTimeout(refresh,250)};
const resetAll=()=>{st.ov={};for(const[k,c]of Object.entries(ctl)){if(c.f.t==='bool'||c.f.t==='select'){}else c.inp.value=''}refresh()};
const form=el('div',{class:'form cfg-form'},
el('div',{class:'cfg-top'},el('span',{class:'pill'},F.type),el('span',{class:'muted sm ltr'},account)),
...GROUPS.map(grp),
el('div',{class:'f'},el('span',{},t('cd_delivery')),dlSeg),apiBox,
el('div',{class:'f'},el('div',{class:'item-h'},el('span',{},t('cd_link')),el('div',{class:'acts'},el('button',{class:'icon-btn',title:t('cd_copy'),onclick:()=>copy(linkBox.value)},ic('copy')))),linkBox),msg);
const d=modal(cfg?t('cd_edit'):t('cd_new',account),form,[
btn(t('cd_save'),'floppy-disk',async()=>{
try{
const b={account,label:st.label,delivery:st.delivery,apis:st.apis,settings:st.ov};
if(cfg)await apPost('/api/apicfg/configs/'+cfg.id,b,'PATCH');else await apPost('/api/apicfg/configs',b);
toast(t('done'));d.close();if(done)done()}catch(e){terr(e)}},'pri'),
btn(t('cd_reset'),'rotate-left',resetAll),
btn(t('cancel'),'xmark',()=>d.close())],'xl');
showApis();refresh()}
/* ---------- subscription switch of the account dialog ---------- */
async function subField(a){
let s;
try{s=await api('GET','/api/apicfg')}catch(e){return null}
if(!s.sub_on)return null;
let on=false,url='',n=0;
if(a){try{const r=await api('GET','/api/apicfg/sub/'+a.name);on=r.enabled;url=r.url;n=r.configs}catch(e){}}
const orig=on;
const note=el('small',{class:'muted'},t('sub_f_hint'));
const na=el('small',{class:'muted'},ic('circle-info'),' '+t('sub_f_na'));
const urlBox=el('div',{class:'inp-row'});
const sws=sw(on,v=>{on=v;paint()});
const paint=()=>{
if(on&&url){const i=el('input',{readonly:true,dir:'ltr',value:url});urlBox.replaceChildren(i,el('button',{type:'button',class:'icon-btn',title:t('copy'),onclick:()=>copy(url)},ic('copy')),el('button',{type:'button',class:'icon-btn',title:t('ap_regen'),onclick:()=>ask(t('ap_regen_confirm'),t('ap_regen'),async()=>{try{const r=await api('PUT','/api/apicfg/sub/'+a.name,{enabled:true,regen:true});url=r.url;paint()}catch(e){terr(e);return false}},{danger:false})},ic('rotate')));urlBox.hidden=false}
else{urlBox.replaceChildren();urlBox.hidden=true}};
const box=el('div',{class:'f'},el('span',{},t('sub_f')),el('div',{class:'kv'},el('span',{},t('sub_f_on')),sws),urlBox,note,a&&n?el('small',{class:'muted'},t('sub_f_cfgs',n)):null,na);
let okv=true;
const set=v=>{okv=!!v;box.hidden=false;sws.hidden=!okv;note.hidden=!okv;na.hidden=okv;urlBox.hidden=!okv||!(on&&url)};
paint();set(true);
return{el:box,set,save:async name=>{if(!okv||on===orig)return;try{await api('PUT','/api/apicfg/sub/'+name,{enabled:on})}catch(e){terr(e)}}}}
