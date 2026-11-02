import React, {useEffect, useRef, useState} from 'react';
import {Link, useLocation} from 'react-router';

export function Button({children, href, variant='primary', ...props}) {
  const className = `button button-${variant} ${props.className || ''}`;
  return href ? <Link to={href} className={className}>{children}</Link> : <button {...props} className={className}>{children}</button>;
}
export function Hero({eyebrow, title, description, back, backLabel='Volver', children}) {
  return <section className="hero-row compact"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{description && <p>{description}</p>}</div>{back && <Button href={back} variant="ghost">{backLabel}</Button>}{children}</section>;
}
export function StatCard({label, value, description, className=''}) {return <article className={'stat-card '+className}><span>{label}</span><strong>{value}</strong><small>{description}</small></article>}
export function Panel({children, className=''}) {return <section className={'panel '+className}>{children}</section>}
export function Csrf({token}) {return <input type="hidden" name="csrfmiddlewaretoken" value={token}/>}
export function Field({field}) {
  const {id,name,label,type,value,required,help,errors,choices,attrs} = field;
  const common = {id,name,required,defaultValue:value, 'aria-invalid': errors.length ? 'true' : undefined, 'aria-describedby': errors.length ? `${id}-error` : undefined};
  let input;
  if(type === 'textarea') input = <textarea {...common} rows={attrs.rows}/>;
  else if(type === 'select') input = <select {...common}>{choices.map(([v,l])=><option key={v} value={v}>{l}</option>)}</select>;
  else if(type === 'file') input = <input id={id} name={name} type="file" required={required} accept={attrs.accept} multiple={attrs.multiple}/>;
  else input = <input {...common} type={type} placeholder={attrs.placeholder}/>;
  return <div className={'form-field '+(['detail','additional_data'].includes(name)?'full-width':'')}><label htmlFor={id}>{label}</label>{input}{help && <small>{help}</small>}{errors.map((e,i)=><span id={`${id}-error`} className="field-error" key={i}>{e}</span>)}</div>;
}
export function FormErrors({errors=[]}) {return errors.length ? <div className="field-error" role="alert">{errors.map((e,i)=><div key={i}>{e}</div>)}</div> : null}
export function EditForm({data, sections, button='Guardar cambios'}) {
  const fields=data.form.fields;
  return <form method="post" encType="multipart/form-data" className="stack-form"><Csrf token={data.csrf}/><FormErrors errors={data.form.errors}/>{sections ? sections.map(section=><React.Fragment key={section.title}><div className="form-section"><span className="eyebrow">{section.eyebrow}</span><h2>{section.title}</h2></div><div className="two-columns">{section.fields.map(name=>fields.find(f=>f.name===name)).filter(Boolean).map(field=><Field key={field.name} field={field}/>)}</div></React.Fragment>) : <div className="two-columns">{fields.map(field=><Field key={field.name} field={field}/>)}</div>}<div className="form-actions"><Button type="submit">{button}</Button></div></form>;
}
export function LinkPdf({href, children}) {return href ? <a href={href} target="_blank" rel="noopener noreferrer">{children}</a> : null}
const menuItems = [
  {label: 'Registros', href: '/', icon: 'records', pages: ['dashboard']},
  {label: 'Cartas', href: '/cartas/', icon: 'letters', pages: ['letters', 'edit_letter', 'edit_movement', 'delete_letter']},
  {label: 'Ingreso manual', href: '/registro/nuevo/', icon: 'manual', pages: ['manual_record']},
  {label: 'Cargar cartas', href: '/cargar/', icon: 'upload', pages: ['upload_letters', 'confirm_upload']},
];
function MenuIcon({name}) {
  const paths = {
    menu: <><path d="M4 6h16M4 12h16M4 18h16"/></>,
    close: <path d="M6 6l12 12M18 6L6 18"/>,
    records: <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18M9 9v11"/></>,
    letters: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></>,
    manual: <><path d="M12 4v16M4 12h16"/></>,
    upload: <><path d="M12 16V4m-4 4 4-4 4 4"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/></>,
    user: <><circle cx="12" cy="8" r="3.5"/><path d="M5 20a7 7 0 0 1 14 0"/></>,
    logout: <><path d="M10 4H5v16h5M14 8l4 4-4 4M8 12h10"/></>,
  };
  return <svg className="menu-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
function UserMenu({data}) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location]);
  const container = useRef(null);
  const trigger = useRef(null);
  useEffect(() => {
    if (!open) return;
    const outside = event => {if (!container.current?.contains(event.target)) setOpen(false);};
    const keys = event => {if (event.key === 'Escape') {setOpen(false); trigger.current?.focus();}};
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', keys);
    return () => {document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', keys);};
  }, [open]);
  return <div className="account-menu" ref={container}><button ref={trigger} type="button" className="account-trigger" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="account-popover" aria-label="Menú de usuario"><span className="account-avatar" aria-hidden="true">{data.username.trim().charAt(0).toUpperCase()}</span><span className="account-name">{data.username}</span><svg className="account-chevron" viewBox="0 0 20 20" aria-hidden="true"><path d="m5 7.5 5 5 5-5" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/></svg></button>{open && <div id="account-popover" className="account-popover"><div className="account-heading"><small>Sesión iniciada</small><strong>{data.username}</strong></div><Link className="account-action" to="/perfil/"><MenuIcon name="user"/>Mi perfil</Link><form method="post" action="/salir/"><Csrf token={data.csrf}/><button type="submit" className="account-action account-logout"><MenuIcon name="logout"/>Cerrar sesión</button></form></div>}</div>;
}
function Sidebar({data}) {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  useEffect(() => setOpen(false), [location]);
  const toggle = useRef(null);
  const close = useRef(null);
  useEffect(() => {
    if (!open) return;
    close.current?.focus();
    const onKeyDown = event => {
      if (event.key === 'Escape') { setOpen(false); toggle.current?.focus(); }
      if (event.key === 'Tab') {
        const links = document.querySelectorAll('#side-menu a, #side-menu button');
        if (!links.length) return;
        if (event.shiftKey && document.activeElement === links[0]) { event.preventDefault(); links[links.length - 1].focus(); }
        else if (!event.shiftKey && document.activeElement === links[links.length - 1]) { event.preventDefault(); links[0].focus(); }
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [open]);
  const dismiss = () => {setOpen(false); toggle.current?.focus();};
  return <>
    <header className="topbar app-topbar"><div className="topbar-left"><button ref={toggle} type="button" className="menu-toggle" onClick={() => setOpen(true)} aria-label="Abrir menú" aria-expanded={open} aria-controls="side-menu"><MenuIcon name="menu"/></button><Link className="brand" to="/" aria-label="Ir al inicio"><span className="brand-mark">KS</span><span><strong>KS</strong><small>Control documental SST</small></span></Link></div><UserMenu data={data}/></header>
    {open && <><div className="menu-backdrop" onClick={dismiss} aria-hidden="true"/><aside id="side-menu" className="side-menu" role="dialog" aria-modal="true" aria-label="Menú principal"><div className="side-menu-header"><div className="brand"><span className="brand-mark">KS</span><span><strong>KS</strong><small>Control documental SST</small></span></div><button ref={close} type="button" className="menu-close" onClick={dismiss} aria-label="Cerrar menú"><MenuIcon name="close"/></button></div><p className="side-menu-caption">MENÚ PRINCIPAL</p><nav className="side-menu-links" aria-label="Navegación principal">{menuItems.filter(item => data.canEdit || !['manual', 'upload'].includes(item.icon)).map(item => <Link key={item.href} className={'side-menu-link '+(item.pages.includes(data.page)?'is-active':'')} to={item.href} aria-current={item.pages.includes(data.page)?'page':undefined}><MenuIcon name={item.icon}/><span>{item.label}</span></Link>)}</nav><div className="side-menu-footer"><span className="side-menu-user">{data.username}</span><form method="post" action="/salir/"><Csrf token={data.csrf}/><button type="submit" className="side-menu-link side-menu-logout"><MenuIcon name="logout"/><span>Salir</span></button></form></div></aside></>}
  </>;
}
export function Layout({data, children}) {
  return <>{data.authenticated && <Sidebar data={data}/>}<main className={'page-shell '+(!data.authenticated?'auth-shell':'')}>{data.messages.length>0 && <div className="messages" aria-live="polite">{data.messages.map((m,i)=><div className={'message message-'+m.tags} key={i}>{m.text}</div>)}</div>}{children}</main></>;
}
