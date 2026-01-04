import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
// Loghi
import logoImage from '../assets/logo.png';

const Navbar = () => {
    const navigate = useNavigate();
    const { logout } = useAuth();

    return (
        <div className="navbar-container">
            <nav className="navbar-glass">
                {/* LOGO */}
                <div 
                    onClick={() => navigate('/dashboard')} 
                    style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}
                >
                    <img 
                        src={logoImage} 
                        alt="GreenField Logo" 
                        style={{ 
                            height: '45px', 
                            width: 'auto', 
                            objectFit: 'contain', 
                            borderRadius: '8px',
                            mixBlendMode: 'multiply' // Rende trasparente lo sfondo bianco del JPG
                        }} 
                    />
                </div>

                {/* MENU LINKS */}
                <div className="nav-links">

                    <NavLink to="/fields" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                        🌱 Campi
                    </NavLink>

                    <NavLink to="/monitoring" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                        📊 Monitor
                    </NavLink>

                    <NavLink to="/ai-dashboard" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                        🧠 AI Advisor
                    </NavLink>

                    <NavLink to="/settings/sensors" className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
                        ⚙️ Configurazione Sensori
                    </NavLink>

                    <NavLink to="/profile" className={({ isActive }) => `nav-item profile-link ${isActive ? 'active' : ''}`}>
                        👤 Account
                    </NavLink>


                            
                    <button 
                        onClick={() => { logout(); navigate('/login'); }}
                        className="nav-btn-logout"
                    >
                        Logout
                    </button>
                </div>
            </nav>
        </div>
    );
};

export default Navbar;