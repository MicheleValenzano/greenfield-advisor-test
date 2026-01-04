import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import toast, { Toaster } from 'react-hot-toast';
import { useAuth } from '../context/AuthContext';

const API_GATEWAY_URL = "https://localhost:8080";

function AIDashboard() {
    const { logout, token, selectedField } = useAuth();
    const navigate = useNavigate();
    
    // Stati
    const [readings, setReadings] = useState([]);
    const [aiResult, setAiResult] = useState(null);
    const [loadingAi, setLoadingAi] = useState(false);
    const [selectedImage, setSelectedImage] = useState(null);
    const [imageAnalysis, setImageAnalysis] = useState(null);
    const [uploadingImg, setUploadingImg] = useState(false);
    const [loading, setLoading] = useState(true);
    const [showExplanation, setShowExplanation] = useState(false);

    useEffect(() => { 
        if (!selectedField) navigate('/fields');
    }, [selectedField, navigate]);

    const getAuthHeader = () => ({ headers: { Authorization: `Bearer ${token}` } });

    const fetchData = async () => {
        if (!selectedField) { setLoading(false); return; }
        const fieldId = selectedField.id || selectedField._id;
        if (!fieldId) { setLoading(false); return; }

        try {
            const res = await axios.get(`${API_GATEWAY_URL}/sensors/readings?field_id=${fieldId}&limit=50`, getAuthHeader());
            // Inverte l'array per avere i dati dal più vecchio al più nuovo (SX -> DX nel grafico)
            setReadings([...res.data].reverse());
        } catch (e) { 
            console.error(e); 
            if (e.response?.status === 401) logout(); 
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const i = setInterval(fetchData, 5000);
        return () => clearInterval(i);
    }, [selectedField]);

    const handleAskAI = async () => {
        // Cerca l'ultima lettura valida (non necessariamente la prima dell'array se ci sono buchi)
        // Ma per semplicità prendiamo l'ultima disponibile nel dataset invertito (quindi l'ultima cronologica)
        if (!readings || readings.length === 0) {
            toast.error("Nessun dato sensori disponibile per l'analisi.");
            return;
        }

        setLoadingAi(true);
        setShowExplanation(false);
        const loadingToast = toast.loading('L\'IA sta analizzando i dati...');
        
        try {
            // Prendiamo l'ultimo elemento perché 'readings' è stato invertito per il grafico (Old -> New)
            const latestReading = readings[readings.length - 1]; 
            
            const payload = { 
                temperature: latestReading.temperature || 25.0, // Fallback safe
                humidity: latestReading.humidity || 50.0,
                soil_moisture: latestReading.soil_moisture || 40.0,
                pressure: latestReading.pressure || 1013.0
            };

            const res = await axios.post(`${API_GATEWAY_URL}/intelligent/predict`, payload, getAuthHeader());
            setAiResult(res.data);
            toast.success("Analisi completata", { id: loadingToast });
        } catch (error) { 
            const msg = error.response?.data?.detail || "Errore analisi AI";
            toast.error(msg, { id: loadingToast }); 
        } finally { 
            setLoadingAi(false); 
        }
    };

    const handleImageUpload = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        setSelectedImage(URL.createObjectURL(file));
        setUploadingImg(true);
        const loadingToast = toast.loading('Analisi drone in corso...');
        const formData = new FormData();
        formData.append('file', file);
        try {
            const res = await axios.post(`${API_GATEWAY_URL}/images/analyze`, formData, { 
                headers: { 'Content-Type': 'multipart/form-data', ...getAuthHeader().headers } 
            });
            setImageAnalysis(res.data);
            toast.success("Analisi completata", { id: loadingToast });
        } catch { toast.error("Errore upload immagine", { id: loadingToast }); } finally { setUploadingImg(false); }
    };

    return (
        <div className="page-container">
            <Toaster position="top-right" />
            
            {/* HEADER BANNER - STILE VIOLA PER AI */}
            <div className="glass-card" style={{ 
                background: 'linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%)', 
                color: 'white', 
                marginBottom: '2rem',
                border: 'none'
            }}>
                <h2 style={{ margin: 0, fontSize: '2rem' }}>🧠 Intelligenza Artificiale</h2>
                <p style={{ opacity: 0.9, marginTop: '0.5rem' }}>
                    Analisi predittiva e visione computerizzata per il campo: <strong>{selectedField ? selectedField.name : '...'}</strong>
                </p>
            </div>

            {loading ? <div style={{textAlign:'center', marginTop: '50px', color:'var(--text-muted)'}}>Caricamento dati in corso...</div> : (
                <div className="split-layout">
                    
                    {/* COLONNA SINISTRA: DATI STORICI (Charts) */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        
                        {/* CHART 1: TEMP */}
                        <div className="glass-card">
                            <h3 style={{color:'#ef4444', marginTop:0, fontSize:'1.1rem'}}>🌡️ Trend Temperatura</h3>
                            <ResponsiveContainer width="100%" height={160}>
                                <AreaChart data={readings}>
                                    <defs>
                                        <linearGradient id="colorTemp" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#ef4444" stopOpacity={0.8}/><stop offset="95%" stopColor="#ef4444" stopOpacity={0}/></linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                                    <XAxis dataKey="timestamp" tick={false} axisLine={false} />
                                    <YAxis axisLine={false} tickLine={false} width={30} />
                                    <Tooltip contentStyle={{ borderRadius:'12px' }} labelFormatter={(l)=>new Date(l).toLocaleTimeString()} />
                                    {/* AGGIUNTO connectNulls={true} */}
                                    <Area type="monotone" dataKey="temperature" stroke="#ef4444" fill="url(#colorTemp)" strokeWidth={2} connectNulls={true} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>

                        {/* CHART 2: HUMIDITY */}
                        <div className="glass-card">
                            <h3 style={{color:'#06b6d4', marginTop:0, fontSize:'1.1rem'}}>💧 Trend Umidità</h3>
                            <ResponsiveContainer width="100%" height={160}>
                                <AreaChart data={readings}>
                                    <defs>
                                        <linearGradient id="colorHum" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#06b6d4" stopOpacity={0.8}/><stop offset="95%" stopColor="#06b6d4" stopOpacity={0}/></linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                                    <XAxis dataKey="timestamp" tick={false} axisLine={false} />
                                    <YAxis domain={[0, 100]} axisLine={false} tickLine={false} width={30} />
                                    <Tooltip contentStyle={{ borderRadius:'12px' }} labelFormatter={(l)=>new Date(l).toLocaleTimeString()} />
                                    {/* AGGIUNTO connectNulls={true} */}
                                    <Area type="monotone" dataKey="humidity" stroke="#06b6d4" fill="url(#colorHum)" strokeWidth={2} connectNulls={true} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>

                        {/* CHART 3: SOIL */}
                        <div className="glass-card">
                            <h3 style={{color:'#d97706', marginTop:0, fontSize:'1.1rem'}}>🌱 Umidità Suolo</h3>
                            <ResponsiveContainer width="100%" height={160}>
                                <AreaChart data={readings}>
                                    <defs>
                                        <linearGradient id="colorSoil" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#d97706" stopOpacity={0.8}/><stop offset="95%" stopColor="#d97706" stopOpacity={0}/></linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} />
                                    <XAxis dataKey="timestamp" tick={false} axisLine={false} />
                                    <YAxis domain={[0, 100]} axisLine={false} tickLine={false} width={30} />
                                    <Tooltip contentStyle={{ borderRadius:'12px' }} labelFormatter={(l)=>new Date(l).toLocaleTimeString()} />
                                    {/* AGGIUNTO connectNulls={true} */}
                                    <Area type="monotone" dataKey="soil_moisture" stroke="#d97706" fill="url(#colorSoil)" strokeWidth={2} connectNulls={true} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>

                    {/* COLONNA DESTRA: STRUMENTI AI */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        
                        {/* 1. AI PREDICTOR */}
                        <div className="glass-card" style={{ border: '2px solid #ddd6fe', background: 'linear-gradient(to bottom right, #fff, #f5f3ff)' }}>
                            <div className="flex-between">
                                <h3 style={{marginTop:0, color:'#6d28d9'}}>🔮 AI Advisor</h3>
                                <span style={{fontSize:'1.5rem'}}>🤖</span>
                            </div>
                            <p className="text-muted text-sm" style={{marginBottom:'1rem'}}>L'IA analizza i dati attuali (Temp, Umidità, Suolo) per suggerire interventi.</p>
                            
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
                                    
                                    <p style={{fontSize:'0.95rem', color:'#4c1d95', lineHeight:'1.5', fontWeight: 500}}>
                                        "{aiResult.advice}"
                                    </p>

                                    <div style={{marginTop:'10px'}}>
                                        <button 
                                            onClick={() => setShowExplanation(!showExplanation)}
                                            style={{background:'transparent', border:'none', color:'#7c3aed', fontSize:'0.8rem', cursor:'pointer', padding:0, textDecoration:'underline'}}
                                        >
                                            {showExplanation ? 'Nascondi dettagli' : 'Perché questo risultato?'}
                                        </button>
                                        
                                        {showExplanation && (
                                            <div style={{marginTop:'10px', background:'white', padding:'10px', borderRadius:'8px', fontSize:'0.85rem', color:'#6b7280', border:'1px solid #e5e7eb'}}>
                                                <strong>Input Analizzati:</strong><br/>
                                                🌡️ Temp: {aiResult.details?.input_received?.temperature}°C<br/>
                                                💧 Umidità: {aiResult.details?.input_received?.humidity}%<br/>
                                                🌱 Suolo: {aiResult.details?.input_received?.soil_moisture}%
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* 2. DRONE VISION */}
                        <div className="glass-card">
                            <div className="flex-between">
                                <h3 style={{color:'#059669', marginTop:0}}>🚁 Drone Vision</h3>
                                <span style={{fontSize:'1.5rem'}}>📸</span>
                            </div>
                            <p className="text-muted text-sm">Carica una foto aerea per analizzare l'indice NDVI.</p>
                            
                            <div 
                                style={{
                                    border:'2px dashed #10b981', borderRadius:'12px', padding:'20px', 
                                    textAlign:'center', background:'rgba(236, 253, 245, 0.5)', cursor:'pointer', 
                                    transition:'all 0.2s', marginTop:'1rem'
                                }} 
                                onClick={() => document.getElementById('imgUpload').click()}
                                onMouseOver={(e) => e.currentTarget.style.background = 'rgba(236, 253, 245, 0.8)'}
                                onMouseOut={(e) => e.currentTarget.style.background = 'rgba(236, 253, 245, 0.5)'}
                            >
                                <input type="file" id="imgUpload" accept="image/*" style={{display:'none'}} onChange={handleImageUpload} />
                                <div style={{fontSize:'2rem', marginBottom:'0.5rem', color:'#059669'}}>☁️</div>
                                <div style={{color:'#047857', fontWeight:'bold', fontSize:'0.9rem'}}>Clicca per caricare</div>
                                <div style={{fontSize:'0.75rem', color:'#6b7280'}}>JPG/PNG Max 5MB</div>
                            </div>

                            {selectedImage && (
                                <div style={{marginTop:'1rem', borderRadius:'12px', overflow:'hidden', border:'1px solid #e5e7eb'}}>
                                    <img src={selectedImage} alt="Preview" style={{width:'100%', display:'block'}} />
                                </div>
                            )}

                            {imageAnalysis && !uploadingImg && (
                                <div style={{marginTop:'1rem', background:'#ecfdf5', padding:'1rem', borderRadius:'12px', border:'1px solid #6ee7b7'}}>
                                    <div className="flex-between" style={{borderBottom:'1px solid #d1fae5', paddingBottom:'0.5rem', marginBottom:'0.5rem'}}>
                                        <span style={{color:'#065f46', fontSize:'0.9rem'}}>NDVI Index</span> 
                                        <strong style={{color: '#047857'}}>{imageAnalysis.ndvi_index?.toFixed(3) || "N/A"}</strong>
                                    </div>
                                    <div className="flex-between" style={{borderBottom:'1px solid #d1fae5', paddingBottom:'0.5rem', marginBottom:'0.5rem'}}>
                                        <span style={{color:'#065f46', fontSize:'0.9rem'}}>Salute</span> 
                                        <strong style={{color: imageAnalysis.health_score < 50 ? '#dc2626' : '#059669'}}>
                                            {imageAnalysis.health_score}%
                                        </strong>
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