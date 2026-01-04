import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import toast, { Toaster } from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';

const API_GATEWAY_URL = "https://localhost:8080";

// Genera un colore univoco per il grafico
const stringToColor = (str) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const c = (hash & 0x00FFFFFF).toString(16).toUpperCase();
    return '#' + '00000'.substring(0, 6 - c.length) + c;
};

// --- HELPER METEO (Conversione codici WMO in emoji) ---
const getWmoIcon = (code) => {
    if (code === 0) return '☀️'; // Sereno
    if ([1, 2, 3].includes(code)) return '⛅'; // Nuvoloso
    if ([45, 48].includes(code)) return '🌫️'; // Nebbia
    if ([51, 53, 55, 61, 63, 65, 80, 81, 82].includes(code)) return '🌧️'; // Pioggia
    if ([71, 73, 75, 77, 85, 86].includes(code)) return '❄️'; // Neve
    if (code >= 95) return '⛈️'; // Temporale
    return '🌡️';
};

const getDayName = (dateStr) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('it-IT', { weekday: 'short' }); // Es: Lun, Mar
};

function Monitoring() {
    const { logout, token, selectedField } = useAuth();
    const navigate = useNavigate();

    const [readings, setReadings] = useState([]);
    const [weather, setWeather] = useState(null);
    const [forecast, setForecast] = useState([]); // Stato per le previsioni
    const [authorizedSensors, setAuthorizedSensors] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [rules, setRules] = useState([]);
    const [sensorTypes, setSensorTypes] = useState([]);
    
    const [newSensor, setNewSensor] = useState({ sensor_id: '', location: '', type: '' });
    const [newRule, setNewRule] = useState({ parameter: 'temperature', operator: '>', threshold: '', message: '' });
    const [loading, setLoading] = useState(true);

    useEffect(() => { 
        if (!selectedField) navigate('/fields'); 
    }, [selectedField, navigate]);

    const getAuthHeader = () => ({ headers: { Authorization: `Bearer ${token}` } });
    
    const formatXAxis = (tickItem) => {
        if (!tickItem) return '';
        return new Date(tickItem).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

    // --- HELPER PER TROVARE L'UNITÀ DI MISURA ---
    const getUnit = (key) => {
        if (key === 'temperature') return '°C';
        if (key === 'humidity') return '%';
        if (key === 'soil_moisture') return '%';
        const found = sensorTypes.find(t => t.name.toLowerCase().replace(/ /g, "_") === key);
        return found ? found.unit : '';
    };

    const fetchData = async () => {
        if (!selectedField) { setLoading(false); return; }
        const fieldId = selectedField.id || selectedField._id;
        if (!fieldId) { setLoading(false); return; }

        try {
            const config = getAuthHeader();
            const fieldQuery = `?field_id=${fieldId}`;
            
            // --- LOGICA INTELLIGENTE PER LOCATION (Coordinate o Città) ---
            let weatherQuery = '';
            const loc = selectedField.location || "Roma";
            
            // Prova a splittare per virgola (es. "45.4, 9.1")
            const parts = loc.split(',').map(s => s.trim());
            const isCoords = parts.length === 2 && !isNaN(parts[0]) && !isNaN(parts[1]);

            if (isCoords) {
                // Se sono coordinate, usa lat/lon
                weatherQuery = `lat=${parts[0]}&lon=${parts[1]}`;
            } else {
                // Altrimenti tratta come nome città (rimuovendo eventuali note tra parentesi)
                const cityName = loc.split('(')[0].trim();
                weatherQuery = `city=${encodeURIComponent(cityName)}`;
            }
            // -------------------------------------------------------------

            const results = await Promise.allSettled([
                axios.get(`${API_GATEWAY_URL}/weather?${weatherQuery}`, config),
                axios.get(`${API_GATEWAY_URL}/sensors/readings${fieldQuery}&limit=50`, config),
                axios.get(`${API_GATEWAY_URL}/sensors/authorized${fieldQuery}`, config),
                axios.get(`${API_GATEWAY_URL}/sensors/rules${fieldQuery}`, config),
                axios.get(`${API_GATEWAY_URL}/sensors/alerts${fieldQuery}&limit=10`, config),
                axios.get(`${API_GATEWAY_URL}/sensors/types`, config),
                axios.get(`${API_GATEWAY_URL}/forecast?${weatherQuery}`, config)
            ]);

            if (results[0].status === 'fulfilled') setWeather(results[0].value.data);
            if (results[1].status === 'fulfilled') setReadings([...results[1].value.data].reverse());
            if (results[2].status === 'fulfilled') setAuthorizedSensors(results[2].value.data);
            if (results[3].status === 'fulfilled') setRules(results[3].value.data.map(r => ({ ...r, id: r._id || r.id })));
            if (results[4].status === 'fulfilled') setAlerts(results[4].value.data);
            if (results[5].status === 'fulfilled') setSensorTypes(results[5].value.data);
            if (results[6].status === 'fulfilled') setForecast(results[6].value.data);

        } catch (error) { 
            if (error.response?.status === 401) logout(); 
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const i = setInterval(fetchData, 5000); 
        return () => clearInterval(i);
    }, [selectedField]);

    // HANDLERS
    const handleRegisterSensor = async (e) => {
        e.preventDefault();
        const fieldId = selectedField?.id || selectedField?._id;
        if (!newSensor.type) return toast.error("Seleziona tipo");
        try {
            await axios.post(`${API_GATEWAY_URL}/sensors/register`, { ...newSensor, field_id: fieldId, active: true }, getAuthHeader());
            toast.success("Sensore aggiunto");
            setNewSensor({ sensor_id: '', location: '', type: '' });
            fetchData();
        } catch (err) { toast.error(err.response?.data?.detail || "Errore"); }
    };

    // --- NUOVA FUNZIONE: CANCELLA ALLARMI ---
    const handleClearAlerts = async () => {
        const fieldId = selectedField?.id || selectedField?._id;
        if (!fieldId || alerts.length === 0) return;
        
        if (!confirm("Archiviare tutti gli allarmi visualizzati?")) return;

        try {
            await axios.delete(`${API_GATEWAY_URL}/sensors/alerts`, { 
                headers: { Authorization: `Bearer ${token}` },
                params: { field_id: fieldId }
            });
            toast.success("Allarmi archiviati");
            setAlerts([]); // Pulisce subito la vista
        } catch (err) {
            console.error(err);
            toast.error("Errore durante l'archiviazione");
        }
    };

    const handleDeleteSensor = async (id) => {
        if (!confirm("Rimuovere?")) return;
        try { await axios.delete(`${API_GATEWAY_URL}/sensors/${id}`, getAuthHeader()); toast.success("Rimosso"); fetchData(); } catch { toast.error("Errore"); }
    };

    const handleAddRule = async (e) => {
        e.preventDefault();
        const fieldId = selectedField?.id || selectedField?._id;
        try {
            await axios.post(`${API_GATEWAY_URL}/sensors/rules`, { ...newRule, threshold: parseFloat(newRule.threshold), field_id: fieldId }, getAuthHeader());
            toast.success("Regola creata"); setNewRule({ parameter: 'temperature', operator: '>', threshold: '', message: '' }); fetchData();
        } catch { toast.error("Errore regola"); }
    };

    const handleDeleteRule = async (id) => {
        try { await axios.delete(`${API_GATEWAY_URL}/sensors/rules/${id}`, getAuthHeader()); toast.success("Eliminata"); fetchData(); } catch { toast.error("Errore"); }
    };

    return (
        <div className="page-container">
            <Toaster position="top-right" />
            
            <div className="glass-card" style={{ background: 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)', color: 'white', marginBottom: '2rem', border: 'none' }}>
                <h2 style={{ margin: 0, fontSize: '2rem' }}>📡 Monitoraggio Live</h2>
                <p style={{ opacity: 0.9, marginTop: '0.5rem' }}>Campo: <strong>{selectedField?.name}</strong></p>
            </div>

            {loading ? <div style={{textAlign:'center', marginTop: '50px'}}>Caricamento...</div> : (
                <div className="split-layout">
                    
                    {/* COLONNA SINISTRA */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        
                        {/* CHART DINAMICO */}
                        <div className="glass-card">
                            <h3 style={{ marginTop: 0, marginBottom: '1rem', color: '#1e3a8a' }}>📊 Andamento Sensori</h3>
                            <ResponsiveContainer width="100%" height={300}>
                                <AreaChart data={readings}>
                                    <defs>
                                        {sensorTypes.map(t => {
                                            const color = stringToColor(t.name);
                                            return (
                                                <linearGradient key={t.id} id={`grad${t.name}`} x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor={color} stopOpacity={0.8}/>
                                                    <stop offset="95%" stopColor={color} stopOpacity={0}/>
                                                </linearGradient>
                                            )
                                        })}
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                                    <XAxis dataKey="timestamp" tickFormatter={formatXAxis} axisLine={false} tickLine={false} style={{fontSize:'0.75rem'}} />
                                    <YAxis axisLine={false} tickLine={false} />
                                    <Tooltip contentStyle={{ borderRadius: '12px' }} />
                                    
                                    {sensorTypes.map(t => {
                                        let dataKey = t.name.toLowerCase().replace(/ /g, "_");
                                        if(t.name.toUpperCase().includes("TEMP")) dataKey = "temperature";
                                        else if(t.name.toUpperCase().includes("HUM") || t.name.toUpperCase().includes("UMID")) dataKey = "humidity";
                                        else if(t.name.toUpperCase().includes("SOIL") || t.name.toUpperCase().includes("SUOLO")) dataKey = "soil_moisture";

                                        return (
                                            <Area 
                                                key={t.id}
                                                type="monotone" 
                                                dataKey={dataKey} 
                                                name={`${t.name} (${t.unit})`}
                                                stroke={stringToColor(t.name)} 
                                                fill={`url(#grad${t.name})`} 
                                                connectNulls={true} 
                                            />
                                        );
                                    })}
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>

                        {/* TABELLA LOG */}
                        <div className="glass-card">
                            <h3 style={{ marginTop: 0, marginBottom: '1rem', color: '#1e3a8a' }}>📋 Log Recenti</h3>
                            <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                                <table className="modern-table" style={{width:'100%'}}>
                                    <thead><tr style={{textAlign:'left', color:'#6b7280'}}><th>Orario</th><th>ID Sensore</th><th>Valori</th></tr></thead>
                                    <tbody>
                                        {[...readings].reverse().map((r, i) => (
                                            <tr key={i} style={{borderBottom:'1px solid #f3f4f6'}}>
                                                <td style={{padding:'10px', fontSize:'0.9rem', color:'#9ca3af'}}>{new Date(r.timestamp).toLocaleTimeString()}</td>
                                                <td style={{padding:'10px', fontWeight:'600', color:'#4b5563'}}>{r.sensor_id}</td>
                                                <td style={{padding:'10px'}}>
                                                    <div style={{ display: 'flex', gap: '10px', flexWrap:'wrap' }}>
                                                        {Object.keys(r).map(key => {
                                                            if (['timestamp', 'sensor_id', '_id'].includes(key)) return null;
                                                            return (
                                                                <span key={key} style={{
                                                                    background: '#eff6ff', color: '#1d4ed8', 
                                                                    padding: '2px 8px', borderRadius: '4px', fontSize: '0.85rem', 
                                                                    fontWeight: '500', textTransform: 'capitalize'
                                                                }}>
                                                                    {key}: {r[key]} <small style={{opacity:0.7}}>{getUnit(key)}</small>
                                                                </span>
                                                            )
                                                        })}
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    {/* COLONNA DESTRA */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        
                        {/* WIDGET METEO & PREVISIONI */}
                        <div className="glass-card" style={{ textAlign: 'center', background: 'linear-gradient(to bottom, #eff6ff, #fff)' }}>
                            <h3 style={{ margin: 0, color: '#1d4ed8' }}>Meteo Attuale</h3>
                            {weather ? (
                                <div style={{marginTop:'10px'}}>
                                    {/* Icona Attuale */}
                                    <div style={{ fontSize: '3.5rem', marginBottom:'-10px' }}>
                                        {getWmoIcon(weather.code)}
                                    </div>
                                    <div style={{ fontSize: '2.5rem', fontWeight: 800, color:'#1e3a8a' }}>{weather.temperature}°C</div>
                                    <div style={{ color: '#6b7280', fontSize:'0.9rem', marginBottom:'1rem' }}>
                                        📍 {weather.city} <br/>
                                        <span style={{fontWeight:'500', color:'#4b5563'}}>{weather.description}</span>
                                    </div>

                                    {/* PREVISIONI 5 GIORNI */}
                                    {forecast.length > 0 && (
                                        <div style={{ 
                                            display: 'flex', 
                                            justifyContent: 'space-between', 
                                            marginTop: '1.5rem', 
                                            paddingTop: '1rem',
                                            borderTop: '1px solid #dbeafe' 
                                        }}>
                                            {forecast.map((day, idx) => (
                                                <div key={idx} style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:'4px' }}>
                                                    <span style={{ fontSize:'0.75rem', fontWeight:'bold', color:'#64748b' }}>
                                                        {getDayName(day.date)}
                                                    </span>
                                                    <span style={{ fontSize:'1.5rem' }}>{getWmoIcon(day.code)}</span>
                                                    <div style={{ fontSize:'0.8rem', fontWeight:'600', color:'#1e40af', display:'flex', flexDirection:'column' }}>
                                                        <span>{Math.round(day.max_temp)}°</span>
                                                        <span style={{fontSize:'0.7rem', color:'#94a3b8', fontWeight:'normal'}}>{Math.round(day.min_temp)}°</span>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ) : <p className="text-muted">Caricamento...</p>}
                        </div>
                        
                        {/* ALERT BOX (AGGIORNATO CON PULSANTE) */}
                        <div className="glass-card" style={{ background: '#fef2f2', border: '1px solid #fee2e2' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                                <h3 style={{ color: '#dc2626', margin: 0, display: 'flex', alignItems: 'center', gap: '10px' }}>
                                    ⚠️ Allarmi Attivi
                                </h3>
                                {alerts.length > 0 && (
                                    <button 
                                        onClick={handleClearAlerts}
                                        className="btn" 
                                        style={{ 
                                            background: '#fee2e2', 
                                            color: '#b91c1c', 
                                            border: '1px solid #fca5a5', 
                                            padding: '4px 10px', 
                                            fontSize: '0.8rem',
                                            cursor: 'pointer',
                                            borderRadius: '6px'
                                        }}
                                    >
                                        Cancella Tutto
                                    </button>
                                )}
                            </div>

                            {alerts.length > 0 ? (
                                <ul style={{ listStyle: 'none', padding: 0, margin: 0, maxHeight: '200px', overflowY: 'auto' }}>
                                    {alerts.map((alert, idx) => (
                                        <li key={idx} style={{ padding: '8px 0', borderBottom: '1px solid #fecaca', fontSize: '0.9rem', color: '#b91c1c' }}>
                                            <span style={{ fontSize: '0.75rem', opacity: 0.8, display:'block' }}>
                                                {new Date(alert.timestamp * 1000).toLocaleTimeString()}
                                            </span>
                                            {alert.message}
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <div style={{ color: '#b91c1c', opacity: 0.7, fontStyle: 'italic' }}>Nessun allarme rilevato.</div>
                            )}
                        </div>

                        {/* RULES ENGINE */}
                        <div className="glass-card">
                            <h3 style={{ marginTop: 0, color:'#374151' }}>⚙️ Automazione</h3>
                            <form onSubmit={handleAddRule} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <select value={newRule.parameter} onChange={(e) => setNewRule({...newRule, parameter: e.target.value})} className="input-field" style={{ flex: 2 }}>
                                        <option value="temperature">Temperature</option>
                                        <option value="humidity">Humidity</option>
                                        <option value="soil_moisture">Soil Moisture</option>
                                        {sensorTypes.map(t => {
                                            const key = t.name.toLowerCase().replace(/ /g, "_");
                                            if(['temperature','humidity','soil_moisture'].includes(key)) return null;
                                            return <option key={t.id} value={key}>{t.name}</option>
                                        })}
                                    </select>
                                    <select value={newRule.operator} onChange={(e) => setNewRule({...newRule, operator: e.target.value})} className="input-field" style={{ flex: 1 }}>
                                        <option value=">">&gt;</option><option value="<">&lt;</option>
                                    </select>
                                </div>
                                <input placeholder="Soglia" type="number" value={newRule.threshold} onChange={(e) => setNewRule({...newRule, threshold: e.target.value})} className="input-field" required />
                                <input placeholder="Messaggio alert..." value={newRule.message} onChange={(e) => setNewRule({...newRule, message: e.target.value})} className="input-field" required />
                                <button type="submit" className="btn btn-primary" style={{ width: '100%', fontSize:'0.9rem' }}>+ Aggiungi Regola</button>
                            </form>
                            
                            <div style={{ maxHeight: '150px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                {(rules || []).map(r => (
                                    <div key={r.id} className="flex-between" style={{ background: '#f9fafb', padding: '0.5rem', borderRadius: '6px' }}>
                                        <span style={{ fontSize: '0.8rem', color:'#374151' }}><b>{r.parameter}</b> {r.operator} {r.threshold}</span>
                                        <button onClick={() => handleDeleteRule(r.id)} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#ef4444' }}>✕</button>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* SENSORS MANAGER */}
                        <div className="glass-card">
                            <h3 style={{ marginTop: 0, color:'#374151' }}>📡 Sensori</h3>
                            <form onSubmit={handleRegisterSensor} style={{ marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                <input placeholder="ID Hardware" value={newSensor.sensor_id} onChange={e=>setNewSensor({...newSensor, sensor_id:e.target.value})} className="input-field" required />
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <input placeholder="Posizione" value={newSensor.location} onChange={e=>setNewSensor({...newSensor, location:e.target.value})} className="input-field" style={{flex: 1}} />
                                    <select value={newSensor.type} onChange={e=>setNewSensor({...newSensor, type:e.target.value})} className="input-field" style={{flex: 1}} required>
                                        <option value="">-- Tipo --</option>
                                        {sensorTypes.map(t => <option key={t.id} value={t.name}>{t.name}</option>)}
                                    </select>
                                </div>
                                <button className="btn btn-secondary" style={{ width: '100%' }}>+ Aggiungi Sensore</button>
                            </form>
                            
                            <div style={{ maxHeight: '120px', overflowY: 'auto' }}>
                                {authorizedSensors.map(s => (
                                    <div key={s.sensor_id} className="flex-between" style={{ padding: '6px 0', borderBottom: '1px solid #f3f4f6' }}>
                                        <div>
                                            <div style={{ fontWeight: '600', fontSize: '0.85rem' }}>{s.sensor_id}</div>
                                            <div style={{fontSize:'0.75rem', color:'#9ca3af'}}>{s.location} • <span className="badge">{s.type}</span></div>
                                        </div>
                                        <button onClick={()=>handleDeleteSensor(s.sensor_id)} style={{ border: 'none', background: 'none', color: '#ef4444', cursor: 'pointer' }}>🗑️</button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default Monitoring;