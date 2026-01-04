import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useAuth } from '../context/AuthContext';
import toast, { Toaster } from 'react-hot-toast';

const API_GATEWAY_URL = "https://localhost:8080";

const SensorTypeManager = () => {
    const { token, logout } = useAuth();
    const [sensorTypes, setSensorTypes] = useState([]);
    const [typeForm, setTypeForm] = useState({ name: '', description: '', unit: '' });
    const [loading, setLoading] = useState(true);

    const getAuthHeader = () => ({ headers: { Authorization: `Bearer ${token}` } });

    const fetchSensorTypes = async () => {
        try {
            const response = await axios.get(`${API_GATEWAY_URL}/sensors/types`, getAuthHeader());
            setSensorTypes(response.data);
        } catch (error) {
            console.error("Errore fetch tipi sensori", error);
            if (error.response?.status === 401) logout();
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (token) fetchSensorTypes();
    }, [token]);

    const handleAddType = async (e) => {
        e.preventDefault();
        if (!typeForm.name || !typeForm.description || !typeForm.unit) {
            toast.error("Tutti i campi sono obbligatori");
            return;
        }
        try {
            await axios.post(`${API_GATEWAY_URL}/sensors/types`, typeForm, getAuthHeader());
            toast.success("Nuova tipologia aggiunta");
            setTypeForm({ name: '', description: '', unit: '' });
            fetchSensorTypes();
        } catch (err) {
            toast.error(err.response?.data?.detail || "Errore creazione tipo");
        }
    };

    const handleDeleteType = async (id) => {
        if (!window.confirm("Rimuovere questa tipologia? I sensori esistenti di questo tipo potrebbero smettere di funzionare correttamente.")) return;
        try {
            await axios.delete(`${API_GATEWAY_URL}/sensors/types/${id}`, getAuthHeader());
            toast.success("Tipologia rimossa");
            fetchSensorTypes();
        } catch (err) {
            toast.error("Errore eliminazione");
        }
    };

    return (
        <div className="page-container">
            <Toaster position="top-right" />

            {/* HEADER */}
            <div className="glass-card" style={{ background: 'linear-gradient(135deg, #6366f1 0%, #4f46e5 100%)', color: 'white', marginBottom: '2rem', border: 'none' }}>
                <h2 style={{ margin: 0, fontSize: '2rem' }}>🛠️ Configurazioni</h2>
                <p style={{ opacity: 0.9, marginTop: '0.5rem' }}>Gestisci le tipologie di sensori supportate dal sistema.</p>
            </div>

            <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', alignItems: 'flex-start' }}>
                
                {/* FORM AGGIUNTA */}
                <div className="glass-card" style={{ flex: 1, minWidth: '300px' }}>
                    <h3 style={{ marginTop: 0, color: '#374151' }}>Aggiungi Tipologia</h3>
                    <form onSubmit={handleAddType} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <div>
                            <label className="text-sm font-bold text-gray-700">Codice/Nome</label>
                            <input 
                                placeholder="Es. DHT22" 
                                value={typeForm.name} 
                                onChange={e => setTypeForm({...typeForm, name: e.target.value.toUpperCase()})} 
                                className="input-field" 
                            />
                            <small className="text-muted">Identificativo univoco (es. DHT22, SOIL_MOISTURE)</small>
                        </div>
                        
                        <div>
                            <label className="text-sm font-bold text-gray-700">Descrizione</label>
                            <input 
                                placeholder="Es. Sensore Temp/Umidità" 
                                value={typeForm.description} 
                                onChange={e => setTypeForm({...typeForm, description: e.target.value})} 
                                className="input-field" 
                            />
                        </div>

                        <div>
                            <label className="text-sm font-bold text-gray-700">Unità di Misura</label>
                            <input 
                                placeholder="Es. °C, %" 
                                value={typeForm.unit} 
                                onChange={e => setTypeForm({...typeForm, unit: e.target.value})} 
                                className="input-field" 
                            />
                        </div>

                        <button className="btn btn-primary" style={{ marginTop: '1rem' }}>Salva Tipologia</button>
                    </form>
                </div>

                {/* LISTA TIPI */}
                <div className="glass-card" style={{ flex: 2, minWidth: '300px' }}>
                    <h3 style={{ marginTop: 0, color: '#374151' }}>Tipologie Attive</h3>
                    
                    {loading ? <p>Caricamento...</p> : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '1rem' }}>
                            {sensorTypes.length === 0 && <p className="text-muted">Nessuna tipologia definita.</p>}
                            
                            {sensorTypes.map(t => (
                                <div key={t.id} style={{ 
                                    background: '#f8fafc', 
                                    border: '1px solid #e2e8f0', 
                                    borderRadius: '8px', 
                                    padding: '1rem', 
                                    position: 'relative' 
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                                        <div style={{ fontWeight: 'bold', color: '#1e293b', fontSize: '1.1rem' }}>{t.name}</div>
                                        <button 
                                            onClick={() => handleDeleteType(t.id)} 
                                            style={{ border: 'none', background: 'transparent', color: '#ef4444', cursor: 'pointer', padding: 0 }}
                                            title="Elimina"
                                        >
                                            🗑️
                                        </button>
                                    </div>
                                    
                                    <div style={{ fontSize: '0.9rem', color: '#64748b', margin: '8px 0' }}>{t.description}</div>
                                    
                                    <div style={{ marginTop: 'auto' }}>
                                        <span className="badge" style={{ background: '#e0f2fe', color: '#0369a1' }}>
                                            Unità: {t.unit}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>

            </div>
        </div>
    );
};

export default SensorTypeManager;