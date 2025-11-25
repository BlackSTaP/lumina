'use client';

import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, ZapOff, Clock, Calendar, Edit3, Save, RotateCcw, Plus, Trash2 } from 'lucide-react';

// --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
const parseScheduleText = (text) => {
  const schedule = Array(24).fill('on'); 
  const lines = text.split('\n');
  const timeRe = /(\d{1,2})(?::\d{2})?\s*[-–—]\s*(\d{1,2})(?::\d{2})?/g;
  
  lines.forEach(line => {
    let match;
    while ((match = timeRe.exec(line)) !== null) {
        let startH = parseInt(match[1]);
        let endH = parseInt(match[2]);
        if (startH >= 24) startH = 0;
        if (endH > 24) endH = 0;
        if (endH === 0 && startH !== 0) endH = 24;
        for (let i = startH; i < endH; i++) {
            if (i < 24) schedule[i] = 'off';
        }
    }
  });
  return schedule;
};

export default function LuminaApp() {
  const [mounted, setMounted] = useState(false);
  const [mode, setMode] = useState('view'); 
  const [currentTime, setCurrentTime] = useState(new Date());
  
  const [groups, setGroups] = useState([{ id: 1, name: "Мой График", schedule: Array(24).fill('on') }]);
  const [activeGroupId, setActiveGroupId] = useState(1);
  const [inputText, setInputText] = useState("");

  const activeGroup = groups.find(g => g.id === activeGroupId) || groups[0];

  useEffect(() => {
    setMounted(true);
    const savedGroups = localStorage.getItem('lumina_groups');
    if (savedGroups) setGroups(JSON.parse(savedGroups));
    const timer = setInterval(() => setCurrentTime(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (mounted) localStorage.setItem('lumina_groups', JSON.stringify(groups));
  }, [groups, mounted]);

  const toggleHour = (hourIndex) => {
    if (mode !== 'edit') return;
    const updatedGroups = groups.map(g => {
      if (g.id === activeGroupId) {
        const newSched = [...g.schedule];
        if (newSched[hourIndex] === 'on') newSched[hourIndex] = 'off';
        else if (newSched[hourIndex] === 'off') newSched[hourIndex] = 'maybe';
        else newSched[hourIndex] = 'on';
        return { ...g, schedule: newSched };
      }
      return g;
    });
    setGroups(updatedGroups);
  };

  const applyTextSchedule = () => {
    const parsedSchedule = parseScheduleText(inputText);
    const updatedGroups = groups.map(g => {
      if (g.id === activeGroupId) return { ...g, schedule: parsedSchedule };
      return g;
    });
    setGroups(updatedGroups);
    setInputText("");
  };

  if (!mounted) return null;

  const currentHour = currentTime.getHours();
  const currentStatus = activeGroup.schedule[currentHour];

  let hoursUntilChange = 0;
  let nextStatus = currentStatus;
  for (let i = 1; i < 24; i++) {
      const checkHour = (currentHour + i) % 24;
      if (activeGroup.schedule[checkHour] !== currentStatus) {
          hoursUntilChange = i;
          nextStatus = activeGroup.schedule[checkHour];
          break;
      }
  }

  const minutesLeftInHour = 60 - currentTime.getMinutes();
  const totalMinutesLeft = (hoursUntilChange - 1) * 60 + minutesLeftInHour;
  const hoursLeftDisplay = Math.floor(totalMinutesLeft / 60);
  const minutesLeftDisplay = totalMinutesLeft % 60;

  return (
    <div className="min-h-screen bg-background text-slate-100 font-sans pb-20 overflow-hidden">
      <div className="max-w-md mx-auto min-h-screen flex flex-col relative">
        <div className={`absolute top-[-10%] left-[-10%] w-[300px] h-[300px] rounded-full blur-[120px] opacity-20 transition-colors duration-1000 ${currentStatus === 'on' ? 'bg-primary' : currentStatus === 'maybe' ? 'bg-warning' : 'bg-danger'}`} />
        
        <header className="flex justify-between items-center p-6 z-10">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 bg-surface/50 rounded-xl flex items-center justify-center border border-white/10 backdrop-blur-md">
               <Zap size={20} className={currentStatus === 'on' ? "text-primary" : "text-slate-400"} />
            </div>
            <div>
              <h1 className="font-bold text-xl leading-none">Lumina</h1>
              <span className="text-[10px] text-slate-400 uppercase tracking-widest">Energy Monitor</span>
            </div>
          </div>
          <button onClick={() => setMode(mode === 'view' ? 'edit' : 'view')} className={`p-3 rounded-full transition-all border backdrop-blur-sm ${mode === 'edit' ? 'bg-primary text-slate-900 border-primary' : 'bg-surface/50 text-slate-400 border-white/10'}`}>
            {mode === 'view' ? <Edit3 size={20}/> : <Save size={20}/>}
          </button>
        </header>

        <main className="flex-1 px-5 z-10 flex flex-col gap-5">
          <div className="flex gap-2 overflow-x-auto pb-2 no-scrollbar">
            {groups.map(g => (
              <button key={g.id} onClick={() => setActiveGroupId(g.id)} className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-all border ${activeGroupId === g.id ? 'bg-white text-slate-900 border-white' : 'bg-surface/40 text-slate-400 border-white/5'}`}>
                {g.name}
              </button>
            ))}
            {mode === 'edit' && (
               <button onClick={() => { setGroups([...groups, { id: Date.now(), name: `Гр. ${groups.length + 1}`, schedule: Array(24).fill('on') }]); }} className="px-3 py-2 rounded-full bg-surface/40 border border-white/5 text-slate-400 hover:text-primary">
                 <Plus size={16} />
               </button>
            )}
          </div>

          <motion.div layout className={`rounded-[2rem] p-6 border transition-all duration-700 relative overflow-hidden ${currentStatus === 'on' ? 'bg-emerald-900/30 border-primary/30' : currentStatus === 'maybe' ? 'bg-yellow-900/30 border-warning/30' : 'bg-rose-900/30 border-danger/30'}`}>
             <div className="relative z-10">
               <div className="flex justify-between items-start mb-6">
                 <div>
                   <h2 className={`text-3xl font-black tracking-tighter ${currentStatus === 'on' ? 'text-primary' : currentStatus === 'maybe' ? 'text-warning' : 'text-danger'}`}>
                      {currentStatus === 'on' ? 'СВЕТ ЕСТЬ' : currentStatus === 'maybe' ? 'ВОЗМОЖНО' : 'СВЕТА НЕТ'}
                   </h2>
                 </div>
                 <div className="text-right">
                    <span className="block text-3xl font-mono font-bold text-white">{currentTime.toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}</span>
                 </div>
               </div>
               <div className="bg-slate-900/50 rounded-2xl p-4 flex items-center gap-4 border border-white/5 backdrop-blur-md">
                 <div className={`p-3 rounded-xl ${currentStatus === 'on' ? 'bg-primary/10 text-primary' : 'bg-surface text-slate-400'}`}><Clock size={24} /></div>
                 <div className="flex flex-col">
                    <span className="text-xs text-slate-400 font-medium uppercase">{nextStatus === 'off' ? 'Отключение через' : 'Включение через'}</span>
                    <div className="flex items-baseline gap-1"><span className="text-2xl font-bold text-white">{hoursLeftDisplay}</span><span className="text-sm text-slate-400">ч</span><span className="text-2xl font-bold text-white">{minutesLeftDisplay}</span><span className="text-sm text-slate-400">мин</span></div>
                 </div>
               </div>
            </div>
          </motion.div>

          <AnimatePresence>
            {mode === 'edit' && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                 <div className="bg-surface/50 rounded-2xl p-5 border border-white/10 backdrop-blur-sm">
                    <div className="flex justify-between mb-3"><label className="text-sm font-semibold">Быстрая настройка</label>{groups.length > 1 && (<button onClick={() => { setGroups(groups.filter(g => g.id !== activeGroupId)); setActiveGroupId(groups[0].id); }} className="text-xs text-danger flex items-center gap-1"><Trash2 size={12}/> Удалить</button>)}</div>
                    <textarea className="w-full bg-slate-900/80 text-slate-200 p-3 rounded-xl border border-white/10 outline-none text-sm font-mono" rows={2} placeholder="Пример: 00-04, 12-16..." value={inputText} onChange={(e) => setInputText(e.target.value)} />
                    <div className="flex gap-2 mt-3">
                      <button onClick={applyTextSchedule} className="flex-1 bg-primary text-slate-900 font-bold py-2 rounded-xl text-sm flex items-center justify-center gap-2"><Save size={16}/> Применить</button>
                      <button onClick={() => { setGroups(groups.map(g => g.id === activeGroupId ? {...g, schedule: Array(24).fill('on')} : g)); }} className="px-4 bg-surface text-slate-300 rounded-xl border border-white/5"><RotateCcw size={18}/></button>
                    </div>
                 </div>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="bg-surface/30 rounded-[2rem] p-6 border border-white/5 backdrop-blur-sm mb-10">
             <div className="flex justify-between items-end mb-6">
                <h3 className="font-bold text-slate-200 flex items-center gap-2 text-lg"><Calendar size={20} className="text-primary"/> График</h3>
                <div className="flex gap-2 text-[10px] font-bold uppercase"><div className="flex items-center gap-1 text-slate-300"><div className="w-2 h-2 rounded-full bg-primary"></div>Есть</div><div className="flex items-center gap-1 text-slate-300"><div className="w-2 h-2 rounded-full bg-danger"></div>Нет</div></div>
             </div>
             <div className="grid grid-cols-4 sm:grid-cols-6 gap-2">
                {activeGroup.schedule.map((status, hour) => {
                   let bgClass = "bg-surface/50 text-slate-500 border-white/5";
                   if (status === 'on') bgClass = "bg-emerald-500/10 text-primary border-emerald-500/20";
                   if (status === 'off') bgClass = "bg-rose-500/10 text-danger border-rose-500/20 grayscale-[0.3]";
                   if (status === 'maybe') bgClass = "bg-yellow-500/10 text-warning border-yellow-500/20";
                   return (
                     <motion.button key={hour} onClick={() => toggleHour(hour)} disabled={mode !== 'edit'} className={`relative aspect-[1.2/1] rounded-2xl flex flex-col items-center justify-center border transition-all ${bgClass} ${hour === currentHour ? 'ring-2 ring-white z-10' : ''}`}>
                        <span className="text-sm font-bold z-10">{hour}:00</span>
                        <div className="absolute inset-0 flex items-center justify-center opacity-20 z-0">{status === 'on' && <Zap size={24} />}{status === 'off' && <ZapOff size={24} />}</div>
                     </motion.button>
                   )
                })}
             </div>
          </div>
        </main>
      </div>
    </div>
  );
}