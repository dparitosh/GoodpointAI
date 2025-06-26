import React, { useRef, useEffect } from 'react';
import * as echarts from 'echarts';
import { PieChart, BarChart } from 'echarts/charts';
import { CanvasRenderer } from 'echarts/renderers';
import { LegendComponent, TooltipComponent } from 'echarts/components';
echarts.use([PieChart, BarChart, CanvasRenderer, LegendComponent, TooltipComponent]); // Register the required components
/**
 * A reusable React component to render Apache ECharts for E2ETrace.
 * @param {object} option - The ECharts option object that defines the chart.
 * @param {object} style - The CSS style for the chart container.
 * @param {string} theme - The ECharts theme to use (e.g., 'light', 'dark').
 */
export function EChartsReact({ option, style, theme }) {
  const chartRef = useRef(null);

  useEffect(() => {
    let chartInstance = null;
    if (chartRef.current) {
      chartInstance = echarts.init(chartRef.current, theme, { renderer: 'svg' });
      chartInstance.setOption(option);
    }

    const handleResize = () => {
      chartInstance?.resize();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      chartInstance?.dispose();
      window.removeEventListener('resize', handleResize);
    };
  }, [option, theme]);

  return <div ref={chartRef} style={style || { width: '100%', height: '400px' }} />;
}