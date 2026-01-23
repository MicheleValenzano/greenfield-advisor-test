import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import toast, { Toaster } from 'react-hot-toast';


delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const API_GATEWAY_URL = "https://localhost:8000";

const tractorIcon = new L.Icon({
    iconUrl: 'https://cdn-icons-png.flaticon.com/512/2083/2083236.png', 
    iconSize: [35, 35],
    iconAnchor: [17, 35],
    popupAnchor: [0, -35]
});

function Dashboard() {
    const { token, user, setSelectedField } = useAuth();
    const navigate = useNavigate();
    
    const [fields, setFields] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [stats, setStats] = useState({ totalHectares: 0, fieldCount: 0 });
    const [loading, setLoading] = useState(true);


    useEffect(() => {
        const fetchData = async () => {
            try {
                const fieldsRes = await axios.get(`${API_GATEWAY_URL}/fields`);
                setFields(fieldsRes.data);

                const alertsRes = await axios.get(`${API_GATEWAY_URL}/alerts?limit=10`);
                setAlerts(alertsRes.data);

                const totalHectares = fieldsRes.data.reduce((acc, curr) => acc + (curr.size || 0), 0);
                
                setStats({
                    totalHectares: totalHectares.toFixed(1),
                    fieldCount: fieldsRes.data.length
                });

            } catch (error) {
                console.error("Errore dashboard:", error);

                if (!error.response) {
                    toast.error("Errore di connessione. Riprova più tardi.");
                } else if (error.response.status != 401) {
                    const errorMsg = error.response?.data?.detail || error.response?.data?.message || "Errore nel caricamento della dashboard";
                    toast.error(errorMsg);
                }
            } finally {
                setLoading(false);
            }
        };

        if (token) {
            fetchData();
        }

    }, [token]);

    // CANCELLA TUTTI GLI AVVISI
    const handleClearAlerts = async () => {
        if (alerts.length === 0) return;
        if (!window.confirm("Vuoi archiviare tutti gli avvisi visualizzati in Dashboard?")) return;

        try {
            await axios.post(`${API_GATEWAY_URL}/archive-alerts`);
            toast.success("Avvisi archiviati con successo!");
            setAlerts([]); // Pulisce la vista immediatamente
        } catch (err) {
            console.error(err);
            toast.error("Errore durante l'archiviazione");
        }
    };

    const getFieldName = (fieldId) => {
        const foundField = fields.find(f => f.field === fieldId);
        return foundField ? foundField.name : "field eliminata";
    }

    const formatAlertDate = (timestamp) => {
        if (!timestamp) return "";
        const date = new Date(timestamp);
        const today = new Date();

        // Controlliamo se è lo stesso giorno, mese e anno
        const isToday = date.getDate() === today.getDate() &&
                        date.getMonth() === today.getMonth() &&
                        date.getFullYear() === today.getFullYear();

        if (isToday) {
            // Solo Ora:Minuti:Secondi
            return date.toLocaleTimeString([], { 
                hour: '2-digit', minute: '2-digit', second: '2-digit' 
            });
        } else {
            // Data Completa + Ora
            return date.toLocaleString([], {
                day: '2-digit', month: '2-digit', year: 'numeric',
                hour: '2-digit', minute: '2-digit', second: '2-digit'
            });
        }
    };

    return (
        <div className="page-container">
            <Toaster position="top-right" />
            
            {/* WELCOME BANNER */}
            <div className="glass-card" style={{ 
                background: 'linear-gradient(120deg, #10b981 0%, #059669 100%)', 
                color: 'white', 
                marginBottom: '2rem',
                position: 'relative',
                overflow: 'hidden',
                border: 'none'
            }}>
                <div style={{ position:'relative', zIndex: 2 }}>
                    <h1 style={{ margin: 0, fontSize: '2rem' }}>Ciao, {user?.name || 'Agricoltore'}! 👋</h1>
                    <p style={{ opacity: 0.9, marginTop: '0.5rem' }}>La tua azienda è operativa al 100%. Ecco cosa succede oggi.</p>
                    <button className="btn" style={{ background: 'white', color: '#059669', marginTop: '1.5rem' }} onClick={() => navigate('/fields')}>
                        Gestisci Campi
                    </button>
                </div>
                <div style={{
                    position: 'absolute', top: '-50%', right: '-10%', 
                    width: '300px', height: '300px', background: 'rgba(255,255,255,0.1)', 
                    borderRadius: '50%', pointerEvents: 'none'
                }}></div>
            </div>

            <div className="bento-grid">
                <div className="glass-card">
                    <div className="text-muted text-sm font-bold uppercase">Estensione</div>
                    <div className="text-gradient" style={{ fontSize: '3rem', fontWeight: 800, lineHeight: 1 }}>
                        {stats.totalHectares} <span style={{ fontSize: '1rem', color: '#888' }}>ha</span>
                    </div>
                    <div className="mt-2 text-sm text-muted">{stats.fieldCount} campi registrati</div>
                </div>
                
                <div className="glass-card">
                    <div className="text-muted text-sm font-bold uppercase">Stato Salute</div>
                    <div style={{ fontSize: '2.5rem', fontWeight: 800, color: alerts.length > 0 ? 'var(--accent)' : 'var(--primary)' }}>
                        {alerts.length > 0 ? 'ATTENZIONE' : 'OTTIMO'}
                    </div>
                    <div className="mt-2 text-sm text-muted">{alerts.length} ultime notifiche</div>
                </div>

                <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                    <div className="text-muted text-sm font-bold uppercase mb-4">Accesso Rapido</div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                        <button onClick={() => navigate('/monitoring')} className="btn btn-secondary" style={{ width: '100%' }}>
                            📊 Monitor
                        </button>
                        <button onClick={() => navigate('/ai-dashboard')} className="btn" style={{ background: '#7c3aed', color: 'white', width: '100%' }}>
                            🧠 AI Brain
                        </button>
                    </div>
                </div>
            </div>

            <div className="split-layout">
                
                {/* MAPPA */}
                <div className="glass-card" style={{ padding: 0, overflow: 'hidden', minHeight: '500px', display: 'flex', flexDirection: 'column' }}>
                    <div style={{ padding: '1rem 1.5rem', borderBottom: '1px solid var(--glass-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <h3 style={{ margin: 0 }}>🌍 Mappa Satellitare</h3>
                        <span className="text-sm text-muted">Live view</span>
                    </div>
                    <div style={{ flex: 1, width: '100%' }}>
                        <MapContainer center={[41.9028, 12.4964]} zoom={6} style={{ height: '100%', width: '100%' }}>
                            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                            {fields.map(field => {
                                if (!field.latitude || !field.longitude) return null;
                                return (
                                    <Marker key={field.field} position={[field.latitude, field.longitude]} icon={tractorIcon}>
                                        <Popup>
                                            <strong>{field.name}</strong><br/>
                                            {field.cultivation_type}<br/>
                                            <button 
                                                className="btn btn-primary"
                                                style={{ padding: '5px 10px', fontSize: '0.8rem', marginTop: '5px' }}
                                                onClick={() => { setSelectedField(field); navigate('/monitoring'); }}
                                            >
                                                Vai al Monitor
                                            </button>
                                        </Popup>
                                    </Marker>
                                )
                            })}
                        </MapContainer>
                    </div>
                </div>

                {/* NOTIFICHE */}
                <div className="glass-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                        <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
                            🔔 Ultime Notifiche
                        </h3>
                        {alerts.length > 0 && (
                            <button 
                                onClick={handleClearAlerts}
                                className="btn btn-sm"
                                style={{ 
                                    background: '#fee2e2', 
                                    color: '#b91c1c', 
                                    border: '1px solid #fca5a5',
                                    fontSize: '0.8rem',
                                    padding: '4px 10px',
                                    borderRadius: '8px',
                                    cursor: 'pointer'
                                }}
                            >
                                Cancella Tutto
                            </button>
                        )}
                    </div>
                    
                    {loading ? <p>Caricamento...</p> : (
                        <div style={{ overflowY: 'auto', maxHeight: '420px' }}>
                            {alerts.length === 0 ? (
                                <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                                    <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✅</div>
                                    Nessun problema rilevato.
                                </div>
                            ) : (
                                alerts.map((alert, idx) => (
                                    <div key={idx} style={{
                                        padding: '1rem',
                                        marginBottom: '1rem',
                                        borderRadius: '12px',
                                        background: '#fef2f2',
                                        borderLeft: '4px solid #ef4444'
                                    }}>
                                        <div style={{ fontWeight: 'bold', color: '#ef4444', display: 'flex', justifyContent: 'space-between' }}>
                                            {getFieldName(alert.field)} - {alert.sensor_type.toUpperCase()}
                                            <span style={{ fontSize: '0.75rem', fontWeight: 'normal', opacity: 0.8, color: '#666' }}>
                                                {formatAlertDate(alert.timestamp)}
                                            </span>
                                        </div>
                                        <div style={{ fontSize: '0.9rem', marginTop: '0.5rem', color: '#333' }}>{alert.message}</div>
                                    </div>
                                ))
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default Dashboard;