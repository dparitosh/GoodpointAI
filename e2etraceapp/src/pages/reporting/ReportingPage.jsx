import React, { useState, useEffect } from 'react';
import ReactECharts from 'echarts-for-react';
import * as echarts from 'echarts'; // Add this import for gradients
import { e2etraceFetchWithRetry } from '../../api/e2etrace-api';
import { API_CONFIG } from '../../config/api-config.js';

const chartTypes = [
  { value: 'bar', label: 'Bar Chart' },
  { value: 'line', label: 'Line Chart' },
  { value: 'pie', label: 'Pie Chart' },
  { value: 'scatter', label: 'Scatter Plot' },
  { value: 'area', label: 'Area Chart' },
];

const aggregationTypes = [
  { value: 'count', label: 'Count' },
  { value: 'sum', label: 'Sum' },
  { value: 'avg', label: 'Average' },
  { value: 'min', label: 'Minimum' },
  { value: 'max', label: 'Maximum' },
];

export default function ReportingPage() {
  const [entities, setEntities] = useState([]);
  const [entity, setEntity] = useState(null);
  const [xProp, setXProp] = useState('');
  const [yProp, setYProp] = useState('');
  const [aggregation, setAggregation] = useState('count');
  const [filter, setFilter] = useState('');
  const [chartType, setChartType] = useState('bar');
  const [loadingEntities, setLoadingEntities] = useState(false);
  const [loadingResult, setLoadingResult] = useState(false);
  const [result, setResult] = useState([]);
  const [chartOption, setChartOption] = useState(null);
  const [limit, setLimit] = useState(50);

  // Fetch available entities and properties
  useEffect(() => {
    setLoadingEntities(true);
    e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.ENTITIES)
      .then(res => res.json())
      .then(data => {
        const validEntities = data.filter(en => Array.isArray(en.properties) && en.properties.length > 0);
        setEntities(validEntities);
        // Auto-select first entity
        if (validEntities.length > 0) {
          setEntity(validEntities[0]);
          setXProp(validEntities[0].properties[0] || '');
        }
      })
      .catch(error => {
        console.error('Error fetching entities:', error);
        setEntities([]);
      })
      .finally(() => setLoadingEntities(false));
  }, []);

  // Generate chart options
  const generateChartOption = (records, chartType) => {
    if (!records || records.length === 0) return null;

    const baseOption = {
      tooltip: { trigger: 'item' },
      toolbox: {
        show: true,
        feature: {
          saveAsImage: { show: true, title: 'Save as Image' },
          dataView: { show: true, title: 'Data View' },
          restore: { show: true, title: 'Restore' },
        }
      },
      grid: { 
        left: '3%', 
        right: '4%', 
        bottom: '3%', 
        containLabel: true 
      },
    };

    switch (chartType) {
      case 'bar':
        return {
          ...baseOption,
          xAxis: { 
            type: 'category', 
            data: records.map(row => String(row.x)),
            axisLabel: { rotate: 45, interval: 0 }
          },
          yAxis: { type: 'value' },
          series: [{
            type: 'bar',
            data: records.map(row => Number(row.y) || 0),
            itemStyle: {
              color: '#188df0'
            }
          }],
        };

      case 'line':
        return {
          ...baseOption,
          xAxis: { 
            type: 'category', 
            data: records.map(row => String(row.x)),
            boundaryGap: false
          },
          yAxis: { type: 'value' },
          series: [{
            type: 'line',
            data: records.map(row => Number(row.y) || 0),
            smooth: true,
            symbol: 'circle',
            symbolSize: 6,
            lineStyle: { width: 2 }
          }],
        };

      case 'pie':
        return {
          ...baseOption,
          tooltip: { trigger: 'item', formatter: '{a} <br/>{b}: {c} ({d}%)' },
          legend: { orient: 'horizontal', bottom: 10 },
          series: [{
            type: 'pie',
            radius: ['30%', '70%'],
            data: records.map(row => ({ 
              value: Number(row.y) || 0, 
              name: String(row.x) 
            })),
            label: {
              show: true,
              formatter: '{b}: {d}%'
            }
          }],
        };

      case 'scatter':
        return {
          ...baseOption,
          xAxis: { type: 'value', name: xProp },
          yAxis: { type: 'value', name: yProp || 'Count' },
          series: [{
            type: 'scatter',
            data: records.map(row => [Number(row.x) || 0, Number(row.y) || 0]),
            symbolSize: 8
          }],
        };

      case 'area':
        return {
          ...baseOption,
          xAxis: { 
            type: 'category', 
            data: records.map(row => String(row.x)),
            boundaryGap: false
          },
          yAxis: { type: 'value' },
          series: [{
            type: 'line',
            data: records.map(row => Number(row.y) || 0),
            smooth: true,
            areaStyle: { opacity: 0.3 }
          }],
        };

      default:
        return baseOption;
    }
  };

  // Generate and run search
  const handleSearch = async () => {
    if (!entity || !xProp) {
      alert('Please select an entity and X property');
      return;
    }
    setLoadingResult(true);
    
    let cypher = '';
    if (aggregation === 'count') {
      cypher = `
        MATCH (n:\`${entity.label}\`)
        ${filter ? `WHERE n.${xProp} ${filter}` : ''}
        RETURN n.${xProp} AS x, count(*) AS y
        ORDER BY y DESC
        LIMIT ${limit}
      `;
    } else if (yProp) {
      cypher = `
        MATCH (n:\`${entity.label}\`)
        WHERE n.${yProp} IS NOT NULL ${filter ? `AND n.${xProp} ${filter}` : ''}
        RETURN n.${xProp} AS x, ${aggregation}(n.${yProp}) AS y
        ORDER BY y DESC
        LIMIT ${limit}
      `;
    } else {
      cypher = `
        MATCH (n:\`${entity.label}\`)
        ${filter ? `WHERE n.${xProp} ${filter}` : ''}
        RETURN n.${xProp} AS x, count(*) AS y
        ORDER BY y DESC
        LIMIT ${limit}
      `;
    }

    try {
      const res = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.GRAPH_QUERY, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cypher }),
      });
      const data = await res.json();
      const records = data.records || [];
      setResult(records);
      
      if (records.length > 0) {
        const chartOption = generateChartOption(records, chartType);
        chartOption.title = { 
          text: `${entity.label} - ${xProp} Analysis`,
          left: 'center',
          textStyle: { fontSize: 18, fontWeight: 'bold' }
        };
        setChartOption(chartOption);
      } else {
        setChartOption(null);
      }
    } catch (error) {
      console.error('Error:', error);
      setResult([]);
      setChartOption(null);
    } finally {
      setLoadingResult(false);
    }
  };

  return (
    <div style={{ padding: '2rem', maxWidth: 1200, margin: '0 auto' }}>
      <h2 style={{ textAlign: 'center', marginBottom: '2rem', color: '#2c3e50' }}>
        Advanced Reporting & Visualization
      </h2>
      
      {/* Enhanced Search Panel */}
      <div style={{
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
        gap: '1rem',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        borderRadius: 12, 
        padding: '2rem', 
        marginBottom: '2rem', 
        boxShadow: '0 10px 30px rgba(0,0,0,0.2)',
        color: 'white'
      }}>
        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Entity
          </label>
          <select
            value={entity ? entity.label : ''}
            onChange={e => {
              const ent = entities.find(en => en.label === e.target.value);
              setEntity(ent); setXProp(''); setYProp('');
            }}
            disabled={loadingEntities || !entities.length}
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          >
            <option value="">Select Entity</option>
            {entities.map(en => (
              <option key={en.label} value={en.label}>
                {en.label} ({en.type})
              </option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            X-Axis Property
          </label>
          <select 
            value={xProp} 
            onChange={e => setXProp(e.target.value)} 
            disabled={!entity}
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          >
            <option value="">Select Property</option>
            {entity && entity.properties && entity.properties.map(p => 
              <option key={p} value={p}>{p}</option>
            )}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Y-Axis Property
          </label>
          <select 
            value={yProp} 
            onChange={e => setYProp(e.target.value)} 
            disabled={!entity}
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          >
            <option value="">Count</option>
            {entity && entity.properties && entity.properties.map(p => 
              <option key={p} value={p}>{p}</option>
            )}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Aggregation
          </label>
          <select 
            value={aggregation} 
            onChange={e => setAggregation(e.target.value)}
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          >
            {aggregationTypes.map(agg => 
              <option key={agg.value} value={agg.value}>{agg.label}</option>
            )}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Chart Type
          </label>
          <select 
            value={chartType} 
            onChange={e => setChartType(e.target.value)}
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          >
            {chartTypes.map(ct => 
              <option key={ct.value} value={ct.value}>{ct.label}</option>
            )}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Filter (Optional)
          </label>
          <input
            type="text"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            placeholder="e.g. > 30 or = 'ACTIVE'"
            disabled={!entity || !xProp}
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Limit
          </label>
          <input
            type="number"
            value={limit}
            onChange={e => setLimit(parseInt(e.target.value) || 50)}
            min="1"
            max="1000"
            style={{ width: '100%', padding: '0.5rem', borderRadius: 6, border: 'none' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-end' }}>
          <button
            onClick={handleSearch}
            style={{ 
              width: '100%',
              padding: '0.75rem 1.5rem', 
              fontWeight: 'bold',
              background: 'linear-gradient(45deg, #FE6B8B 30%, #FF8E53 90%)',
              color: 'white',
              border: 'none',
              borderRadius: 6,
              cursor: 'pointer',
              fontSize: '1rem',
              transition: 'transform 0.2s',
            }}
            disabled={!entity || !xProp || loadingResult}
            onMouseOver={e => e.target.style.transform = 'scale(1.05)'}
            onMouseOut={e => e.target.style.transform = 'scale(1)'
            }
          >
            {loadingResult ? 'Analyzing...' : 'Generate Visualization'}
          </button>
        </div>
      </div>

      {/* Enhanced Chart Display */}
      <div style={{ 
        background: '#fff', 
        borderRadius: 12, 
        boxShadow: '0 8px 32px rgba(0,0,0,0.1)', 
        padding: '2rem', 
        marginBottom: '2rem',
        minHeight: 400
      }}>
        {chartOption ? (
          <ReactECharts 
            option={chartOption} 
            theme={theme}
            style={{ height: 500, width: '100%' }} 
            opts={{ renderer: 'canvas' }}
          />
        ) : (
          <div style={{ 
            textAlign: 'center', 
            color: '#888', 
            fontSize: '1.2rem',
            paddingTop: '3rem'
          }}>
            📊 Configure your search parameters and generate a visualization
          </div>
        )}
      </div>

      {/* Enhanced Result Table */}
      {result.length > 0 && (
        <div style={{ 
          background: '#fff', 
          borderRadius: 12, 
          boxShadow: '0 8px 32px rgba(0,0,0,0.1)', 
          overflow: 'hidden',
          marginBottom: '2rem'
        }}>
          <div style={{ 
            background: 'linear-gradient(90deg, #667eea 0%, #764ba2 100%)',
            color: 'white',
            padding: '1rem 2rem',
            fontSize: '1.1rem',
            fontWeight: 'bold'
          }}>
            📈 Data Results ({result.length} records)
          </div>
          <div style={{ maxHeight: 400, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead style={{ position: 'sticky', top: 0, background: '#f8f9fa' }}>
                <tr>
                  <th style={{ padding: '1rem', borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
                    {xProp || 'X'}
                  </th>
                  <th style={{ padding: '1rem', borderBottom: '2px solid #dee2e6', textAlign: 'left' }}>
                    {yProp || 'Count'}
                  </th>
                </tr>
              </thead>
              <tbody>
                {result.map((row, idx) => (
                  <tr key={idx} style={{ 
                    background: idx % 2 === 0 ? '#f8f9fa' : '#fff',
                    transition: 'background-color 0.2s'
                  }}>
                    <td style={{ padding: '0.75rem 1rem', borderBottom: '1px solid #dee2e6' }}>
                      {row.x}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', borderBottom: '1px solid #dee2e6' }}>
                      {typeof row.y === 'number' ? row.y.toLocaleString() : row.y}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Link to dedicated spreadsheet page */}
      <div style={{ 
        marginTop: '3rem', 
        textAlign: 'center',
        padding: '2rem',
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        borderRadius: '12px',
        color: 'white'
      }}>
        <h3 style={{ margin: '0 0 1rem 0' }}>📊 Need Advanced Data Analysis?</h3>
        <p style={{ margin: '0 0 1.5rem 0', opacity: 0.9 }}>
          Use our dedicated ECharts Spreadsheet for Excel import/export, advanced charting, and data manipulation.
        </p>
        <a 
          href="#/spreadsheet" 
          style={{
            display: 'inline-block',
            padding: '0.75rem 1.5rem',
            background: 'rgba(255, 255, 255, 0.2)',
            border: '2px solid rgba(255, 255, 255, 0.3)',
            borderRadius: '8px',
            color: 'white',
            textDecoration: 'none',
            fontWeight: 'bold',
            transition: 'all 0.3s ease'
          }}
          onMouseOver={(e) => {
            e.target.style.background = 'rgba(255, 255, 255, 0.3)';
            e.target.style.transform = 'translateY(-2px)';
          }}
          onMouseOut={(e) => {
            e.target.style.background = 'rgba(255, 255, 255, 0.2)';
            e.target.style.transform = 'translateY(0)';
          }}
        >
          🚀 Open ECharts Spreadsheet
        </a>
      </div>
    </div>
  );
}
