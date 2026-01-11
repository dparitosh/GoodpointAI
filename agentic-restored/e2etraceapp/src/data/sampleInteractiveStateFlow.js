export const SAMPLE_WORKFLOW_ID = 'demo';

export const getSampleInteractiveStateFlow = () => {
  // Explicit positions prevent Cytoscape edge endpoint warnings from node overlap
  const nodes = [
    {
      id: 'start',
      label: 'Start',
      type: 'extract',
      group: 'extract',
      backgroundColor: '#42A5F5',
      properties: {
        description: 'Workflow initialized',
        owner: 'Orchestrator',
      },
      status: 'healthy',
      size: 60,
      position: { x: 100, y: 200 },
    },
    {
      id: 'extract',
      label: 'Extract',
      type: 'extract',
      group: 'extract',
      backgroundColor: '#42A5F5',
      properties: {
        description: 'Pull source data from PLM',
        source: 'Teamcenter (sample)',
      },
      size: 70,
      position: { x: 250, y: 200 },
    },
    {
      id: 'transform',
      label: 'Transform',
      type: 'transform',
      group: 'transform',
      backgroundColor: '#FB8C00',
      properties: {
        description: 'Map + normalize schema',
        rules: 'Mapping v1',
      },
      size: 70,
      position: { x: 400, y: 200 },
    },
    {
      id: 'quality',
      label: 'Validate',
      type: 'quality',
      group: 'quality',
      backgroundColor: '#43A047',
      properties: {
        description: 'Run SODA checks',
        checks: 12,
      },
      size: 70,
      position: { x: 550, y: 200 },
    },
    {
      id: 'load',
      label: 'Load',
      type: 'load',
      group: 'load',
      backgroundColor: '#5E35B1',
      properties: {
        description: 'Write to target graph',
        target: 'Neo4j',
      },
      size: 70,
      position: { x: 700, y: 200 },
    },
    {
      id: 'complete',
      label: 'Complete',
      type: 'target',
      group: 'target',
      backgroundColor: '#263238',
      properties: {
        description: 'Workflow finished',
        result: 'Success',
      },
      status: 'healthy',
      size: 60,
      position: { x: 850, y: 200 },
    },
    {
      id: 'agent',
      label: 'AI Agent',
      type: 'ai_agent',
      group: 'ai_agent',
      backgroundColor: '#6A1B9A',
      properties: {
        description: 'Guided automation agent',
        capabilities: ['route selection', 'retry', 'validation'],
      },
      size: 65,
      position: { x: 475, y: 80 },
    },
  ];

  const edges = [
    { id: 'e-start-extract', source: 'start', target: 'extract', label: 'BEGIN', type: 'FLOW' },
    { id: 'e-extract-transform', source: 'extract', target: 'transform', label: 'DATA_READY', type: 'FLOW' },
    { id: 'e-transform-quality', source: 'transform', target: 'quality', label: 'MAPPED', type: 'FLOW' },
    { id: 'e-quality-load', source: 'quality', target: 'load', label: 'VALID', type: 'FLOW' },
    { id: 'e-load-complete', source: 'load', target: 'complete', label: 'LOADED', type: 'FLOW' },
    { id: 'e-agent-transform', source: 'agent', target: 'transform', label: 'GUIDE', type: 'ASSISTS' },
    { id: 'e-agent-quality', source: 'agent', target: 'quality', label: 'CHECK', type: 'ASSISTS' },
  ];

  return { nodes, edges };
};
