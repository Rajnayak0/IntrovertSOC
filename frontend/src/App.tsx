import type { ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { useAuth } from './auth';
import { Layout } from './components/Layout';
import { Alerts } from './pages/Alerts';
import { Audit } from './pages/Audit';
import { CaseDetailPage } from './pages/CaseDetail';
import { Cases } from './pages/Cases';
import { Dashboard } from './pages/Dashboard';
import { Enrichment } from './pages/Enrichment';
import { Knowledge } from './pages/Knowledge';
import { Login } from './pages/Login';
import { ModelSettings } from './pages/ModelSettings';
import { Playbooks } from './pages/Playbooks';

function RequireAuth({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted">Loading…</div>
    );
  }
  if (!me) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  if (loading) return null;
  if (me) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <RedirectIfAuthed>
            <Login />
          </RedirectIfAuthed>
        }
      />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="cases" element={<Cases />} />
        <Route path="cases/:id" element={<CaseDetailPage />} />
        <Route path="playbooks" element={<Playbooks />} />
        <Route path="knowledge" element={<Knowledge />} />
        <Route path="enrichment" element={<Enrichment />} />
        <Route path="model" element={<ModelSettings />} />
        <Route path="audit" element={<Audit />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
