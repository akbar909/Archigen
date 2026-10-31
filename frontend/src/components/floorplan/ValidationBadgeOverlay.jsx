import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, X } from 'lucide-react';
export default function ValidationBadgeOverlay({
  issues,
  onSelect,
  autoOpenKey,
  onRepair
}) {
  const [open, setOpen] = useState(false),
    errors = issues.filter(i => i.severity === 'error').length;
  const warnings=issues.length-errors;
  useEffect(() => { if (autoOpenKey) setOpen(true) }, [autoOpenKey]);
  return <div className="cad-validation"><button aria-expanded={open} onClick={() => setOpen(!open)} className={issues.length ? 'has-issues' : 'valid'}>{issues.length ? <AlertTriangle size={15} /> : <CheckCircle2 size={15} />}<span>{issues.length ? `${errors} ${errors===1?'error':'errors'} · ${warnings} ${warnings===1?'warning':'warnings'}` : 'Design checks passed'}</span></button>{open && <div className="cad-diagnostics"><div className="cad-panel-heading"><strong>Design checks</strong><button aria-label="Close design checks" onClick={() => setOpen(false)}><X size={16} /></button></div><p>Select an issue to inspect the affected element.</p>{onRepair && issues.some(i=>i.code==='connection'||i.code==='server-conflict')&&<button className="cad-repair-links" onClick={onRepair}>Repair door links</button>}{issues.length === 0 && <p>No issues found.</p>}{issues.map((issue, index) => <button key={`${issue.floorIndex}-${issue.code}-${issue.entity.id}-${index}`} onClick={() => {
        onSelect(issue);
        setOpen(false);
      }}><span className={`cad-severity ${issue.severity}`} />{issue.message}</button>)}</div>}</div>;
}
