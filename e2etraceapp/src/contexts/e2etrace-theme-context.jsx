import React, { createContext, useContext, useState, useMemo, useEffect } from 'react';

const E2ETraceThemeContext = createContext();

export const E2ETraceThemeProvider = ({ children }) => {
    const [theme, setTheme] = useState(() => {
        // You can expand this to check user preference in localStorage
        return 'dark'; 
    });

    useEffect(() => {
        // Apply the theme to the root element
        document.documentElement.setAttribute('data-theme', theme);
    }, [theme]);

    const toggleTheme = () => {
        setTheme(prevTheme => (prevTheme === 'light' ? 'dark' : 'light'));
    };

    const value = useMemo(() => ({
        theme,
        toggleTheme
    }), [theme]);

    return (
        <E2ETraceThemeContext.Provider value={value}>
            {children}
        </E2ETraceThemeContext.Provider>
    );
};

export const e2etraceUseTheme = () => useContext(E2ETraceThemeContext);