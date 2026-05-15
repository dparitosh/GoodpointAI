/**
 * discoveryUtils.js — Utilities for Discovery Step 2 refactored components
 * 
 * Provides:
 * - Metric calculations (readiness score, risk levels, anomalies)
 * - Data transformations (field grouping, risk sorting)
 * - Anomaly detection logic
 * - Plain-English explanations for metrics
 */

// ── Score & Tier Calculations ────────────────────────────────────────────────

/**
 * Calculate 0-100 readiness score based on quality metrics
 * Factors: quality score, nulls, duplicates, completeness, fields detected
 */
export function calculateReadinessScore(qualityScore, nullCount, duplicateRows, avgCompleteness, fieldsDetected) {
  let score = 100;
  
  // Quality gate (40 points max weight)
  if (qualityScore != null) {
    score = Math.max(0, score - (100 - qualityScore) * 0.4);
  } else {
    score -= 20; // Unknown quality = -20
  }
  
  // Nulls penalty (20 points)
  if (nullCount > 0) {
    const nullPenalty = Math.min(20, (nullCount / 10) * 20);
    score -= nullPenalty;
  }
  
  // Duplicates penalty (15 points)
  if (duplicateRows > 0) {
    const dupPenalty = Math.min(15, duplicateRows * 3);
    score -= dupPenalty;
  }
  
  // Completeness bonus/penalty (15 points)
  if (avgCompleteness != null) {
    if (avgCompleteness < 70) {
      score -= Math.min(15, (70 - avgCompleteness) * 0.3);
    }
  } else {
    score -= 5; // Unknown completeness = -5
  }
  
  // Fields detected bonus (10 points)
  if (fieldsDetected != null && fieldsDetected > 0) {
    score = Math.min(100, score + 5);
  }
  
  return Math.max(0, Math.round(score));
}

/**
 * Map readiness score to status tier
 */
export function getReadinessStatus(score) {
  if (score >= 85) return 'pass';
  if (score >= 70) return 'warning';
  return 'fail';
}

/**
 * Parse any confidence representation → 0-100 integer
 */
export function parsePct(v) {
  if (v == null) return 0;
  if (typeof v === 'string' && v.endsWith('%')) return Math.min(100, parseInt(v, 10));
  if (typeof v === 'number' && v > 0 && v <= 1.0) return Math.round(v * 100);
  if (typeof v === 'number') return Math.min(100, Math.round(v));
  return 0;
}

/**
 * Map 0-100 pct → confidence tier ('high' | 'medium' | 'low')
 */
export function confidenceTier(pct) {
  const p = parsePct(pct);
  if (p >= 80) return 'high';
  if (p >= 60) return 'medium';
  return 'low';
}

/**
 * Map field quality metrics → risk tier ('high' | 'medium' | 'low')
 */
export function getFieldRiskTier(field, dqReport) {
  if (!field) return 'low';
  
  let riskScore = 0;
  
  // High risk indicators
  if (field.nullCount > 10) riskScore += 40;
  if (field.duplicateRows > 5) riskScore += 30;
  if (field.completeness != null && field.completeness < 70) riskScore += 35;
  if (field.completeness != null && field.completeness < 50) riskScore += 15;
  
  // Very high risk: empty/unreachable source
  if (field.completeness == null && field.nullCount == null) riskScore += 50;
  
  if (riskScore >= 70) return 'high';
  if (riskScore >= 40) return 'medium';
  return 'low';
}

// ── Field & Mapping Grouping ────────────────────────────────────────────────

/**
 * Sort and tier mappings by confidence level
 */
export function tierMappings(mappings) {
  const sorted = [...mappings].sort((a, b) => parsePct(b.confidence) - parsePct(a.confidence));
  return {
    strong: sorted.filter(m => parsePct(m.confidence) >= 80),
    review: sorted.filter(m => parsePct(m.confidence) >= 60 && parsePct(m.confidence) < 80),
    weak: sorted.filter(m => parsePct(m.confidence) < 60),
  };
}

