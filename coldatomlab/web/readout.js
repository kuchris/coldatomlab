"use strict";
(() => {
  const arms=["direct","ideal","finite"];
  const convention="fixed-N spatial modes; phase gate exp[-i(N-n)(alpha+pi/2)]; positive-J mixing; z=Re(q exp[-i alpha]); finite width=(1+error)/(8J) seconds";
  const defaults={base:{...TwoMode.presets.diffusion,interaction_hz:0,phase:.7,duration_ms:100},hold_ms:0,echo:false,pulse_j_hz:10,duration_error:0,points:12,shots:256,seed:17};
  function validate(input){
    const p={...input,base:TwoMode.validate(input.base)};
    if(Object.keys(p).sort().join()!==Object.keys(defaults).sort().join())throw new Error("Unknown readout setting.");
    if(p.base.tunnelling_hz!==0)throw new Error("Readout preparation requires hold J = 0.");
    if(typeof p.echo!=="boolean")throw new Error("Invalid echo setting.");
    for(const [k,lo,hi,integer] of [["hold_ms",0,1000,false],["pulse_j_hz",.5,20,false],["duration_error",-.5,.5,false],["points",8,32,true],["shots",16,4096,true],["seed",0,4294967295,true]])
      if(!Number.isFinite(p[k])||p[k]<lo||p[k]>hi||(integer&&!Number.isInteger(p[k])))throw new Error(`${k} must be ${integer?'an integer ':''}between ${lo} and ${hi}.`);
    return p;
  }
  const width=p=>125/p.pulse_j_hz*(1+p.duration_error);
  const observe=(c,s,time)=>Echo.observe(c,s,time);
  function incoming(p){const c=p.base,s=TwoMode.initial(c);let out;
    if(p.echo)out=Echo.propagate(c,Echo.swap(Echo.propagate(c,s,p.hold_ms/2)),p.hold_ms/2);
    else out=Echo.propagate(c,s,p.hold_ms);
    return observe(c,out,p.hold_ms);
  }
  function shifted(state,alpha){const N=state.real.length-1,r=new Float64Array(N+1),im=new Float64Array(N+1);
    for(let n=0;n<=N;n++){const angle=-(N-n)*(alpha+Math.PI/2),a=Math.cos(angle),b=Math.sin(angle);r[n]=state.real[n]*a-state.imag[n]*b;im[n]=state.real[n]*b+state.imag[n]*a;}return {r,im};}
  function statistics(counts,N){const shots=counts.reduce((a,b)=>a+b,0),mean=counts.reduce((s,v,n)=>s+n*v,0)/shots;
    const variance=counts.reduce((s,v,n)=>s+v*(n-mean)**2,0)/(shots-1);
    return {mean_left:mean,variance_left:variance,sem_left:Math.sqrt(variance/shots),z:2*mean/N-1,variance_z_mean:4*variance/(N*N*shots)};}
  // Fit consumes only observed means and their empirical variances, never model q.
  function fit(rows){const K=rows.length,weights=rows.map(r=>[1/K,2*Math.cos(r.alpha)/K,2*Math.sin(r.alpha)/K]);
    const beta=[0,1,2].map(j=>rows.reduce((s,r,i)=>s+weights[i][j]*r.z,0));
    const covariance=[0,1,2].map(j=>[0,1,2].map(k=>rows.reduce((s,r,i)=>s+weights[i][j]*weights[i][k]*r.variance_z_mean,0)));
    const [offset,a,b]=beta,C=Math.hypot(a,b),v=covariance;
    const maxVar=(v[1][1]+v[2][2]+Math.hypot(v[1][1]-v[2][2],2*v[1][2]))/2;
    const resolved=C>Math.max(1e-8,3*Math.sqrt(Math.max(0,maxVar)));
    const phase=resolved?Math.atan2(b,a):null;
    const phase_se=resolved?Math.sqrt(Math.max(0,b*b*v[1][1]+a*a*v[2][2]-2*a*b*v[1][2]))/(C*C):null;
    const residual_rms=Math.sqrt(rows.reduce((s,r)=>s+(r.z-offset-a*Math.cos(r.alpha)-b*Math.sin(r.alpha))**2,0)/K);
    return {offset,cosine:a,sine:b,contrast:C,phase,phase_se,residual_rms,covariance,resolved};
  }
  function point(p,source,index){if(!Number.isInteger(index)||index<0||index>=p.points)throw new Error("Invalid scan index.");
    const alpha=2*Math.PI*index/p.points,s=shifted(source,alpha),result={index,alpha,arms:{}};
    for(const [ai,arm] of arms.entries()){
      const ideal=arm==="ideal",c={...p.base,tunnelling_hz:p.pulse_j_hz,duration_ms:1000,...(ideal?{interaction_hz:0,bias_hz:0}:{})};
      let state;
      if(arm==="direct")state=source;
      else {state=new TwoMode.Solver(c,s).at(ideal?125/p.pulse_j_hz:width(p));state.time_ms=p.hold_ms+(ideal?0:width(p));}
      // Non-overlapping blocks in one LCG stream, one block per setting and arm.
      let seed=p.seed>>>0;for(let k=0;k<(index*3+ai)*p.shots;k++)seed=(Math.imul(1664525,seed)+1013904223)>>>0;
      const measurement=TwoMode.sample(state,p.shots,seed);
      result.arms[arm]={state,measurement,statistics:statistics(measurement.counts,p.base.atoms)};
    }return result;
  }
  function report(p,source,records,status){const complete=records.length===p.points;
    const fits=complete?Object.fromEntries(["ideal","finite"].map(arm=>[arm,{
      measured:fit(records.map(r=>({alpha:r.alpha,...r.arms[arm].statistics}))),
      model:fit(records.map(r=>({alpha:r.alpha,z:2*r.arms[arm].state.mean_left/p.base.atoms-1,variance_z_mean:0})))
    }])):null;
    return {schema:"coldatomlab-readout-v1",version:"0.14.0",convention,plan:p,status,finite_width_ms:width(p),source,records,fits};}
  globalThis.Readout={arms,convention,defaults,validate,width,incoming,shifted,statistics,fit,point,report};
})();
