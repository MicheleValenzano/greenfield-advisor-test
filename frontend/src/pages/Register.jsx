import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import axios from 'axios';
import toast, { Toaster } from 'react-hot-toast';

// Loghi (assumendo che siano nella stessa cartella assets di Login)
import logoIntero from '../assets/LOGO_1.jpg';

const API_GATEWAY_URL = "https://localhost:8000";

function Register() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [fieldErrors, setFieldErrors] = useState({});
  
  const navigate = useNavigate();

  // Funzione per pulire gli errori di un campo specifico
  const clearErrorField = (fieldName) => {
    setFieldErrors(prevErrors => ({ ...prevErrors, [fieldName]: undefined }));
  }

  // Helper per lo stile degli input con errori (bordo rosso)
  const getInputStyle = (fieldName) => ({
    borderColor: fieldErrors[fieldName] ? 'var(--danger, #dc3545)' : '',
  });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFieldErrors({}); // Resetta errori precedenti

    if (password !== confirmPassword) {
      toast.error("Le password non coincidono!");
      return;
    }

    const loadingToast = toast.loading("Creazione account in corso...");

    try {
      const payload = {
        name: name,
        email: email,
        password: password
      };

      await axios.post(`${API_GATEWAY_URL}/register`, payload); // Assicurati che l'endpoint sia corretto (es. /auth/register o solo /register a seconda del backend)
      
      toast.success("Account creato con successo!", { id: loadingToast });
      setTimeout(() => navigate('/login'), 2000);

    } catch (err) {
      console.error("Errore Registrazione:", err);

      if (!err.response) {
        toast.error("Errore di connessione. Riprova più tardi.", { id: loadingToast });
        return;
      }

      if (err.response.status === 422 && err.response.data.errors) {
        toast.error("Controlla i campi evidenziati in rosso.", { id: loadingToast });

        const errorsObj = {};
        err.response.data.errors.forEach(errorItem => {
          errorsObj[errorItem.field] = errorItem.message;
        });
        setFieldErrors(errorsObj);
      } else {
        const errorMsg = err.response?.data?.detail || err.response?.data?.message || "Impossibile registrare l'utente.";
        toast.error(errorMsg, { id: loadingToast });
      }
    }
  };

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
                      height: '150px', 
                      borderRadius: '20px',
                      mixBlendMode: 'multiply',
                      marginBottom: '1rem'
                  }} 
              />
              <h2 style={{ margin: 0, color: 'var(--primary-dark)' }}>Unisciti a Noi</h2>
              <p className="text-muted">Inizia a monitorare le tue colture oggi</p>
          </div>
          
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div>
                <input 
                    type="text" 
                    placeholder="Nome e Cognome" 
                    value={name} 
                    onChange={(e) => { setName(e.target.value); clearErrorField('name'); }}
                    className={`input-field ${fieldErrors.name ? 'input-error' : ''}`}
                    style={getInputStyle('name')}
                    required 
                />
                {fieldErrors.name && (
                  <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                    {fieldErrors.name}
                  </span>
                )}
            </div>
            <div>
                <input 
                    type="email" 
                    placeholder="Email" 
                    value={email} 
                    onChange={(e) => { setEmail(e.target.value); clearErrorField('email'); }} 
                    className={`input-field ${fieldErrors.email ? 'input-error' : ''}`}
                    style={getInputStyle('email')}
                    required 
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
                    onChange={(e) => { setPassword(e.target.value); clearErrorField('password'); }} 
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
            <div>
                <input 
                    type="password" 
                    placeholder="Conferma Password" 
                    value={confirmPassword} 
                    onChange={(e) => { setConfirmPassword(e.target.value); clearErrorField('confirmPassword'); }} 
                    className={`input-field ${fieldErrors.confirmPassword ? 'input-error' : ''}`}
                    style={getInputStyle('confirmPassword')}
                    required 
                />
                {fieldErrors.confirmPassword && (
                  <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                    {fieldErrors.confirmPassword}
                  </span>
                )}
            </div>

            <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '12px', fontSize: '1rem', marginTop: '10px' }}>
                Crea Account
            </button>
          </form>
          
          <div style={{ marginTop: '2rem', fontSize: '0.9rem', color: 'var(--text-muted)' }}>
            Hai già un account? <br/>
            <Link 
                to="/login"
                style={{ color: 'var(--primary)', fontWeight: 'bold', cursor: 'pointer', textDecoration: 'underline' }}
            >
                Accedi qui
            </Link>
          </div>
      </div>
    </div>
  );
}

export default Register;