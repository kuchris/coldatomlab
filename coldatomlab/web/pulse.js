"use strict";
(() => {
  const arms = ["no_echo", "ideal", "short", "nominal", "long"];
  const convention = "fixed-N; H/h=-J(aL†aR+aR†aL)+U m^2-bias m; equal total time; centered rectangular pulse; tau_pi=1/(4J) seconds; ideal S global phase omitted, finite pulse phase retained";
  const defaults = { ...Echo.defaults, base: { ...Echo.defaults.base }, preparations: 32, pulse_j_hz: 10, duration_error: 0.2 };
  function ensemble(plan) { const { pulse_j_hz, duration_error, ...p } = plan; return p; }
  function validate(input) {
    const p = { ...Echo.validate(ensemble(input)), pulse_j_hz: input.pulse_j_hz, duration_error: input.duration_error };
    for (const [key, lo, hi] of [["pulse_j_hz", .5, 20], ["duration_error", 0, .5]])
      if (!Number.isFinite(p[key]) || p[key] < lo || p[key] > hi) throw new Error(`${key} must be between ${lo} and ${hi}.`);
    if (250 / p.pulse_j_hz * (1 + p.duration_error) >= p.base.duration_ms)
      throw new Error("The longest pulse must be shorter than the total duration. Increase total time or pulse J.");
    return p;
  }
  function windows(p) {
    const T = p.base.duration_ms, nominal = 250 / p.pulse_j_hz;
    return Object.fromEntries([["short", 1-p.duration_error], ["nominal", 1], ["long", 1+p.duration_error]].map(([arm, ratio]) => {
      const width_ms = nominal * ratio;
      return [arm, { width_ms, ratio, start_ms: (T-width_ms)/2, end_ms: (T+width_ms)/2 }];
    }));
  }
  function checkpoints(p) {
    const events = [p.base.duration_ms/2, ...Object.values(windows(p)).flatMap(w=>[w.start_ms,w.end_ms])];
    const times = [];
    const pulseTimes = Object.values(windows(p)).flatMap(w=>Array.from({length:21},(_,i)=>w.start_ms+w.width_ms*i/20));
    for (const t of [...events, ...pulseTimes, ...Array.from({length:101},(_,i)=>p.base.duration_ms*i/100)])
      if (!times.some(x=>Math.abs(x-t)<1e-9)) times.push(t);
    return times.sort((a,b)=>a-b).flatMap(time_ms => events.some(x=>Math.abs(x-time_ms)<1e-9)
      ? [{time_ms, side:"before"},{time_ms, side:"after"}] : [{time_ms, side:"after"}]);
  }
  const components = state => ({ r: Float64Array.from(state.real), im: Float64Array.from(state.imag) });
  function fidelity(a,b) {
    let re=0, im=0;
    for(let k=0;k<a.real.length;k++){re+=a.real[k]*b.real[k]+a.imag[k]*b.imag[k];im+=a.real[k]*b.imag[k]-a.imag[k]*b.real[k];}
    return re*re+im*im;
  }
  function evolve(p, recipe) {
    const c=TwoMode.validate(recipe.config), initial=TwoMode.initial(c), T=c.duration_ms, win=windows(p);
    if(c.tunnelling_hz!==0) throw new Error("Hold J must be zero.");
    const swapped=Echo.swap(Echo.propagate(c,initial,T/2)), pulses={};
    const record={...recipe, arms:{}, boundaries:{}};
    for(const arm of ["short","nominal","long"]){
      const w=win[arm], pc={...c,tunnelling_hz:p.pulse_j_hz};
      const incoming=Echo.propagate(c,initial,w.start_ms), solver=new TwoMode.Solver(pc,incoming), outgoing=components(solver.at(w.width_ms));
      pulses[arm]={solver,outgoing,pc};
      record.boundaries[arm]={
        before_on:Echo.observe(c,incoming,w.start_ms), after_on:Echo.observe(pc,incoming,w.start_ms),
        before_off:Echo.observe(pc,outgoing,w.end_ms), after_off:Echo.observe(c,outgoing,w.end_ms),
      };
    }
    for(const arm of arms) record.arms[arm]={history:[]};
    for(const point of checkpoints(p)) for(const arm of arms){
      const t=point.time_ms, after=point.side==="after";
      let state, active_j_hz=0, stage=0;
      if(arm==="no_echo") state=Echo.observe(c,Echo.propagate(c,initial,t),t);
      else if(arm==="ideal"){
        const applied=t>T/2+1e-9 || (Math.abs(t-T/2)<1e-9 && after);stage=applied?2:0;
        state=Echo.observe(c,Echo.propagate(c,applied?swapped:initial,applied?Math.max(0,t-T/2):t),t);
      }else{
        const w=win[arm], pulse=pulses[arm];
        if(t<w.start_ms-1e-9 || (Math.abs(t-w.start_ms)<1e-9 && !after))
          state=Echo.observe(c,Echo.propagate(c,initial,t),t);
        else if(t>w.end_ms+1e-9 || (Math.abs(t-w.end_ms)<1e-9 && after)){
          stage=2;state=Echo.observe(c,Echo.propagate(c,pulse.outgoing,Math.max(0,t-w.end_ms)),t);
        }else{
          stage=1;active_j_hz=p.pulse_j_hz;state={...pulse.solver.at(Math.max(0,Math.min(w.width_ms,t-w.start_ms))),time_ms:t};
        }
      }
      record.arms[arm].state=state;
      record.arms[arm].history.push({...Object.fromEntries(Preparation.historyKeys.map(k=>[k,state[k]])), stage, active_j_hz});
    }
    for(const arm of arms)record.arms[arm].fidelity_to_ideal=fidelity(record.arms[arm].state,record.arms.ideal.state);
    return record;
  }
  function reference(p){return evolve(p,{index:-1,phase_offset:0,bias_offset_hz:0,config:{...p.base}});}
  function aggregate(p, ref, records){
    if(!records.length)return null;
    return Object.fromEntries(arms.map(arm=>{
      const result=Preparation.aggregate(ensemble(p),ref.arms[arm],records.map(r=>r.arms[arm]));
      // No isolated-well sinc guide is valid through a finite driven pulse.
      for(let i=0;i<result.history.length;i++){
        delete result.history[i].guide_coherence;
        result.history[i].stage=ref.arms[arm].history[i].stage;
        result.history[i].active_j_hz=ref.arms[arm].history[i].active_j_hz;
      }
      result.mean_fidelity_to_ideal=records.reduce((s,r)=>s+r.arms[arm].fidelity_to_ideal,0)/records.length;
      return [arm,result];
    }));
  }
  function report(p,ref,records,status){return {schema:"coldatomlab-pulse-v1",version:"0.14.0",convention,plan:p,status,windows:windows(p),checkpoints:checkpoints(p),reference:ref,records,aggregate:aggregate(p,ref,records)};}
  globalThis.FinitePulse={arms,convention,defaults,ensemble,validate,windows,checkpoints,components,fidelity,evolve,reference,aggregate,report};
})();
