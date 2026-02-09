/**
 * Centralized ETL (Extract, Transform, Load) Engine
 * Handles all data processing operations in a structured pipeline
 */

import { e2etraceFetchWithRetry } from '../api/e2etrace-api';
import { API_CONFIG } from '../config/api-config.js';
import { readExcelArrayBufferToAoa } from '../utils/spreadsheet-utils.js';

class ETLEngine {
  constructor() {
    this.pipelines = new Map();
    this.processors = new Map();
    this.validators = new Map();
    this.extractors = new Map();
    this.transformers = new Map();
    this.loaders = new Map();
    
    this.initializeDefaultProcessors();
  }

  initializeDefaultProcessors() {
    // Use arrow functions to avoid binding issues
    // Initialize default extractors
    this.registerExtractor('neo4j', (config) => this.extractFromNeo4j(config));
    this.registerExtractor('csv', (config) => this.extractFromCSV(config));
    this.registerExtractor('json', (config) => this.extractFromJSON(config));
    this.registerExtractor('xml', (config) => this.extractFromXML(config));

    // Initialize default transformers
    this.registerTransformer('mapping', (data, config) => this.applyDataMapping(data, config));
    this.registerTransformer('normalize', (data, config) => this.normalizeData(data, config));
    this.registerTransformer('cleanse', (data, config) => this.cleanseData(data, config));

    // Initialize default loaders
    this.registerLoader('neo4j', (data, config) => this.loadToNeo4j(data, config));
    this.registerLoader('csv', (data, config) => this.loadToCSV(data, config));

    // Initialize validators
    this.registerValidator('schema', (data, config) => this.validateSchema(data, config));
    this.registerValidator('business', (data, config) => this.validateBusinessRules(data, config));
  }

  // ============= PIPELINE MANAGEMENT =============
  
  createPipeline(name, config) {
    const pipeline = {
      id: Date.now().toString(),
      name,
      config,
      status: 'created',
      steps: [],
      metrics: {
        recordsProcessed: 0,
        errors: 0,
        warnings: 0,
        duration: 0,
        throughput: 0
      },
      history: []
    };
    
    this.pipelines.set(pipeline.id, pipeline);
    return pipeline;
  }

  async executePipeline(pipelineId, inputData = null, options = {}) {
    const pipeline = this.pipelines.get(pipelineId);
    if (!pipeline) throw new Error(`Pipeline not found: ${pipelineId}`);

    pipeline.status = 'running';
    pipeline.metrics.startTime = Date.now();
    
    try {
      let data = inputData;
      const results = [];

      // Execute ETL steps in sequence
      for (const step of pipeline.steps) {
        const stepResult = await this.executeStep(step, data, options);
        results.push(stepResult);
        data = stepResult.data;
        
        // Update metrics
        pipeline.metrics.recordsProcessed += stepResult.recordsProcessed || 0;
        pipeline.metrics.errors += stepResult.errors?.length || 0;
        pipeline.metrics.warnings += stepResult.warnings?.length || 0;
      }

      pipeline.status = 'completed';
      pipeline.metrics.endTime = Date.now();
      pipeline.metrics.duration = pipeline.metrics.endTime - pipeline.metrics.startTime;
      pipeline.metrics.throughput = pipeline.metrics.recordsProcessed / (pipeline.metrics.duration / 1000);

      return {
        pipelineId,
        status: 'success',
        data,
        results,
        metrics: pipeline.metrics
      };

    } catch (error) {
      pipeline.status = 'failed';
      pipeline.metrics.endTime = Date.now();
      pipeline.metrics.duration = pipeline.metrics.endTime - pipeline.metrics.startTime;
      
      throw new Error(`Pipeline execution failed: ${error.message}`);
    }
  }

  async executeStep(step, data, options) {
    switch (step.type) {
      case 'extract':
        return await this.extract(step.extractor, step.config, options);
      case 'transform':
        return await this.transform(step.transformer, data, step.config, options);
      case 'load':
        return await this.load(step.loader, data, step.config, options);
      case 'validate':
        return await this.validate(step.validator, data, step.config, options);
      default:
        throw new Error(`Unknown step type: ${step.type}`);
    }
  }