/**
 * Group fields by risk level for display
 */
export function groupFieldsByRisk(dqReport) {
  const high = [];
  const medium = [];
  const low = [];
  
  dqReport.forEach(field => {
    const tier = getFieldRiskTier(field, dqReport);
    if (tier === 'high') high.push(field);
    else if (tier === 'medium') medium.push(field);
    else low.push(field);
  });
  
  return { high, medium, low };
}

// ── Anomaly Detection ────────────────────────────────────────────────────────

/**
 * Detect anomalies in source files and fields
 * Returns array of anomalies with severity and recommended action
 */
export function detectAnomalies(sample, dqReport, semanticProfile, mappings) {
  const anomalies = [];
  
  // Anomaly 1: Empty/unreadable JSON files
  if (sample?.source_files) {
    sample.source_files.forEach(file => {
      if ((file.type === 'json' || file.type === 'xml') && file.record_count === 0) {
        anomalies.push({
          id: `empty-${file.name}`,
          severity: 'high',
          type: 'empty_source',
          title: `"${file.name}" is empty or unreadable`,
          description: `Expected data but found 0 records. JSON/XML parsing may have failed or the source connection is invalid.`,
          affectedFields: file.field_names?.slice(0, 3) || [],
          action: 'Check source file format and verify connection settings in Step 1',
          confidence: 0.98,
        });
      }
    });
  }
  
  // Anomaly 2: Mixed case values (data quality issue)
  const colSemMap = {};
  (semanticProfile?.column_semantics || []).forEach(cs => { colSemMap[cs.column] = cs; });
  
  if (sample?.records?.length > 0) {
    const recordSamples = sample.records.slice(0, 10);
    const fieldVariants = {};
    
    recordSamples.forEach(record => {
      Object.entries(record).forEach(([field, value]) => {
        const strVal = String(value || '').trim();
        if (!strVal || strVal === '—') return;
        
        if (!fieldVariants[field]) fieldVariants[field] = new Set();
        fieldVariants[field].add(strVal);
      });
    });
    
    // Check for mixed case in text fields
    Object.entries(fieldVariants).forEach(([field, variants]) => {
      if (variants.size >= 2) {
        const variantArray = Array.from(variants);
        const cases = variantArray.map(v => /[A-Z]/.test(v) ? 'upper' : /[a-z]/.test(v) ? 'lower' : 'mixed');
        
        if (new Set(cases).size > 1) {
          anomalies.push({
            id: `mixed-case-${field}`,
            severity: 'medium',
            type: 'mixed_format',
            title: `"${field}" field has mixed case values`,
            description: `Values appear in different cases (e.g., "nexperia" vs "NEXPERIA" vs "NexPeria"). This should be normalized during mapping.`,
            affectedField: field,
            sampleValues: variantArray.slice(0, 3),
            action: 'Add UPPERCASE() or LOWERCASE() transformation in Step 3 mapping',
            confidence: 0.85,
          });
        }
      }
    });
  }
  
  // Anomaly 3: File variants with same schema (duplicates or redundant)
  if (sample?.source_files?.length > 0) {
    const filesBySchema = {};
    sample.source_files.forEach(file => {
      const schemaKey = (file.field_names || []).sort().join('|');
      if (schemaKey) {
        if (!filesBySchema[schemaKey]) filesBySchema[schemaKey] = [];
        filesBySchema[schemaKey].push(file);
      }
    });
    
    Object.entries(filesBySchema).forEach(([schema, files]) => {
      if (files.length > 1) {
        const fileNames = files.map(f => f.name).join(', ');
        const recordCounts = files.map(f => f.record_count || 0);
        
        anomalies.push({
          id: `duplicate-schema-${schema.slice(0, 20)}`,
          severity: 'medium',
          type: 'duplicate_files',
          title: `${files.length} files share the same schema`,
          description: `Files: ${fileNames}. These have identical field structures but different record counts (${recordCounts.join(', ')}). Consider merging or deduplicating during ETL.`,
          affectedFiles: files.map(f => f.name),
          action: 'Verify these files should be separate or merged in the mapping/transformation',
          confidence: 0.92,
        });
      }
    });
  }
  
  return anomalies.sort((a, b) => {
    const severityOrder = { high: 0, medium: 1, low: 2 };
    return severityOrder[a.severity] - severityOrder[b.severity];
  });
}

