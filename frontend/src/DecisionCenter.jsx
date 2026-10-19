import { useEffect, useState } from 'react';
import { AlertTriangle, BrainCircuit, Download, FileCheck2, RefreshCw } from 'lucide-react';
import './DecisionCenter.css';

const API = 'http://127.0.0.1:8000';
async function fetchJson(path, options) {
  const response = await fetch(API + path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
  return data;
}
const code = obj => JSON.stringify(obj, null, 2);

export default function DecisionCenter() {
  const [target, setTarget] = useState('students_v3');
  const [report, setReport] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [scenarios, setScenarios] = useState([]);
  const [scenario, setScenario] = useState('');
  const [query, setQuery] = useState('Q1');
  const [prediction, setPrediction] = useState(null);
  const [reviewer, setReviewer] = useState('research_operator');
  const [notes, setNotes] = useState({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchJson('/api/ml/scenarios').then(data => {
      setScenarios(data.scenarios || []);
      setScenario(data.scenarios?.[0] || '');
    }).catch(err => setError(err.message));
  }, []);

  async function analyze() {
    setBusy(true); setError(''); setMessage(''); setReport(null);
    try {
      const [impact, history] = await Promise.all([
        fetchJson(`/api/migration/impact?target=${encodeURIComponent(target)}`),
        fetchJson(`/api/reviews?target=${encodeURIComponent(target)}`),
      ]);
      setReport(impact); setReviews(history.reviews || []);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function submitReview(queryId, decision) {
    setBusy(true); setError(''); setMessage('');
    try {
      await fetchJson('/api/reviews', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target, query_id: queryId, decision, reviewer, note: notes[queryId] || '' }),
      });
      const history = await fetchJson(`/api/reviews?target=${encodeURIComponent(target)}`);
      setReviews(history.reviews || []);
      setMessage(`Review saved for ${queryId}; no migration was executed.`);
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function predict() {
    setBusy(true); setPrediction(null); setError('');
    try {
      const params = new URLSearchParams({ scenario_id: scenario, query_id: query });
      setPrediction(await fetchJson(`/api/ml/predict?${params}`));
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <div className="decision-page">
    <div className="decision-panel">
      <h2>Migration Review & Recommendations</h2>
      <p className="decision-muted">Verify five registered queries, inspect repair recommendations and record human decisions. This never executes a migration.</p>
      <div className="decision-controls">
        <label>Target schema
          <select value={target} onChange={e => { setTarget(e.target.value); setReport(null); setReviews([]); }}>
            <option value="students_v2">students_v2</option>
            <option value="students_v3">students_v3</option>
          </select>
        </label>
        <label>Reviewer name<input maxLength={80} value={reviewer} onChange={e => setReviewer(e.target.value)} /></label>
        <button onClick={analyze} disabled={busy}><RefreshCw size={17}/> Analyze & Load Reviews</button>
        <a className="decision-download" href={`${API}/api/reports/migration.pdf?target=${encodeURIComponent(target)}`}><Download size={17}/> Export PDF</a>
      </div>
      {error && <div className="decision-error"><AlertTriangle size={16}/>{error}</div>}
      {message && <p className="decision-message">{message}</p>}
      {report && <>
        <div className="decision-summary"><strong>{report.summary.decision.replaceAll('_', ' ')}</strong>
          <span>{report.summary.compatible_queries}/{report.summary.total_queries} registered queries passed · {report.summary.review_required} require review</span></div>
        <div className="decision-grid">{report.queries.map(item =>
          <div className="decision-card" key={item.query_id}>
            <div className="decision-card-top"><h3>{item.query_id} · {item.query_name}</h3><span>{item.status.replaceAll('_', ' ')}</span></div>
            <p>{item.reason}</p>
            <h4>Recommendations</h4>
            {item.recommendations.map((rec, i) => <p key={i} className="decision-rec">• {rec}</p>)}
            <details><summary>View verification evidence</summary><pre>{code({ original: item.original_filter, repaired: item.repaired_filter, mappings: item.field_mappings, missing: item.missing_examples })}</pre></details>
            <textarea rows={2} maxLength={1200} placeholder="Review note (optional)" value={notes[item.query_id] || ''} onChange={e => setNotes(old => ({...old, [item.query_id]: e.target.value}))}/>
            <div className="decision-actions">
              <button disabled={busy || !reviewer.trim() || item.status === 'REVIEW_REQUIRED' || item.status === 'EXECUTION_ERROR'} onClick={() => submitReview(item.query_id, 'APPROVE_REPAIR')}>Approve repair</button>
              <button disabled={busy || !reviewer.trim()} onClick={() => submitReview(item.query_id, 'REJECT_REPAIR')}>Reject</button>
              <button disabled={busy || !reviewer.trim()} onClick={() => submitReview(item.query_id, 'NEEDS_INVESTIGATION')}>Investigate</button>
            </div>
          </div>)}</div>
        <h3>Audit Trail</h3>
        {reviews.length === 0 ? <p className="decision-muted">No reviews recorded for this target yet.</p> :
          <div className="decision-history">{reviews.map(r => <p key={r.review_id}><b>{r.query_id}</b> · {r.decision} · {r.reviewer} · {r.created_at} {r.note && `· ${r.note}`}</p>)}</div>}
      </>}
    </div>
    <div className="decision-panel">
      <h2><BrainCircuit size={20}/> Advisory ML Risk Score</h2>
      <p className="decision-muted">Historical synthetic benchmark only. This model cannot score an arbitrary live migration using the current feature pipeline.</p>
      <div className="decision-controls">
        <label>Historical scenario<select value={scenario} onChange={e => { setScenario(e.target.value); setPrediction(null); }}>
          {scenarios.map(s => <option key={s} value={s}>{s}</option>)}
        </select></label>
        <label>Query<select value={query} onChange={e => { setQuery(e.target.value); setPrediction(null); }}>
          {['Q1','Q2','Q3','Q4','Q5'].map(q => <option key={q} value={q}>{q}</option>)}
        </select></label>
        <button disabled={busy || !scenario} onClick={predict}>Calculate advisory score</button>
      </div>
      {prediction && <div className="decision-score"><strong>{(prediction.risk_score*100).toFixed(1)}%</strong>
        <span>Model risk score · Benchmark label: {prediction.actual_benchmark_label ? 'review required' : 'compatible/restored'}</span>
        <p>{prediction.warning}</p></div>}
    </div>
  </div>;
}