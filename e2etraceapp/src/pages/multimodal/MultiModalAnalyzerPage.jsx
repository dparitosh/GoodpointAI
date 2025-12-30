/**
 * Multi-Modal Analyzer Page - Parse PDFs, images, CAD, Excel with vision AI
 * Features:
 * - File upload with drag-and-drop
 * - Multiple file type support (PDF, images, Excel, Word, CAD)
 * - Vision model selection (LLaVA, BakLLaVA)
 * - Extraction methods: OCR, Vision LLM, Hybrid
 * - Real-time analysis with progress indicators
 * - Extracted text, metadata, and image insights display
 * - TCS color scheme: Blue #0066cc, white/gray backgrounds
 */

import React, { useState, useRef, useCallback } from 'react';
import './MultiModalAnalyzerPage.css';

// Prefer relative URLs so Vite proxy (dev) and same-origin deploys work by default.
const API_BASE = import.meta.env.VITE_API_BASE_URL || '';

const MultiModalAnalyzerPage = () => {
  const [file, setFile] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [supportedFormats, setSupportedFormats] = useState(null);

  // Configuration
  const [visionModel, setVisionModel] = useState('llava:latest');
  const [extractionMethod, setExtractionMethod] = useState('vision_llm');
  const [ocrEnabled, setOcrEnabled] = useState(true);
  const [temperature, setTemperature] = useState(0.2);

  const fileInputRef = useRef(null);

  // Load supported formats on mount
  React.useEffect(() => {
    fetch(`${API_BASE}/api/multimodal/supported-formats`)
      .then(res => res.json())
      .then(data => setSupportedFormats(data))
      .catch(err => console.error('Failed to load supported formats:', err));
  }, []);

  // Drag and drop handlers
  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  }, []);

  const handleFileSelect = (selectedFile) => {
    setFile(selectedFile);
    setResult(null);
    setError(null);
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  };

  const analyzeFile = async () => {
    if (!file) return;

    setAnalyzing(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('vision_model', visionModel);
    formData.append('extraction_method', extractionMethod);
    formData.append('enable_ocr', ocrEnabled);
    formData.append('temperature', temperature);

    try {
      const response = await fetch(`${API_BASE}/api/multimodal/analyze-file`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Analysis failed');
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const clearFile = () => {
    setFile(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
  };

  const getFileIcon = (filename) => {
    const ext = filename.split('.').pop().toLowerCase();
    if (['pdf'].includes(ext)) return '◳';
    if (['png', 'jpg', 'jpeg', 'bmp', 'webp', 'tiff'].includes(ext)) return '◻';
    if (['xls', 'xlsx', 'csv', 'xlsm'].includes(ext)) return '◳';
    if (['doc', 'docx'].includes(ext)) return '✎';
    if (['dwg', 'dxf', 'step', 'igs', 'iges', 'stp'].includes(ext)) return '⚙';
    return '◻';
  };

  return (
    <div className="multimodal-page">
      <div className="multimodal-header">
        <div className="multimodal-header__grid">
          <div className="multimodal-header__text">
            <h1>↯ Multi-Modal Data Analyzer</h1>
            <p className="multimodal-header__subtitle">
              Use vision AI to extract text, metadata, and insights from documents and drawings.
            </p>

            <ul className="multimodal-header__bullets" aria-label="Key capabilities">
              <li><strong>Text</strong>: OCR + structured extraction</li>
              <li><strong>Metadata</strong>: file properties and attributes</li>
              <li><strong>Insights</strong>: summaries and key signals</li>
            </ul>

            <div className="multimodal-header__chips" aria-label="Supported inputs">
              <span className="mm-chip">PDF</span>
              <span className="mm-chip">Images</span>
              <span className="mm-chip">CAD</span>
              <span className="mm-chip">Excel</span>
              <span className="mm-chip">Word</span>
            </div>

            {supportedFormats ? (
              <div className="multimodal-header__formats" aria-label="Supported file formats">
                <span className="multimodal-header__formats-label">Supported formats:</span>
                <span className="multimodal-header__formats-value">
                  {Object.entries(supportedFormats)
                    .map(([category, extensions]) => `${category}: ${extensions.join(', ')}`)
                    .join(' • ')}
                </span>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="multimodal-container">
        {/* Left Panel: Configuration & Upload */}
        <div className="multimodal-left-panel">
          <div className="multimodal-left-row">
            {/* Vision Model Selection */}
            <div className="config-section">
              <h3>⚙ Configuration</h3>
              
              <div className="config-group">
                <label>Vision Model:</label>
                <select 
                  value={visionModel} 
                  onChange={(e) => setVisionModel(e.target.value)}
                  disabled={analyzing}
                >
                  <option value="llava:latest">LLaVA (Latest)</option>
                  <option value="llava:13b">LLaVA 13B</option>
                  <option value="llava:7b">LLaVA 7B</option>
                  <option value="bakllava:latest">BakLLaVA</option>
                </select>
              </div>

              <div className="config-group">
                <label>Extraction Method:</label>
                <div className="radio-group">
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="extraction"
                      value="vision_llm"
                      checked={extractionMethod === 'vision_llm'}
                      onChange={(e) => setExtractionMethod(e.target.value)}
                      disabled={analyzing}
                    />
                    Vision LLM
                  </label>
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="extraction"
                      value="ocr"
                      checked={extractionMethod === 'ocr'}
                      onChange={(e) => setExtractionMethod(e.target.value)}
                      disabled={analyzing}
                    />
                    OCR Only
                  </label>
                  <label className="radio-label">
                    <input
                      type="radio"
                      name="extraction"
                      value="hybrid"
                      checked={extractionMethod === 'hybrid'}
                      onChange={(e) => setExtractionMethod(e.target.value)}
                      disabled={analyzing}
                    />
                    Hybrid
                  </label>
                </div>
              </div>

              <div className="config-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={ocrEnabled}
                    onChange={(e) => setOcrEnabled(e.target.checked)}
                    disabled={analyzing}
                  />
                  Enable OCR Fallback
                </label>
              </div>

              <div className="config-group">
                <label>Temperature: {temperature}</label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value))}
                  disabled={analyzing}
                  className="temperature-slider"
                />
                <small>Lower = more factual, Higher = more creative</small>
              </div>
            </div>

            {/* File Upload Area */}
            <div className="upload-section">
              <h3>Upload File</h3>
              
              <div
                className={`drop-zone ${dragActive ? 'active' : ''} ${file ? 'has-file' : ''}`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => !file && fileInputRef.current?.click()}
              >
                {!file ? (
                  <div className="drop-zone-empty">
                    <div className="drop-icon" aria-hidden="true">⬆</div>
                    <div className="drop-zone-empty-text">
                      <div className="drop-zone-empty-title">Drag & drop file here or click to browse</div>
                      <div className="drop-zone-empty-subtitle">Supported: PDF, Images, Excel, Word, CAD</div>
                    </div>
                  </div>
                ) : (
                  <div className="file-info">
                    <div className="file-icon-large">{getFileIcon(file.name)}</div>
                    <div className="file-details">
                      <div className="file-name">{file.name}</div>
                      <div className="file-size">{formatFileSize(file.size)}</div>
                    </div>
                    <button className="clear-btn" onClick={(e) => { e.stopPropagation(); clearFile(); }}>
                      ✗
                    </button>
                  </div>
                )}
              </div>

              <input
                ref={fileInputRef}
                type="file"
                onChange={handleFileInputChange}
                style={{ display: 'none' }}
                accept=".pdf,.png,.jpg,.jpeg,.bmp,.webp,.tiff,.xls,.xlsx,.csv,.xlsm,.doc,.docx,.dwg,.dxf,.step,.igs,.iges,.stp"
              />

              <button
                className="analyze-btn"
                onClick={analyzeFile}
                disabled={!file || analyzing}
              >
                {analyzing ? '⟲ Analyzing...' : '▶ Analyze File'}
              </button>
            </div>
          </div>

        </div>

        {/* Right Panel: Results */}
        <div className="multimodal-right-panel">
          <h3>◳ Analysis Results</h3>

          {analyzing && (
            <div className="analyzing-state">
              <div className="spinner"></div>
              <p>Analyzing {file?.name}...</p>
              <small>Processing with {visionModel} using {extractionMethod} method</small>
            </div>
          )}

          {error && (
            <div className="error-state">
              <div className="error-icon">✗</div>
              <h4>Analysis Failed</h4>
              <p>{error}</p>
            </div>
          )}

          {result && !analyzing && (
            <div className="results-container">
              {/* File Info */}
              <div className="result-section">
                <h4>⊞ File Information</h4>
                <div className="info-grid">
                  <div className="info-item">
                    <span className="info-label">Filename:</span>
                    <span className="info-value">{result.filename}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">File Type:</span>
                    <span className="info-value">{result.file_type}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Size:</span>
                    <span className="info-value">{formatFileSize(result.file_size)}</span>
                  </div>
                  <div className="info-item">
                    <span className="info-label">Analyzed:</span>
                    <span className="info-value">{new Date(result.analyzed_at).toLocaleString()}</span>
                  </div>
                  {result.processing_time_seconds && (
                    <div className="info-item">
                      <span className="info-label">Processing Time:</span>
                      <span className="info-value">{result.processing_time_seconds.toFixed(2)}s</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Extracted Text */}
              {result.extracted_text && result.extracted_text.length > 0 && (
                <div className="result-section">
                  <h4>✎ Extracted Text ({result.extracted_text.length} characters)</h4>
                  <div className="text-content">
                    {result.extracted_text}
                  </div>
                </div>
              )}

              {/* Vision Analysis */}
              {result.vision_analysis && (
                <div className="result-section">
                  <h4>◉ Vision AI Analysis</h4>
                  <div className="analysis-content">
                    {result.vision_analysis}
                  </div>
                </div>
              )}

              {/* Metadata */}
              {result.metadata && Object.keys(result.metadata).length > 0 && (
                <div className="result-section">
                  <h4>⚙ Metadata</h4>
                  <div className="metadata-grid">
                    {Object.entries(result.metadata).map(([key, value]) => (
                      <div key={key} className="metadata-item">
                        <span className="metadata-key">{key}:</span>
                        <span className="metadata-value">
                          {typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Images Found */}
              {result.images_analyzed && result.images_analyzed.length > 0 && (
                <div className="result-section">
                  <h4>◻ Images Analyzed ({result.images_analyzed.length})</h4>
                  <div className="images-list">
                    {result.images_analyzed.map((img, idx) => (
                      <div key={idx} className="image-analysis-item">
                        <div className="image-number">Image {idx + 1}</div>
                        {img.format && <div>Format: {img.format}</div>}
                        {img.size && <div>Size: {img.size[0]} × {img.size[1]}px</div>}
                        {img.analysis && <div className="image-analysis-text">{img.analysis}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Excel/Structured Data */}
              {result.structured_data && (
                <div className="result-section">
                  <h4>◳ Structured Data</h4>
                  <div className="structured-data">
                    <pre>{JSON.stringify(result.structured_data, null, 2)}</pre>
                  </div>
                </div>
              )}
            </div>
          )}

          {!result && !analyzing && !error && (
            <div className="empty-state">
              <div className="empty-icon">⊙</div>
              <p>Upload a file to begin analysis</p>
              <small>Drag and drop or click the upload area</small>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default MultiModalAnalyzerPage;