// ── Plain-English Explanations ──────────────────────────────────────────────

export const CONFIDENCE_EXPLANATIONS = {
  high: 'Strong match — field name, data type, and semantic role all align with target',
  medium: 'Name match — field names are identical or very similar; review data type compatibility',
  low: 'Weak match — AI found partial similarity; manual review required before mapping',
};

export const RISK_EXPLANATIONS = {
  high: 'This field has data quality issues that require review before mapping',
  medium: 'Minor quality issues; may need transformation or validation rules',
  low: 'All quality checks passed; ready to proceed',
};

export const STATUS_MESSAGES = {
  pass: {
    label: 'Ready to Proceed',
    icon: 'fa-check-circle',
    color: 'success',
    message: 'Data quality is excellent. You can proceed to mapping with confidence.',
  },
  warning: {
    label: 'Review Recommended',
    icon: 'fa-exclamation-triangle',
    color: 'warning',
    message: 'Data has minor quality issues. Review the issues below before mapping.',
  },
  fail: {
    label: 'Attention Required',
    icon: 'fa-times-circle',
    color: 'danger',
    message: 'Significant data quality issues detected. Address high-risk fields before mapping.',
  },
};

// ── Recommended Actions ──────────────────────────────────────────────────────

/**
 * Generate recommended next steps based on discovery results
 */
