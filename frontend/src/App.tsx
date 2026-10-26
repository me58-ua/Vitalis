import { BrowserRouter, Link, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthProvider';
import { PublicLayout } from './layouts/PublicLayout';
import { HomePage } from './pages/HomePage';

export function App() {
  return <BrowserRouter><AuthProvider><Routes><Route element={<PublicLayout />}>
    <Route path="/" element={<HomePage />} />
    <Route path="*" element={<main id="contenido" className="not-found section-container"><h1>Página no disponible</h1><Link to="/">Volver al inicio</Link></main>} />
  </Route></Routes></AuthProvider></BrowserRouter>;
}
