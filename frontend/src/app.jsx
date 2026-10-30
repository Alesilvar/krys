import React from 'react';
import {createRoot} from 'react-dom/client';
import Dashboard from './dashboard';
import {Layout} from './components';
import {Login, FormPage, DeletePage, Letters, Upload, Profile} from './pages';

const data=JSON.parse(document.getElementById('krys-data').textContent);
const pages={profile:Profile,login:Login,dashboard:Dashboard,manual_record:FormPage,edit_presentation:FormPage,edit_letter:FormPage,edit_movement:FormPage,delete_letter:DeletePage,letters:Letters,upload_letters:Upload};
const Page=pages[data.page];
if (Page) {
  createRoot(document.getElementById('app-root')).render(<Layout data={data}><Page data={data}/></Layout>);
  document.getElementById('app-fallback').hidden=true;
}
