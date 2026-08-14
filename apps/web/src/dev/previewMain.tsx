import React from 'react';
import ReactDOM from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { MotionPreferenceProvider } from '../features/pipeline/layout/MotionPreferenceProvider';
import { StagePreviewApp } from './StagePreviewApp';

export function mountStagePreview(container: HTMLElement) {
  const router = createBrowserRouter(
    [{ path: '*', element: <StagePreviewApp /> }],
    { future: { v7_relativeSplatPath: true } },
  );
  ReactDOM.createRoot(container).render(
    <React.StrictMode>
      <MotionPreferenceProvider>
        <RouterProvider future={{ v7_startTransition: true }} router={router} />
      </MotionPreferenceProvider>
    </React.StrictMode>,
  );
}
