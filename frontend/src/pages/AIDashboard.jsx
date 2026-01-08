import React, { useEffect, useState, useMemo, useRef } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import toast, { Toaster } from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';

const API_GATEWAY_URL = "https://localhost:8000";
const WS_URL = "wss://localhost:8000/ws/notifications";

const stringToColor = (str) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = str.charCodeAt(i) + ((hash << 5) - hash);
    }
    const c = (hash & 0x00FFFFFF).toString(16).toUpperCase();
    return '#' + '00000'.substring(0, 6 - c.length) + c;
};

const formatSensorName = (sensorType) => {
    if (!sensorType) return "Sconosciuto";
    return sensorType.replace(/_/g, ' ');
}

function AIDashboard() {
    const { token, selectedField } = useAuth();
    const navigate = useNavigate();

    const ws = useRef(null);
    const errorToastId = useRef(null);
    
    // NOTA: Inizializziamo readings come oggetto vuoto {}, non array []
    const [readings, setReadings] = useState({});
    const [aiResult, setAiResult] = useState(null);
    const [loadingAi, setLoadingAi] = useState(false);

    // Stati immagini
    const [processedImage, setProcessedImage] = useState(null);
    const [imageAnalysis, setImageAnalysis] = useState(null);
    const [uploadingImg, setUploadingImg] = useState(false);
    const [loading, setLoading] = useState(true);
    const [showExplanation, setShowExplanation] = useState(false);

    const HISTORY_LIMIT = 50;

    useEffect(() => { 
        if (!selectedField) navigate('/fields');
    }, [selectedField, navigate]);

    const fetchData = async () => {
        if (!selectedField) { setLoading(false); return; }
        const field = selectedField.field;
        if (!field) { setLoading(false); return; }

        try {
            const res = await axios.get(`${API_GATEWAY_URL}/fields/${field}/latest-types-readings`);
            // res.data è del tipo: { temperature: [...], humidity: [...] }
            setReadings(res.data);
        } catch (e) { 
            console.error(e); 
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, [selectedField]);

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
                        const sensorType = data.sensor_type;
                        setReadings(prevReadings => {
                            const currentList = prevReadings[sensorType] || [];
                            const updatedList = [data, ...currentList].slice(0, HISTORY_LIMIT); // Mantieni solo gli ultimi N elementi
                            return { ...prevReadings, [sensorType]: updatedList };
                        })
                    }
                    
                    // Gestione nuovi allarmi
                    if (type === 'alert') {
                        toast.error(`⚠️ Nuovo allarme: ${data.message}\n(Tipo sensore: ${data.sensor_type})`, { duration: 3000 });
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

    // --- LOGICA DI AGGREGAZIONE E PREPARAZIONE DATI GRAFICI ---
    const chartsData = useMemo(() => {
        if (!readings || Object.keys(readings).length === 0) return [];

        // Iteriamo su ogni chiave (es. "temperature", "humidity")
        return Object.keys(readings).map(sensorType => {
            const rawData = readings[sensorType];
            
            // 1. Raggruppamento per timestamp (ignorando millisecondi)
            const grouped = {};
            let unit = ""; // Cerchiamo di catturare l'unità dal primo dato disponibile

            rawData.forEach(item => {
                if(!unit && item.unit) unit = item.unit;

                const date = new Date(item.timestamp);
                date.setSeconds(0);
                date.setMilliseconds(0); // Rimuove i millisecondi
                const timeKey = date.toISOString(); // Chiave univoca es: "2026-01-07T14:07:00.000Z"

                if (!grouped[timeKey]) {
                    grouped[timeKey] = { sum: 0, count: 0 };
                }
                grouped[timeKey].sum += item.value;
                grouped[timeKey].count += 1;
            });

            // 2. Calcolo Media e creazione array per Recharts
            const chartData = Object.entries(grouped).map(([timestamp, data]) => ({
                timestamp,
                value: Number((data.sum / data.count).toFixed(2)), // Media a 2 decimali
                unit: unit
            })).sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

            const dynamicColor = stringToColor(sensorType);
            const dynamicTitle = `Trend ${formatSensorName(sensorType)}`;

            return {
                type: sensorType,
                title: dynamicTitle,
                color: dynamicColor,
                data: chartData,
                unit: unit || config.unit
            };
        });
    }, [readings]);

    const formatXAsis = (tickItem) => {
        const date = new Date(tickItem);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    // --- GESTIONE AI E IMMAGINI (Invariata) ---
    const handleAskAI = async () => {
        const field = selectedField.field;
        if (!field) return toast.error("Seleziona campo");
        setAiResult(null); setShowExplanation(false); setLoadingAi(true);
        const loadingToast = toast.loading('L\'IA sta analizzando i dati...');
        try {
            const res = await axios.get(`${API_GATEWAY_URL}/ai-prediction`, { params: { field: field } });
            setAiResult(res.data);
            toast.success("Analisi completata", { id: loadingToast });
        } catch (error) { 
            toast.error("Errore analisi AI", { id: loadingToast });
        } finally { setLoadingAi(false); }
    };

    const handleImageUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setProcessedImage(null); setImageAnalysis(null); setUploadingImg(true);
        const loadingToast = toast.loading('Elaborazione NDVI...');
        const formData = new FormData();
        formData.append('file', file);
        try {
            const res = await axios.post(`${API_GATEWAY_URL}/compute-ndvi`, formData);
            setProcessedImage(`data:image/png;base64,${res.data.ndvi_image_base64}`);
            setImageAnalysis({ ndvi_index: res.data.mean_ndvi, vegetation_status: res.data.description, health_score: res.data.mean_ndvi });
            toast.success("NDVI calcolato con successo", { id: loadingToast });
        } catch(error) { toast.error("Errore upload", { id: loadingToast }); } 
        finally { setUploadingImg(false); }
    };

    // Helper formatter tooltip
    const formatTooltipDate = (label) => {
        if (!label) return '';
        return new Date(label).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    };

    return (
        <div className="page-container">
            <Toaster position="top-right" />
            
            <div className="glass-card" style={{ background: 'linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%)', color: 'white', marginBottom: '2rem', border: 'none' }}>
                <h2 style={{ margin: 0, fontSize: '2rem' }}>🧠 Intelligenza Artificiale</h2>
                <p style={{ opacity: 0.9, marginTop: '0.5rem' }}>Analisi per il campo: <strong>{selectedField?.name}</strong></p>
            </div>

            {loading ? <div style={{textAlign:'center', marginTop:'50px'}}>Caricamento...</div> : (
                <div className="split-layout">
                    
                    {/* COLONNA SINISTRA: GRAFICI DINAMICI */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        
                        {chartsData.length > 0 ? (
                            chartsData.map((chart) => (
                                <div key={chart.type} className="glass-card">
                                    <h3 style={{ color: chart.color, marginTop: 0, fontSize: '1.1rem', textTransform: 'capitalize' }}>
                                        {chart.title}
                                    </h3>
                                    <ResponsiveContainer width="100%" height={160}>
                                        <AreaChart data={chart.data}>
                                            <defs>
                                                <linearGradient id={`color${chart.type}`} x1="0" y1="0" x2="0" y2="1">
                                                    <stop offset="5%" stopColor={chart.color} stopOpacity={0.8}/>
                                                    <stop offset="95%" stopColor={chart.color} stopOpacity={0}/>
                                                </linearGradient>
                                            </defs>
                                            <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                                            <XAxis dataKey="timestamp" tickFormatter={formatXAsis} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: '#9ca3af' }} minTickGap={30} />
                                            <YAxis axisLine={false} tickLine={false} width={30} domain={['auto', 'auto']} />
                                            <Tooltip 
                                                contentStyle={{ borderRadius: '12px' }} 
                                                labelFormatter={formatTooltipDate}
                                                formatter={(value) => [`${value} ${chart.unit}`, 'Media']}
                                            />
                                            <Area 
                                                type="monotone" 
                                                dataKey="value" 
                                                stroke={chart.color} 
                                                fill={`url(#color${chart.type})`} 
                                                strokeWidth={2} 
                                                connectNulls={true} 
                                            />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </div>
                            ))
                        ) : (
                            <div className="glass-card" style={{textAlign:'center', color:'#6b7280'}}>
                                Nessun dato storico recente disponibile per i grafici.
                            </div>
                        )}

                    </div>

                    {/* COLONNA DESTRA: STRUMENTI AI (Invariato nel layout, ma codice incluso per completezza) */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        
                        {/* AI PREDICTOR */}
                        <div className="glass-card" style={{ border: '2px solid #ddd6fe', background: 'linear-gradient(to bottom right, #fff, #f5f3ff)' }}>
                            <div className="flex-between">
                                <h3 style={{marginTop:0, color:'#6d28d9'}}>🔮 AI Advisor</h3>
                                <span style={{fontSize:'1.5rem'}}>🤖</span>
                            </div>
                            <p className="text-muted text-sm" style={{marginBottom:'1rem'}}>L'IA analizza i dati attuali per suggerire interventi.</p>
                            
                            <button onClick={handleAskAI} disabled={loadingAi} className="btn" style={{ background: '#7c3aed', color: 'white', width: '100%' }}>
                                {loadingAi ? 'Elaborazione...' : 'Genera Previsione'}
                            </button>

                            {aiResult && (
                                <div style={{marginTop:'20px', background:'rgba(139, 92, 246, 0.1)', padding:'1rem', borderRadius:'12px', borderLeft:'4px solid #7c3aed'}}>
                                    <div className="flex-between" style={{marginBottom:'0.5rem'}}>
                                        <h4 style={{margin:0, color:'#5b21b6'}}>{aiResult.status}</h4>
                                        <span className="badge" style={{background:'#ede9fe', color:'#6d28d9'}}>
                                            {(aiResult.confidence * 100).toFixed(0)}% Confidenza
                                        </span>
                                    </div>
                                    <p style={{fontSize:'0.95rem', color:'#4c1d95', lineHeight:'1.5', fontWeight: 500}}>"{aiResult.advice}"</p>
                                    <div style={{marginTop:'10px'}}>
                                        <button 
                                            onClick={() => setShowExplanation(!showExplanation)}
                                            style={{background:'transparent', border:'none', color:'#7c3aed', fontSize:'0.8rem', cursor:'pointer', padding:0, textDecoration:'underline'}}
                                        >
                                            {showExplanation ? 'Nascondi dettagli' : 'Perché questo risultato?'}
                                        </button>
                                        
                                        {showExplanation && (
                                            <div style={{marginTop:'10px', background:'white', padding:'10px', borderRadius:'8px', fontSize:'0.85rem', color:'#6b7280', border:'1px solid #e5e7eb'}}>
                                                <strong>Input Analizzati (Medie):</strong><br/>
                                                
                                                {aiResult.details?.input_recieved && Object.entries(aiResult.details.input_recieved).map(([k, data]) => {
                                                    // Verifica se il dato è nel nuovo formato oggetto o nel vecchio formato (numero) per retrocompatibilità
                                                    const value = data?.value !== undefined ? data.value : data;
                                                    const unit = data?.unit || '';

                                                    return (
                                                        <div key={k} style={{textTransform:'capitalize'}}>
                                                            • {k.replace('_', ' ')}: 
                                                            {' '}
                                                            <strong>
                                                                {typeof value === 'number' ? value.toFixed(1) : value} {unit}
                                                            </strong>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* DRONE VISION */}
                        <div className="glass-card">
                            <div className="flex-between">
                                <h3 style={{color:'#059669', marginTop:0}}>🚁 Drone Vision (NDVI)</h3>
                                <span style={{fontSize:'1.5rem'}}>📸</span>
                            </div>
                            <p className="text-muted text-sm">Carica un file TIFF multispettrale (.tiff).</p>
                            
                            <div 
                                style={{
                                    border:'2px dashed #10b981', borderRadius:'12px', padding:'20px', 
                                    textAlign:'center', background:'rgba(236, 253, 245, 0.5)', cursor:'pointer', 
                                    transition:'all 0.2s', marginTop:'1rem'
                                }} 
                                onClick={() => document.getElementById('imgUpload').click()}
                            >
                                <input type="file" id="imgUpload" accept=".tif,.tiff" style={{display:'none'}} onChange={handleImageUpload} />
                                <div style={{fontSize:'2rem', marginBottom:'0.5rem', color:'#059669'}}>☁️</div>
                                <div style={{color:'#047857', fontWeight:'bold', fontSize:'0.9rem'}}>Clicca per caricare</div>
                            </div>

                            {processedImage && (
                                <div style={{marginTop:'1rem', borderRadius:'12px', overflow:'hidden', border:'1px solid #e5e7eb'}}>
                                    <p style={{fontSize:'0.8rem', textAlign:'center', color:'#6b7280', marginBottom:'5px'}}>Mappa NDVI generata:</p>
                                    <img src={processedImage} alt="Analisi NDVI" style={{width:'100%', display:'block'}} />
                                </div>
                            )}

                            {imageAnalysis && !uploadingImg && (
                                <div style={{marginTop:'1rem', background:'#ecfdf5', padding:'1rem', borderRadius:'12px', border:'1px solid #6ee7b7'}}>
                                    <div className="flex-between" style={{borderBottom:'1px solid #d1fae5', paddingBottom:'0.5rem', marginBottom:'0.5rem'}}>
                                        <span style={{color:'#065f46', fontSize:'0.9rem'}}>NDVI Index</span> 
                                        <strong style={{color: '#047857'}}>{imageAnalysis.ndvi_index?.toFixed(3) || "N/A"}</strong>
                                    </div>
                                    <div className="flex-between">
                                        <span style={{color:'#065f46', fontSize:'0.9rem'}}>Stato</span> 
                                        <strong style={{color: '#059669'}}>{imageAnalysis.vegetation_status}</strong>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

export default AIDashboard;