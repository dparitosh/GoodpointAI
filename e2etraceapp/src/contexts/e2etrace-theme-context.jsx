import React, { createContext, useContext, useState, useMemo, useEffect } from 'react';

const E2ETraceThemeContext = createContext();

export const E2ETraceThemeProvider = ({ children }) => {
    const [theme, setTheme] = useState(() => {
        // You can expand this to check user preference in localStorage
        const storedTheme = localStorage.getItem('e2etrace-theme');
        if (storedTheme) {
            return storedTheme;
        }
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    });

    useEffect(() => {
        // Apply the theme to the root element
        document.documentElement.setAttribute('data-theme', theme);
        try {
            localStorage.setItem('e2etrace-theme', theme);
        } catch {
            // ignore storage failures (private mode, quota, etc.)
        }
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

export const useE2ETraceTheme = () => useContext(E2ETraceThemeContext);

// Backwards compatibility for existing imports.
export const e2etraceUseTheme = useE2ETraceTheme;