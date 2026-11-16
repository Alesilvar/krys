import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {BrowserRouter, Route, Routes, useLocation, useNavigate} from 'react-router';
import Dashboard, {Records} from './dashboard';
import {Layout} from './components';
import {Login, FormPage, DeletePage, Letters, Upload, Profile} from './pages';

const initialData = JSON.parse(document.getElementById('krys-data').textContent);
const initialUrl = location.pathname + location.search;
const pages = {profile: Profile, login: Login, dashboard: Dashboard, records_list: Records, manual_record: FormPage, edit_presentation: FormPage, edit_letter: FormPage, edit_movement: FormPage, delete_letter: DeletePage, letters: Letters, upload_letters: Upload};

async function requestPage(url, options = {}) {
  const response = await fetch(url, {...options, headers: {...options.headers, 'X-KS-Client': 'react', 'Accept': 'application/json'}});
  const finalUrl = new URL(response.url);
  if (finalUrl.pathname === '/ingresar/' && url !== '/ingresar/') {
    window.location.assign('/ingresar/?next=' + encodeURIComponent(location.pathname + location.search));
    return null;
  }
  if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('No se pudo cargar la página. Inténtalo nuevamente.');
  return {data: await response.json(), url: finalUrl.pathname + finalUrl.search, redirected: response.redirected};
}

function RoutedApp() {
  const location = useLocation();
  const navigate = useNavigate();
  const [data, setData] = useState(initialData);
  const [version, setVersion] = useState(0);
  const [loading, setLoading] = useState(false);
  const [readyUrl, setReadyUrl] = useState(initialUrl);
  const [error, setError] = useState('');
  const pending = useRef(null);
  const first = useRef(true);
  const busy = useRef(false);
  const url = location.pathname + location.search;
  useEffect(() => {
    if (first.current) {first.current = false; if (url === initialUrl) return;}
    if (pending.current?.url === url) {setData(pending.current.data); pending.current = null; setReadyUrl(url); setVersion(v => v+1); setLoading(false); setError(''); return;}
    const controller = new AbortController();
    setLoading(true); setError('');
    requestPage(url, {signal: controller.signal}).then(result => {if (result) {setData(result.data); setReadyUrl(url); setVersion(v=>v+1);}}).catch(e=>{if (e.name !== 'AbortError') setError('No se pudo cargar esta página. Comprueba la conexión y vuelve a intentarlo.');}).finally(()=>{if (!controller.signal.aborted) setLoading(false);});
    return () => controller.abort();
  }, [url]);

  async function submit(event) {
    const form = event.target;
    const target = new URL(form.action || url, window.location.href);
    if (target.origin !== window.location.origin || target.pathname === '/ingresar/' || target.pathname === '/salir/') return;
    event.preventDefault();
    if (busy.current) return;
    if (form.method.toLowerCase() === 'get') {
      const params = new URLSearchParams(new FormData(form));
      navigate(target.pathname + (params.size ? '?' + params.toString() : ''));
      return;
    }
    busy.current = true; setLoading(true); setError('');
    try {
      const result = await requestPage(target.pathname + target.search, {method: 'POST', body: new FormData(form)});
      if (!result) return;
      if (result.redirected && result.url !== url) {pending.current = result; navigate(result.url);}
      else {setData(result.data); setVersion(v=>v+1);}
    } catch (e) {setError('No se pudo completar la operación. Comprueba la conexión y vuelve a intentarlo.');} finally {busy.current = false; setLoading(false);}
  }
  const Page = pages[data.page];
  useEffect(() => {document.title = ({dashboard:'Inicio', records_list:'Registros', letters:'Cartas', upload_letters:'Cargar cartas', manual_record:'Ingreso manual', profile:'Mi perfil', login:'Ingresar', edit_presentation:'Editar registro', edit_letter:'Editar carta', edit_movement:'Editar desmovilización', delete_letter:'Eliminar carta'}[data.page] || 'KS') + ' · KS';}, [data.page]);
  return <div onSubmitCapture={submit}><Layout data={data}>{error && <div className="message message-error" role="alert"><strong>No se pudo completar la solicitud</strong><span>{error}</span>{readyUrl !== url && <button className="button button-ghost button-small" type="button" onClick={()=>window.location.reload()}>Volver a intentar</button>}</div>}{loading && <div className="loading-state" role="status"><span className="loading-indicator" aria-hidden="true"/>Procesando, espera un momento…</div>}{readyUrl === url && Page && <Page key={version} data={data}/>}</Layout></div>;
}

const routes = ['/', '/registros/', '/ingresar/', '/perfil/', '/cartas/', '/cargar/', '/registro/nuevo/', '/registro/:id/editar/', '/carta/:id/editar/', '/carta/:id/eliminar/', '/desmovilizacion/:id/editar/'];
if (pages[initialData.page]) {
  createRoot(document.getElementById('app-root')).render(<BrowserRouter><Routes><Route element={<RoutedApp/>}>{routes.map(path => <Route key={path} path={path} element={null}/>)}</Route></Routes></BrowserRouter>);
  document.getElementById('app-fallback').hidden = true;
}
