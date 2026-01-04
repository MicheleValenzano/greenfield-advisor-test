// frontend/src/App.jsx
import { Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Register from './pages/Register';
import FieldManager from './pages/FieldManager';
import Dashboard from './pages/Dashboard';
import Monitoring from './pages/Monitoring';
import AIDashboard from './pages/AIDashboard';
import SensorTypeManager from './pages/SensorTypeManager'; // <--- IMPORTA QUI
import Profile from './pages/Profile';
import { ProtectedRoute } from './context/AuthContext'; // Importa quello aggiornato
import MainLayout from './layouts/MainLayout';

function App() {
  return (
    <Routes>
      {/* Rotte Pubbliche */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Rotte Protette */}
      <Route element={
        <ProtectedRoute>
          <MainLayout />
        </ProtectedRoute>
      }>
          {/* Redirect da root a dashboard */}
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/fields" element={<FieldManager />} />
          <Route path="/monitoring" element={<Monitoring />} />
          <Route path="/ai-dashboard" element={<AIDashboard />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/settings/sensors" element={<SensorTypeManager />} />
      </Route>
      
      {/* Fallback */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;