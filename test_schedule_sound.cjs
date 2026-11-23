const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');

// Exercise the polling, schedule import and audio paths from the page.
const script = readFileSync('index.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const core = script.split('// <core>')[1].split('// </core>')[0];
const audio = script.slice(script.indexOf('let actx ='),script.indexOf('let titleTimer'));
const polling = script.slice(script.indexOf('function processJsonData('),script.indexOf("$('#importJsonBtn').addEventListener"));
const soundToggle = script.slice(script.indexOf("soundCheck.addEventListener('change'"),script.indexOf('function renderVersions('));

async function run() {
  const store = new Map(), listeners = new Map(), soundCheck = {checked:true,addEventListener(k,f){listeners.set('sound:'+k,f);}};
  let notes = 0, requests = 0, permitted = false, context, response, hold;
  class AudioContext {
    constructor(){context=this; this.state='suspended'; this.currentTime=0;}
    async resume(){if (!permitted) throw Error('gesture required'); this.state='running'; this.onstatechange();}
    createOscillator(){return {frequency:{},connect(){},start(){notes++;},stop(){}};}
    createGain(){return {gain:{setValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){}};}
  }
  const noop = () => {};
  const node = () => ({value:'',classList:{toggle:noop},addEventListener:noop});
  const env = {store,soundCheck,window:{AudioContext},document:{addEventListener:(k,f)=>listeners.set(k,f)},$:node,
    oldInput:node(),newInput:node(),vizInput:node(),mySel:node(),updateStatus:node(),state:{days:[]},notifyOn:{checked:false},
    autosize:noop,rebuildDayMap:noop,renderVersions:noop,renderTables:noop,renderLive:noop,setStatus:noop,
    renderCompare:noop,toast:noop,flashTitle:noop,location:{protocol:'https:'},
    fetch:async()=>{requests++; if (hold) await hold; return {ok:true,json:async()=>structuredClone(response)};}};
  const api = vm.runInNewContext(core+'\n'+audio+'\n'+soundToggle+'\n'+polling+
    "\nnowKyiv=()=>({date:'23.11.2026'}); ({checkForUpdates,processJsonData,playSound})",env);
  const today={date:'23.11.2026',published_at:'2026-11-23T09:00:00+02:00',queues:{'1.1':'09:00 - 13:00'}};
  const tomorrow={...today,date:'24.11.2026'};
  response=[tomorrow,today];
  await api.checkForUpdates();
  assert.equal(notes,0,'quiet first download');
  response=[tomorrow,{...today,queues:{'1.1':'10:00 - 13:00'}}];
  store.set('last_raw_json',JSON.stringify(response)); // A different tab has already updated the shared cache.
  await api.checkForUpdates();
  assert.equal(notes,0,'audio is blocked');
  permitted=true;
  listeners.get('click')();
  await Promise.resolve();
  assert.equal(notes,4,'one delayed chime for today while tomorrow is already published');
  listeners.get('touchend')();
  await api.checkForUpdates();
  assert.equal(notes,4,'same gesture or repeated response does not replay the event');
  response.reverse();
  response[0].versions=[{published_at:today.published_at,queues:today.queues}];
  await api.checkForUpdates();
  assert.equal(notes,4,'history/order changes are quiet');
  api.processJsonData([today]);
  assert.equal(notes,4,'manual import is quiet');
  store.set('new','');
  context.state='interrupted';
  response[1]={...tomorrow,published_at:'2026-11-23T13:30:00+02:00'};
  let release;
  hold=new Promise(resolve=>{release=resolve;});
  const before=requests, first=api.checkForUpdates();
  await api.checkForUpdates();
  release(); await first; hold=null;
  assert.equal(requests,before+1,'overlapping polls share a single fetch');
  assert.equal(notes,8,'a tomorrow update resumes an interrupted context');
  response[1].published_at='2026-11-23T13:30:23+02:00';
  context.state='suspended'; permitted=false;
  await api.checkForUpdates();
  soundCheck.checked=false; listeners.get('sound:change')();
  permitted=true; listeners.get('click')();
  soundCheck.checked=true; listeners.get('sound:change')();
  assert.equal(notes,8,'muting clears a pending sound');
  soundCheck.checked=false;
  response[0]=today;
  await api.checkForUpdates();
  assert.equal(notes,8,'disabled sound is respected');
  assert.equal(await api.playSound(true),true);
  assert.equal(notes,12,'explicit sound test still works when automatic sounds are muted');
  console.log('Schedule update sound tests passed');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
