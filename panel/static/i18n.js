'use strict';
let LANG='ar';
try{LANG=localStorage.getItem('lang')||'ar'}catch(e){}
const I18N={
ar:{
app_title:'لوحة VPN',login_title:'تسجيل الدخول',login_user:'اسم المشرف',login_pass:'كلمة المرور',login_btn:'دخول',
nav_dashboard:'الرئيسية',nav_accounts:'الحسابات',nav_settings:'الإعدادات',logout:'خروج',
close:'إغلاق',copy:'نسخ',copied:'تم النسخ',copy_fail:'تعذر النسخ',done:'تم',deleted:'تم الحذف',save:'حفظ',create:'إنشاء',
unlimited:'مفتوح',ended:'منتهي',days_n:'{0} يوم',d_short:'{0} يوم',h_short:'{0} س',m_short:'{0} د',
d_cpu:'المعالج',d_ram:'الذاكرة',d_disk:'القرص',d_net:'الشبكة',d_cores:'{0} نواة',d_load:'الحمل',d_accounts:'الحسابات',d_active_n:'{0} نشط',d_online:'المتصلون الآن',d_online_sub:'إجمالي الأجهزة المتصلة',d_traffic:'إجمالي الاستهلاك',d_uptime:'مدة التشغيل',d_by_proto:'الحسابات حسب البروتوكول',d_top:'الأعلى استهلاكاً',d_expiring:'تنتهي قريباً (7 أيام)',d_services:'حالة الخدمات',d_none:'لا توجد بيانات',
a_search:'بحث بالاسم أو الملاحظة',a_all_protos:'كل البروتوكولات',a_all_status:'كل الحالات',a_add:'حساب جديد',a_empty:'لا توجد حسابات',a_info:'معلومات الحساب',a_edit:'تعديل',a_enable:'تفعيل',a_disable:'تعطيل',a_delete:'حذف',a_confirm_del:'حذف الحساب {0} نهائياً؟',a_new:'حساب جديد',a_edit_t:'تعديل {0}',
c_name:'الحساب',c_proto:'البروتوكول',c_status:'الحالة',c_devices:'الأجهزة',c_usage:'الاستهلاك',c_expiry:'الصلاحية',c_actions:'إجراءات',
st_active:'نشط',st_disabled:'معطّل',st_expired:'منتهي',st_limit:'تجاوز الحد',
f_type:'نوع الحساب',f_proto:'البروتوكول',f_tls:'وضع الاتصال',f_tls_hint:'TLS عبر المنفذ 443، وبدون TLS عبر المنفذ 80',tls_tls:'TLS',tls_plain:'بدون TLS',tls_both:'الاثنان',f_ssh_hint:'حساب SSH يعمل على المنفذ 80 (بدون TLS) والمنفذ 443 (مع TLS)',f_name:'اسم المستخدم',f_password:'كلمة المرور',f_uuid:'UUID',f_auto:'تلقائي',f_keep:'اتركه فارغاً بدون تغيير',f_gen:'توليد',f_days:'الصلاحية بالأيام',f_quota:'حد الترافيك GB',f_devices:'حد الأجهزة المتصلة',f_devices_hint:'0 = بدون حد. يُحسب SSH بعدد الجلسات، وV2Ray بعدد عناوين IP المختلفة',f_note:'ملاحظة',regen:'سر جديد',regen_done:'تم توليد سر جديد',reset_traffic:'تصفير الترافيك',reset_done:'تم تصفير الترافيك',
i_title:'معلومات {0}',i_connected:'المتصلون',
l_ssh_tls:'SSH WS + TLS (443)',l_ssh_plain:'SSH WS بدون TLS (80)',l_payload:'Payload',l_user:'المستخدم',l_pass:'كلمة المرور',l_uuid:'UUID',l_link_tls:'رابط TLS (443)',l_link_plain:'رابط بدون TLS (80)',
s_appearance:'المظهر واللغة',s_theme:'الثيم',theme_dark:'مظلم',theme_light:'مشرق',s_language:'اللغة',s_security:'الأمان',s_cur:'كلمة المرور الحالية',s_new:'كلمة المرور الجديدة',s_new_hint:'10 أحرف على الأقل',s_confirm:'تأكيد كلمة المرور',s_change:'تغيير كلمة المرور',s_mismatch:'كلمتا المرور غير متطابقتين',s_changed:'تم تغيير كلمة المرور',s_about:'عن اللوحة',s_version:'الإصدار',s_domain:'الدومين',s_update_hint:'للتحديث إلى آخر إصدار اكتب isile في الطرفية واختر 4',
e_unauthorized:'انتهت الجلسة',e_csrf:'جلسة غير صالحة، حدّث الصفحة',e_bad_proto:'بروتوكول غير صالح',e_bad_name:'الاسم: أحرف إنجليزية صغيرة وأرقام و _ بطول 3-20 ويبدأ بحرف',e_bad_values:'قيم غير صالحة',e_bad_uuid:'UUID غير صالح',e_bad_secret:'كلمة المرور: 6-64 حرفاً من A-Za-z0-9@#%_.+=-',e_name_taken:'الاسم مستخدم',e_name_reserved:'الاسم محجوز في النظام',e_not_found:'غير موجود',e_wrong_password:'كلمة المرور الحالية غير صحيحة',e_short_password:'كلمة المرور الجديدة: 10 أحرف على الأقل',e_system:'خطأ في النظام',e_too_many:'محاولات كثيرة، حاول لاحقاً',e_session_expired:'انتهت الجلسة، أعد المحاولة',e_bad_login:'بيانات الدخول غير صحيحة'
},
en:{
app_title:'VPN Panel',login_title:'Sign in',login_user:'Admin username',login_pass:'Password',login_btn:'Sign in',
nav_dashboard:'Dashboard',nav_accounts:'Accounts',nav_settings:'Settings',logout:'Logout',
close:'Close',copy:'Copy',copied:'Copied',copy_fail:'Copy failed',done:'Done',deleted:'Deleted',save:'Save',create:'Create',
unlimited:'Unlimited',ended:'Ended',days_n:'{0} days',d_short:'{0}d',h_short:'{0}h',m_short:'{0}m',
d_cpu:'CPU',d_ram:'Memory',d_disk:'Disk',d_net:'Network',d_cores:'{0} cores',d_load:'Load',d_accounts:'Accounts',d_active_n:'{0} active',d_online:'Online now',d_online_sub:'Total connected devices',d_traffic:'Total traffic',d_uptime:'Uptime',d_by_proto:'Accounts by protocol',d_top:'Top consumers',d_expiring:'Expiring soon (7 days)',d_services:'Services',d_none:'No data',
a_search:'Search by name or note',a_all_protos:'All protocols',a_all_status:'All statuses',a_add:'New account',a_empty:'No accounts',a_info:'Account info',a_edit:'Edit',a_enable:'Enable',a_disable:'Disable',a_delete:'Delete',a_confirm_del:'Delete account {0} permanently?',a_new:'New account',a_edit_t:'Edit {0}',
c_name:'Account',c_proto:'Protocol',c_status:'Status',c_devices:'Devices',c_usage:'Usage',c_expiry:'Expiry',c_actions:'Actions',
st_active:'Active',st_disabled:'Disabled',st_expired:'Expired',st_limit:'Over limit',
f_type:'Account type',f_proto:'Protocol',f_tls:'Connection mode',f_tls_hint:'TLS on port 443, no TLS on port 80',tls_tls:'TLS',tls_plain:'No TLS',tls_both:'Both',f_ssh_hint:'SSH accounts work on port 80 (no TLS) and port 443 (TLS)',f_name:'Username',f_password:'Password',f_uuid:'UUID',f_auto:'Automatic',f_keep:'Leave empty to keep',f_gen:'Generate',f_days:'Validity in days',f_quota:'Traffic limit GB',f_devices:'Concurrent devices limit',f_devices_hint:'0 = unlimited. SSH counts sessions, V2Ray counts distinct IP addresses',f_note:'Note',regen:'New secret',regen_done:'New secret generated',reset_traffic:'Reset traffic',reset_done:'Traffic reset',
i_title:'{0} info',i_connected:'Connected',
l_ssh_tls:'SSH WS + TLS (443)',l_ssh_plain:'SSH WS no TLS (80)',l_payload:'Payload',l_user:'Username',l_pass:'Password',l_uuid:'UUID',l_link_tls:'TLS link (443)',l_link_plain:'Non-TLS link (80)',
s_appearance:'Appearance & language',s_theme:'Theme',theme_dark:'Dark',theme_light:'Light',s_language:'Language',s_security:'Security',s_cur:'Current password',s_new:'New password',s_new_hint:'At least 10 characters',s_confirm:'Confirm password',s_change:'Change password',s_mismatch:'Passwords do not match',s_changed:'Password changed',s_about:'About',s_version:'Version',s_domain:'Domain',s_update_hint:'To update to the latest version run isile in the terminal and choose 4',
e_unauthorized:'Session expired',e_csrf:'Invalid session, reload the page',e_bad_proto:'Invalid protocol',e_bad_name:'Name: 3-20 lowercase letters, digits or _, starting with a letter',e_bad_values:'Invalid values',e_bad_uuid:'Invalid UUID',e_bad_secret:'Password: 6-64 chars of A-Za-z0-9@#%_.+=-',e_name_taken:'Name already in use',e_name_reserved:'Name is reserved by the system',e_not_found:'Not found',e_wrong_password:'Current password is incorrect',e_short_password:'New password must be at least 10 characters',e_system:'System error',e_too_many:'Too many attempts, try later',e_session_expired:'Session expired, try again',e_bad_login:'Invalid credentials'
}};
const tx=k=>(I18N[LANG]&&I18N[LANG][k])||k;
const t=(k,...a)=>tx(k).replace(/\{(\d+)\}/g,(m,i)=>a[i]);
