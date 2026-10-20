'use strict';
document.querySelectorAll('[data-i18n]').forEach(e=>{e.textContent=t(e.dataset.i18n)});
document.title=t('login_title');
const eb=document.querySelector('[data-err]');
if(eb){const c=eb.dataset.err;if(c){eb.textContent=t('e_'+c);eb.hidden=false}}
