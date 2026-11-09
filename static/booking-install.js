(() => {
 const box=document.getElementById('installBookingBox');
 if(!box)return;
 if(window.matchMedia('(display-mode: standalone)').matches || navigator.standalone || /; wv\)/.test(navigator.userAgent)){box.hidden=true;return;}
 if('serviceWorker' in navigator)navigator.serviceWorker.register('/agendamento-sw.js',{scope:'/agendar'}).catch(()=>{});
 const button=document.getElementById('installBooking');let pending;
 window.addEventListener('beforeinstallprompt',event=>{event.preventDefault();pending=event;button.hidden=false;});
 button.addEventListener('click',async()=>{if(!pending)return;await pending.prompt();await pending.userChoice;pending=null;button.hidden=true;});
 window.addEventListener('appinstalled',()=>{box.hidden=true;});
})();
