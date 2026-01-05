import React, { useState, useEffect } from "react";
import axios from "axios";
import { useAuth } from "../context/AuthContext";
import { Toaster, toast } from "react-hot-toast";

const API = "https://localhost:8000";

export default function Profile() {
  const { user, token, setUser } = useAuth();
  
  // Stati per le modalità di modifica
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);

  // Gestione errori campi UI
  const [fieldErrors, setFieldErrors] = useState({});

  // Form dati profilo
  const [form, setForm] = useState({
    name: "", bio: "", phone: "", location: "", birthdate: "",
  });

  // Form password
  const [passForm, setPassForm] = useState({
    current_password: "",
    new_password: "",
    confirm_password: ""
  });

  useEffect(() => {
    if (user) {
      setForm({
        name: user.name || "",
        bio: user.bio || "",
        phone: user.phone || "",
        location: user.location || "",
        birthdate: user.birthdate || "",
      });
    }
  }, [user]);

  const clearErrorField = (fieldName) => {
    setFieldErrors(prevErrors => ({ ...prevErrors, [fieldName]: undefined }));
  }

  const getInputStyle = (fieldName) => ({
    borderColor: fieldErrors[fieldName] ? 'var(--danger, #dc3545)' : '',
  });


  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
    clearErrorField(e.target.name);
  }

  const handlePassChange = (e) => {
    setPassForm({ ...passForm, [e.target.name]: e.target.value });
    clearErrorField(e.target.name);
  }

  const handleCancel = () => {
    setIsEditingProfile(false);
    setIsChangingPassword(false);
    setFieldErrors({});
  }

  // Salvataggio Profilo (Info generali)
  const handleSaveProfile = async (e) => {
    e.preventDefault();
    setFieldErrors({});
    const toastId = toast.loading("Aggiornamento profilo...");
    try {
      const updated = await axios.put(`${API}/users/me`, form, {
        headers: { "Content-Type": "application/json" } // qui ho cancellato "Authorization": "Bearer " + token, (perché dovrebbe già farlo l'interceptor, in caso rimettilo)
      });

      setUser(updated.data);
      toast.success("Profilo aggiornato!", { id: toastId });
      setIsEditingProfile(false);
    } catch (err) {
      console.error(err);

      if (err.response && err.response.status === 422 && err.response.data.errors) {
        toast.error("Controlla i campi evidenziati in rosso.", { id: toastId });

        const errorsObj = {};
        err.response.data.errors.forEach(errorItem => {
          errorsObj[errorItem.field] = errorItem.message;
        });
        setFieldErrors(errorsObj);
      } else {
        const msg = err.response?.data?.detail || "Errore salvataggio profilo";
        toast.error(msg, { id: toastId });
      }
    }
  };

  // Salvataggio nuova Password
  const handleSavePassword = async (e) => {
    e.preventDefault();
    setFieldErrors({});

    if (passForm.new_password !== passForm.confirm_password) {
      toast.error("Le nuove password non coincidono");
      return;
    }

    const toastId = toast.loading("Modifica password in corso...");
    try {
      await axios.put(`${API}/users/me/password`, {
        current_password: passForm.current_password,
        new_password: passForm.new_password
      });

      // , {
      //   headers: { "Authorization": "Bearer " + token, "Content-Type": "application/json" }
      // }

      toast.success("Password modificata con successo!", { id: toastId });
      setIsChangingPassword(false);
      setPassForm({ current_password: "", new_password: "", confirm_password: "" });
    } catch (err) {
      console.error(err);
      if (err.response && err.response.status === 422 && err.response.data.errors) {
        toast.error("Controlla i campi evidenziati in rosso.", { id: toastId });

        const errorsObj = {};
        err.response.data.errors.forEach(errorItem => {
          errorsObj[errorItem.field] = errorItem.message;
        });
        setFieldErrors(errorsObj);
      } else {
        const msg = err.response?.data?.detail || "Errore modifica password";
        toast.error(msg, { id: toastId });
      }
    }
  };

  if (!user) return <div style={{ textAlign: "center", marginTop: 50 }}>Caricamento...</div>;

  return (
    <div className="page-container" style={{ display: "flex", justifyContent: "center", paddingBottom: '50px' }}>
      <Toaster position="top-center" />
      
      <div className="glass-card" style={{ maxWidth: '700px', width: '100%', padding: '2.5rem' }}>

        <div className="flex-between" style={{ marginBottom: '2rem' }}>
             <h2 style={{ margin: 0, color: 'var(--primary-dark)' }}>
                👤 Il mio Profilo
             </h2>
        </div>

        {/* --- HEADER UTENTE --- */}
        <div style={{ textAlign: "center", marginBottom: '2rem', paddingBottom: '2rem', borderBottom: '1px solid #eee' }}>
          <div style={{ 
            width: 90, height: 90, borderRadius: "50%", 
            background: "linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%)", 
            color: "white", 
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "2.5rem", margin: "0 auto 1rem auto", fontWeight: "bold",
            boxShadow: "0 4px 15px rgba(0,0,0,0.1)"
          }}>
            {user.name ? user.name.charAt(0).toUpperCase() : "U"}
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 'bold', color: '#333' }}>{user.name}</div>
          <div className="text-muted" style={{ fontSize: '0.95rem' }}>{user.email}</div>
        </div>

        {/* --- SEZIONE INFO PROFILO --- */}
        {!isEditingProfile ? (
          <div style={{ marginBottom: '2rem' }}>
            <div className="flex-between" style={{ marginBottom: '1rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#555' }}>Dettagli Personali</h3>
                <button 
                    onClick={() => { setIsEditingProfile(true); setIsChangingPassword(false); setFieldErrors({}); }} 
                    className="btn btn-sm btn-secondary"
                >
                    ✏️ Modifica Dati
                </button>
            </div>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <ProfileCard label="Telefono" value={user.phone} />
              <ProfileCard label="Data di Nascita" value={user.birthdate} />
              <ProfileCard label="Località" value={user.location} fullWidth />
              <ProfileCard label="Bio" value={user.bio} fullWidth isBio />
            </div>
          </div>
        ) : (
          <form onSubmit={handleSaveProfile} className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', marginBottom: '2rem', padding: '1.5rem', background: '#f8f9fa', borderRadius: '12px', border: '1px solid #eee' }}>
            <div className="flex-between">
                <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Modifica Dati</h3>
                <span style={{ fontSize: '0.8rem', color: '#888' }}>* Campi obbligatori</span>
            </div>

            <div>
                <label className="label-text">Nome Completo</label>
                <input name="name" value={form.name} onChange={handleChange} className="input-field" style={getInputStyle('name')} />
                {fieldErrors.name && <span className="error-text">{fieldErrors.name}</span>}
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                    <label className="label-text">Telefono</label>
                    <input name="phone" value={form.phone} onChange={handleChange} className="input-field" style={getInputStyle('phone')} />
                    {fieldErrors.phone && (
                      <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                        {fieldErrors.phone}
                      </span>
                    )}
                </div>
                <div>
                    <label className="label-text">Data di Nascita</label>
                    <input type="date" name="birthdate" value={form.birthdate} onChange={handleChange} className="input-field" style={getInputStyle('birthdate')} />
                    {fieldErrors.birthdate && (
                      <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                        {fieldErrors.birthdate}
                      </span>
                    )}
                </div>
            </div>

            <div>
                <label className="label-text">Località</label>
                <input name="location" value={form.location} onChange={handleChange} className="input-field" style={getInputStyle('location')} />
                {fieldErrors.location && (
                  <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                    {fieldErrors.location}
                  </span>
                )}
            </div>

            <div>
                <label className="label-text">Biografia</label>
                <textarea name="bio" value={form.bio} onChange={handleChange} className="input-field" style={{ height: '80px', resize: 'vertical', ...getInputStyle('bio') }} />
                {fieldErrors.bio && (
                  <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                    {fieldErrors.bio}
                  </span>
                )}
            </div>

            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
                <button type="submit" className="btn btn-primary" style={{ flex: 1 }}>Salva Modifiche</button>
                <button type="button" onClick={handleCancel} className="btn" style={{ background: '#e5e7eb', color: '#374151', flex: 1 }}>Annulla</button>
            </div>
          </form>
        )}

        {/* --- SEZIONE SICUREZZA (PASSWORD) --- */}
        {!isChangingPassword ? (
          <div style={{ borderTop: '1px solid #eee', paddingTop: '1.5rem', marginTop: '1rem' }}>
            <div className="flex-between">
                <h3 style={{ margin: 0, fontSize: '1.1rem', color: '#555' }}>Sicurezza</h3>
                <button 
                    onClick={() => { setIsChangingPassword(true); setIsEditingProfile(false); setFieldErrors({}); }} 
                    className="btn btn-sm" 
                    style={{ background: '#fff0f0', color: '#d32f2f', border: '1px solid #ffcdd2' }}
                >
                    🔒 Modifica Password
                </button>
            </div>
          </div>
        ) : (
          <form onSubmit={handleSavePassword} className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: '1rem', borderTop: '1px solid #eee', paddingTop: '1.5rem', marginTop: '1rem' }}>
             <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Cambia Password</h3>
             
             <div>
                <label className="label-text">Password Attuale</label>
                <input type="password" name="current_password" value={passForm.current_password} onChange={handlePassChange} className="input-field" required />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div>
                    <label className="label-text">Nuova Password</label>
                    <input type="password" name="new_password" value={passForm.new_password} onChange={handlePassChange} className="input-field" style={getInputStyle('new_password')} required />
                    {fieldErrors.new_password && (
                      <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                        {fieldErrors.new_password}
                      </span>
                    )}
                </div>
                <div>
                    <label className="label-text">Conferma Nuova Password</label>
                    <input type="password" name="confirm_password" value={passForm.confirm_password} onChange={handlePassChange} className="input-field" style={getInputStyle('confirm_password')} required />
                    {fieldErrors.confirm_password && (
                      <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                        {fieldErrors.confirm_password}
                      </span>
                    )}
                </div>
            </div>

            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
                <button type="submit" className="btn btn-primary" style={{ flex: 1 }}>Aggiorna Password</button>
                <button type="button" onClick={handleCancel} className="btn" style={{ background: '#e5e7eb', color: '#374151', flex: 1 }}>Annulla</button>
            </div>
          </form>
        )}

      </div>
    </div>
  );
}

// Piccolo componente per mostrare i dati in sola lettura (più pulito)
const ProfileCard = ({ label, value, fullWidth, isBio }) => (
    <div className="glass-card" style={{ 
        padding: '1rem', 
        background: 'rgba(255,255,255,0.6)', 
        border:'1px solid rgba(255,255,255,0.8)', 
        boxShadow: 'none',
        gridColumn: fullWidth ? 'span 2' : 'span 1'
    }}>
        <div className="text-muted text-sm uppercase" style={{ fontSize: '0.75rem', letterSpacing: '0.5px' }}>{label}</div>
        <div style={{ fontWeight: 500, fontSize: '1rem', marginTop: '4px', lineHeight: isBio ? 1.5 : 1 }}>
            {value || <span style={{ fontStyle: 'italic', color: '#aaa' }}>Non specificato</span>}
        </div>
    </div>
);