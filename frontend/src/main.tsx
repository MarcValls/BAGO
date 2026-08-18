import React from 'react';
import ReactDOM from 'react-dom/client';
import { ControlPlane } from '@/app/ControlPlane';
import './styles/index.css';
import './styles/capability-redesign.css';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ControlPlane />
  </React.StrictMode>
);
