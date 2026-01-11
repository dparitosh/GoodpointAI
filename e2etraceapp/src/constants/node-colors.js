/**
 * DYNAMIC COLOR SYSTEM for Node and Relationship Types
 * 
 * Colors are AUTO-GENERATED based on type names using a deterministic hash.
 * This ensures consistent colors without hardcoding specific types.
 * 
 * Node/Relationship types are fetched dynamically from Neo4j via /api/entities
 */

// ============================================
// COLOR PALETTE - VIBGYOR (Rainbow) + Green variations
// ============================================

/**
 * VIBGYOR color palette for node types
 * Violet → Indigo → Blue → Green → Yellow → Orange → Red
 * Plus additional green/teal shades for variety
 */
const NODE_COLOR_PALETTE = [
  // VIBGYOR Primary Colors
  '#8B00FF',   // Violet
  '#4B0082',   // Indigo
  '#0000FF',   // Blue
  '#00FF00',   // Green
  '#FFFF00',   // Yellow
  '#FF7F00',   // Orange
  '#FF0000',   // Red
  
  // Extended VIBGYOR variations
  '#9400D3',   // Dark Violet
  '#6A5ACD',   // Slate Blue (Indigo family)
  '#1E90FF',   // Dodger Blue
  '#00CED1',   // Dark Turquoise (Blue-Green)
  '#32CD32',   // Lime Green
  '#228B22',   // Forest Green
  '#9ACD32',   // Yellow Green
  '#FFD700',   // Gold (Yellow family)
  '#FFA500',   // Orange
  '#FF6347',   // Tomato (Orange-Red)
  '#DC143C',   // Crimson (Red family)
  
  // Additional greens (user requested)
  '#00FA9A',   // Medium Spring Green
  '#2E8B57',   // Sea Green
  '#3CB371',   // Medium Sea Green
  '#20B2AA',   // Light Sea Green
  '#008B8B',   // Dark Cyan
];

/**
 * VIBGYOR color palette for relationship/edge types
 */
const EDGE_COLOR_PALETTE = [
  '#8B00FF',   // Violet
  '#4B0082',   // Indigo
  '#0000FF',   // Blue
  '#00FF00',   // Green
  '#FFFF00',   // Yellow
  '#FF7F00',   // Orange
  '#FF0000',   // Red
  '#00CED1',   // Dark Turquoise
  '#32CD32',   // Lime Green
  '#FFD700',   // Gold
];

/**
 * Diverse shape options for nodes
 * Each type gets a distinct shape based on hash
 */
const SHAPE_OPTIONS = [
  'ellipse',           // Circle/Oval - common nodes
  'rectangle',         // Square - data containers
  'round-rectangle',   // Rounded box - entities
  'diamond',           // Diamond - decision/transform
  'hexagon',           // Hexagon - processing
  'octagon',           // Octagon - stop/important
  'triangle',          // Triangle - directional
  'star',              // Star - special/highlight
  'barrel',            // Cylinder - databases
  'pentagon',          // Pentagon - documents
  'vee',               // V-shape - connectors
  'rhomboid',          // Parallelogram - I/O
];

/**
 * Edge style options
 */
const EDGE_STYLE_OPTIONS = ['solid', 'dashed', 'dotted'];

// ============================================
// HASH FUNCTION - Deterministic color assignment
// ============================================

/**
 * Generate a deterministic hash from a string
 * Same input always produces same output
 * @param {string} str - Input string (type name)
 * @returns {number} Hash value
 */
const hashString = (str) => {
  if (!str) return 0;
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return Math.abs(hash);
};

// ============================================
// DYNAMIC COLOR/SHAPE GETTERS
// ============================================

/**
 * Get color for a node type - auto-assigned from palette
 * @param {string} type - Node type/label name
 * @returns {string} Hex color code
 */
export const getNodeColor = (type) => {
  if (!type) return '#95a5a6'; // Default gray
  const hash = hashString(type);
  return NODE_COLOR_PALETTE[hash % NODE_COLOR_PALETTE.length];
};

/**
 * Get shape for a node type - auto-assigned from options
 * @param {string} type - Node type/label name
 * @returns {string} Cytoscape shape name
 */
export const getNodeShape = (type) => {
  if (!type) return 'ellipse';
  const hash = hashString(type);
  return SHAPE_OPTIONS[hash % SHAPE_OPTIONS.length];
};

/**
 * Get color for an edge/relationship type
 * @param {string} type - Relationship type name
 * @returns {string} Hex color code
 */
export const getEdgeColor = (type) => {
  if (!type) return '#7f8c8d'; // Default gray
  const hash = hashString(type);
  return EDGE_COLOR_PALETTE[hash % EDGE_COLOR_PALETTE.length];
};

/**
 * Get style for an edge/relationship type
 * @param {string} type - Relationship type name
 * @returns {string} CSS line style
 */
export const getEdgeStyle = (type) => {
  if (!type) return 'solid';
  const hash = hashString(type);
  return EDGE_STYLE_OPTIONS[hash % EDGE_STYLE_OPTIONS.length];
};

// ============================================
// CONFIG OBJECTS (for components that need them)
// ============================================

/**
 * Get complete node type config
 * @param {string} type - Node type name
 * @returns {Object} { color, shape, label }
 */
export const getNodeTypeConfig = (type) => {
  return {
    color: getNodeColor(type),
    shape: getNodeShape(type),
    label: type || 'Unknown',
  };
};

/**
 * Get complete edge type config
 * @param {string} type - Relationship type name
 * @returns {Object} { color, style, label }
 */
export const getEdgeTypeConfig = (type) => {
  return {
    color: getEdgeColor(type),
    style: getEdgeStyle(type),
    label: type || 'Unknown',
  };
};

// ============================================
// LEGACY EXPORTS (for backward compatibility)
// These are kept empty - colors are now dynamic
// ============================================

export const NODE_COLORS = {};
export const NODE_SHAPES = {};
export const EDGE_COLORS = {};
export const EDGE_STYLES = {};

/**
 * Get all defined node types - now returns empty (types come from Neo4j)
 * @deprecated Use /api/entities to fetch types from Neo4j
 */
export const getAllNodeTypes = () => [];

// ============================================
// UTILITY: Build legend from fetched types
// ============================================

/**
 * Build a legend configuration from fetched entity types
 * @param {Array} entities - Array from /api/entities endpoint
 * @returns {Object} { nodeTypes: [...], relationshipTypes: [...] }
 */
export const buildLegendFromEntities = (entities) => {
  const nodeTypes = [];
  const relationshipTypes = [];

  entities.forEach(entity => {
    if (entity.type === 'node') {
      nodeTypes.push({
        label: entity.label,
        color: getNodeColor(entity.label),
        shape: getNodeShape(entity.label),
      });
    } else if (entity.type === 'relationship') {
      relationshipTypes.push({
        label: entity.label,
        color: getEdgeColor(entity.label),
        style: getEdgeStyle(entity.label),
      });
    }
  });

  return { nodeTypes, relationshipTypes };
};
