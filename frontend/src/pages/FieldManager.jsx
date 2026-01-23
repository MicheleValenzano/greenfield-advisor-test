import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import toast, { Toaster } from 'react-hot-toast';
import { MapContainer, TileLayer, Marker, useMapEvents, useMap } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';


delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const API_GATEWAY_URL = "https://localhost:8000";

function ChangeView({ center, zoom }) {
  const map = useMap();
  map.setView(center, zoom);
  return null;
}

function MapClickHandler({ setForm, setMarkerPosition, clearError, setMapCenter, setZoom }) {
    useMapEvents({
        async click(e) {
            const { lat, lng } = e.latlng;
            setMarkerPosition([lat, lng]);

            setMapCenter([lat, lng]);
            setZoom(13);

            
            // Feedback immediato all'utente mentre carichiamo
            setForm(prev => ({ 
                ...prev, 
                location: `Recupero indirizzo... (${lat.toFixed(4)}, ${lng.toFixed(4)})` 
            }));
            
            try {
                // Chiamata API Reverse Geocoding (nel backend per evitare CORS)
                const response = await axios.get(`${API_GATEWAY_URL}/fields/geocoding/reverse`, {
                    params: { lat: lat, lon: lng }
                })
                
                const data = response.data;
                
                // Logica di estrazione nome (Priorità: town -> city -> village -> display_name parziale)
                const addr = data.address || {};
                const cityName = addr.town || addr.city || addr.village || addr.hamlet || addr.municipality || (data.display_name ? data.display_name.split(',')[0] : "Posizione sconosciuta");

                // Aggiornamento finale del form
                setForm(prev => ({ 
                    ...prev, 
                    location: `${cityName} (${lat.toFixed(4)}, ${lng.toFixed(4)})` 
                }));
                
                clearError('location');
                toast.success(`Posizione: ${cityName}`);

            } catch (error) {
                console.error("Errore reverse geocoding:", error);
                // Fallback: se l'API fallisce, lasciamo solo le coordinate
                setForm(prev => ({ 
                    ...prev, 
                    location: `${lat.toFixed(4)}, ${lng.toFixed(4)}` 
                }));
                toast.error("Impossibile recuperare il nome della città");
            }
        },
    });
    return null;
}

