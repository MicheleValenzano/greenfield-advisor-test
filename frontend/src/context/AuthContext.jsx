// frontend/src/context/AuthContext.jsx
import { createContext, useState, useContext, useEffect } from "react";
import axios from "axios";
import { useNavigate, useLocation, Navigate } from "react-router-dom";

const AuthContext = createContext();
const API = "https://localhost:8000";

export const AuthProvider = ({ children }) => {
  const navigate = useNavigate();
  // const location = useLocation();

  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem("token") || null);
  // Aggiungiamo uno stato di caricamento per evitare flash o redirect errati
  const [loading, setLoading] = useState(true);

  const [selectedField, setSelectedField] = useState(() => {
    const saved = localStorage.getItem("selectedField");
    return saved ? JSON.parse(saved) : null;
  });

  const logout = () => {
    setToken(null);
    setUser(null);
    setSelectedField(null);
    localStorage.removeItem("token");
    localStorage.removeItem("selectedField");
    navigate("/login");
  }

  // AXIOS INTERCEPTOR
  useEffect(() => {
    const interceptor = axios.interceptors.response.use(
      (response) => {
        return response;
      },
      (error) => {
        if (error.response && (error.response.status === 401 || error.response.status === 403)) {
          console.log("Sessione scaduta o non autorizzata. Login richiesto.");
          logout();
        }
        // Restituiso l'errore al componente che ha fatto la chiamata
        return Promise.reject(error);
      }
    );

    return () => {
      axios.interceptors.response.eject(interceptor);
    };
  }, [navigate]);

  // CARICA UTENTE DAL BACKEND
  const fetchUser = async (jwt) => {
    try {
      const res = await axios.get(`${API}/users/me`, {
        headers: { Authorization: `Bearer ${jwt}` },
      });
      setUser(res.data);
    } catch (err) {
      console.error("Errore caricamento profilo utente:", err);
      // NON rimuoviamo il token subito se è solo un errore di rete.
      // Lo rimuoviamo solo se è un errore di autorizzazione (401/403)
      // Check
      // if (err.response && (err.response.status === 401 || err.response.status === 403)) {
      //   logout();
      // }
    } finally {
      setLoading(false);
    }
  };

  // ========= GESTIONE TOKEN =========
  useEffect(() => {
    if (token) {
      localStorage.setItem("token", token);
      
      // Impostazione dell'header di default per tutte le richieste axios
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;

      if (!user) {
        fetchUser(token);
      } else {
        setLoading(false);
      }
    } else {
      localStorage.removeItem("token");
      // Rimuoviamo l'header di autorizzazione se non c'è token
      delete axios.defaults.headers.common['Authorization'];
      setUser(null);
      setLoading(false);
    }
  }, [token]);

  // ========= GESTIONE CAMPO SELEZIONATO =========
  useEffect(() => {
    if (selectedField) {
      localStorage.setItem("selectedField", JSON.stringify(selectedField));
    } else {
      localStorage.removeItem("selectedField");
    }
  }, [selectedField]);

  // ========= LOGIN =========
  const login = (jwtToken, userData = null) => {
    setLoading(true); // Inizio login
    setToken(jwtToken);
    
    // Se abbiamo già i dati utente dal login (opzionale), li settiamo subito
    if (userData) {
      setUser(userData);
      setLoading(false);
    }
    
    // Naviga alla dashboard (o fields)
    navigate("/dashboard"); 
  };

  return (
    <AuthContext.Provider
      value={{ 
        user, 
        setUser, 
        token, 
        login, 
        logout, 
        selectedField, 
        setSelectedField,
        loading, 
        isAuthenticated: !!token // Helper booleano
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);

// ========= COMPONENTE ROTTA PROTETTA =========
// Spostato qui per avere accesso a useAuth
export const ProtectedRoute = ({ children }) => {
  const { token, loading } = useAuth();

  // 1. Se stiamo ancora caricando (check token/fetch user), mostriamo uno spinner o nulla
  if (loading) {
    return <div style={{ textAlign: "center", marginTop: "50px" }}>Caricamento in corso...</div>;
  }

  // 2. Se finito il caricamento non c'è token, REDIRECT al login
  if (!token) {
    return <Navigate to="/login" replace />;
  }

  // 3. Altrimenti mostra la pagina protetta
  return children;
};