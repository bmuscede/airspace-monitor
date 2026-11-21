import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import ErrorBoundary from './components/ErrorBoundary.tsx'
import ErrorDialogProvider from './components/ErrorDialogProvider.tsx'
import ToastProvider from './components/ToastProvider.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <ToastProvider>
        <ErrorDialogProvider>
          <App />
        </ErrorDialogProvider>
      </ToastProvider>
    </ErrorBoundary>
  </StrictMode>,
)
