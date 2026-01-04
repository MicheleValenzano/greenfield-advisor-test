import React, { useState } from 'react';
// import { useNavigate } from 'react-router-dom';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import axios from 'axios';
import toast, { Toaster } from 'react-hot-toast';

// Loghi
import logoIntero from '../assets/LOGO_1.jpg';

const API_GATEWAY_URL = "https://localhost:8000";

function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});

  // const navigate = useNavigate();
  const { login } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();

    setFieldErrors({}); // Resetta errori precedenti
    const loadingToast = toast.loading("Accesso in corso...");
    
    try {
      const response = await axios.post(`${API_GATEWAY_URL}/login`, { email, password });
      login(response.data.access_token, response.data.user); 
      toast.success("Benvenuto!", { id: loadingToast });
      // navigate('/dashboard');
    } catch (err) {
      console.log(err);

      if (!err.response) {
        toast.error("Errore di connessione. Riprova più tardi.", { id: loadingToast });
        return;
      }

      if (err.response.status === 422 && err.response.data.errors) {
        toast.dismiss(loadingToast); // Chiusura del toast di caricamento

        const errorsObj = {};
        err.response.data.errors.forEach(errorItem => {
          errorsObj[errorItem.field] = errorItem.message;
        })
        setFieldErrors(errorsObj);
      } else {
        const errorMsg = err.response?.data?.message || err.response?.data?.detail || "Credenziali non valide";
        toast.error(errorMsg, { id: loadingToast });
      }
    }
  };

  const clearErrorField = (fieldName) => {
    setFieldErrors(prevErrors => ({ ...prevErrors, [fieldName]: undefined }));
  }

  // Helper per lo stile degli input con errori (bordo rosso)
  const getInputStyle = (fieldName) => ({
    borderColor: fieldErrors[fieldName] ? 'var(--danger, #dc3545)' : '',
  })

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px' }}>
      <Toaster position="top-center" />
      
      <div className="glass-card" style={{ maxWidth: '400px', width: '100%', textAlign: 'center', padding: '2.5rem' }}>
          
          {/* LOGO */}
          <div style={{ marginBottom: '2rem' }}>
              <img 
                  src={logoIntero} 
                  alt="GreenField Logo" 
                  style={{ 
                      height: '180px', 
                      borderRadius: '20px',
                      mixBlendMode: 'multiply',
                      marginBottom: '1rem'
                  }} 
              />
              <h2 style={{ margin: 0, color: 'var(--primary-dark)' }}>Bentornato</h2>
              <p className="text-muted">Accedi al tuo monitoraggio intelligente</p>
          </div>
          
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
                <input 
                    type="email" 
                    placeholder="Email" 
                    value={email} 
                    onChange={(e) => {
                      setEmail(e.target.value);
                      clearErrorField('email');
                    }} 
                    className={`input-field ${fieldErrors.email ? 'input-error' : ''}`}
                    style={getInputStyle('email')}
                    required 
                    autoFocus
                />
                {fieldErrors.email && (
                  <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                    Indirizzo email non valido
                  </span>
                )}
            </div>
            <div>
                <input 
                    type="password" 
                    placeholder="Password" 
                    value={password} 
                    onChange={(e) => {
                      setPassword(e.target.value);
                      clearErrorField('password');
                    }} 
                    className={`input-field ${fieldErrors.password ? 'input-error' : ''}`}
                    style={getInputStyle('password')}
                    required 
                />
                {fieldErrors.password && (
                  <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                    {fieldErrors.password}
                  </span>
                )}
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '12px', fontSize: '1rem' }}>
                Accedi
            </button>
          </form>
          
          <div style={{ marginTop: '2rem', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
            Non hai un account? <br/>
            <Link 
                to="/register" 
                style={{ color: 'var(--primary)', fontWeight: 'bold', cursor: 'pointer', textDecoration: 'underline' }}
            >
                Registrati qui
            </Link>
          </div>
      </div>
    </div>
  );
}

export default Login;