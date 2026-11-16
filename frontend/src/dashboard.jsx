import React, {useEffect, useState} from 'react';
import {StatCard} from './components';
import {Link, useLocation} from 'react-router';

export default function Dashboard() {
  const location = useLocation();
  const [data, setData] = useState(null);
  const [filters, setFilters] = useState(() => Object.fromEntries(new URLSearchParams(location.search)));
  const [error, setError] = useState('');
  useEffect(() => {
    fetch('/api/dashboard/' + location.search, {headers: {'Accept': 'application/json'}})
      .then(r => { if (r.redirected && new URL(r.url).pathname === '/ingresar/') { window.location.assign('/ingresar/?next=' + encodeURIComponent(location.pathname + location.search)); return new Promise(() => {}); } if (!r.ok || !r.headers.get('content-type')?.includes('application/json')) throw Error(); return r.json(); })
      .then(d => setData(d))
      .catch(() => setError('No se pudo cargar el panel. Recarga la página.'));
  }, [location.search]);
  if (!data) return error ? <p role="alert">{error}</p> : null;
  const m = data.metrics;
  const currentCards = [['Activos documentados',m.active_chart.total,'equipos con estado activo','stat-approved'],['En uso con aprobación',m.inventory_total,'tipo registrado; incluye retiro solicitado','stat-approved'],['Equipos retirados',m.retired,'estado operativo actual','stat-retired'],['Cartas sin respuesta',m.pending_letters,'cartas CPC pendientes','stat-observed']];
  const historyCards = [['Registros históricos',m.total,'presentaciones y retiros',''],['Evaluaciones aprobadas',m.approved,'resultados registrados en el historial','stat-approved'],['Evaluaciones observadas',m.observed,'resultados históricos; pueden estar subsanados','stat-observed']];
  const params = new URLSearchParams({q: data.filters.q, result: data.filters.result, status: data.filters.status}).toString();
  return <>
    <section className="hero-row"><div><span className="eyebrow">Base de equipos</span><h1>Seguimiento de cartas y evaluaciones</h1><p>Consulta cada presentación, su resultado SST y el estado operativo del equipo.</p><a className="search-jump" href="#historial">Buscar en el historial ↓</a></div>{data.canEdit && <div className="hero-actions"><Link className="button button-secondary" to="/registro/nuevo/">Ingreso manual</Link><Link className="button button-primary" to="/cargar/">+ Cargar cartas PDF</Link></div>}</section>
    <section className="dashboard-summary" aria-labelledby="current-summary"><div className="summary-heading"><div><span className="eyebrow">Situación actual</span><h2 id="current-summary">Estado de equipos y cartas</h2></div><p>Indicadores generales, independientes de los filtros del historial.</p></div><div className="summary-grid">{currentCards.map(([label,value,description,style]) => <StatCard key={label} label={label} value={value} description={description} className={style}/>)}</div></section>
    <section className="panel active-chart-panel" aria-labelledby="active-chart-title">
      <div className="panel-heading"><div><span className="eyebrow">Estado operativo</span><h2 id="active-chart-title">Equipos activos por tipo</h2></div><span className="count-pill">{m.active_chart.total} equipos</span></div>
      <p className="chart-description">Equipos con estado activo y al menos una presentación o movimiento. Los equipos sin historial no se cuentan.</p>
      {m.active_chart.total ? <div className="chart-layout"><div className="pie-chart" aria-hidden="true" style={{background: `conic-gradient(${m.active_chart.gradient})`}}/><ul className="chart-legend">{m.active_chart.items.map(item => <li key={item.equipment_type}><span className="chart-swatch" aria-hidden="true" style={{background: item.color}}/><span>{item.equipment_type}</span><strong>{item.total} <small>({item.percentage} %)</small></strong></li>)}</ul></div> : <div className="empty-state"><span>No hay equipos activos para mostrar.</span></div>}
    </section>
    <section className="dashboard-summary history-summary" aria-labelledby="history-summary"><div className="summary-heading"><div><span className="eyebrow">Historial</span><h2 id="history-summary">Actividad registrada</h2></div><p>Una misma unidad puede tener varias presentaciones y evaluaciones.</p></div><div className="summary-grid">{historyCards.map(([label,value,description,style]) => <StatCard key={label} label={label} value={value} description={description} className={style}/>)}</div></section>
    <section className="panel records-panel" id="historial" aria-labelledby="records-title">
      <div className="panel-heading"><div><span className="eyebrow">Consulta</span><h2 id="records-title">Historial de registros</h2></div><span className="result-count" role="status">{data.records.length} {data.records.length === 1 ? 'resultado' : 'resultados'}</span></div>
      <div className="panel-toolbar"><form method="get" className="record-filters">
        <label>Buscar por placa, carta o tipo<input type="search" name="q" value={filters.q || ''} onChange={e=>setFilters({...filters,q:e.target.value})} placeholder="Ej. BVL-812"/></label>
        <label>Resultado SST<select name="result" value={filters.result || ''} onChange={e=>setFilters({...filters,result:e.target.value})}><option value="">Todos los resultados</option><option value="APPROVED">Aprobado</option><option value="OBSERVED">Observado-No conforme</option></select></label>
        <label>Estado operativo<select name="status" value={filters.status || ''} onChange={e=>setFilters({...filters,status:e.target.value})}><option value="">Todos los estados</option><option value="ACTIVE">Activo</option><option value="REQUESTED">Retiro solicitado</option><option value="RETIRED">Retirado</option><option value="REVIEW">Por revisar</option></select></label>
        <div className="filter-actions"><button className="button button-primary">Buscar</button><Link className="button button-ghost" to="/" onClick={()=>setFilters({})}>Limpiar</Link></div>
      </form></div>
      <div className="results-toolbar"><span>La exportación incluye todos los resultados filtrados.</span><div className="export-actions"><a href={'/exportar/csv/?'+params}>CSV</a><a href={'/exportar/xlsx/?'+params}>Excel</a></div></div>
      <div className="table-wrap"><table className="records-table"><thead><tr>{['Equipo','Estado operativo','Resultado SST','Detalle y documentos'].map(x=><th key={x}>{x}</th>)}</tr></thead><tbody>{data.records.length ? data.records.map(r=><tr key={r.id}><td><strong>{r.equipment}</strong><small>{r.equipmentType}</small><small>CPC {r.cpc} · {r.date}</small></td><td><span className={'status '+(r.status==='RETIRED'?'status-observed':(r.status==='REQUESTED'||r.status==='REVIEW')?'status-pending':'status-approved')}>{r.statusLabel}</span>{r.statusDate && <small>{r.statusDate}</small>}{r.resolveStatusUrl && <a href={r.resolveStatusUrl}>Revisar empate</a>}</td><td><span className={'status '+(r.result==='APPROVED'?'status-approved':r.result==='OBSERVED'?'status-observed':'status-pending')}>{r.resultLabel}</span><small className="detail-text">{r.detail}</small></td><td><details className="record-detail"><summary>Ver detalle <span className="sr-only">de {r.equipment}, carta {r.cpc}</span></summary><div className="record-detail-body"><p><strong>Carta CPC:</strong> {r.number}<br/><strong>Fecha:</strong> {r.date} · <strong>Recepción:</strong> {r.reception}</p><p><strong>Trámite:</strong> {r.event}{r.movementDetail && <> · {r.movementDetail}</>}</p><p><strong>Respuesta AAM:</strong> {r.response}{r.responseDate && ` · ${r.responseDate}`}</p><div className="detail-actions">{r.editUrl && <Link to={r.editUrl}>Editar registro</Link>}{r.cpcPdf && <a href={r.cpcPdf} target="_blank" rel="noreferrer">PDF CPC</a>}{r.responsePdf && <a href={r.responsePdf} target="_blank" rel="noreferrer">PDF AAM</a>}<Link to={"/cartas/?q="+encodeURIComponent(r.number)}>Ver carta en expedientes</Link></div></div></details></td></tr>) : <tr><td colSpan="4"><div className="empty-state"><strong>{data.filters.q || data.filters.result || data.filters.status ? 'No hay resultados para estos filtros.' : 'Aún no hay registros.'}</strong><span>{data.filters.q || data.filters.result || data.filters.status ? 'Prueba otra búsqueda o limpia los filtros.' : 'Carga una carta CPC para comenzar.'}</span></div></td></tr>}</tbody></table></div>
    </section>
  </>;
}
