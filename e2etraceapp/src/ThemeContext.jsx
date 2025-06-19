import React, { createContext, useState, useContext } from 'react';

// Define initial values for the theme variables we want to make configurable.
// These should ideally match the defaults used in your CSS or NDL system.
const initialThemeConfig = {
    // This context is no longer directly applying NDL CSS variables.
    // It's kept minimal. If not used for any theme switching (e.g., Fluent UI), it could be removed.
};

const ThemeContext = createContext({
    themeConfig: initialThemeConfig,
    setThemeConfig: () => {},
});

export const ThemeProvider = ({ children }) => {
    const [themeConfig, setThemeConfig] = useState(initialThemeConfig);

    return (
        <ThemeContext.Provider value={{ themeConfig, setThemeConfig }}>
            {children}
        </ThemeContext.Provider>
    );
};

export const useTheme = () => useContext(ThemeContext);