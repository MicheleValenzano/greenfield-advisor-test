import React from 'react';
import { Outlet } from 'react-router-dom';
import Navbar from '../components/Navbar';

const MainLayout = () => {
    return (
        <div className="main-layout">
            {/* Navbar "Sticky" */}
            <Navbar />
            
            {/* Contenuto della pagina che cambia */}
            <main style={{ flex: 1, position: 'relative' }}>
                <Outlet />
            </main>
        </div>
    );
};

export default MainLayout;