export function generateRecommendedActions(readinessScore, fieldRisks, anomalies, mappingTiers, unreadableFiles) {
  const actions = [];
  let stepNum = 1;
  
  // Action 1: Handle empty/unreadable sources
  if (unreadableFiles.length > 0) {
    actions.push({
      id: `action-${stepNum}`,
      priority: 'critical',
      title: `Fix ${unreadableFiles.length} file(s) with empty/unreadable source`,
      description: `Files: ${unreadableFiles.map(f => f.name).join(', ')}. If needed, adjust source connection in Step 1.`,
      impact: 'Blocks migration',
      cta: 'Review & Fix',
      affectedArea: unreadableFiles.map(f => f.name).join(', '),
    });
    stepNum++;
  }
  
  // Action 2: Address high-risk fields
  if (fieldRisks.high.length > 0) {
    actions.push({
      id: `action-${stepNum}`,
      priority: 'high',
      title: `Review ${fieldRisks.high.length} high-risk field(s)`,
      description: `These fields have quality issues (nulls, duplicates, low completeness). Review before mapping.`,
      impact: 'May block mapping',
      cta: 'Review Fields',
      affectedArea: fieldRisks.high.map(f => f.field).join(', '),
      details: fieldRisks.high.slice(0, 3).map(f => 
        `${f.field}: ${f.nullCount ? f.nullCount + ' nulls' : ''} ${f.completeness ? f.completeness + '% complete' : ''}`
      ),
    });
    stepNum++;
  }
  
  // Action 3: Handle anomalies
  if (anomalies.length > 0) {
    const criticalAnomalies = anomalies.filter(a => a.severity === 'high');
    if (criticalAnomalies.length > 0) {
      actions.push({
        id: `action-${stepNum}`,
        priority: 'high',
        title: `Address ${criticalAnomalies.length} critical anomaly(ies)`,
        description: `Anomalies detected: ${criticalAnomalies.map(a => a.title).join('; ')}`,
        impact: 'Data quality issue',
        cta: 'Review Anomalies',
        affectedArea: 'Anomaly Detection',
        details: criticalAnomalies.map(a => `${a.title} (${Math.round(a.confidence * 100)}% confidence)`),
      });
      stepNum++;
    }
  }
  
  // Action 4: Handle weak-confidence mappings
  if (mappingTiers.weak.length > 0) {
    actions.push({
      id: `action-${stepNum}`,
      priority: 'medium',
      title: `Prepare ${mappingTiers.weak.length} weak-confidence mapping(s)`,
      description: `AI couldn't confidently match these fields. You'll need to select targets manually in Step 3.`,
      impact: 'Manual work needed',
      cta: 'Review Mappings',
      affectedArea: mappingTiers.weak.map(m => m.source).join(', '),
      details: mappingTiers.weak.slice(0, 3).map(m => 
        `${m.source} → ${m.target} (${Math.round(parsePct(m.confidence))}% confidence)`
      ),
    });
    stepNum++;
  }
  
  // Action 5: Handle transformations
  const transformNeeded = anomalies.filter(a => a.action && (a.action.includes('transformation') || a.action.includes('UPPERCASE') || a.action.includes('LOWERCASE'))).length;
  if (transformNeeded > 0) {
    actions.push({
      id: `action-${stepNum}`,
      priority: 'medium',
      title: `Apply ${transformNeeded} transformation(s) during mapping`,
      description: `Anomalies detected that require data normalization (case, formatting, etc.)`,
      impact: 'Optional optimization',
      cta: 'Plan Transformations',
      affectedArea: 'Data Normalization',
      details: anomalies.slice(0, 3).filter(a => a.action).map(a => a.action),
    });
    stepNum++;
  }
  
  // Action 6: Proceed to mapping (only if readiness score is acceptable)
  if (readinessScore >= 60) {
    actions.push({
      id: `action-${stepNum}`,
      priority: 'high',
      title: 'Proceed to Field Mapping (Step 3)',
      description: `${mappingTiers.strong.length} strong-confidence mappings ready. Address any issues above before proceeding.`,
      impact: 'Next step unlocked',
      cta: 'Continue to Mapping',
      affectedArea: 'Workflow progress',
      details: [
        `${mappingTiers.strong.length} strong confidence mappings available`,
        `${mappingTiers.review.length} mappings need review`,
        `${mappingTiers.weak.length} mappings need manual selection`,
      ],
    });
    stepNum++;
  } else {
    // Blocker: readiness too low
    actions.push({
      id: `action-${stepNum}`,
      priority: 'critical',
      title: 'Readiness score too low to proceed',
      description: `Your readiness score is ${readinessScore}/100. Complete critical items above to unlock Step 3.`,
      impact: 'Blocks progression',
      affectedArea: 'Readiness score',
    });
  }
  
  return actions;
}

// ── Quality Summary Stats ────────────────────────────────────────────────────

/**
 * Calculate quality summary statistics for display
 */
export function calculateQualitySummary(dqReport, sodaResult, qualityScore) {
  const totalFields = dqReport.length;
  const fieldsWithNulls = dqReport.filter(f => (f.nullCount || 0) > 0).length;
  const fieldsWithDups = [...new Set(dqReport.filter(f => f.duplicateRows > 0).map(f => f.file))].length;
  const fieldWithLowCompleteness = dqReport.filter(f => f.completeness != null && f.completeness < 70).length;
  
  const totalNulls = dqReport.reduce((sum, f) => sum + (f.nullCount || 0), 0);
  const totalDups = dqReport.reduce((sum, f) => sum + (f.duplicateRows || 0), 0);
  
  const completenessValues = dqReport.filter(f => f.completeness != null).map(f => f.completeness);
  const avgCompleteness = completenessValues.length 
    ? Math.round(completenessValues.reduce((a, b) => a + b, 0) / completenessValues.length)
    : null;
  
  return {
    totalFields,
    fieldsWithNulls,
    fieldsWithDups,
    fieldWithLowCompleteness,
    totalNulls,
    totalDups,
    avgCompleteness,
    qualityScore: qualityScore != null ? qualityScore : null,
    sodaStatus: sodaResult?.status || null,
  };
}
