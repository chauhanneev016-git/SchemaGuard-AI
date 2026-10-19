import { useState } from 'react';
import { AlertTriangle, Download, FileSearch } from 'lucide-react';
import './MigrationImpact.css';
const API = 'http://127.0.0.1:8000';
export default function MigrationImpact() {
  const [target,setTarget]=useState('students_v3');
  const [report,setReport]=useState(null);
  const [loading,setLoading]=useState(false);
  const [error,setError]=useState('');
  async function analyze() {
    setLoading(true);setReport(null);setError('');
    try {
      const res=await fetch(`${API}/api/migration/impact?target=${encodeURIComponent(target)}`);
      const data=await res.json();
      if(!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
      setReport(data);
    } catch(e){setError(e.message);} finally{setLoading(false);}
  }
  function exportJson() {
    if(!report) return;
    const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
    const link=document.createElement('a'); link.href=url;link.download=`SchemaGuard_Impact_${target}.json`;
    document.body.appendChild(link);link.click();link.remove();URL.revokeObjectURL(url);
  }
  return <section className="impact-page">
    <div className="impact-heading"><h2>Migration Impact Analyzer</h2><p>Batch verification of five registered V1 queries</p></div>
    <div className="impact-controls">
      <label>Target schema<select value={target} onChange={e=>{setTarget(e.target.value);setReport(null);}}><option value="students_v2">students_v2</option><option value="students_v3">students_v3</option></select></label>
      <button onClick={analyze} disabled={loading}><FileSearch size={17}/>{loading?'Analyzing...':'Analyze Migration'}</button>
      {report&&<><button onClick={exportJson}><Download size={17}/>Export JSON</button>
      <a href={`${API}/api/reports/migration.pdf?target=${encodeURIComponent(target)}`}>Export PDF</a></>}
    </div>
    {error&&<p className="impact-error"><AlertTriangle size={17}/>{error}</p>}
    {report&&<>
      <div className="impact-summary"><div><span>Queries</span><b>{report.summary.total_queries}</b></div><div><span>Exact</span><b>{report.summary.exact_match}</b></div><div><span>Semantic</span><b>{report.summary.semantic_match}</b></div><div><span>Review</span><b>{report.summary.review_required}</b></div></div>
      <p className="impact-decision">{report.summary.decision.replaceAll('_',' ')} — {report.summary.compatible_queries} of {report.summary.total_queries} registered queries passed; this is not production approval.</p>
      {report.queries.map(item=><details className="impact-query" key={item.query_id}><summary><b>{item.query_id}</b> {item.query_name}<span>{item.status.replaceAll('_',' ')}</span></summary><p>{item.reason}</p><div className="impact-code"><pre>{JSON.stringify(item.original_filter,null,2)}</pre><pre>{JSON.stringify(item.repaired_filter,null,2)}</pre></div><h4>Recommendations</h4>{item.recommendations.map((r,i)=><p key={i}>• {r}</p>)}</details>)}
      <p className="impact-foot">{report.limitations.join(' · ')}</p>
    </>}
  </section>;
}