// This file contains functions to generate ECharts options for the analytics page,
// keeping the main component clean and focused on rendering.

/**
 * Generates the ECharts option for the node distribution by label bar chart.
 * @param {object} metrics - The processed analytics metrics.
 * @param {string} theme - The current theme ('dark' or 'light').
 * @returns {object|null} The ECharts option object or null if data is unavailable.
 */
 export const getLabelChartOption = (metrics, theme) => {
    if (!metrics || !metrics.labelCounts) return null;
    return {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: [{
            type: 'category',
            data: Object.keys(metrics.labelCounts),
            axisTick: { alignWithLabel: true },
            axisLabel: { color: 'var(--text-color)' }
        }],
        yAxis: [{ type: 'value', axisLabel: { color: 'var(--text-color)' } }],
        series: [{
            name: 'Node Count',
            type: 'bar',
            barWidth: '60%',
            data: Object.values(metrics.labelCounts),
            itemStyle: { color: 'var(--accent-color)' }
        }],
        backgroundColor: 'transparent'
    };
};


/**
 * Generates the ECharts option for the mapping coverage gauge chart.
 * @param {object} metrics - The processed analytics metrics.
 * @param {string} theme - The current theme ('dark' or 'light').
 * @returns {object|null} The ECharts option object or null if data is unavailable.
 */
export const getMappingCoverageGaugeOption = (metrics, theme) => {
    if (!metrics || !metrics.mappingCoverage) return null;

    const coveragePercentage = (metrics.mappingCoverage.mapped + metrics.mappingCoverage.unmapped) > 0
        ? (metrics.mappingCoverage.mapped / (metrics.mappingCoverage.mapped + metrics.mappingCoverage.unmapped)) * 100
        : 0;

    return {
        series: [{
            type: 'gauge',
            startAngle: 180,
            endAngle: 0,
            center: ['50%', '75%'],
            radius: '90%',
            min: 0,
            max: 100,
            splitNumber: 5,
            axisLine: {
                lineStyle: {
                    width: 8,
                    color: [
                        [0.7, '#d32f2f'],
                        [0.9, '#fbc02d'],
                        [1, '#388e3c']
                    ]
                }
            },
            pointer: {
                icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
                length: '12%',
                width: 20,
                offsetCenter: [0, '-60%'],
                itemStyle: { color: 'auto' }
            },
            axisTick: { length: 12, lineStyle: { color: 'auto', width: 2 } },
            splitLine: { length: 20, lineStyle: { color: 'auto', width: 5 } },
            axisLabel: { color: 'var(--text-muted-color)', fontSize: 14, distance: -55 },
            title: { offsetCenter: [0, '-10%'], fontSize: 20, color: 'var(--text-color)' },
            detail: {
                fontSize: 30,
                offsetCenter: [0, '-35%'],
                valueAnimation: true,
                formatter: (value) => `${Math.round(value)}%`,
                color: 'inherit'
            },
            data: [{ value: coveragePercentage, name: 'Mapping Coverage' }]
        }],
        backgroundColor: 'transparent'
    };
};


/**
 * Generates the ECharts option for the node status distribution pie chart.
 * @param {object} metrics - The processed analytics metrics.
 * @param {string} theme - The current theme ('dark' or 'light').
 * @returns {object|null} The ECharts option object or null if data is unavailable.
 */
export const getStatusDistributionChartOption = (metrics, theme) => {
    if (!metrics || !metrics.propertyValueCounts || !metrics.propertyValueCounts.status) return null;

    return {
        tooltip: { trigger: 'item' },
        legend: { orient: 'vertical', left: 'left', textStyle: { color: 'var(--text-color)' } },
        series: [{
            name: 'Node Status',
            type: 'pie',
            radius: ['40%', '70%'],
            data: Object.entries(metrics.propertyValueCounts.status).map(([name, value]) => ({ name, value })),
            emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } }
        }],
        backgroundColor: 'transparent'
    };
};

/**
 * Generates the ECharts option for the relationship types pie chart.
 * @param {object} metrics - The processed analytics metrics.
 * @param {string} theme - The current theme ('dark' or 'light').
 * @returns {object|null} The ECharts option object or null if data is unavailable.
 */
export const getRelationshipChartOption = (metrics, theme) => {
    if (!metrics || !metrics.relationshipCounts) return null;

    return {
        tooltip: { trigger: 'item' },
        legend: { orient: 'vertical', left: 'left', textStyle: { color: 'var(--text-color)' } },
        series: [{
            name: 'Relationship Types',
            type: 'pie',
            radius: '70%',
            data: Object.entries(metrics.relationshipCounts).map(([name, value]) => ({ name, value })),
            emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0, 0, 0, 0.5)' } }
        }],
        backgroundColor: 'transparent'
    };
};