const FieldManager = () => {
    const { token, selectedField, setSelectedField } = useAuth();
    const [fields, setFields] = useState([]);
    const [loading, setLoading] = useState(true);

    const [mapCenter, setMapCenter] = useState([41.9028, 12.4964]);
    const [markerPosition, setMarkerPosition] = useState(null);
    const [zoom, setZoom] = useState(6);

    const [form, setForm] = useState({
        name: '', start_date: '', cultivation_type: '', size: '', location: '', description: '', is_indoor: false
    });

    const [fieldErrors, setFieldErrors] = useState({});

    // STATI PER L'AUTOCOMPLETAMENTO
    const [citySuggestions, setCitySuggestions] = useState([]);
    const [loadingCities, setLoadingCities] = useState(false);

    const navigate = useNavigate();

    const clearFieldError = (fieldName) => {
        setFieldErrors(prevErrors => ({ ...prevErrors, [fieldName]: undefined }));
    };

    const getInputStyle = (fieldName) => ({
        borderColor: fieldErrors[fieldName] ? 'var(--danger, #dc3545)' : '',
    });

    // FUNZIONI DI RICERCA CITTÀ
    // Funzione per effettuare la ricerca API e popolare i suggerimenti
    const searchLocation = async (query = form.location) => {
        if (!query || query.length < 2) {
            setCitySuggestions([]);
            return;
        }
        setLoadingCities(true);
        try {

            const response = await axios.get(`${API_GATEWAY_URL}/fields/geocoding/search`, {
                params: { name: query, limit: 5 }
            });

            if (response.data.results && response.data.results.length > 0) {
                // Se la ricerca è attiva (query > 2), mostriamo i suggerimenti
                setCitySuggestions(response.data.results.map(place => ({
                    name: place.name,
                    full: `${place.name}, ${place.admin1 || '', place.country}`,
                    lat: place.latitude,
                    lng: place.longitude
                })));

                if (query === form.location && form.location.length >= 2) {
                    const place = response.data.results[0];
                    const lat = place.latitude;
                    const lng = place.longitude;
                    setMapCenter([lat, lng]);
                    setMarkerPosition([lat, lng]);
                    setZoom(13);
                    setForm(prev => ({ ...prev, location: `${place.name} (${lat.toFixed(4)}, ${lng.toFixed(4)})` }));
                    toast.success(`Trovato: ${place.name}`);
                    setCitySuggestions([]); // Chiudiamo i suggerimenti dopo la ricerca esplicita
                }
            } else {
                setCitySuggestions([]);
                if (query === form.location) {
                    toast.error("Località non trovata");
                }
            }
        } catch (error) {
            toast.error("Errore durante la ricerca API");
        } finally {
            setLoadingCities(false);
        }
    };

    // Funzione chiamata quando l'utente clicca un suggerimento
    const handleSelectSuggestion = (suggestion) => {
        const { name, lat, lng } = suggestion;

        // Aggiorna il campo Form con il nome e le coordinate per la registrazione
        setForm(prev => ({
            ...prev,
            location: `${name} (${lat.toFixed(4)}, ${lng.toFixed(4)})`
        }));

        // Aggiorna la Mappa e il Marker
        setMapCenter([lat, lng]);
        setMarkerPosition([lat, lng]);
        setZoom(13);

        // Chiude l'elenco dei suggerimenti
        setCitySuggestions([]);
        toast.success(`Posizione impostata su: ${name}`);
    };

    // Funzione chiamata ad ogni cambio dell'input "Posizione"
    const handleLocationInputChange = (e) => {
        const value = e.target.value;
        setForm({...form, location: value});
        // Ricerca automatica per popolare l'autocomplete
        clearFieldError('location');
        searchLocation(value);
    };

    const fetchFields = async () => {
        if (!token) return;
        setLoading(true);
        try {
            const response = await axios.get(`${API_GATEWAY_URL}/fields`);
            setFields(response.data);
            if (response.data.length > 0 && !selectedField) setSelectedField(response.data[0]);
        } catch (error) {
            console.error("Errore fetch campi:", error);
            if (!error.response) {
                toast.error("Errore di connessione. Riprova più tardi.");
            } else {
                const errorMsg = error.response?.data?.message || error.response?.data?.detail || "Errore nel recupero dei campi.";
                toast.error(errorMsg);
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchFields(); }, [token]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        const loadingToast = toast.loading("Registrazione campo...");
        try {

            const payload = { ...form, size: parseFloat(form.size), start_date: form.start_date === '' ? null : form.start_date };

            const response = await axios.post(`${API_GATEWAY_URL}/fields`, payload);
            toast.success("Campo registrato!", { id: loadingToast });
            
            setForm({ name: '', start_date: '', cultivation_type: '', size: '', location: '', description: '', is_indoor: false });
            setMarkerPosition(null);
            fetchFields();
        } catch (error) {
            console.error("Errore Registrazione Campo:", error);

            if (!error.response) {
                toast.error("Errore di connessione. Riprova più tardi.", { id: loadingToast });
                return;
            }

            if (error.response.status === 422 && error.response.data.errors) {
                toast.dismiss(loadingToast);
                const errorsObj = {};
                error.response.data.errors.forEach(errorItem => {
                    errorsObj[errorItem.field] = errorItem.message;
                });
                setFieldErrors(errorsObj);
                toast.error("Controlla i campi evidenziati in rosso.", { id: loadingToast });
            } else {
                const errorMsg = error.response?.data?.detail || error.response?.data?.message || "Impossibile registrare il campo.";
                toast.error(errorMsg, { id: loadingToast });
            }
        }
    };

    const handleDeleteField = async (fieldId, fieldName) => {
        
        if (!window.confirm(`Sei sicuro di voler eliminare "${fieldName}"?\nEliminerai anche tutti i sensori associati.`)) return;

        const loadingToast = toast.loading("Eliminazione...");
        try {
            await axios.delete(`${API_GATEWAY_URL}/fields/${fieldId}`);
            toast.success("Campo eliminato", { id: loadingToast });

            if (selectedField && (selectedField.field === fieldId)) setSelectedField(null);
            fetchFields();
        } catch (error) {
            if (!error.response) {
                toast.error("Errore di connessione. Riprova più tardi.", { id: loadingToast });  
            } else {
                const errorMsg = error.response?.data?.message || error.response?.data?.detail || "Errore nell'eliminazione del campo.";
                toast.error(errorMsg, { id: loadingToast });
            }
        }
    };

    const handleSelectField = (field) => {
        setSelectedField(field);
        toast.success(`Accesso a: ${field.name}`);
        setTimeout(() => navigate('/monitoring'), 500);
    };

    return (
        <div className="page-container">
            <Toaster position="top-right" />

            {/* HEADER BANNER */}
            <div className="glass-card" style={{
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                color: 'white',
                marginBottom: '2rem',
                border: 'none'
            }}>
                <h2 style={{ margin: 0, fontSize: '2rem' }}>🌱 Gestione Campi</h2>
                <p style={{ opacity: 0.9, marginTop: '0.5rem' }}>
                    Configura, geolocalizza e gestisci le tue aree di coltivazione.
                </p>
            </div>

            {/* SEZIONE INPUT E MAPPA */}
            <div className="glass-card mb-4">
                 <h3 style={{ marginTop: 0, marginBottom: '1.5rem', color: '#047857' }}>Registra Nuovo Campo</h3>

                 <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
                     {/* COLONNA SINISTRA: FORM */}
                     <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        <div>
                            <label className="text-sm font-bold text-gray-700">Nome Campo</label>
                            <input type="text" placeholder="Es. Vigna Nord" value={form.name} onChange={e => { setForm({...form, name: e.target.value}); clearFieldError('name'); }} style={getInputStyle('name')} className="input-field" required />
                            {fieldErrors.name && (
                            <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                                {fieldErrors.name}
                            </span>
                            )}
                        </div>

                        {/* CAMPO POSIZIONE CON AUTOCOMPLETAMENTO */}
                        <div style={{position: 'relative'}}>
                            <label className="text-sm font-bold text-gray-700">Posizione (Città, Reg. o Coord.)</label>
                            
                            <input
                                type="text"
                                placeholder={loadingCities ? 'Caricamento suggerimenti...' : 'Città o clicca mappa'}
                                value={form.location}
                                onChange={handleLocationInputChange}
                                onBlur={() => setTimeout(() => setCitySuggestions([]), 200)} // Chiude i suggerimenti dopo un breve ritardo
                                className="input-field"
                                style={{width: '100%', borderBottomLeftRadius: citySuggestions.length > 0 ? 0 : '0.5rem', borderBottomRightRadius: citySuggestions.length > 0 ? 0 : '0.5rem', ...getInputStyle('location')}}
                                required
                            />
                            {fieldErrors.location && (
                                <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                                    {fieldErrors.location}
                                </span>
                            )}

                            {/* LISTA SUGGERIMENTI */}
                            {citySuggestions.length > 0 && (
                                <ul style={{
                                    position: 'absolute',
                                    top: '100%',
                                    left: 0,
                                    right: 0,
                                    zIndex: 1000,
                                    listStyle: 'none',
                                    padding: 0,
                                    margin: '0',
                                    background: 'white',
                                    border: '1px solid #ccc',
                                    borderTop: 'none',
                                    borderRadius: '0 0 8px 8px',
                                    boxShadow: '0 4px 10px rgba(0,0,0,0.1)',
                                    maxHeight: '200px',
                                    overflowY: 'auto'
                                }}>
                                    {citySuggestions.map((s, index) => (
                                        <li
                                            key={index}
                                            onClick={() => handleSelectSuggestion(s)}
                                            style={{
                                                padding: '10px',
                                                cursor: 'pointer',
                                                textAlign: 'left',
                                                fontSize: '0.9rem',
                                                color: '#333',
                                                transition: 'background-color 0.1s'
                                            }}
                                            className="hover-bg-green"
                                        >
                                            {s.full}
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </div>

                        <div>
                            <label className="text-sm font-bold text-gray-700">Tipo Coltura</label>
                            <input type="text" placeholder="Es. Pomodori, Grano..." value={form.cultivation_type} onChange={e => { setForm({...form, cultivation_type: e.target.value}); clearFieldError('cultivation_type'); }} className="input-field" style={getInputStyle('cultivation_type')} required />
                            {fieldErrors.cultivation_type && (
                                <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                                    {fieldErrors.cultivation_type}
                                </span>
                            )}
                        </div>

                        <div className="split-layout" style={{ gap: '1rem', gridTemplateColumns: '1fr 1fr' }}>
                            <div>
                                <label className="text-sm font-bold text-gray-700">Data Inizio</label>
                                <input type="date" value={form.start_date} onChange={e => { setForm({...form, start_date: e.target.value}); clearFieldError('start_date'); }} className="input-field" style={getInputStyle('start_date')} />
                                {fieldErrors.start_date && (
                                    <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                                        {fieldErrors.start_date}
                                    </span>
                                )}
                            </div>
                            <div>
                                <label className="text-sm font-bold text-gray-700">Ettari (ha)</label>
                                <input type="number" placeholder="2.5" value={form.size} onChange={e => { setForm({...form, size: e.target.value}); clearFieldError('size'); }} className="input-field" style={getInputStyle('size')} step="0.1" required />
                                {fieldErrors.size && (
                                    <span style={{ color: '#dc3545', fontSize: '0.85rem', marginTop: '4px', display: 'block' }}>
                                        {fieldErrors.size}
                                    </span>
                                )}
                            </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px', background: '#f0fdf4', borderRadius: '8px' }}>
                            <input type="checkbox" id="isGreenhouse" checked={form.is_indoor} onChange={(e) => setForm({ ...form, is_indoor: e.target.checked })} style={{ width: '18px', height: '18px' }} />
                            <label htmlFor="isGreenhouse" style={{ margin: 0, cursor: 'pointer', color: '#15803d', fontWeight:'500' }}>🏠 È una serra / indoor?</label>
                        </div>

                        <button type="submit" className="btn btn-primary" style={{ width: '100%', padding: '12px', marginTop:'10px' }}>
                             + Aggiungi Campo
                        </button>
                     </form>

                     {/* COLONNA DESTRA: MAPPA */}
                     <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                         <div style={{ borderRadius: '12px', overflow: 'hidden', height: '100%', minHeight: '350px', border: '1px solid #e5e7eb', position:'relative', boxShadow: 'inset 0 0 10px rgba(0,0,0,0.05)' }}>
                            <MapContainer center={mapCenter} zoom={zoom} style={{ height: '100%', width: '100%' }}>
                                <ChangeView center={mapCenter} zoom={zoom} />
                                <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                                <MapClickHandler setForm={setForm} setMarkerPosition={setMarkerPosition} clearError={clearFieldError} setMapCenter={setMapCenter} setZoom={setZoom} />
                                {markerPosition && <Marker position={markerPosition} />}
                            </MapContainer>
                            <div style={{position:'absolute', bottom:10, left:10, right:10, background:'rgba(255,255,255,0.9)', padding:'8px', borderRadius:'8px', fontSize:'0.75rem', textAlign:'center', color:'#555', zIndex: 1000}}>
                                Clicca sulla mappa per impostare le coordinate
                            </div>
                         </div>
                     </div>
                 </div>
             </div>

             {/* LISTA CAMPI */}
             <div>
                 <h3 style={{ color: 'var(--text-main)', marginBottom:'1.5rem' }}>Le tue Colture</h3>
                 
                 {loading ? <p className="text-center text-muted">Caricamento...</p> : (
                     <div className="bento-grid">
                         {fields.length === 0 ? <div className="glass-card" style={{ gridColumn: '1/-1', textAlign: 'center', padding: '3rem', color: '#6b7280' }}>Nessun campo trovato. Usa il form sopra per crearne uno.</div> :
                         fields.map((field, index) => {
                             const isSelected = selectedField && (selectedField.field === field.field);
                             return (
                             <div 
                                key={index} 
                                onClick={() => handleSelectField(field)} 
                                className="glass-card field-card"
                                style={{
                                    cursor: 'pointer', 
                                    border: isSelected ? '2px solid #10b981' : '1px solid transparent',
                                    background: isSelected ? '#ecfdf5' : 'white',
                                    transition: 'all 0.2s ease'
                                }}
                             >
                                 <div className="flex-between" style={{ marginBottom: '1rem' }}>
                                     <h4 style={{ margin: 0, fontSize: '1.2rem', color: isSelected ? '#047857' : '#1f2937' }}>
                                        {field.name} {field.is_indoor && "🏠"}
                                     </h4>
                                     <button 
                                         onClick={(e) => { e.stopPropagation(); handleDeleteField(field.field, field.name); }}
                                         style={{ background: 'transparent', border: 'none', color: '#9ca3af', cursor: 'pointer', padding: '5px' }}
                                         className="hover-danger"
                                         title="Elimina"
                                     >
                                         ✕
                                     </button>
                                 </div>
                                 
                                 <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.9rem', color: '#4b5563' }}>
                                     <div className="flex-between"><span>Coltura:</span> <strong style={{color:'#111'}}>{field.cultivation_type}</strong></div>
                                     <div className="flex-between"><span>Estensione:</span> <strong>{field.size} ha</strong></div>
                                     <div className="flex-between"><span>Inizio:</span> <span>{field.start_date}</span></div>
                                 </div>

                                 <div style={{ marginTop: '1.5rem', textAlign: 'center' }}>
                                     {isSelected ? 
                                        <span className="badge" style={{background:'#10b981', color:'white'}}>Selezionato</span> : 
                                        <span style={{ fontSize: '0.8rem', color: '#059669', textDecoration: 'underline' }}>Clicca per gestire</span>
                                     }
                                 </div>
                             </div>
                         )})}
                     </div>
                 )}
             </div>
         </div>
     );
 };
 export default FieldManager;