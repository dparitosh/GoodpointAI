import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

const STORAGE_KEY = 'e2etrace-language';

const resources = {
  en: {
    translation: {
      nav: {
        quickAccess: 'Quick Access',
        home: 'Home',
        overview: 'Overview',
        migrationTools: 'Migration Tools',
        insightsReports: 'Insights & Reports',
        advancedTools: 'Advanced Tools',
        workflowManagement: 'Workflow Management',
        workflowManager: 'Workflow Manager',
        workflowDetail: 'Workflow Detail',
        interactiveStateFlow: 'Interactive State Flow',
        selfHealingMonitor: 'Self-Healing Monitor',
        multiModalAnalyzer: 'Multi-Modal Analyzer',
        dataOperations: 'Data Operations',
        dataConfig: 'Data Configuration',
        spreadsheet: 'Spreadsheet',
        dataProcessingHub: 'Data Processing Hub',
        graphExplorer: 'Graph Explorer',
        dataLineage: 'Data Lineage',
        qualityMonitoring: 'Quality & Monitoring',
        dataQuality: 'Data Quality (SODA)',
        observability: 'Observability',
        analytics: 'Analytics',
        reporting: 'Reports & Dashboards',
        apiDocs: 'API Docs (OpenAPI/Swagger)',
        settings: 'Settings',
        preferences: 'Preferences',
      },
      errors: {
        notFound: 'Not Found',
      },
      processingHub: {
        subtitle: 'Centralized ETL workflows and quick file processing',
        confirmDelete: 'Are you sure you want to delete this workflow?',
        status: {
          unknown: 'unknown',
        },
        metrics: {
          total: 'Total Workflows',
          success: 'Successful Runs',
          active: 'Active',
        },
        tabs: {
          label: 'Data processing tabs',
          workflows: 'Workflows',
          templates: 'Templates',
          quick: 'Quick Tools',
          quality: 'Data Quality (SODA)',
        },
        workflows: {
          title: 'Workflows',
          create: 'Create',
          empty: 'No workflows yet. Create one to get started.',
        },
        templates: {
          title: 'Workflow Templates',
        },
        quick: {
          title: 'Quick File Processing',
          fileLabel: 'Choose a file',
          latestResults: 'Latest results',
        },
        results: {
          unnamed: 'Result',
          recordsProcessed: 'Records processed',
        },
        createModal: {
          title: 'Create Workflow',
          template: 'Template',
          name: 'Name',
            success: 'Completed',
        },
        actions: {
          run: 'Run',
          delete: 'Delete',
          close: 'Close',
          cancel: 'Cancel',
            unavailable: 'Workflows are unavailable.',
          create: 'Create',
        },
      },
            unavailable: 'Workflow templates are unavailable.',
      settings: {
        title: 'Settings',
        language: 'Language',
      },
    },
            unavailable: 'Quick tools are unavailable.',
  },
  es: {
    translation: {
      nav: {
            sourceId: 'Source ID',
            targetId: 'Target ID',
        quickAccess: 'Acceso rápido',
        home: 'Inicio',
        overview: 'Resumen',
        migrationTools: 'Herramientas de migración',
        insightsReports: 'Insights e informes',
        advancedTools: 'Herramientas avanzadas',
        workflowManagement: 'Gestión de flujos',
        workflowManager: 'Gestor de flujos',
        workflowDetail: 'Detalle del workflow',
        interactiveStateFlow: 'Flujo de estado interactivo',
        selfHealingMonitor: 'Monitor de autorreparación',
        multiModalAnalyzer: 'Analizador multimodal',
        dataOperations: 'Operaciones de datos',
        dataConfig: 'Configuración de datos',
        spreadsheet: 'Hoja de cálculo',
        dataProcessingHub: 'Centro de procesamiento de datos',
        graphExplorer: 'Explorador de grafo',
        dataLineage: 'Linaje de datos',
        qualityMonitoring: 'Calidad y monitoreo',
        dataQuality: 'Calidad de datos (SODA)',
        observability: 'Observabilidad',
        analytics: 'Analítica',
        reporting: 'Informes y paneles',
        apiDocs: 'Docs API (OpenAPI/Swagger)',
        settings: 'Configuración',
        preferences: 'Preferencias',
      },
      errors: {
        notFound: 'No encontrado',
      },
      processingHub: {
        subtitle: 'Workflows ETL centralizados y procesamiento rápido de archivos',
        confirmDelete: '¿Seguro que quieres eliminar este workflow?',
        status: {
          unknown: 'desconocido',
        },
        metrics: {
          total: 'Workflows totales',
          success: 'Ejecuciones exitosas',
          active: 'Activos',
        },
        tabs: {
          label: 'Pestañas de procesamiento de datos',
          workflows: 'Workflows',
          templates: 'Plantillas',
          quick: 'Herramientas rápidas',
          quality: 'Calidad de datos (SODA)',
        },
        workflows: {
          title: 'Workflows',
          create: 'Crear',
          empty: 'Aún no hay workflows. Crea uno para comenzar.',
        },
        templates: {
          title: 'Plantillas de workflow',
        },
        quick: {
          title: 'Procesamiento rápido de archivos',
          fileLabel: 'Elige un archivo',
          latestResults: 'Últimos resultados',
        },
        results: {
          unnamed: 'Resultado',
          recordsProcessed: 'Registros procesados',
        },
        createModal: {
          title: 'Crear workflow',
          template: 'Plantilla',
          name: 'Nombre',
            success: 'Completados',
        },
        actions: {
          run: 'Ejecutar',
          delete: 'Eliminar',
          close: 'Cerrar',
          cancel: 'Cancelar',
            unavailable: 'Los workflows no están disponibles.',
          create: 'Crear',
        },
      },
            unavailable: 'Las plantillas no están disponibles.',
      settings: {
        title: 'Configuración',
        language: 'Idioma',
      },
    },
            unavailable: 'Las herramientas rápidas no están disponibles.',
  },
  fr: {
    translation: {
      nav: {
            sourceId: 'ID de origen',
            targetId: 'ID de destino',
        quickAccess: 'Accès rapide',
        home: 'Accueil',
        overview: 'Aperçu',
        migrationTools: 'Outils de migration',
        insightsReports: 'Insights et rapports',
        advancedTools: 'Outils avancés',
        workflowManagement: 'Gestion des workflows',
        workflowManager: 'Gestionnaire de workflows',
        workflowDetail: 'Détail du workflow',
        interactiveStateFlow: "Flux d'état interactif",
        selfHealingMonitor: 'Surveillance auto-réparation',
        multiModalAnalyzer: 'Analyseur multimodal',
        dataOperations: 'Opérations de données',
        dataConfig: 'Configuration des données',
        spreadsheet: 'Tableur',
        dataProcessingHub: 'Centre de traitement des données',
        graphExplorer: 'Explorateur de graphe',
        dataLineage: 'Traçabilité des données',
        qualityMonitoring: 'Qualité et surveillance',
        dataQuality: 'Qualité des données (SODA)',
        observability: 'Observabilité',
        analytics: 'Analytique',
        reporting: 'Rapports et tableaux de bord',
        apiDocs: 'Docs API (OpenAPI/Swagger)',
        settings: 'Paramètres',
        preferences: 'Préférences',
      },
      errors: {
        notFound: 'Introuvable',
      },
      processingHub: {
        subtitle: 'Workflows ETL centralisés et traitement rapide des fichiers',
        confirmDelete: 'Êtes-vous sûr de vouloir supprimer ce workflow ?',
        status: {
          unknown: 'inconnu',
        },
        metrics: {
          total: 'Workflows totaux',
          success: 'Exécutions réussies',
          active: 'Actifs',
        },
        tabs: {
          label: 'Onglets de traitement des données',
          workflows: 'Workflows',
          templates: 'Modèles',
          quick: 'Outils rapides',
          quality: 'Qualité des données (SODA)',
        },
        workflows: {
          title: 'Workflows',
          create: 'Créer',
          empty: 'Aucun workflow pour le moment. Créez-en un pour commencer.',
        },
        templates: {
          title: 'Modèles de workflow',
        },
        quick: {
          title: 'Traitement rapide des fichiers',
          fileLabel: 'Choisir un fichier',
          latestResults: 'Derniers résultats',
        },
        results: {
          unnamed: 'Résultat',
          recordsProcessed: 'Enregistrements traités',
        },
        createModal: {
          title: 'Créer un workflow',
          template: 'Modèle',
          name: 'Nom',
            success: 'Terminés',
        },
        actions: {
          run: 'Exécuter',
          delete: 'Supprimer',
          close: 'Fermer',
          cancel: 'Annuler',
            unavailable: 'Les workflows ne sont pas disponibles.',
          create: 'Créer',
        },
      },
            unavailable: 'Les modèles de workflow ne sont pas disponibles.',
      settings: {
        title: 'Paramètres',
        language: 'Langue',
      },
    },
            unavailable: 'Les outils rapides ne sont pas disponibles.',
  },
  de: {
    translation: {
      nav: {
            sourceId: 'ID source',
            targetId: 'ID cible',
        quickAccess: 'Schnellzugriff',
        home: 'Start',
        overview: 'Übersicht',
        migrationTools: 'Migrationstools',
        insightsReports: 'Insights & Berichte',
        advancedTools: 'Erweiterte Tools',
        workflowManagement: 'Workflow-Verwaltung',
        workflowManager: 'Workflow-Manager',
        workflowDetail: 'Workflow-Details',
        interactiveStateFlow: 'Interaktiver Zustandsfluss',
        selfHealingMonitor: 'Self-Healing Monitor',
        multiModalAnalyzer: 'Multimodaler Analysator',
        dataOperations: 'Datenoperationen',
        dataConfig: 'Datenkonfiguration',
        spreadsheet: 'Tabellenblatt',
        dataProcessingHub: 'Datenverarbeitung',
        graphExplorer: 'Graph-Explorer',
        dataLineage: 'Datenherkunft',
        qualityMonitoring: 'Qualität & Monitoring',
        dataQuality: 'Datenqualität (SODA)',
        observability: 'Observability',
        analytics: 'Analytics',
        reporting: 'Berichte & Dashboards',
        apiDocs: 'API-Dokumentation (OpenAPI/Swagger)',
        settings: 'Einstellungen',
        preferences: 'Präferenzen',
      },
      errors: {
        notFound: 'Nicht gefunden',
      },
      processingHub: {
        subtitle: 'Zentrale ETL-Workflows und schnelle Dateiverarbeitung',
        confirmDelete: 'Möchten Sie diesen Workflow wirklich löschen?',
        status: {
          unknown: 'unbekannt',
        },
        metrics: {
          total: 'Workflows gesamt',
          success: 'Erfolgreiche Läufe',
          active: 'Aktiv',
        },
        tabs: {
          label: 'Tabs für Datenverarbeitung',
          workflows: 'Workflows',
          templates: 'Vorlagen',
          quick: 'Schnelltools',
        },
        workflows: {
          title: 'Workflows',
          create: 'Erstellen',
          empty: 'Noch keine Workflows. Erstellen Sie einen, um zu starten.',
        },
        templates: {
          title: 'Workflow-Vorlagen',
        },
        quick: {
          title: 'Schnelle Dateiverarbeitung',
          fileLabel: 'Datei auswählen',
          latestResults: 'Letzte Ergebnisse',
        },
        results: {
          unnamed: 'Ergebnis',
          recordsProcessed: 'Verarbeitete Datensätze',
        },
        createModal: {
          title: 'Workflow erstellen',
          template: 'Vorlage',
          name: 'Name',
          description: 'Beschreibung',
        },
        actions: {
          run: 'Starten',
          delete: 'Löschen',
          close: 'Schließen',
          cancel: 'Abbrechen',
          create: 'Erstellen',
        },
      },
      settings: {
        title: 'Einstellungen',
        language: 'Sprache',
      },
    },
  },
  zh: {
    translation: {
      nav: {
        home: '主页',
        overview: '概览',
        workflowManagement: '工作流管理',
        workflowManager: '工作流管理器',
        workflowDetail: '工作流详情',
        interactiveStateFlow: '交互式状态流',
        selfHealingMonitor: '自愈监控',
        multiModalAnalyzer: '多模态分析器',
        dataOperations: '数据操作',
        dataConfig: '数据配置',
        spreadsheet: '电子表格',
        dataProcessingHub: '数据处理中心',
        graphExplorer: '图谱浏览',
        dataLineage: '数据血缘',
        qualityMonitoring: '质量与监控',
        dataQuality: '数据质量（SODA）',
        observability: '可观测性',
        analytics: '分析',
        reporting: '报表与仪表板',
        apiDocs: 'API 文档（OpenAPI/Swagger）',
        settings: '设置',
        preferences: '偏好',
      },
      errors: {
        notFound: '未找到',
      },
      processingHub: {
        subtitle: '集中式 ETL 工作流与快速文件处理',
        confirmDelete: '确定要删除此工作流吗？',
        status: {
          unknown: '未知',
        },
        metrics: {
          total: '工作流总数',
          success: '成功次数',
          active: '活跃',
        },
        tabs: {
          label: '数据处理选项卡',
          workflows: '工作流',
          templates: '模板',
          quick: '快速工具',
        },
        workflows: {
          title: '工作流',
          create: '创建',
          empty: '暂无工作流。创建一个开始吧。',
        },
        templates: {
          title: '工作流模板',
        },
        quick: {
          title: '快速文件处理',
          fileLabel: '选择文件',
          latestResults: '最新结果',
        },
        results: {
          unnamed: '结果',
          recordsProcessed: '已处理记录数',
        },
        createModal: {
          title: '创建工作流',
          template: '模板',
          name: '名称',
          description: '描述',
        },
        actions: {
          run: '运行',
          delete: '删除',
          close: '关闭',
          cancel: '取消',
          create: '创建',
        },
      },
      settings: {
        title: '设置',
        language: '语言',
      },
    },
  },
};

function getInitialLanguage() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return stored;
  } catch {
    // ignore
  }

  const browserLang = (navigator.language || 'en').toLowerCase();
  const short = browserLang.split('-')[0];
  if (resources[short]) return short;
  return 'en';
}

i18n.use(initReactI18next).init({
  resources,
  lng: getInitialLanguage(),
  fallbackLng: 'en',
  interpolation: {
    escapeValue: false,
  },
});

export function setAppLanguage(language) {
  i18n.changeLanguage(language);
  try {
    localStorage.setItem(STORAGE_KEY, language);
  } catch {
    // ignore
  }
}

export { STORAGE_KEY as E2ETRACE_LANGUAGE_STORAGE_KEY };
export default i18n;
