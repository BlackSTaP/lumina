/* Progressive enhancements for the schedule, outside the city illustration. */
const motionPreference = matchMedia('(prefers-reduced-motion: reduce)');
let scheduleAnimation;
function animateScheduleChange() {
  const cards = document.querySelector('#queueCards');
  const target = cards.hidden ? document.querySelector('#queueTableView') : cards;
  scheduleAnimation?.cancel();
  if (!motionPreference.matches && target.animate) {
    scheduleAnimation = target.animate([{opacity:.25,transform:'translateY(7px)'},{opacity:1,transform:'translateY(0)'}],{duration:220,easing:'ease-out'});
  }
}

// Keep native details semantics; only intercept the summary's activation.
const disclosureAnimations = new Map();
document.addEventListener('click', event => {
  const summary = event.target.closest('#queueCards summary, #resultArea summary, #liveCard .mq-slot summary');
  if (!summary || event.target.closest('button,a,input,[data-timeline]')) return;
  const detail = summary.parentElement;
  if (motionPreference.matches || !detail.animate) return;
  event.preventDefault();
  const previous = disclosureAnimations.get(detail);
  const opening = previous ? !previous.opening : !detail.open;
  const start = detail.getBoundingClientRect().height;
  previous?.animation.cancel();
  detail.style.height = ''; detail.style.overflow = 'hidden';
  detail.open = true;
  const full = detail.getBoundingClientRect().height;
  const style = getComputedStyle(detail);
  const closed = summary.getBoundingClientRect().height + parseFloat(style.paddingTop) + parseFloat(style.paddingBottom) + parseFloat(style.borderTopWidth) + parseFloat(style.borderBottomWidth);
  const animation = detail.animate([{height:start+'px'},{height:(opening ? full : closed)+'px'}],{duration:240,easing:'cubic-bezier(.2,.7,.2,1)'});
  disclosureAnimations.set(detail,{animation,opening});
  animation.onfinish = () => {
    detail.open = opening; detail.style.overflow = ''; disclosureAnimations.delete(detail);
  };
});
motionPreference.addEventListener('change', () => {
  scheduleAnimation?.cancel();
  for (const [detail,{animation,opening}] of disclosureAnimations) {
    animation.cancel(); detail.open=opening; detail.style.overflow='';
  }
  disclosureAnimations.clear();
});

// One tooltip for all tracks, including the modal's horizontally scrolling grid.
const scheduleTip = document.createElement('div');
scheduleTip.id = 'schedule-tip'; scheduleTip.className = 'schedule-tip';
scheduleTip.setAttribute('role','tooltip'); scheduleTip.setAttribute('popover','manual');
scheduleTip.hidden = true; document.body.append(scheduleTip);
let tipTarget = null, tipIndex = 0;
function hideScheduleTip() {
  tipTarget?.removeAttribute('aria-describedby'); tipTarget=null;
  if (scheduleTip.hidePopover && scheduleTip.matches(':popover-open')) scheduleTip.hidePopover();
  scheduleTip.hidden=true;
}
function showScheduleTip(target, index, clientX) {
  const segments = JSON.parse(target.dataset.timeline);
  if (!segments.length) return;
  if (tipTarget !== target) tipTarget?.removeAttribute('aria-describedby');
  tipTarget=target; tipIndex=Math.max(0,Math.min(index,segments.length-1));
  const [start,end,label] = segments[tipIndex];
  scheduleTip.textContent = `${label}\n${fmt(start)}–${fmt(end)} · ${hmFull(end-start)}`;
  target.setAttribute('aria-describedby',scheduleTip.id);
  scheduleTip.hidden=false;
  // A popover remains visible above a modal dialog. Fall back inside the dialog.
  if (scheduleTip.showPopover) { if (!scheduleTip.matches(':popover-open')) scheduleTip.showPopover(); }
  else (target.closest('dialog') || document.body).append(scheduleTip);
  const box=target.getBoundingClientRect(), tip=scheduleTip.getBoundingClientRect();
  const x=clientX ?? box.left+box.width/2;
  scheduleTip.style.left=Math.max(12,Math.min(x-tip.width/2,innerWidth-tip.width-12))+'px';
  const top=box.top-tip.height-10;
  scheduleTip.style.top=Math.max(8,Math.min(top>=8 ? top : box.bottom+10,innerHeight-tip.height-8))+'px';
}
function showPointerInterval(event, target) {
  const rect=target.getBoundingClientRect(), parts=JSON.parse(target.dataset.timeline);
  const start=Number(target.dataset.start || 0), end=Number(target.dataset.end || 1440);
  const minute=start+Math.max(0,Math.min(.999999,(event.clientX-rect.left)/rect.width))*(end-start);
  const index=parts.findIndex(([a,b]) => a<=minute && minute<b);
  if (index>=0) showScheduleTip(target,index,event.clientX);
}
document.addEventListener('pointermove', event => {
  if (event.pointerType !== 'mouse') return;
  const target=event.target.closest('[data-timeline]');
  if (target) showPointerInterval(event,target);
  else if (tipTarget && tipTarget !== document.activeElement) hideScheduleTip();
});
document.addEventListener('pointerdown', event => {
  const target=event.target.closest('[data-timeline]');
  if (target) showPointerInterval(event,target); else hideScheduleTip();
});
document.addEventListener('focusin', event => {
  const target=event.target.closest('[data-timeline]');
  if (target) { if (tipTarget !== target) showScheduleTip(target,0); } else hideScheduleTip();
});
document.addEventListener('keydown', event => {
  if (event.key==='Escape') { hideScheduleTip(); return; }
  const target=event.target.closest('[data-timeline]');
  if (!target || !['ArrowLeft','ArrowRight','Home','End','Enter',' '].includes(event.key)) return;
  event.preventDefault();
  const last=JSON.parse(target.dataset.timeline).length-1;
  const current=tipTarget===target ? tipIndex : 0;
  const index=event.key==='Home' ? 0 : event.key==='End' ? last : current+(event.key==='ArrowRight' ? 1 : event.key==='ArrowLeft' ? -1 : 0);
  showScheduleTip(target,index);
});
document.addEventListener('scroll',() => {
  if (tipTarget && tipTarget === document.activeElement) {
    const box=tipTarget.getBoundingClientRect();
    if (box.bottom>0 && box.top<innerHeight) { showScheduleTip(tipTarget,tipIndex); return; }
  }
  hideScheduleTip();
},true);
window.addEventListener('resize',hideScheduleTip);
document.addEventListener('pointerleave',hideScheduleTip);
document.querySelector('#chartModal').addEventListener('close',hideScheduleTip);
// Re-rendering removes tracks; never leave an orphaned tooltip on screen.
const trackObserver = new MutationObserver(() => { if (tipTarget && !tipTarget.isConnected) hideScheduleTip(); });
trackObserver.observe(document.querySelector('.container'),{childList:true,subtree:true});
trackObserver.observe(document.querySelector('#chartHost'),{childList:true,subtree:true});
document.querySelector('.tabs').addEventListener('keydown', event => {
  if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
  const buttons=[...document.querySelectorAll('.tabs button')], current=buttons.indexOf(event.target);
  if (current<0) return;
  event.preventDefault();
  const index=event.key==='Home' ? 0 : event.key==='End' ? buttons.length-1 : (current+(event.key==='ArrowRight' ? 1 : -1)+buttons.length)%buttons.length;
  buttons[index].click(); buttons[index].focus();
});
