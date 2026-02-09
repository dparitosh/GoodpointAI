import React, { createContext, useState, useContext } from 'react';

const GraphFilterContext = createContext(null);

export const GraphFilterProvider = ({ children }) => {
  const [filterText, setFilterText] = useState('');

  return (
    <GraphFilterContext.Provider value={{ filterText, setFilterText }}>
      {children}
    </GraphFilterContext.Provider>
  );
};

export const useGraphFilter = () => {
  const context = useContext(GraphFilterContext);
  if (!context) {
    throw new Error('useGraphFilter must be used within a GraphFilterProvider');
  }
  return context;
};