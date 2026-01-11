import React from 'react';
import { EChartsReact } from './components/e2etrace-echarts-react.jsx'; // Import the component
import { pieChartOption } from './chartOptions'; // Import your chart configuration

function App() {
    return (
        <div>
            <h1>Hello from React!</h1>
            {/* Render the ECharts component with options */}
            <EChartsReact option={pieChartOption} style={{ height: '500px' }} />
        </div>
    );
}

export default App;