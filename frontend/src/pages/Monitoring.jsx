import React, { useEffect, useState, useMemo } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import toast, { Toaster } from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';

const API_GATEWAY_URL = "https://localhost:8000";

// Genera un colore univoco per il grafico
const stringToColor = (str) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const c = (hash & 0x00FFFFFF).toString(16).toUpperCase();
    return '#' + '00000'.substring(0, 6 - c.length) + c;
};

// Vedere se mi serve
const getDayName = (dateStr) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('it-IT', { weekday: 'short' }); // Es: Lun, Mar
};

const formatAlertDate = (timestamp) => {
    if (!timestamp) return "";
    // Gestione timestamp secondi vs millisecondi
    const ms = timestamp > 1e10 ? timestamp : timestamp * 1000;
    const date = new Date(ms);
    const today = new Date();

    const isToday = date.getDate() === today.getDate() &&
                    date.getMonth() === today.getMonth() &&
                    date.getFullYear() === today.getFullYear();

    if (isToday) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } else {
        return date.toLocaleString([], {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    }
};

function Monitoring() {
    const { token, selectedField } = useAuth();
    const navigate = useNavigate();

    const [readings, setReadings] = useState([]);
    const [weather, setWeather] = useState(null);
    const [forecast, setForecast] = useState([]); // Stato per le previsioni
    const [authorizedSensors, setAuthorizedSensors] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [rules, setRules] = useState([]);
    const [sensorTypes, setSensorTypes] = useState([]);
    
    const [newSensor, setNewSensor] = useState({ sensor_id: '', location: '', sensor_type: '' });
    const [newRule, setNewRule] = useState({ sensor_type: '', condition: '>', threshold: '', message: '' });
    const [loading, setLoading] = useState(true);

    useEffect(() => { 
        if (!selectedField) navigate('/fields'); 
    }, [selectedField, navigate]);

    useEffect(() => {
        if (sensorTypes.length > 0 && newRule.sensor_type === '') {
            setNewRule(prev => ({ ...prev, sensor_type: sensorTypes[0].type_name }) );
        }
    }, [sensorTypes]);
    
    const formatXAxis = (tickItem) => {
        if (!tickItem) return '';
        return new Date(tickItem).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

    const fetchData = async () => {
        if (!selectedField) { setLoading(false); return; }
        const field_name = selectedField.field
        if (!field_name) { setLoading(false); return; }

        try {
            // const fieldQuery = `?field_id=${fieldId}`;

            const results = await Promise.allSettled([
                axios.get(`${API_GATEWAY_URL}/fields/${field_name}/weather`),
                axios.get(`${API_GATEWAY_URL}/fields/${field_name}/readings?limit=50`),
                axios.get(`${API_GATEWAY_URL}/fields/${field_name}/sensors`),
                axios.get(`${API_GATEWAY_URL}/rules?field=${field_name}`),
                axios.get(`${API_GATEWAY_URL}/alerts/${field_name}?limit=10`),
                axios.get(`${API_GATEWAY_URL}/sensor-types`)
            ]);

            console.log("Meteo: ", results[0].value.data.current_weather);
            console.log("Previsioni: ", results[0].value.data.forecast);
            console.log("Letture: ", results[1].value.data);
            console.log("Sensori nella field:", results[2].value.data);
            console.log("Regole:", results[3].value.data);
            console.log("Allarmi:", results[4].value.data);
            console.log("Tipi Sensori:", results[5].value.data);

            if (results[0].status === 'fulfilled') {
                setWeather(results[0].value.data.current_weather);
                setForecast(results[0].value.data.forecast);
            }
            if (results[1].status === 'fulfilled') setReadings(results[1].value.data);
            if (results[2].status === 'fulfilled') setAuthorizedSensors(results[2].value.data);
            if (results[3].status === 'fulfilled') setRules(results[3].value.data);
            if (results[4].status === 'fulfilled') setAlerts(results[4].value.data);
            if (results[5].status === 'fulfilled') setSensorTypes(results[5].value.data);

        } catch (error) { 
            console.log(error);
        } finally {
            setLoading(false);
        }
    };

    // da sostituire con WS
    useEffect(() => {
        fetchData();
    }, [selectedField]);

    // HANDLERS
    const handleRegisterSensor = async (e) => {
        e.preventDefault();
        const field_name = selectedField?.field;
        if (!newSensor.sensor_type) return toast.error("Seleziona tipo");
        try {
            await axios.post(`${API_GATEWAY_URL}/fields/${field_name}/sensors`, { ...newSensor, field_name: field_name, active: true });
            toast.success("Sensore aggiunto");
            setNewSensor({ sensor_id: '', location: '', sensor_type: '' });
            fetchData();
        } catch (err) {
            // logica di validazione come gli altri file
            toast.error(err.response?.data?.detail || "Errore");
        }
    };

    // --- NUOVA FUNZIONE: CANCELLA ALLARMI ---
    const handleClearAlerts = async () => {
        const fieldId = selectedField?.field;
        if (!fieldId || alerts.length === 0) return;
        
        if (!confirm("Archiviare tutti gli allarmi visualizzati?")) return;

        try {
            await axios.post(`${API_GATEWAY_URL}/archive-alerts/${fieldId}`);
            toast.success("Allarmi archiviati");
            setAlerts([]); // Pulisce subito la vista
        } catch (err) {
            console.error(err);
            toast.error("Errore durante l'archiviazione");
        }
    };

    const handleDeleteSensor = async (sensor_id) => {
        if (!confirm("Rimuovere?")) return;
        const field_name = selectedField?.field;
        try {
            await axios.delete(`${API_GATEWAY_URL}/fields/${field_name}/sensors/${sensor_id}`);
            toast.success("Sensore rimosso");
            fetchData();
        } catch (err) {
            console.log(err);
            toast.error("Errore");
        }
    };

    const handleAddRule = async (e) => {
        e.preventDefault();
        const field_name = selectedField?.field;
        try {
            await axios.post(`${API_GATEWAY_URL}/rules`, { ...newRule, threshold: parseFloat(newRule.threshold), field: field_name });
            toast.success("Regola creata");
            setNewRule({ sensor_type: sensorTypes.length > 0 ? sensorTypes[0].type_name : '', condition: '>', threshold: '', message: '' });
            fetchData();
        } catch(err){
            // gestione errori di validazione come gli altri file
            console.log(err);
            toast.error("Errore regola");
        }
    };

    const handleDeleteRule = async (rule_name) => {
        try {
            await axios.delete(`${API_GATEWAY_URL}/rules/${rule_name}`);
            toast.success("Eliminata");
            fetchData();
        } catch {
            toast.error("Errore");
        }
    };

    const truncateText = (text, limit) => {
        if (!text) return '';
        return text.length > limit ? text.substring(0, limit) + '...' : text;
    }

    const formatTooltipLabel = (label) => {
        if (!label) return '';
        return new Date(label).toLocaleString('it-IT', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    }

    const { chartData, activeCurves } = useMemo(() => {
        if (!readings || readings.length === 0) return { chartData: [], activeCurves: [] };

        const curvesSet = new Map(); // Usiamo una Map per tenere traccia delle curve uniche trovate

        // 1. Raggruppa per timestamp
        const grouped = readings.reduce((acc, curr) => {
            // Arrotonda al secondo per allineare i dati
            const dateObj = new Date(curr.timestamp);
            dateObj.setMilliseconds(0);
            // volendo posso fare anche dateObj.setSeconds(0);
            const timeKey = dateObj.toISOString();

            if (!acc[timeKey]) {
                acc[timeKey] = { timestamp: timeKey };
            }

            // CREIAMO UNA CHIAVE UNICA: tipo + id sensore
            // Es: temperature_sensor01
            const typeKey = curr.sensor_type.toLowerCase().replace(/ /g, "_");
            const uniqueKey = `${typeKey}_${curr.sensor_id}`;

            // Salviamo il valore
            acc[timeKey][uniqueKey] = curr.value;

            // Salviamo i dettagli di questa curva se non l'abbiamo già fatto
            if (!curvesSet.has(uniqueKey)) {
                curvesSet.set(uniqueKey, {
                    dataKey: uniqueKey,
                    sensorId: curr.sensor_id,
                    type: curr.sensor_type,
                    unit: curr.unit,
                    name: `${curr.sensor_type} (${curr.sensor_id})` // Nome per la legenda
                });
            }

            return acc;
        }, {});

        // 2. Ordina cronologicamente
        const data = Object.values(grouped).sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        return { chartData: data, activeCurves: Array.from(curvesSet.values()) };

    }, [readings]);

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
                                <AreaChart data={chartData}>
                                    <defs>
                                        {/* Generiamo gradienti per ogni curva specifica */}
                                        {activeCurves.map(curve => {
                                            // Generiamo un colore basato sull'ID del sensore o sulla chiave unica
                                            const color = stringToColor(curve.dataKey); 
                                            return (
                                                <linearGradient key={curve.dataKey} id={`grad${curve.dataKey}`} x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor={color} stopOpacity={0.8}/>
                                                    <stop offset="95%" stopColor={color} stopOpacity={0}/>
                                                </linearGradient>
                                            )
                                        })}
                                    </defs>
                                    
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                                    <XAxis dataKey="timestamp" tickFormatter={formatXAxis} axisLine={false} tickLine={false} style={{fontSize:'0.75rem'}} />
                                    <YAxis axisLine={false} tickLine={false} />
                                    <Tooltip contentStyle={{ borderRadius: '12px' }} labelFormatter={formatTooltipLabel} />
                                    
                                    {/* Cicliamo sulle curve attive calcolate nel useMemo */}
                                    {activeCurves.map(curve => {
                                        const color = stringToColor(curve.dataKey);
                                        return (
                                            <Area 
                                                key={curve.dataKey}
                                                type="monotone" 
                                                dataKey={curve.dataKey} 
                                                name={curve.name} // Es: temperature (sensor01)
                                                unit={curve.unit}
                                                stroke={color} 
                                                fill={`url(#grad${curve.dataKey})`} 
                                                connectNulls={true} 
                                                strokeWidth={2}
                                                activeDot={{ r: 6 }}
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
                                <table className="modern-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                                    <thead style={{ position: 'sticky', top: 0, background: 'white', zIndex: 1 }}>
                                        <tr style={{ textAlign: 'left', color: '#6b7280', borderBottom: '2px solid #e5e7eb' }}>
                                            <th style={{ padding: '12px 10px' }}>Orario</th>
                                            <th style={{ padding: '12px 10px' }}>Sensore</th>
                                            <th style={{ padding: '12px 10px' }}>Tipo</th>
                                            <th style={{ padding: '12px 10px' }}>Valore</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {[...readings]
                                            // Ordina dal più recente al più vecchio
                                            .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
                                            .map((r, i) => (
                                            <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                                                
                                                {/* COLONNA 1: ORARIO (gg/mm/aaaa hh:mm:ss) */}
                                                <td style={{ padding: '10px', fontSize: '0.85rem', color: '#6b7280', whiteSpace: 'nowrap' }}>
                                                    {new Date(r.timestamp).toLocaleString('it-IT', {
                                                        day: '2-digit', month: '2-digit', year: 'numeric',
                                                        hour: '2-digit', minute: '2-digit', second: '2-digit'
                                                    })}
                                                </td>

                                                {/* COLONNA 2: ID SENSORE */}
                                                <td style={{ padding: '10px', fontWeight: '600', color: '#374151' }}>
                                                    {r.sensor_id}
                                                </td>

                                                {/* COLONNA 3: TIPO (formattato per togliere underscore) */}
                                                <td style={{ padding: '10px', textTransform: 'capitalize', color: '#4b5563' }}>
                                                    {r.sensor_type.replace(/_/g, ' ')}
                                                </td>

                                                {/* COLONNA 4: VALORE + UNITÀ */}
                                                <td style={{ padding: '10px' }}>
                                                    <span style={{
                                                        background: '#eff6ff', 
                                                        color: '#1d4ed8', 
                                                        padding: '4px 10px', 
                                                        borderRadius: '20px', 
                                                        fontWeight: '600',
                                                        fontSize: '0.9rem',
                                                        display: 'inline-block'
                                                    }}>
                                                        {r.value} 
                                                        <span style={{ fontSize: '0.8em', marginLeft: '3px', opacity: 0.8 }}>
                                                            {r.unit}
                                                        </span>
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        {/* WIDGET METEO & PREVISIONI */}
                        <div className="glass-card" style={{ textAlign: 'center', background: 'linear-gradient(to bottom, #eff6ff, #fff)' }}>
                            <h3 style={{ margin: 0, color: '#1d4ed8' }}>Meteo Attuale</h3>
                            
                            {weather ? (
                                <div style={{ marginTop: '10px' }}>
                                    {/* SEZIONE PRINCIPALE: ICONA E TEMPERATURA */}
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '15px' }}>
                                        <img 
                                            src={`https://openweathermap.org/img/wn/${weather.icon}@2x.png`} 
                                            alt={weather.description}
                                            style={{ width: '80px', height: '80px', filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.1))' }}
                                        />
                                        <div style={{ textAlign: 'left' }}>
                                            <div style={{ fontSize: '2.5rem', fontWeight: 800, color: '#1e3a8a', lineHeight: 1 }}>
                                                {Math.round(weather.temperature)}°
                                            </div>
                                            <div style={{ fontSize: '0.9rem', color: '#6b7280', textTransform: 'capitalize' }}>
                                                {weather.description}
                                            </div>
                                        </div>
                                    </div>

                                    {/* DETTAGLI LOCALITÀ E MIN/MAX ATTUALI */}
                                    <div style={{ color: '#6b7280', fontSize: '0.9rem', marginBottom: '1.5rem', marginTop: '0.5rem' }}>
                                        <div style={{ marginBottom: '8px' }}>📍 <strong>{weather.city}</strong></div>
                                        
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', fontSize: '0.9rem', color: '#374151' }}>
                                            <div><strong>max:</strong> {Math.round(weather.max_temperature)}°</div>
                                            <div><strong>min:</strong> {Math.round(weather.min_temperature)}°</div>
                                        </div>
                                    </div>

                                    {/* PREVISIONI PROSSIMI GIORNI */}
                                    {forecast.length > 0 && (
                                        <div style={{ 
                                            display: 'flex', 
                                            justifyContent: 'space-between', 
                                            marginTop: '1rem', 
                                            paddingTop: '1rem',
                                            borderTop: '1px solid #dbeafe',
                                            gap: '5px'
                                        }}>
                                            {forecast.slice(1).map((day, idx) => (
                                                <div key={idx} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
                                                    {/* Data */}
                                                    <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#64748b', whiteSpace: 'nowrap' }}>
                                                        {day.date.split(' ')[0]} <span style={{fontSize:'0.65rem', fontWeight:'normal'}}>{day.date.split(' ')[1]}</span>
                                                    </span>
                                                    
                                                    {/* Icona (FORZATA A GIORNO) */}
                                                    <img 
                                                        // QUI LA MODIFICA: .replace('n', 'd') forza la 'd' (day) anche se l'API manda 'n' (night)
                                                        src={`https://openweathermap.org/img/wn/${day.icon.replace('n', 'd')}.png`} 
                                                        alt="icon" 
                                                        style={{ width: '40px', height: '40px' }}
                                                    />
                                                    
                                                    {/* Temperature Min/Max Forecast */}
                                                    <div style={{ display: 'flex', flexDirection: 'column', fontSize: '0.75rem', lineHeight: '1.4', width: '100%' }}>
                                                        <div style={{ color: '#1e40af' }}>
                                                            <strong>max:</strong> {Math.round(day.max_temperature)}°
                                                        </div>
                                                        <div style={{ color: '#64748b' }}>
                                                            <strong>min:</strong> {Math.round(day.min_temperature)}°
                                                        </div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <p className="text-muted" style={{ padding: '20px' }}>Caricamento meteo...</p>
                            )}
                        </div>

                        {/* ALERT BOX */}
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
                                <ul style={{ listStyle: 'none', padding: 0, margin: 0, maxHeight: '300px', overflowY: 'auto' }}>
                                    {alerts.map((alert) => {
                                        // LOGICA DATA: Controllo se è oggi
                                        const alertDate = new Date(alert.timestamp);
                                        const today = new Date();
                                        const isToday = alertDate.toDateString() === today.toDateString();

                                        return (
                                            <li key={alert.id} style={{ padding: '10px 0', borderBottom: '1px solid #fecaca', fontSize: '0.9rem', color: '#b91c1c' }}>
                                                {/* Data e Ora Condizionale */}
                                                <span style={{ fontSize: '0.75rem', opacity: 0.7, display: 'block', marginBottom: '2px', color: '#991b1b' }}>
                                                    {isToday 
                                                        ? alertDate.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) // Solo ore:min:sec
                                                        : alertDate.toLocaleString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' }) // gg/mm/aaaa hh:mm:ss
                                                    }
                                                </span>
                                                
                                                {/* Tipo Sensore e Messaggio */}
                                                <div style={{ lineHeight: '1.4' }}>
                                                    <span style={{ 
                                                        fontWeight: 'bold', 
                                                        textTransform: 'capitalize', 
                                                        marginRight: '5px',
                                                        background: '#fee2e2',
                                                        padding: '1px 6px',
                                                        borderRadius: '4px',
                                                        fontSize: '0.8rem'
                                                    }}>
                                                        {alert.sensor_type}:
                                                    </span>
                                                    {alert.message}
                                                </div>
                                            </li>
                                        );
                                    })}
                                </ul>
                            ) : (
                                <div style={{ color: '#b91c1c', opacity: 0.7, fontStyle: 'italic', padding: '10px 0' }}>
                                    Nessun allarme rilevato.
                                </div>
                            )}
                        </div>
                        {/* RULES ENGINE */}
                        <div className="glass-card">
                            <h3 style={{ marginTop: 0, color: '#374151' }}>⚙️ Automazione</h3>
                            
                            {/* FORM DI AGGIUNTA */}
                            <form onSubmit={handleAddRule} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    
                                    {/* SELECT SENSOR TYPE */}
                                    <select 
                                        value={newRule.sensor_type} 
                                        onChange={(e) => setNewRule({ ...newRule, sensor_type: e.target.value })} 
                                        className="input-field" 
                                        style={{ flex: 2 }}
                                        required
                                    >
                                        {[...new Set(sensorTypes.map(t => t.type_name))].map((typeName, index) => (
                                            <option key={index} value={typeName}>
                                                {typeName}
                                            </option>
                                        ))}
                                    </select>

                                    {/* SELECT OPERATOR */}
                                    <select 
                                        value={newRule.condition} 
                                        onChange={(e) => setNewRule({ ...newRule, condition: e.target.value })} 
                                        className="input-field" 
                                        style={{ flex: 1 }}
                                    >
                                        <option value=">">&gt;</option>
                                        <option value="<">&lt;</option>
                                        <option value="==">==</option>
                                    </select>
                                </div>

                                <input 
                                    placeholder="Soglia" 
                                    type="number" 
                                    value={newRule.threshold} 
                                    onChange={(e) => setNewRule({ ...newRule, threshold: e.target.value })} 
                                    className="input-field" 
                                    required 
                                />
                                <input 
                                    placeholder="Messaggio alert..." 
                                    value={newRule.message} 
                                    onChange={(e) => setNewRule({ ...newRule, message: e.target.value })} 
                                    className="input-field" 
                                    required 
                                />
                                <button type="submit" className="btn btn-primary" style={{ width: '100%', fontSize: '0.9rem' }}>+ Aggiungi Regola</button>
                            </form>
                            
                            {/* LISTA REGOLE ESISTENTI */}
                            <div style={{ maxHeight: '150px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                {(rules || []).map((r, idx) => (
                                    <div key={idx} className="flex-between" style={{ background: '#f9fafb', padding: '0.5rem', borderRadius: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <span style={{ fontSize: '0.8rem', color: '#374151' }}>
                                            {/* Mostra il tipo sensore ESATTAMENTE come salvato nel DB */}
                                            <b>{r.sensor_type}</b> {r.condition} {r.threshold}
                                        </span>
                                        <button 
                                            onClick={() => handleDeleteRule(r.rule_name)} 
                                            style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#ef4444', fontSize: '1.2rem', lineHeight: 1 }}
                                        >
                                            ✕
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>

                    
                    {/*
                    COLONNA DESTRA
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

                        RULES ENGINE
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

                        {/* SENSORS MANAGER
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
                    */}
                </div>
            )}
        </div>
    );
}

export default Monitoring;