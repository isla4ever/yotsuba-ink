import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import './styles/entry-core.css';
import { App } from './App';
import { MotionPreferenceProvider } from './features/pipeline/layout/MotionPreferenceProvider';

const root = document.getElementById('root')!;

if (import.meta.env.DEV && window.location.pathname.startsWith('/__preview')) {
  // Offline stage design preview; excluded from production bundles.
  void import('./dev/previewMain').then(({ mountStagePreview }) => mountStagePreview(root));
} else {
  const router = createBrowserRouter(
    [{ path: '*', element: <App /> }],
    { future: { v7_relativeSplatPath: true } },
  );

  ReactDOM.createRoot(root).render(
    <React.StrictMode>
      <MotionPreferenceProvider>
        <RouterProvider future={{ v7_startTransition: true }} router={router} />
      </MotionPreferenceProvider>
    </React.StrictMode>,
  );
}
