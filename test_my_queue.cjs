/* My Queue regression tests: execute the real inlined JS with Node, no browser dependencies. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('index.html', 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/);
assert.ok(script, 'inline script should exist');
assert.doesNotThrow(() => new vm.Script(script[1]), 'full app JavaScript should compile');

const core = script[1].split('// <core>')[1].split('// </core>')[0];
const timeline = script[1].split('function tlHtml(')[1].split('const MQ_ICONS =')[0];
const view = script[1].split('const MQ_ICONS =')[1].split('// ---------- summary table ----------')[0];
const api = vm.runInNewContext(core + '\n;({myQueueIntervals, myQueueForecast, computeLive, stats, nowKyiv, mqTime:undefined})', {});
const one = [[540, 780]];
const original = JSON.stringify(one);
const periods = api.myQueueIntervals(one);
assert.equal(JSON.stringify(periods[0].off), JSON.stringify([554, 558]));
assert.equal(JSON.stringify(periods[0].on), JSON.stringify([750, 760]));
assert.equal(JSON.stringify(one), original, 'forecast must not mutate official intervals');
for (const [minute, phase] of [
  [539, 'on'],[540,'on'],[553,'on'],[554,'transition-off'],[557,'transition-off'],
  [558,'off'],[749,'off'],[750,'transition-on'],[759,'transition-on'],
  [760,'on'],[779,'on'],[780,'on']
]) assert.equal(api.myQueueForecast(one, minute).phase, phase, 'phase at minute ' + minute);
assert.equal(api.myQueueForecast(one, 540).next.kind, 'off');
assert.equal(api.myQueueForecast(one, 558).next.kind, 'on');
assert.equal(api.myQueueForecast(one, 760).next, undefined);
const multi = api.myQueueForecast([[540,780],[960,1200]], 760);
assert.equal(multi.next.kind, 'off');
assert.equal(multi.next.window[0], 974);
const afterMidnight = api.myQueueForecast([[1410,1440],[1470,1620]], 1440);
assert.equal(afterMidnight.next.kind, 'off');
assert.equal(afterMidnight.next.window[0], 1484);
const short = api.myQueueForecast([[540,570]], 545);
assert.equal(short.intervals[0].adjusted, false);
assert.equal(short.phase, 'off');
assert.equal(JSON.stringify(api.stats(one)), JSON.stringify({off:240,on:1200,count:1,maxOn:660,maxOff:240}));

const mocks = String.raw`
const mySel={value:'1.1'};
const t={date:'03.11.2026',sec:540*60};
const dayMap = new Map([['03.11.2026',{date:'03.11.2026',time:'08:12',queues:new Map([['1.1',[[540,780]]]])}]]);
const state={dayMap};
const liveCard={innerHTML:'',querySelector(){return null;}};
nowKyiv=()=>t;
renderLive();
globalThis.rendered=liveCard.innerHTML;
globalThis.displayWindow=mqWindow([554,558]);
globalThis.dayModel=computeLive(dayMap,'1.1',t);
`;
const sandbox = {};
vm.runInNewContext(core + '\nfunction tlHtml(' + timeline + '\nconst MQ_ICONS =' + view + '\n' + mocks, sandbox);
assert.match(sandbox.rendered, /09:14–09:18/);
assert.match(sandbox.rendered, /12:30–12:40/);
assert.match(sandbox.rendered, /По официальному графику/);
assert.match(sandbox.rendered, /с учетом погрешности/);
assert.match(sandbox.rendered, /class="mq-hero/);
assert.equal(sandbox.dayModel.next.at, 780, 'official engine stays unchanged');
assert.equal(sandbox.dayModel.off, true, 'original scheduled status stays unchanged');
const cardFunction = script[1].slice(script[1].indexOf('function queueCard('), script[1].indexOf('function updateCards('));
const cardApi = vm.runInNewContext(core + '\nconst MQ_ICONS =' + view + '\n' + cardFunction +
  '\n;({card:(iv,minute)=>queueCard("1.1",iv,stats(iv),minute,true),mqScheduleSlots,myQueueForecast})', {});
assert.match(cardApi.card(one,540), /data-tone="off"/);
assert.match(cardApi.card(one,780), /data-tone="on"/);
assert.match(cardApi.card(one,null), /План на завтра/);
assert.match(cardApi.card([],0), /Отключений не запланировано/);
assert.match(cardApi.card(one,600), /09:00–13:00/);
const tomorrowSlots = cardApi.mqScheduleSlots(cardApi.myQueueForecast([[2820,2880]],500),1);
assert.match(tomorrowSlots, /23:00–24:00/);
assert.match(tomorrowSlots, /data-slot="2820-2880"/);
console.log('My Queue regression tests passed');
