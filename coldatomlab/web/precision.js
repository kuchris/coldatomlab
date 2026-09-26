"use strict";
(() => {
  const arms=["ideal","finite"],cases=["baseline","more_atoms","more_shots"];
  const convention="v0.14 readout; independent full-scan repetitions; LCG blocks: trial,case,setting,arm; circular statistics conditional on resolved fits";
  const defaults={readout:{...Readout.defaults,base:{...Readout.defaults.base,atoms:20},shots:64},more_atoms:80,more_shots:256,repetitions:100};
  function validate(input){
    if(Object.keys(input).sort().join()!==Object.keys(defaults).sort().join())throw new Error("Unknown precision setting.");
    const p={...input,readout:Readout.validate(input.readout)};
    for(const [k,lo,hi] of [["more_atoms",p.readout.base.atoms+1,100],["more_shots",p.readout.shots+1,4096],["repetitions",20,300]])
      if(!Number.isInteger(p[k])||p[k]<lo||p[k]>hi)throw new Error(`${k} must be an integer between ${lo} and ${hi}.`);
    if(drawsPerTrial(p)*p.repetitions>16000000)throw new Error("Workload exceeds 16 million count draws. Reduce repetitions, settings or shots.");
    return p;
  }
  const drawsPerTrial=p=>2*p.readout.points*(2*p.readout.shots+p.more_shots);
  const wrap=x=>Math.atan2(Math.sin(x),Math.cos(x));
  // Affine LCG skip-ahead, preserving unsigned 32-bit arithmetic exactly.
  function jump(seed,steps){let a=1664525,c=1013904223,x=seed>>>0;
    while(steps>0){if(steps%2===1)x=(Math.imul(a,x)+c)>>>0;c=(Math.imul(a,c)+c)>>>0;a=Math.imul(a,a)>>>0;steps=Math.floor(steps/2);}return x;}
  function configs(p){return cases.map(name=>({name,plan:Readout.validate({...p.readout,base:{...p.readout.base,atoms:name==="more_atoms"?p.more_atoms:p.readout.base.atoms},shots:name==="more_shots"?p.more_shots:p.readout.shots})}));}
  function modelCase(item){const {name,plan}=item,source=Readout.incoming(plan);
    const points=Array.from({length:plan.points},(_,i)=>{const r=Readout.states(plan,source,i);return {index:i,alpha:r.alpha,arms:Object.fromEntries(arms.map(a=>[a,r.arms[a]]))};});
    const model_fits=Object.fromEntries(arms.map(a=>[a,Readout.fit(points.map(r=>({alpha:r.alpha,z:2*r.arms[a].mean_left/plan.base.atoms-1,variance_z_mean:0})))]));
    const eligible=plan.base.initial==="coherent"&&plan.base.left_fraction===.5&&plan.base.interaction_hz===0;
    return {name,plan,source,points,model_fits,ideal_scatter_guide:eligible?Math.sqrt(3/(2*plan.base.atoms*plan.points*plan.shots)):null};
  }
  function trial(p,models,index){if(!Number.isInteger(index)||index<0||index>=p.repetitions)throw new Error("Invalid repetition index.");
    let seed=jump(p.readout.seed,index*drawsPerTrial(p));const result={index,cases:{}};
    for(const model of models){const S=model.plan.shots,N=model.plan.base.atoms,values=Object.fromEntries(arms.map(a=>[a,{measurements:[],fit:null}]));
      for(const r of model.points)for(const a of arms){const sample=TwoMode.sample(r.arms[a],S,seed);values[a].measurements.push({seed,counts:sample.counts});seed=jump(seed,S);}
      for(const a of arms)values[a].fit=Readout.fit(values[a].measurements.map((m,i)=>({alpha:model.points[i].alpha,...Readout.statistics(m.counts,N)})));
      result.cases[model.name]=values;
    }return result;
  }
  function summary(model,records,arm){const fits=records.map(r=>r.cases[model.name][arm].fit),valid=fits.filter(f=>f.phase!==null),n=valid.length,truth=model.source.phase;
    const result={attempted:fits.length,resolved:n,unresolved:fits.length-n,circular_bias:null,circular_scatter:null,wrapped_rmse:null,rms_reported_se:null,scatter_over_se:null,within_one_se:null,model_bias:truth!==null&&model.model_fits[arm].phase!==null?wrap(model.model_fits[arm].phase-truth):null};
    if(n<2)return result;
    const re=valid.reduce((s,f)=>s+Math.cos(f.phase),0)/n,im=valid.reduce((s,f)=>s+Math.sin(f.phase),0)/n,R=Math.min(1,Math.hypot(re,im));
    if(R>1e-8){result.circular_scatter=Math.sqrt(Math.max(0,-2*Math.log(R)));if(truth!==null)result.circular_bias=wrap(Math.atan2(im,re)-truth);}
    result.rms_reported_se=Math.sqrt(valid.reduce((s,f)=>s+f.phase_se**2,0)/n);
    if(result.rms_reported_se>0&&result.circular_scatter!==null)result.scatter_over_se=result.circular_scatter/result.rms_reported_se;
    if(truth!==null){result.wrapped_rmse=Math.sqrt(valid.reduce((s,f)=>s+wrap(f.phase-truth)**2,0)/n);result.within_one_se=valid.filter(f=>Math.abs(wrap(f.phase-truth))<=f.phase_se).length/n;}
    return result;
  }
  function report(p,models,records,status){return {schema:"coldatomlab-precision-v1",version:"0.15.0",convention,plan:p,status,models,records,summary:Object.fromEntries(models.map(m=>[m.name,Object.fromEntries(arms.map(a=>[a,summary(m,records,a)]))]))};}
  globalThis.Precision={arms,cases,convention,defaults,validate,drawsPerTrial,wrap,jump,configs,modelCase,trial,summary,report};
})();
