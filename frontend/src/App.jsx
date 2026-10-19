import { useEffect, useState } from 'react';
import { Activity, AlertTriangle, ArrowRight, BrainCircuit, CheckCircle2, Database, GitCompareArrows, Layers, RefreshCw, Server, ShieldCheck } from 'lucide-react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend } from 'recharts';
import MigrationImpact from './MigrationImpact';
import DecisionCenter from './DecisionCenter';
import './App.css';

const API = 'http://127.0.0.1:8000';
const pages = [
  ['overview','Overview',Activity], ['collections','MongoDB Explorer',Database],
  ['schema','Schema Comparison',GitCompareArrows], ['repair','Query Repair',CheckCircle2], ['impact','Migration Impact',Layers], ['decisions','Review & Reports',ShieldCheck], ['benchmark','Compatibility Tests',Layers],
  ['models','Machine Learning',BrainCircuit], ['safety','Safety Evaluation',ShieldCheck]
];
const format = value => typeof value === 'number' ? value.toLocaleString() : value ?? '—';

function Metric({label,value,caption,danger=false}) {
  return <div className={'metric '+(danger?'danger':'')}><span>{label}</span><strong>{format(value)}</strong>{caption&&<small>{caption}</small>}</div>;
}
function SectionTitle({title,subtitle,tag}) {
  return <div className="section-title"><div><h2>{title}</h2><p>{subtitle}</p></div>{tag&&<span className="tag">{tag}</span>}</div>;
}
function FieldPanel({title,items,kind}) {
  return <div className="subpanel"><h3>{title}</h3><div className="field-scroll">{items.length ? items.map(v=><div className={'field '+kind} key={v}>{kind==='added'?'+':'−'} {v}</div>) : <p className="muted">No fields detected.</p>}</div></div>;
}
export default function App() {
  const [page,setPage]=useState('overview');
  const [health,setHealth]=useState(null),[collections,setCollections]=useState([]);
  const [benchmark,setBenchmark]=useState(null),[ml,setMl]=useState(null),[hybrid,setHybrid]=useState(null);
  const [loading,setLoading]=useState(true),[error,setError]=useState('');
  const [source,setSource]=useState('students'),[target,setTarget]=useState('students_v3');
  const [comparison,setComparison]=useState(null),[comparing,setComparing]=useState(false),[compareError,setCompareError]=useState('');
  const [mapping,setMapping]=useState(null),[mappingLoading,setMappingLoading]=useState(false),[mappingError,setMappingError]=useState('');
  const [queryChoices,setQueryChoices]=useState([]);
  const [queryId,setQueryId]=useState('Q1');
  const [repairTarget,setRepairTarget]=useState('students_v3');
  const [repairResult,setRepairResult]=useState(null);
  const [repairLoading,setRepairLoading]=useState(false);
  const [repairError,setRepairError]=useState('');

  async function get(path) {
    const res=await fetch(`${API}${path}`);
    if(!res.ok) {
      let message=`HTTP ${res.status}`;
      try { const body=await res.json(); if(typeof body.detail==='string') message=body.detail; } catch { /* keep status */ }
      throw new Error(message);
    }
    return res.json();
  }
  async function refresh() {
    setLoading(true);setError('');
    try {
      const [h,c,b,m,r]=await Promise.all([
        get('/api/health'),get('/api/database/collections'),get('/api/research/benchmark'),
        get('/api/research/ml-results'),get('/api/research/hybrid-results')
      ]);
      setHealth(h);setCollections(c.collections||[]);setBenchmark(b);setMl(m);setHybrid(r);
    } catch(e) {setError(e.message);} finally {setLoading(false);}
  }
  useEffect(()=>{
    refresh();
    get('/api/query/registered')
      .then(data => setQueryChoices(data.queries || []))
      .catch(err => setRepairError(err.message));
  },[]);
  function resetCompare() {setComparison(null);setMapping(null);setCompareError('');setMappingError('');}
  async function compare() {
    setComparing(true);setCompareError('');setComparison(null);setMapping(null);
    try {setComparison(await get(`/api/schema/compare?${new URLSearchParams({source,target,sample_size:'500'})}`));}
    catch(e){setCompareError(e.message);} finally{setComparing(false);}
  }
  async function discover() {
    setMappingLoading(true);setMappingError('');setMapping(null);
    try {setMapping(await get(`/api/schema/mappings?${new URLSearchParams({source,target,join_key:'student_id',sample_size:'500'})}`));}
    catch(e){setMappingError(e.message);} finally{setMappingLoading(false);}
  }
  async function verifyRepair() {
    setRepairLoading(true);
    setRepairError('');
    setRepairResult(null);
    try {
      const params = new URLSearchParams({query_id:queryId,target:repairTarget});
      setRepairResult(await get(`/api/query/verify?${params}`));
    } catch (err) {
      setRepairError(err.message);
    } finally {
      setRepairLoading(false);
    }
  }
  const summary=benchmark?.summary||{};
  const models=ml?.overall||{},lr=models['Logistic Regression'],rf=models['Random Forest'],safety=hybrid?.Hybrid;
  const modelData=[['Logistic Regression',lr],['Random Forest',rf]].map(([name,r])=>({name,recall:(r?.recall||0)*100,precision:(r?.precision||0)*100,f1:(r?.f1||0)*100}));
  const outcomeData=[['Exact',summary.EXACT_MATCH],['Restored',summary.ADAPTER_RESTORED],['Review',summary.REVIEW_REQUIRED]].map(([name,count])=>({name,count:count||0}));
  const total=collections.reduce((sum,c)=>sum+c.documents,0);
  const chart=(data,series)=><div className="chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} margin={{bottom:12}}><CartesianGrid stroke="#263b51" vertical={false} strokeDasharray="3 3"/><XAxis dataKey="name" stroke="#95aac3" tick={{fontSize:11}}/><YAxis stroke="#95aac3" tick={{fontSize:11}}/><Tooltip contentStyle={{background:'#1a2a40',border:'1px solid #335069',color:'#f0f6ff'}}/><Legend/>{series.map(([key,color])=><Bar key={key} name={key} dataKey={key} fill={color} radius={[5,5,0,0]}/>)}</BarChart></ResponsiveContainer></div>;
  return <div className="app">
    <aside className="sidebar"><div className="brand"><div className="brand-icon"><ShieldCheck/></div><div><strong>SchemaGuard</strong><small>AI RESEARCH PLATFORM</small></div></div><div className="nav-label">WORKSPACE</div><nav>{pages.map(([id,label,Icon])=><button key={id} className={'nav '+(page===id?'active':'')} onClick={()=>setPage(id)}><Icon size={19}/>{label}</button>)}</nav><div className="sidebar-foot"><p><Server size={17}/> System Status</p><small><i className={health?.status==='connected'?'dot online':'dot'}/> {health?.status==='connected'?'MongoDB Connected':'Connection unverified'}</small><p className="version">SCHEMAGUARD AI · V0.4</p></div></aside>
    <main className="main"><header className="header"><div><div className="eyebrow">DATABASE INTELLIGENCE PLATFORM</div><h1>{pages.find(x=>x[0]===page)?.[1]}</h1><p>MongoDB schema evolution, application compatibility and migration safety.</p></div><button className="button secondary" disabled={loading} onClick={refresh}><RefreshCw size={16}/>{loading?'Refreshing':'Refresh Data'}</button></header>
      {error&&<div className="error"><AlertTriangle size={18}/>Backend: {error}</div>}
      {page==='overview'&&<><div className="stats"><Metric label="Migration Scenarios" value={benchmark?.scenario_count} caption="Controlled variants"/><Metric label="Query Evaluations" value={benchmark?.evaluation_count} caption="Saved research benchmark"/><Metric label="Adapter Restored" value={summary.ADAPTER_RESTORED} caption="Recovered outputs"/><Metric label="Review Required" value={summary.REVIEW_REQUIRED} danger caption="Potential incompatibilities"/></div><div className="two"><div className="panel"><SectionTitle title="Compatibility Outcomes" subtitle="Results from saved experimental benchmark" tag="RESEARCH"/>{chart(outcomeData,[['count','#37cda1']])}</div><div className="panel"><SectionTitle title="ML Evaluation" subtitle="Held-out migration family results" tag="ML"/>{chart(modelData,[['recall','#37cda1'],['precision','#7699ff'],['f1','#edb776']])}</div></div><div className="panel"><SectionTitle title="Database Overview" subtitle="Current local MongoDB research environment" tag="CONNECTED DATA"/><div className="stats three"><Metric label="Collections" value={collections.length}/><Metric label="Documents" value={total}/><Metric label="Logistic Risk Recall" value={lr?`${(lr.recall*100).toFixed(1)}%`:null}/></div><p className="muted">Evaluation metrics are from controlled synthetic experiments, not a real-world safety guarantee.</p></div></>}
      {page==='collections'&&<div className="panel"><SectionTitle title="MongoDB Collections" subtitle="Live document counts" tag={`${collections.length} COLLECTIONS`}/><div className="table-scroll"><table><thead><tr><th>Collection</th><th>Documents</th></tr></thead><tbody>{collections.map(c=><tr key={c.name}><td><Database size={15}/> {c.name}</td><td>{format(c.documents)}</td></tr>)}</tbody></table></div></div>}
      {page==='schema'&&<div className="panel"><SectionTitle title="Live Schema Comparison" subtitle="Read-only structure and field-mapping inspection" tag="LIVE DATABASE"/><div className="controls"><label>Source Collection<select value={source} onChange={e=>{setSource(e.target.value);resetCompare();}}>{collections.map(c=><option key={c.name} value={c.name}>{c.name}</option>)}</select></label><label>Target Collection<select value={target} onChange={e=>{setTarget(e.target.value);resetCompare();}}>{collections.map(c=><option key={c.name} value={c.name}>{c.name}</option>)}</select></label><button className="button primary" disabled={comparing||loading||source===target} onClick={compare}><GitCompareArrows size={18}/>{comparing?'Analyzing...':'Compare Schemas'}</button></div>{compareError&&<div className="error">{compareError}</div>}
        {!comparison&&<div className="empty"><GitCompareArrows size={38}/><h3>Ready for schema analysis</h3><p>Choose two collections and run a comparison.</p></div>}
        {comparison&&<><div className="banner"><Database size={18}/>{comparison.source.collection}<ArrowRight size={19}/>{comparison.target.collection}</div><div className="stats"><Metric label="Added Paths" value={comparison.summary.added_fields}/><Metric label="Removed Paths" value={comparison.summary.removed_fields}/><Metric label="Type Changes" value={comparison.summary.type_changes}/><Metric label="Coverage Changes" value={comparison.summary.coverage_changes}/></div><div className="two"><FieldPanel title="Added Field Paths" items={comparison.changes.added} kind="added"/><FieldPanel title="Removed Field Paths" items={comparison.changes.removed} kind="removed"/></div><div className="subpanel"><h3>Type Changes</h3>{comparison.changes.type_changes.length?comparison.changes.type_changes.map(x=><p key={x.field}>{x.field}: {x.source_types.join(', ')} → {x.target_types.join(', ')}</p>):<p className="muted">No changed types detected at shared field paths.</p>}</div><div className="subpanel"><h3>Coverage Changes</h3>{comparison.changes.coverage_changes.length?comparison.changes.coverage_changes.map(x=><p key={x.field}>{x.field}: {(x.source_coverage*100).toFixed(1)}% → {(x.target_coverage*100).toFixed(1)}%</p>):<p className="muted">No coverage changes detected at shared field paths.</p>}</div><p className="muted">Compared {comparison.source.sampled_documents} source and {comparison.target.sampled_documents} target records. Sample analysis may miss rare fields.</p>
          <div className="mapping"><div className="mapping-head"><div><h2>Intelligent Field Mapping</h2><p>Heuristic recommendations from paired source and target records</p></div><button className="button primary" disabled={mappingLoading} onClick={discover}><BrainCircuit size={17}/>{mappingLoading?'Finding mappings...':'Discover Field Mappings'}</button></div>{mappingError&&<div className="error"><AlertTriangle size={16}/>{mappingError}</div>}{mapping&&<><p className="muted">Matched: {mapping.matched_records} · Discovery: {mapping.discovery_records} · Validation: {mapping.validation_records}</p><div className="two">{mapping.recommendations.map(r=><div className="mapping-card" key={r.source_field}><span className={'pill '+(r.status==='SUGGESTED'?'good':'warn')}>{r.status.replaceAll('_',' ')}</span><div className="path-row"><strong>{r.source_field}</strong><ArrowRight size={18}/><strong>{r.recommended_field||'Unresolved'}</strong></div>{r.candidates[0]&&<div className="evidence"><div>Discovery match<strong>{(r.candidates[0].agreement*100).toFixed(1)}%</strong></div><div>Discovery coverage<strong>{(r.candidates[0].coverage*100).toFixed(1)}%</strong></div><div>Held-out match<strong>{(r.validation.agreement*100).toFixed(1)}%</strong></div></div>}{r.warnings.map((w,i)=><p className="warning" key={i}><AlertTriangle size={14}/>{w}</p>)}{r.candidates.length>1&&<details><summary>Alternative candidates</summary>{r.candidates.slice(1).map(c=><p key={c.path}>{c.path} · score {c.score.toFixed(3)}</p>)}</details>}</div>)}</div><p className="muted">{mapping.disclaimer}</p></>}</div></>}
      </div>}
      {page==='repair'&&<div className="panel">
        <SectionTitle title="Query Repair & Verification" subtitle="Read-only validation against the saved V1 baseline" tag="LIVE TEST"/>
        <div className="controls">
          <label>Registered V1 Query
            <select value={queryId} onChange={e=>{setQueryId(e.target.value);setRepairResult(null);}}>
              {queryChoices.map(q=><option key={q.id} value={q.id}>{q.id} — {q.name}</option>)}
            </select>
          </label>
          <label>Target Schema
            <select value={repairTarget} onChange={e=>{setRepairTarget(e.target.value);setRepairResult(null);}}>
              <option value="students_v2">students_v2</option>
              <option value="students_v3">students_v3</option>
            </select>
          </label>
          <button className="button primary" disabled={repairLoading || !queryChoices.length} onClick={verifyRepair}>
            <CheckCircle2 size={17}/>{repairLoading?'Verifying...':'Preview & Verify'}
          </button>
        </div>
        {repairError&&<div className="error"><AlertTriangle size={17}/>{repairError}</div>}
        {!repairResult&&<div className="empty"><ShieldCheck size={38}/><h3>Ready to verify a query</h3><p>Select a registered query and target schema to preview safe repairs.</p></div>}
        {repairResult&&<div className="repair-output">
          <div className="banner"><ShieldCheck size={18}/><strong>{repairResult.query_id}</strong><span className={repairResult.status==='REVIEW_REQUIRED'?'repair-status fail':'repair-status pass'}>{repairResult.status.replaceAll('_',' ')}</span></div>
          <p className="muted">{repairResult.reason}</p>
          {repairResult.executed&&<>
            <div className="stats three">
              <Metric label="V1 Expected Records" value={repairResult.expected_count}/>
              <Metric label="Target Records" value={repairResult.actual_count}/>
              <Metric label="Missing Field Occurrences" value={repairResult.missing_field_occurrences} danger={repairResult.missing_field_occurrences>0}/>
            </div>
            <div className="two">
              <div className="subpanel"><h3>Original Filter</h3><pre className="json-view">{JSON.stringify(repairResult.original_filter,null,2)}</pre></div>
              <div className="subpanel"><h3>Repaired Filter</h3><pre className="json-view">{JSON.stringify(repairResult.repaired_filter,null,2)}</pre></div>
            </div>
            <div className="subpanel"><h3>Projected Field Mapping</h3><pre className="json-view">{JSON.stringify(repairResult.repaired_fields,null,2)}</pre></div>
            <div className="two">
              <div className="subpanel"><h3>V1 Result Preview</h3><pre className="json-view">{JSON.stringify(repairResult.expected_preview,null,2)}</pre></div>
              <div className="subpanel"><h3>Target Result Preview</h3><pre className="json-view">{JSON.stringify(repairResult.actual_preview,null,2)}</pre></div>
            </div>
          </>}
          <p className="muted">{repairResult.disclaimer || 'Manual review required. No query executed.'}</p>
        </div>}
      </div>}
      {page==='impact'&&<MigrationImpact/>}
      {page==='decisions'&&<DecisionCenter/>}
      {page==='benchmark'&&<div className="panel"><SectionTitle title="Compatibility Benchmark" subtitle="1,800 saved query-scenario evaluations" tag="EXPERIMENTAL"/><div className="stats"><Metric label="Exact" value={summary.EXACT_MATCH}/><Metric label="Restored" value={summary.ADAPTER_RESTORED}/><Metric label="Review" value={summary.REVIEW_REQUIRED}/><Metric label="Errors" value={summary.EXECUTION_ERROR||0}/></div><div className="table-scroll"><table><thead><tr><th>Family</th><th>Exact</th><th>Restored</th><th>Review</th></tr></thead><tbody>{Object.entries(benchmark?.by_family||{}).map(([name,r])=><tr key={name}><td>{name}</td><td>{r.EXACT_MATCH||0}</td><td>{r.ADAPTER_RESTORED||0}</td><td>{r.REVIEW_REQUIRED||0}</td></tr>)}</tbody></table></div></div>}
      {page==='models'&&<div className="panel"><SectionTitle title="Machine Learning Evaluation" subtitle="Leave-one-migration-family-out evaluation" tag="MODEL RESULTS"/>{chart(modelData,[['recall','#37cda1'],['precision','#7699ff'],['f1','#edb776']])}<div className="stats"><Metric label="Logistic Recall" value={lr?`${(lr.recall*100).toFixed(1)}%`:null}/><Metric label="Logistic F1" value={lr?.f1?.toFixed(3)}/><Metric label="Forest Recall" value={rf?`${(rf.recall*100).toFixed(1)}%`:null}/><Metric label="Logistic Missed Risks" value={lr?.FN}/></div></div>}
      {page==='safety'&&<div className="panel"><SectionTitle title="Safety Evaluation" subtitle="Development-set comparison of rules and ML" tag="NOT PRODUCTION VALIDATED"/><div className="stats"><Metric label="Hybrid Recall" value={safety?`${(safety.recall*100).toFixed(1)}%`:null}/><Metric label="Precision" value={safety?`${(safety.precision*100).toFixed(1)}%`:null}/><Metric label="False Negatives" value={safety?.FN}/><Metric label="False Positives" value={safety?.FP}/></div><div className="notice"><ShieldCheck size={20}/>On the existing benchmark, hybrid predictions do not outperform rules alone. No migration is approved automatically.</div></div>}
      <footer>SchemaGuard AI · Read-only MongoDB Research Prototype · v1.0 <span>MongoDB {health?.mongodb_version||'—'}</span></footer>
    </main>
  </div>;
}