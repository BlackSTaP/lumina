/* The visualizer must always reflect the official source, without My Queue offsets. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html=fs.readFileSync('index.html','utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const core=script.split('// <core>')[1].split('// </core>')[0];
const viz=script.split('// <viz-core>')[1].split('// </viz-core>')[0];
const api=vm.runInNewContext(core+'\n'+viz+'\n({buildModel,vizSlot,vizRows,vizHoursForWidth,vizCellLabel,myQueueForecast})');
const original='=== 04.11.2026 · 14:32 ===\n⚡ Черга 1.1\nз 09:00 до 13:00\nз 16:00 до 20:00\n⚡ Черга 1.2\nз 09:30 до 13:00';
const model=api.buildModel(original,false);
assert.equal(model.date,'04.11.2026');
assert.equal(model.time,'14:32');
assert.equal(JSON.stringify(model.rows[0].iv),'[[540,780],[960,1200]]');
assert.equal(api.vizSlot(model.rows[0].iv,17).off,0);
assert.equal(api.vizSlot(model.rows[0].iv,18).off,30);
assert.equal(api.vizSlot(model.rows[0].iv,25).off,30);
assert.equal(api.vizSlot(model.rows[0].iv,26).off,0);
assert.equal(api.vizSlot(model.rows[1].iv,18).off,0);
assert.equal(api.vizSlot(model.rows[1].iv,19).off,30);
assert.match(api.vizCellLabel(model.rows[0],18),/09:00–09:30/);
assert.equal(api.myQueueForecast(model.rows[0].iv,540).phase,'on','My Queue alone retains estimated switching times');
assert.equal(api.vizSlot(model.rows[0].iv,18).kind,'off','official grid already shows an outage at 09:00');
for(const day of JSON.parse(fs.readFileSync('schedule.json','utf8'))){
  const m=api.buildModel(Object.entries(day.queues).map(([q,r])=>q+': '+r).join('\n'),false);
  for(const row of m.rows){
    const total=Array.from({length:48},(_,slot)=>api.vizSlot(row.iv,slot).off).reduce((a,b)=>a+b,0);
    assert.equal(total,row.total,'all source minutes survive rendering for '+row.name);
  }
}
assert.equal(api.vizSlot([[1410,1440]],47).off,30);
assert.equal(api.vizSlot([[540,550],[560,570]],18).off,20,'disjoint source ranges in one cell');
assert.equal(api.vizSlot([[540,565],[550,570]],18).off,30,'overlaps are merged');
assert.equal(api.vizSlot([],0).off,0);
assert.equal(api.vizRows(model,'1.2','1.1').length,2,'mine survives comparison filter');
assert.equal(api.vizRows(model,'1.1','1.1').length,1,'mine is not duplicated');
assert.equal(api.vizRows(model,'1.2','9.9').length,1,'missing queue is not fabricated');
for(const [width,hours] of [[320,6],[390,6],[768,12],[1070,24],[1600,24]])assert.equal(api.vizHoursForWidth(width),hours);
// Exercise the actual SVG export, including exact official intervals and escaping.
const poster=script.slice(script.indexOf('function chartPoster('),script.indexOf('async function chartPng('));
const exportApi=vm.runInNewContext(core+'\n'+viz+'\nconst vizCity="";\n'+poster+'\n({chartPoster})');
const exported=exportApi.chartPoster(model,model.rows,{date:model.date,sec:540*60},'1.1');
assert.equal(exported.width,1600);
assert.match(exported.svg,/09:00–13:00/);
assert.match(exported.svg,/09:30–13:00/);
assert.doesNotMatch(exported.svg,/09:14|09:18|12:30–12:40/);
assert.match(exported.svg,/МОЯ ОЧЕРЕДЬ/);
assert.match(exported.svg,/stroke="white"/);
const future=exportApi.chartPoster(model,model.rows,{date:'03.11.2026',sec:540*60},'1.1');
assert.doesNotMatch(future.svg,/stroke="white"/,'only current date receives a now marker');
console.log('Visualizer tests passed: exact source times, half hours, filters, responsive grouping and PNG source');
