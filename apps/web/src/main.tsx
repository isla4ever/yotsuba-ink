import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import './styles/entry-core.css';
import { App } from './App';
import { MotionPreferenceProvider } from './features/pipeline/layout/MotionPreferenceProvider';

const router = createBrowserRouter(
  [{ path: '*', element: <App /> }],
  { future: { v7_relativeSplatPath: true } },
);

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <MotionPreferenceProvider>
      <RouterProvider future={{ v7_startTransition: true }} router={router} />
    </MotionPreferenceProvider>
  </React.StrictMode>,
);