  // ============= EXTRACT OPERATIONS =============

  registerExtractor(name, extractorFn) {
    this.extractors.set(name, extractorFn);
  }

  async extract(extractorName, config, options = {}) {
    const extractor = this.extractors.get(extractorName);
    if (!extractor) throw new Error(`Extractor not found: ${extractorName}`);
    
    const startTime = Date.now();
    try {
      const result = await extractor(config, options);
      return {
        type: 'extract',
        extractor: extractorName,
        data: result.data,
        recordsProcessed: result.recordCount || 0,
        duration: Date.now() - startTime,
        metadata: result.metadata || {}
      };
    } catch (error) {
      throw new Error(`Extract operation failed (${extractorName}): ${error.message}`);
    }
  }

  async extractFromNeo4j(config) {
    const { query, params = {} } = config;
    const response = await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.GRAPH_QUERY, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, params })
    });
    
    const result = await response.json();
    return {
      data: result.records || [],
      recordCount: result.records?.length || 0,
      metadata: { database: 'neo4j', query }
    };
  }

  async extractFromCSV(config) {
    const { file, url, delimiter = ',' } = config;
    let data = [];
    let headers = [];
    
    if (file) {
      // Check if it's an Excel file
      const fileName = file.name || '';
      const isExcel = fileName.endsWith('.xlsx') || fileName.endsWith('.xls');
      
      if (isExcel) {
        // Handle Excel files
        const arrayBuffer = await this.readFileAsArrayBuffer(file);
        const jsonData = await readExcelArrayBufferToAoa(arrayBuffer);
        
        if (jsonData.length > 0) {
          headers = jsonData[0];
          data = jsonData.slice(1).map(row => {
            const record = {};
            headers.forEach((header, index) => {
              record[header] = row[index] || '';
            });
            return record;
          });
        }
      } else {
        // Handle CSV files
        const csvText = await this.readFileAsText(file);
        const lines = csvText.split('\n').filter(line => line.trim());
        headers = lines[0].split(delimiter);
        data = lines.slice(1).map(line => {
          const values = line.split(delimiter);
          const record = {};
          headers.forEach((header, index) => {
            record[header.trim()] = values[index]?.trim() || '';
          });
          return record;
        });
      }
    } else if (url) {
      const response = await fetch(url);
      const csvText = await response.text();
      const lines = csvText.split('\n').filter(line => line.trim());
      headers = lines[0].split(delimiter);
      data = lines.slice(1).map(line => {
        const values = line.split(delimiter);
        const record = {};
        headers.forEach((header, index) => {
          record[header.trim()] = values[index]?.trim() || '';
        });
        return record;
      });
    } else {
      throw new Error('CSV extractor requires file or URL');
    }

    return {
      data,
      recordCount: data.length,
      metadata: { format: 'csv', headers }
    };
  }

  async extractFromJSON(config) {
    const { file, url, data: jsonData } = config;
    let data = jsonData;
    
    if (file) {
      const text = await this.readFileAsText(file);
      data = JSON.parse(text);
    } else if (url) {
      const response = await fetch(url);
      data = await response.json();
    }

    const records = Array.isArray(data) ? data : [data];
    return {
      data: records,
      recordCount: records.length,
      metadata: { format: 'json' }
    };
  }

  async extractFromXML(config) {
    const { file, url, rootElement = 'root' } = config;
    let xmlText = '';
    
    if (file) {
      xmlText = await this.readFileAsText(file);
    } else if (url) {
      const response = await fetch(url);
      xmlText = await response.text();
    }

    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlText, 'text/xml');
    
    // Convert XML to JSON-like structure
    const data = this.xmlToJson(xmlDoc);
    const records = Array.isArray(data) ? data : [data];
    
    return {
      data: records,
      recordCount: records.length,
      metadata: { format: 'xml', rootElement }
    };
  }

  // ============= TRANSFORM OPERATIONS =============

  registerTransformer(name, transformerFn) {
    this.transformers.set(name, transformerFn);
  }

  async transform(transformerName, data, config, options = {}) {
    const transformer = this.transformers.get(transformerName);
    if (!transformer) throw new Error(`Transformer not found: ${transformerName}`);
    
    const startTime = Date.now();
    try {
      const result = await transformer(data, config, options);
      return {
        type: 'transform',
        transformer: transformerName,
        data: result.data,
        recordsProcessed: result.recordCount || 0,
        duration: Date.now() - startTime,
        transformations: result.transformations || [],
        warnings: result.warnings || []
      };
    } catch (error) {
      throw new Error(`Transform operation failed (${transformerName}): ${error.message}`);
    }
  }

  async applyDataMapping(data, config) {
    const { mappings } = config;
    const transformedData = [];
    const transformations = [];

    for (const record of data) {
      const transformedRecord = {};
      
      for (const mapping of mappings) {
        const { sourceField, targetField, transformation, defaultValue } = mapping;
        let value = record[sourceField];
        
        // Apply transformation
        if (transformation) {
          switch (transformation.type) {
            case 'uppercase':
              value = String(value).toUpperCase();
              break;
            case 'lowercase':
              value = String(value).toLowerCase();
              break;
            case 'date_format':
              value = new Date(value).toISOString();
              break;
            case 'custom':
              value = this.executeCustomTransformation(value, transformation.function);
              break;
          }
        }
        
        transformedRecord[targetField] = value !== undefined ? value : defaultValue;
        transformations.push({ sourceField, targetField, transformation: transformation?.type });
      }
      
      transformedData.push(transformedRecord);
    }

    return {
      data: transformedData,
      recordCount: transformedData.length,
      transformations
    };
  }

  // ============= LOAD OPERATIONS =============

  registerLoader(name, loaderFn) {
    this.loaders.set(name, loaderFn);
  }

  async load(loaderName, data, config, options = {}) {
    const loader = this.loaders.get(loaderName);
    if (!loader) throw new Error(`Loader not found: ${loaderName}`);
    
    const startTime = Date.now();
    try {
      const result = await loader(data, config, options);
      return {
        type: 'load',
        loader: loaderName,
        recordsProcessed: result.recordCount || 0,
        duration: Date.now() - startTime,
        destination: result.destination,
        status: result.status || 'success'
      };
    } catch (error) {
      throw new Error(`Load operation failed (${loaderName}): ${error.message}`);
    }
  }

  async loadToNeo4j(data, config) {
    const { nodeLabel, properties: _properties } = config;
    let recordCount = 0;
    
    for (const record of data) {
      const cypher = `
        CREATE (n:${nodeLabel})
        SET n = $properties
        RETURN n
      `;
      
      await e2etraceFetchWithRetry(API_CONFIG.ENDPOINTS.GRAPH_QUERY, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query: cypher, 
          params: { properties: record }
        })
      });
      
      recordCount++;
    }

    return {
      recordCount,
      destination: 'neo4j',
      status: 'success'
    };
  }

  async loadToCSV(data, config) {
    const { filename = 'export.csv' } = config;
    
    if (!Array.isArray(data) || data.length === 0) {
      throw new Error('No data to export to CSV');
    }

    const headers = Object.keys(data[0]);
    const csvData = [headers];
    
    data.forEach(record => {
      const row = headers.map(header => {
        const value = record[header];
        return value !== null && value !== undefined ? String(value) : '';
      });
      csvData.push(row);
    });

    const csvContent = csvData.map(row => 
      row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')
    ).join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    
    return {
      recordCount: data.length,
      destination: 'csv_file',
      status: 'success',
      url,
      filename
    };
  }

  // ============= MISSING TRANSFORMER METHODS =============

  async normalizeData(data, config) {
    const { schema: _schema = {}, autoDetectTypes = true } = config;
    const normalizedData = [];

    for (const record of data) {
      const normalizedRecord = {};
      
      for (const [key, value] of Object.entries(record)) {
        let normalizedValue = value;
        
        // Auto-detect and normalize types
        if (autoDetectTypes) {
          if (value === null || value === undefined || value === '') {
            normalizedValue = null;
          } else if (!isNaN(value) && !isNaN(parseFloat(value))) {
            normalizedValue = parseFloat(value);
          } else if (typeof value === 'string') {
            // Try to parse as date
            const dateValue = Date.parse(value);
            if (!isNaN(dateValue)) {
              normalizedValue = new Date(dateValue).toISOString();
            } else {
              normalizedValue = value.trim();
            }
          }
        }
        
        normalizedRecord[key] = normalizedValue;
      }
      
      normalizedData.push(normalizedRecord);
    }

    return {
      data: normalizedData,
      recordCount: normalizedData.length,
      transformations: ['type_normalization', 'null_handling', 'date_standardization']
    };
  }

  async cleanseData(data, config) {
    const { rules: _rules = [], aggressive = false } = config;
    const cleansedData = [];
    const issues = [];

    for (let i = 0; i < data.length; i++) {
      const record = data[i];
      const cleansedRecord = { ...record };

      // Remove duplicates (if aggressive mode)
      if (aggressive) {
        const isDuplicate = data.slice(0, i).some(prevRecord => 
          JSON.stringify(prevRecord) === JSON.stringify(record)
        );
        if (isDuplicate) {
          issues.push({ row: i, issue: 'duplicate_record' });
          continue;
        }
      }

      // Cleanse each field
      for (const [key, value] of Object.entries(record)) {
        if (value === null || value === undefined || value === '') {
          if (aggressive) {
            delete cleansedRecord[key];
          }
        } else if (typeof value === 'string') {
          // Trim whitespace
          cleansedRecord[key] = value.trim();
          
          // Remove special characters if specified
          if (aggressive) {
            cleansedRecord[key] = cleansedRecord[key].replace(/[^\w\s-_.@]/g, '');
          }
        }
      }

      cleansedData.push(cleansedRecord);
    }

    return {
      data: cleansedData,
      recordCount: cleansedData.length,
      transformations: ['whitespace_removal', 'null_handling'],
      issues
    };
  }

  // ============= MISSING VALIDATOR METHODS =============

  async validateBusinessRules(data, config) {
    const { rules = [] } = config;
    const errors = [];
    const warnings = [];
    let validCount = 0;

    for (let i = 0; i < data.length; i++) {
      const record = data[i];
      const recordErrors = [];

      // Apply business rules
      for (const rule of rules) {
        const { field, rule: ruleType, message } = rule;
        const value = record[field];

        switch (ruleType) {
          case 'unique':
            {
              const duplicates = data.filter((r, idx) => idx !== i && r[field] === value);
              if (duplicates.length > 0) {
                recordErrors.push(`${message}: Duplicate value '${value}' found`);
              }
              break;
            }
          
          case 'email':
            if (value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
              recordErrors.push(`${message}: '${value}' is not a valid email`);
            }
            break;
          
          case 'date':
            if (value && isNaN(Date.parse(value))) {
              recordErrors.push(`${message}: '${value}' is not a valid date`);
            }
            break;
          
          case 'range':
            {
              const numValue = parseFloat(value);
              if (!isNaN(numValue)) {
                if (rule.min !== undefined && numValue < rule.min) {
                  recordErrors.push(`${message}: Value ${numValue} is below minimum ${rule.min}`);
                }
                if (rule.max !== undefined && numValue > rule.max) {
                  recordErrors.push(`${message}: Value ${numValue} is above maximum ${rule.max}`);
                }
              }
              break;
            }
        }
      }

      if (recordErrors.length === 0) {
        validCount++;
      } else {
        errors.push({ row: i, errors: recordErrors });
      }
    }

    return {
      isValid: errors.length === 0,
      recordCount: data.length,
      validRecords: validCount,
      errors,
      warnings,
      results: {
        totalRecords: data.length,
        validRecords: validCount,
        errorRecords: errors.length,
        passRate: (validCount / data.length) * 100
      }
    };
  }

  // ============= VALIDATION OPERATIONS =============

  registerValidator(name, validatorFn) {
    this.validators.set(name, validatorFn);
  }

  async validate(validatorName, data, config, options = {}) {
    const validator = this.validators.get(validatorName);
    if (!validator) throw new Error(`Validator not found: ${validatorName}`);
    
    const startTime = Date.now();
    try {
      const result = await validator(data, config, options);
      return {
        type: 'validate',
        validator: validatorName,
        data,
        recordsProcessed: result.recordCount || 0,
        duration: Date.now() - startTime,
        isValid: result.isValid,
        errors: result.errors || [],
        warnings: result.warnings || [],
        validationResults: result.results || []
      };
    } catch (error) {
      throw new Error(`Validation failed (${validatorName}): ${error.message}`);
    }
  }

  async validateSchema(data, config) {
    const { schema } = config;
    const errors = [];
    const warnings = [];
    let validCount = 0;

    for (let i = 0; i < data.length; i++) {
      const record = data[i];
      const recordErrors = [];

      // Check required fields
      for (const field of schema.required || []) {
        if (!Object.prototype.hasOwnProperty.call(record, field) || record[field] === null || record[field] === undefined) {
          recordErrors.push(`Missing required field: ${field}`);
        }
      }

      // Check field types
      for (const [field, expectedType] of Object.entries(schema.types || {})) {
        if (Object.prototype.hasOwnProperty.call(record, field) && record[field] !== null) {
          const actualType = typeof record[field];
          if (actualType !== expectedType) {
            recordErrors.push(`Field ${field} should be ${expectedType}, got ${actualType}`);
          }
        }
      }

      if (recordErrors.length === 0) {
        validCount++;
      } else {
        errors.push({ row: i, errors: recordErrors });
      }
    }

    return {
      isValid: errors.length === 0,
      recordCount: data.length,
      validRecords: validCount,
      errors,
      warnings,
      results: {
        totalRecords: data.length,
        validRecords: validCount,
        errorRecords: errors.length,
        passRate: (validCount / data.length) * 100
      }
    };
  }

  // ============= UTILITY METHODS =============

  async readFileAsText(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = e => resolve(e.target.result);
      reader.onerror = reject;
      reader.readAsText(file);
    });
  }

  async readFileAsArrayBuffer(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = e => resolve(e.target.result);
      reader.onerror = reject;
      reader.readAsArrayBuffer(file);
    });
  }

  xmlToJson(xml) {
    // Simple XML to JSON converter
    const result = {};
    
    if (xml.nodeType === 1) { // Element node
      if (xml.attributes.length > 0) {
        result['@attributes'] = {};
        for (let i = 0; i < xml.attributes.length; i++) {
          const attr = xml.attributes.item(i);
          result['@attributes'][attr.nodeName] = attr.nodeValue;
        }
      }
    }
    
    if (xml.hasChildNodes()) {
      for (let i = 0; i < xml.childNodes.length; i++) {
        const child = xml.childNodes.item(i);
        const nodeName = child.nodeName;
        
        if (child.nodeType === 3) { // Text node
          const text = child.nodeValue.trim();
          if (text) return text;
        } else {
          if (!result[nodeName]) {
            result[nodeName] = this.xmlToJson(child);
          } else {
            if (!Array.isArray(result[nodeName])) {
              result[nodeName] = [result[nodeName]];
            }
            result[nodeName].push(this.xmlToJson(child));
          }
        }
      }
    }
    
    return result;
  }

  executeCustomTransformation(value, transformationFn) {
    try {
      return new Function('value', transformationFn)(value);
    } catch (error) {
      console.warn('Custom transformation failed:', error);
      return value;
    }
  }
}

// Export singleton instance and class
export { ETLEngine };
export const etlEngine = new ETLEngine();
export default etlEngine;
