import React, { useEffect, useState, useMemo, useRef } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import toast, { Toaster } from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';

const API_GATEWAY_URL = "https://localhost:8000";
const WS_URL = "wss://localhost:8000/ws/notifications";

// Genera un colore univoco per il grafico
const stringToColor = (str) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const c = (hash & 0x00FFFFFF).toString(16).toUpperCase();
    return '#' + '00000'.substring(0, 6 - c.length) + c;
};

function Monitoring() {
    const { token, selectedField } = useAuth();
    const navigate = useNavigate();

    // Riferimento WebSocket
    const ws = useRef(null);
    // Toast id di connessione
    const errorToastId = useRef(null);

    // STATI DATI
    const [readings, setReadings] = useState([]);
    const [weather, setWeather] = useState(null);
    const [forecast, setForecast] = useState([]); 
    const [authorizedSensors, setAuthorizedSensors] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [rules, setRules] = useState([]);
    const [sensorTypes, setSensorTypes] = useState([]);

    // Stato per il limite di letture
    const [historyLimit, setHistoryLimit] = useState(50);
    const limitRef = useRef(50);

    // Sincronizzazione del ref ogni volta che cambia lo stato
    useEffect(() => {
        limitRef.current = historyLimit;
    }, [historyLimit]);

    
    // STATI FORM (Inizializzati vuoti, verranno popolati dall'useEffect)
    const [newSensor, setNewSensor] = useState({ sensor_id: '', location: '', sensor_type: '' });
    const [newRule, setNewRule] = useState({ sensor_type: '', condition: '>', threshold: '', message: '' });
    const [loading, setLoading] = useState(true);

    // STATO PER GLI ERRORI DI VALIDAZIONE
    const [fieldErrors, setFieldErrors] = useState({});

    // NAVIGAZIONE
    useEffect(() => { 
        if (!selectedField) navigate('/fields'); 
    }, [selectedField, navigate]);
    
    // --- AUTO-SELEZIONE TIPO SENSORE E REGOLA ---
    // Appena caricano i sensorTypes, impostiamo il valore di default per entrambi i form
    useEffect(() => {
        if (sensorTypes.length > 0) {
            const defaultType = sensorTypes[0].type_name;
            
            // Per le Regole
            if (newRule.sensor_type === '') {
                setNewRule(prev => ({ ...prev, sensor_type: defaultType }));
            }
            // Per i Sensori (Nuova modifica)
            if (newSensor.sensor_type === '') {
                setNewSensor(prev => ({ ...prev, sensor_type: defaultType }));
            }
        }
    }, [sensorTypes]);

    const clearErrorField = (fieldName) => {
        setFieldErrors(prevErrors => ({ ...prevErrors, [fieldName]: undefined }));        
    };

    const getInputStyle = (fieldName) => ({
        borderColor: fieldErrors[fieldName] ? 'var(--danger, #dc3545)' : '',
    });

    const handleApiError = (err, toastId) => {
        if (err.response && err.response.status === 422 && err.response.data.errors) {
            toast.error("Controlla i campi evidenziati in rosso.", { id: toastId });
            const objErrors = {};
            err.response.data.errors.forEach(errorItem => {
                objErrors[errorItem.field] = errorItem.message;
            });
            setFieldErrors(objErrors);
        } else {
            const errorMsg = err.response?.data?.message || err.response?.data?.detail || "Errore durante la richiesta";
            toast.error(errorMsg, { id: toastId });
        }
    }

    // FETCH DATI
    const fetchData = async () => {
        if (!selectedField) { setLoading(false); return; }
        const field_name = selectedField.field
        if (!field_name) { setLoading(false); return; }

        try {
            const results = await Promise.allSettled([
                axios.get(`${API_GATEWAY_URL}/fields/${field_name}/weather`),
                axios.get(`${API_GATEWAY_URL}/fields/${field_name}/readings?limit=${historyLimit}`),
                axios.get(`${API_GATEWAY_URL}/fields/${field_name}/sensors`),
                axios.get(`${API_GATEWAY_URL}/rules?field=${field_name}`),
                axios.get(`${API_GATEWAY_URL}/alerts/${field_name}?limit=10`),
                axios.get(`${API_GATEWAY_URL}/sensor-types`)
            ]);

            if (results[0].status === 'fulfilled') {
                setWeather(results[0].value.data.current_weather);
                setForecast(results[0].value.data.forecast);
            }
            if (results[1].status === 'fulfilled') setReadings(results[1].value.data);
            if (results[2].status === 'fulfilled') setAuthorizedSensors(results[2].value.data);
            if (results[3].status === 'fulfilled') setRules(results[3].value.data);
            if (results[4].status === 'fulfilled') setAlerts(results[4].value.data);
            if (results[5].status === 'fulfilled') setSensorTypes(results[5].value.data);

            console.log("Readings fetched:", results[1].value.data);

        } catch (error) { 
            console.log(error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [selectedField, historyLimit]);
    // Gestione WebSocket per notifiche in tempo reale
    useEffect(() => {
        if (!token || !selectedField) return; // Se mancano i dati necessari, non si prova la connessione

        let successToastId = null;

        const connectWebSocket = () => {
            const field_name = selectedField.field;

            if (ws.current) {
                ws.current.onclose = null; // Evita la riconnessione al momento della chiusura manuale
                ws.current.close();
            }

            errorToastId.current = null;

            const socket = new WebSocket(`${WS_URL}?token=${token}&field=${field_name}`);
            ws.current = socket;

            // All'apertura della socket
            socket.onopen = () => {
                if (errorToastId.current) {
                    toast.dismiss(errorToastId.current);
                    errorToastId.current = null;
                }
                successToastId = toast.success(`Connesso al sistema di notifica in tempo reale del campo ${selectedField.name}.`);
            }

            // Quando arriva un messaggio
            socket.onmessage = (event) => {
                try {
                    console.log("Messaggio WebSocket ricevuto:", event.data);
                    const response = JSON.parse(event.data);
                    const { type, data } = response;

                    // Gestione alert nuove letture
                    if (type === 'reading') {
                        setReadings(prevReadings => {
                            const updatedReadings = [data, ...prevReadings];

                            if (updatedReadings.length > limitRef.current) {
                                return updatedReadings.slice(0, limitRef.current);
                            }
                            return updatedReadings;
                        });
                    }
                    
                    // Gestione nuovi allarmi
                    if (type === 'alert') {
                        setAlerts(prevAlerts => {
                            const uniqueId = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
                            const newAlert = {...data, id: uniqueId }; // Generazione id causale
                            return [newAlert, ...prevAlerts];
                        })

                        toast.error(`⚠️ Nuovo allarme: ${data.message}\n(Tipo sensore: ${data.sensor_type})`, { duration: 4000 });
                    }

                } catch (err) {
                    console.error("Errore parsing messaggio WebSocket:", err);
                }
            }

            const handleConnectionLoss = () => {
                if (errorToastId.current) return;
                errorToastId.current = toast.error(<div onClick={() => window.location.reload()} style={{ cursor: 'pointer' }}><b>Connessione alle notifiche persa.</b><br/>Ricaricare la pagina</div>, { duration: Infinity, id: 'ws-error-toast' });
            }

            socket.onclose = (event) => {
                console.log(`Connessione WebSocket chiusa pulitamente, codice=${event.code} motivo=${event.reason}`);

                if (successToastId) {
                    toast.dismiss(successToastId);
                    successToastId = null;
                }

                handleConnectionLoss();
            }

            socket.onerror = (err) => {
                console.error("Errore WebSocket:", err);
            }
        };

        connectWebSocket();

        return () => {
            // Chiusura della connessione WebSocket
            if (ws.current) {
                ws.current.onclose = null; // Evita la riconnessione al momento della chiusura manuale
                ws.current.close();
            }

            if (successToastId) {
                toast.dismiss(successToastId);
            }
        }

    }, [selectedField, token]);

    // --- HANDLERS ---

    const handleRegisterSensor = async (e) => {
        e.preventDefault();
        setFieldErrors({}); // Resetta errori precedenti

        const field_name = selectedField?.field;
        // Controllo di sicurezza, anche se è preselezionato
        if (!newSensor.sensor_type) return toast.error("Seleziona tipo");
        
        try {
            await axios.post(`${API_GATEWAY_URL}/fields/${field_name}/sensors`, { ...newSensor, field_name: field_name, active: true });
            toast.success("Sensore aggiunto");
            
            // RESET: Manteniamo il primo tipo disponibile
            const defaultType = sensorTypes.length > 0 ? sensorTypes[0].type_name : '';
            setNewSensor({ sensor_id: '', location: '', sensor_type: defaultType });
            
            fetchData();
        } catch (err) {
            handleApiError(err);
        }
    };

    const handleClearAlerts = async () => {
        const fieldId = selectedField?.field;
        if (!fieldId || alerts.length === 0) return;
        if (!confirm("Archiviare tutti gli allarmi visualizzati?")) return;
        try {
            await axios.post(`${API_GATEWAY_URL}/archive-alerts/${fieldId}`);
            toast.success("Allarmi archiviati");
            setAlerts([]); 
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
        setFieldErrors({}); // Resetta errori precedenti

        const field_name = selectedField?.field;
        if (!newRule.sensor_type) return toast.error("Tipo sensore mancante");

        try {
            await axios.post(`${API_GATEWAY_URL}/rules`, { ...newRule, threshold: parseFloat(newRule.threshold), field: field_name });
            toast.success("Regola creata");
            
            // RESET: Manteniamo il primo tipo disponibile
            const defaultType = sensorTypes.length > 0 ? sensorTypes[0].type_name : '';
            setNewRule({ sensor_type: defaultType, condition: '>', threshold: '', message: '' });
            
            fetchData();
        } catch(err){
            handleApiError(err);
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

    // --- HELPERS VISIVI ---

    const truncateText = (text, limit) => {
        if (!text) return '';
        return text.length > limit ? text.substring(0, limit) + '...' : text;
    };

    const formatXAxis = (tickItem) => {
        if (!tickItem) return '';
        return new Date(tickItem).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    };

    const formatTooltipLabel = (label) => {
        if (!label) return '';
        return new Date(label).toLocaleString('it-IT', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    };

    // --- ELABORAZIONE DATI GRAFICO ---

    const { chartData, activeCurves, unitsMap } = useMemo(() => {
        if (!readings || readings.length === 0) {
            return { chartData: [], activeCurves: [], unitsMap: {} };
        }

        const grouped = {};
        const unit = {};

        readings.forEach(r => {
            const date = new Date(r.timestamp);
            date.setMilliseconds(0);
            const timeKey = date.toISOString();

            const typeKey = r.sensor_type.toLowerCase().replace(/ /g, "_");

            if (!unit[typeKey]) {
                unit[typeKey] = r.unit;
            }

            if (!grouped[timeKey]) {
                grouped[timeKey] = {};
            }

            if (!grouped[timeKey][typeKey]) {
                grouped[timeKey][typeKey] = [];
            }

            grouped[timeKey][typeKey].push(r.value);
        });

        // Calcolo medie
        const data = Object.entries(grouped).map(([timestamp, sensors]) => {
            const row = { timestamp };

            Object.entries(sensors).forEach(([type, values]) => {
                const avg =
                    values.reduce((sum, v) => sum + v, 0) / values.length;
                row[type] = Number(avg.toFixed(2));
            });

            return row;
        });

        data.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

        // Curve attive = una per tipo sensore
        const sensorTypesSet = new Set();
        readings.forEach(r =>
            sensorTypesSet.add(
                r.sensor_type.toLowerCase().replace(/ /g, "_")
            )
        );

        const curves = Array.from(sensorTypesSet).map(type => ({
            dataKey: type,
            name: `${type.replace(/_/g, " ")} (media)`
        }));

        return { chartData: data, activeCurves: curves, unitsMap: unit };
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
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                <h3 style={{ margin: 0, color: '#1e3a8a' }}>📊 Andamento Medio Rilevazioni Sensori</h3>
                                
                                {/* NUOVA SELECT */}
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                    <label htmlFor="limitSelect" style={{ fontSize: '0.85rem', color: '#6b7280', whiteSpace: 'nowrap', margin: 0 }}>Mostra:</label>
                                    <select 
                                        id="limitSelect"
                                        value={historyLimit}
                                        onChange={(e) => setHistoryLimit(Number(e.target.value))}
                                        className="input-field"
                                        style={{ padding: '4px 8px', fontSize: '0.85rem', width: 'auto', height: '30px' }}
                                    >
                                        <option value={20}>Ultime 20</option>
                                        <option value={50}>Ultime 50</option>
                                        <option value={100}>Ultime 100</option>
                                        <option value={200}>Ultime 200</option>
                                    </select>
                                </div>
                            </div>
                            <ResponsiveContainer width="100%" height={300}>
                                <AreaChart data={chartData}>
                                    <defs>
                                    {activeCurves.map(curve => {
                                        const color = stringToColor(curve.dataKey);
                                        return (
                                        <linearGradient key={curve.dataKey} id={`grad${curve.dataKey}`} x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor={color} stopOpacity={0.3}/>
                                            <stop offset="95%" stopColor={color} stopOpacity={0}/>
                                        </linearGradient>
                                        );
                                    })}
                                    </defs>

                                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                                    <XAxis dataKey="timestamp" tickFormatter={formatXAxis} axisLine={false} tickLine={false} style={{fontSize:'0.75rem'}} />
                                    <YAxis axisLine={false} tickLine={false} />
                                    <Tooltip 
                                        contentStyle={{ borderRadius: '12px' }} 
                                        labelFormatter={formatTooltipLabel} 
                                        formatter={(value, name, item) => {
                                            const unit = unitsMap[item.dataKey] || '';
                                            return [`${value} ${unit}`, name];
                                        }} 
                                    />

                                    {activeCurves.map(curve => {
                                    const color = stringToColor(curve.dataKey);
                                    return (
                                        <Area 
                                        key={curve.dataKey}
                                        type="monotone" 
                                        dataKey={curve.dataKey} 
                                        name={curve.name}
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
                                            .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
                                            .map((r, i) => (
                                            <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                                                <td style={{ padding: '10px', fontSize: '0.85rem', color: '#6b7280', whiteSpace: 'nowrap' }}>
                                                    {new Date(r.timestamp).toLocaleString('it-IT', {
                                                        day: '2-digit', month: '2-digit', year: 'numeric',
                                                        hour: '2-digit', minute: '2-digit', second: '2-digit'
                                                    })}
                                                </td>
                                                <td style={{ padding: '10px', fontWeight: '600', color: '#374151' }}>{r.sensor_id}</td>
                                                <td style={{ padding: '10px', textTransform: 'capitalize', color: '#4b5563' }}>{r.sensor_type.replace(/_/g, ' ')}</td>
                                                <td style={{ padding: '10px' }}>
                                                    <span style={{
                                                        background: '#eff6ff', color: '#1d4ed8', 
                                                        padding: '4px 10px', borderRadius: '20px', fontWeight: '600', fontSize: '0.9rem', display: 'inline-block'
                                                    }}>
                                                        {r.value} <span style={{ fontSize: '0.8em', marginLeft: '3px', opacity: 0.8 }}>{r.unit}</span>
                                                    </span>
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
                                <div style={{ marginTop: '10px' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '15px' }}>
                                        <img 
                                            src={`https://openweathermap.org/img/wn/${weather.icon}@2x.png`} 
                                            alt={weather.description}
                                            style={{ width: '80px', height: '80px', filter: 'drop-shadow(0 4px 6px rgba(0,0,0,0.1))' }}
                                        />
                                        <div style={{ textAlign: 'left' }}>
                                            <div style={{ fontSize: '2.5rem', fontWeight: 800, color: '#1e3a8a', lineHeight: 1 }}>{Math.round(weather.temperature)}°</div>
                                            <div style={{ fontSize: '0.9rem', color: '#6b7280', textTransform: 'capitalize' }}>{weather.description}</div>
                                        </div>
                                    </div>
                                    <div style={{ color: '#6b7280', fontSize: '0.9rem', marginBottom: '1.5rem', marginTop: '0.5rem' }}>
                                        <div style={{ marginBottom: '8px' }}>📍 <strong>{weather.city}</strong></div>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', fontSize: '0.9rem', color: '#374151' }}>
                                            <div><strong>max:</strong> {Math.round(weather.max_temperature)}°</div>
                                            <div><strong>min:</strong> {Math.round(weather.min_temperature)}°</div>
                                        </div>
                                    </div>
                                    {forecast.length > 0 && (
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #dbeafe', gap: '5px' }}>
                                            {forecast.slice(1).map((day, idx) => (
                                                <div key={idx} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
                                                    <span style={{ fontSize: '0.75rem', fontWeight: 'bold', color: '#64748b', whiteSpace: 'nowrap' }}>
                                                        {day.date.split(' ')[0]} <span style={{fontSize:'0.65rem', fontWeight:'normal'}}>{day.date.split(' ')[1]}</span>
                                                    </span>
                                                    <img src={`https://openweathermap.org/img/wn/${day.icon.replace('n', 'd')}.png`} alt="icon" style={{ width: '40px', height: '40px' }} />
                                                    <div style={{ display: 'flex', flexDirection: 'column', fontSize: '0.75rem', lineHeight: '1.4', width: '100%' }}>
                                                        <div style={{ color: '#1e40af' }}><strong>max:</strong> {Math.round(day.max_temperature)}°</div>
                                                        <div style={{ color: '#64748b' }}><strong>min:</strong> {Math.round(day.min_temperature)}°</div>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            ) : <p className="text-muted" style={{ padding: '20px' }}>Caricamento meteo...</p>}
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
                                            background: '#fee2e2', color: '#b91c1c', border: '1px solid #fca5a5', 
                                            padding: '4px 10px', fontSize: '0.8rem', cursor: 'pointer', borderRadius: '6px'
                                        }}
                                    >
                                        Cancella Tutto
                                    </button>
                                )}
                            </div>

                            {alerts.length > 0 ? (
                                <ul style={{ listStyle: 'none', padding: 0, margin: 0, maxHeight: '300px', overflowY: 'auto' }}>
                                    {alerts.map((alert) => {
                                        const alertDate = new Date(alert.timestamp);
                                        const today = new Date();
                                        const isToday = alertDate.toDateString() === today.toDateString();

                                        return (
                                            <li key={alert.id} style={{ padding: '10px 0', borderBottom: '1px solid #fecaca', fontSize: '0.9rem', color: '#b91c1c' }}>
                                                <span style={{ fontSize: '0.75rem', opacity: 0.7, display: 'block', marginBottom: '2px', color: '#991b1b' }}>
                                                    {isToday 
                                                        ? alertDate.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) 
                                                        : alertDate.toLocaleString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit' })
                                                    }
                                                </span>
                                                <div style={{ lineHeight: '1.4' }}>
                                                    <span style={{ 
                                                        fontWeight: 'bold', textTransform: 'capitalize', marginRight: '5px',
                                                        background: '#fee2e2', padding: '1px 6px', borderRadius: '4px', fontSize: '0.8rem'
                                                    }}>
                                                        {alert.sensor_type}:
                                                    </span>
                                                    <span title={alert.message}>
                                                        {truncateText(alert.message, 45)}
                                                    </span>
                                                </div>
                                            </li>
                                        );
                                    })}
                                </ul>
                            ) : <div style={{ color: '#b91c1c', opacity: 0.7, fontStyle: 'italic', padding: '10px 0' }}>Nessun allarme rilevato.</div>}
                        </div>

                        {/* RULES ENGINE */}
                        <div className="glass-card">
                            <h3 style={{ marginTop: 0, color: '#374151' }}>⚙️ Automazione</h3>
                            
                            <form onSubmit={handleAddRule} style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <select 
                                        value={newRule.sensor_type} 
                                        onChange={(e) => setNewRule({ ...newRule, sensor_type: e.target.value })} 
                                        className="input-field" 
                                        style={{ flex: 2 }}
                                        required
                                    >
                                        {[...new Set(sensorTypes.map(t => t.type_name))].map((typeName, index) => (
                                            <option key={index} value={typeName}>{typeName}</option>
                                        ))}
                                    </select>

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
                                <input placeholder="Soglia" type="number" value={newRule.threshold} onChange={(e) => { setNewRule({ ...newRule, threshold: e.target.value }); clearErrorField('threshold'); }} className={`input-field ${fieldErrors.threshold ? 'input-error' : ''}`} style={getInputStyle('threshold')} required />
                                {fieldErrors.threshold && (
                                    <span style={{ color: '#dc3545', fontSize: '0.8rem', marginTop: '2px', display: 'block' }}>
                                        {fieldErrors.threshold}
                                    </span>
                                )}
                                <input placeholder="Messaggio alert..." value={newRule.message} onChange={(e) => { setNewRule({ ...newRule, message: e.target.value }); clearErrorField('message'); }} className={`input-field ${fieldErrors.message ? 'input-error' : ''}`} style={getInputStyle('message')} required />
                                {fieldErrors.message && (
                                    <span style={{ color: '#dc3545', fontSize: '0.8rem', marginTop: '2px', display: 'block' }}>
                                        {fieldErrors.message}
                                    </span>
                                )}
                                <button type="submit" className="btn btn-primary" style={{ width: '100%', fontSize: '0.9rem' }}>+ Aggiungi Regola</button>
                            </form>
                            
                            <div style={{ maxHeight: '150px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                {(rules || []).map((r, idx) => (
                                    <div key={idx} className="flex-between" style={{ background: '#f9fafb', padding: '0.5rem', borderRadius: '6px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <span style={{ fontSize: '0.8rem', color: '#374151' }}>
                                            <b>{r.sensor_type}</b> {r.condition} {r.threshold}
                                            {r.message ? ` : ${r.message}` : ''}
                                        </span>
                                        <button onClick={() => handleDeleteRule(r.rule_name)} style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#ef4444', fontSize: '1.2rem', lineHeight: 1 }}>✕</button>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* SENSORS MANAGER */}
                        <div className="glass-card">
                            <h3 style={{ marginTop: 0, color: '#374151' }}>📡 Sensori</h3>
                            
                            <form onSubmit={handleRegisterSensor} style={{ marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                <input 
                                    placeholder="ID Hardware" 
                                    value={newSensor.sensor_id} 
                                    onChange={e => { setNewSensor({ ...newSensor, sensor_id: e.target.value }); clearErrorField('sensor_id'); }} 
                                    className={`input-field ${fieldErrors.sensor_id ? 'input-error' : ''}`}
                                    style={getInputStyle('sensor_id')}
                                    required
                                />
                                {fieldErrors.sensor_id && (
                                    <span style={{ color: '#dc3545', fontSize: '0.8rem', marginTop: '2px', display: 'block' }}>
                                        {fieldErrors.sensor_id}
                                    </span>
                                )}
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <div style={{ flex: 1 }}>
                                        <input 
                                            placeholder="Posizione" 
                                            value={newSensor.location} 
                                            onChange={e => { setNewSensor({ ...newSensor, location: e.target.value }); clearErrorField('location'); }} 
                                            className={`input-field ${fieldErrors.location ? 'input-error' : ''}`}
                                            style={{ width: '100%', ...getInputStyle('location') }} 
                                            required
                                        />
                                        {fieldErrors.location && (
                                            <span style={{ color: '#dc3545', fontSize: '0.8rem', marginTop: '2px', display: 'block' }}>
                                                {fieldErrors.location}
                                            </span>
                                        )}
                                    </div>
                                    <select 
                                        value={newSensor.sensor_type} 
                                        onChange={e => setNewSensor({ ...newSensor, sensor_type: e.target.value })} 
                                        className="input-field" 
                                        style={{ flex: 1 }} 
                                        required
                                    >
                                        {[...new Set(sensorTypes.map(t => t.type_name))].map((typeName, index) => (
                                            <option key={index} value={typeName}>{typeName}</option>
                                        ))}
                                    </select>
                                </div>
                                <button className="btn btn-secondary" style={{ width: '100%' }}>+ Aggiungi Sensore</button>
                            </form>
                            
                            <div style={{ maxHeight: '120px', overflowY: 'auto' }}>
                                {authorizedSensors.map(s => (
                                    <div key={s.sensor_id} className="flex-between" style={{ padding: '6px 0', borderBottom: '1px solid #f3f4f6', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                        <div>
                                            <div style={{ fontWeight: '600', fontSize: '0.85rem' }}>{s.sensor_id}</div>
                                            <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>
                                                {s.location} 
                                                {s.location && ' • '}
                                                <span style={{ 
                                                    background: '#e5e7eb', padding: '2px 6px', borderRadius: '4px', 
                                                    color: '#374151', textTransform: 'capitalize' 
                                                }}>
                                                    {s.sensor_type}
                                                </span>
                                            </div>
                                        </div>
                                        <button onClick={() => handleDeleteSensor(s.sensor_id)} style={{ border: 'none', background: 'none', color: '#ef4444', cursor: 'pointer' }}>✕</button>
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