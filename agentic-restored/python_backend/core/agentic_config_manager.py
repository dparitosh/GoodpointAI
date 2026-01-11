"""
Agentic Configuration Manager
============================

Modern agentic system for managing database configurations with JSON schema validation,
automatic deployment triggers, and intelligent orchestration.

This module provides:
- JSON schema-based configuration management
- Automatic backend deployment triggers
- Real-time configuration validation
- Agentic decision making for optimal configurations
- WebSocket-based real-time updates to frontend
"""

import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from pydantic import BaseModel, ValidationError, Field
from fastapi import WebSocket, HTTPException, BackgroundTasks
import jsonschema  # type: ignore[import-untyped]  # pyright: ignore[reportMissingTypeStubs]

from graph_api.database_adapters import DatabaseAdapterFactory

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConfigurationMetadata(BaseModel):
    """Configuration metadata model"""
    version: str = "2.0.0"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: Optional[str] = None
    environment: str = Field(..., pattern="^(development|staging|production)$")
    description: Optional[str] = None

class DeploymentConfig(BaseModel):
    """Deployment configuration model"""
    auto_deploy: bool = True
    deployment_strategy: str = Field("progressive", pattern="^(progressive|offline|enterprise)$")
    install_types: List[str] = Field(default=["all"])
    verification_level: str = Field("comprehensive", pattern="^(basic|comprehensive|none)$")
    cache_dependencies: bool = True
    enterprise_features: bool = False

class DeploymentStatus(BaseModel):
    """Deployment status model"""
    status: str = "idle"  # idle, running, completed, failed
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    message: str = ""

class AgenticOrchestrationConfig(BaseModel):
    """Agentic orchestration configuration"""
    enabled: bool = True
    orchestration_mode: str = Field("intelligent", pattern="^(reactive|proactive|intelligent)$")
    workflows: List[Dict[str, Any]] = Field(default_factory=list)
    intelligent_features: Dict[str, bool] = Field(default_factory=dict)

class E2ETraceConfiguration(BaseModel):
    """Main configuration model"""
    metadata: ConfigurationMetadata
    deployment: DeploymentConfig
    data_sources: List[Dict[str, Any]] = Field(default_factory=list)
    agentic_orchestration: AgenticOrchestrationConfig = Field(default_factory=lambda: AgenticOrchestrationConfig(orchestration_mode="intelligent"))
    security: Optional[Dict[str, Any]] = None

class AgenticConfigurationManager:
    """
    Modern agentic configuration manager with JSON schema validation
    and automatic deployment capabilities.
    """
    
    def __init__(self, config_file: str = "agentic_config.json", schema_file: str = "config_schema.json"):
        backend_root = Path(__file__).resolve().parents[1]

        config_path = Path(config_file)
        schema_path = Path(schema_file)

        self.config_file = config_path if config_path.is_absolute() else (backend_root / config_path)
        self.schema_file = schema_path if schema_path.is_absolute() else (backend_root / schema_path)
        self.current_config: Optional[E2ETraceConfiguration] = None
        self.websocket_connections: List[WebSocket] = []
        self.deployment_status = DeploymentStatus()
        
        # Load JSON schema
        self.schema = self._load_schema()
        
        # Initialize database adapter factory
        self.adapter_factory = DatabaseAdapterFactory()
        
        # Load existing configuration
        self._load_configuration()
        
        logger.info("Agentic Configuration Manager initialized")
    
    def _load_schema(self) -> Dict[str, Any]:
        """Load JSON schema for validation"""
        try:
            with open(self.schema_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning("Schema file %s not found", self.schema_file)
            return {}
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in schema file: %s", e)
            return {}
    
    def _load_configuration(self) -> None:
        """Load existing configuration from file"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                    
                # Validate against schema
                if self.schema:
                    jsonschema.validate(config_data, self.schema)
                
                # Create configuration object
                self.current_config = E2ETraceConfiguration(**config_data['configuration'])
                logger.info("Configuration loaded successfully")
                
            except (json.JSONDecodeError, ValidationError, jsonschema.ValidationError) as e:
                logger.error("Error loading configuration: %s", e)
                self._create_default_configuration()
        else:
            self._create_default_configuration()
    
    def _create_default_configuration(self) -> None:
        """Create default configuration"""
        default_config = E2ETraceConfiguration(
            metadata=ConfigurationMetadata(
                environment="development",
                description="Default E2ETrace configuration"
            ),
            deployment=DeploymentConfig(
                auto_deploy=True,
                deployment_strategy="progressive",
                install_types=["all"],
                verification_level="comprehensive",
                cache_dependencies=True,
                enterprise_features=False
            ),
            data_sources=[],
            agentic_orchestration=AgenticOrchestrationConfig(
                enabled=True,
                orchestration_mode="intelligent",
                workflows=[],
                intelligent_features={}
            ),
            security={
                "encryption": {
                    "encrypt_at_rest": False,
                    "encrypt_in_transit": True
                },
                "access_control": {
                    "enable_rbac": False,
                    "require_mfa": False
                }
            }
        )
        
        self.current_config = default_config
        self._save_configuration()
        logger.info("Default configuration created")
    
    def _save_configuration(self) -> None:
        """Save configuration to file"""
        if self.current_config:
            try:
                # Convert to dict and handle datetime serialization
                config_dict = {
                    "configuration": self.current_config.dict()
                }
                # Convert datetime objects to ISO format strings
                def convert_datetime(obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    elif isinstance(obj, dict):
                        return {k: convert_datetime(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [convert_datetime(item) for item in obj]
                    return obj
                config_dict = convert_datetime(config_dict)
                # Validate before saving
                if self.schema:
                    jsonschema.validate(config_dict, self.schema)
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config_dict, f, indent=2, default=str)
                logger.info("Configuration saved successfully")
            except (jsonschema.ValidationError, Exception) as e:  # pylint: disable=broad-exception-caught
                logger.error("Error saving configuration: %s", e)
                raise HTTPException(status_code=500, detail=f"Failed to save configuration: {e}") from e
    
    async def update_configuration(self, config_update: Dict[str, Any], 
                                 trigger_deployment: bool = True) -> Dict[str, Any]:
        """
        Update configuration with agentic validation and optional deployment trigger
        """
        try:
            # Merge with existing configuration
            if self.current_config:
                current_dict = self.current_config.dict()
                # Deep merge the update
                merged_config = self._deep_merge(current_dict, config_update)
            else:
                merged_config = config_update
            
            # Validate merged configuration
            config_with_wrapper = {"configuration": merged_config}
            if self.schema:
                jsonschema.validate(config_with_wrapper, self.schema)
            
            # Create new configuration object
            new_config = E2ETraceConfiguration(**merged_config)
            
            # Agentic analysis of configuration changes
            analysis = await self._analyze_configuration_changes(self.current_config, new_config)
            
            # Update current configuration
            self.current_config = new_config
            self.current_config.metadata.updated_at = datetime.now()
            
            # Save to file
            self._save_configuration()
            
            # Notify WebSocket clients
            await self._notify_websocket_clients({
                "type": "configuration_updated",
                "data": {
                    "config": self.current_config.dict(),
                    "analysis": analysis
                }
            })
            
            # Trigger deployment if requested and analysis recommends it
            deployment_result = None
            if trigger_deployment and (analysis["requires_deployment"] or 
                                     self.current_config.deployment.auto_deploy):
                deployment_result = await self._trigger_deployment(analysis)
            
            return {
                "status": "success",
                "message": "Configuration updated successfully",
                "analysis": analysis,
                "deployment": deployment_result,
                "config": self.current_config.dict()
            }
            
        except ValidationError as e:
            logger.error("Configuration validation error: %s", e)
            raise HTTPException(status_code=400, detail=f"Invalid configuration: {e}") from e
        except jsonschema.ValidationError as e:
            logger.error("JSON schema validation error: %s", e)
            raise HTTPException(status_code=400, detail=f"Schema validation failed: {e}") from e
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error updating configuration: %s", e)
            raise HTTPException(status_code=500, detail=f"Configuration update failed: {e}") from e
    
    async def _analyze_configuration_changes(self, old_config: Optional[E2ETraceConfiguration], 
                                           new_config: E2ETraceConfiguration) -> Dict[str, Any]:
        """
        Agentic analysis of configuration changes to determine required actions
        """
        new_data_sources: List[str] = []
        modified_data_sources: List[str] = []
        deployment_recommendations: List[str] = []
        optimization_suggestions: List[str] = []
        requires_deployment = False
        requires_restart = False
        risk_assessment = "low"
        
        if not old_config:
            requires_deployment = True
            deployment_recommendations.append("Initial deployment required")
            return {
                "requires_deployment": requires_deployment,
                "requires_restart": requires_restart,
                "new_data_sources": new_data_sources,
                "modified_data_sources": modified_data_sources,
                "deployment_recommendations": deployment_recommendations,
                "optimization_suggestions": optimization_suggestions,
                "risk_assessment": risk_assessment,
            }
        
        # Analyze deployment configuration changes
        if old_config.deployment != new_config.deployment:
            requires_deployment = True
            deployment_recommendations.append("Deployment configuration changed")
        
        # Analyze data source changes
        old_sources = {ds["id"]: ds for ds in old_config.data_sources if isinstance(ds, dict) and "id" in ds}
        new_sources = {ds["id"]: ds for ds in new_config.data_sources if isinstance(ds, dict) and "id" in ds}
        
        # Check for new data sources
        for ds_id, ds_config in new_sources.items():
            if ds_id not in old_sources:
                new_data_sources.append(ds_id)
                requires_deployment = True
                # Check if new database type requires additional dependencies
                db_type = ds_config.get("type")
                if db_type in ["oracle", "mssql"] and not self._check_database_driver_installed(db_type):
                    deployment_recommendations.append(
                        f"Install {db_type} database drivers"
                    )
        
        # Check for modified data sources
        for ds_id, ds_config in new_sources.items():
            if ds_id in old_sources and old_sources[ds_id] != ds_config:
                modified_data_sources.append(ds_id)
        
        # Agentic optimization suggestions
        optimization_suggestions = self._generate_optimization_suggestions(new_config)
        
        # Risk assessment
        risk_assessment = self._assess_configuration_risk(new_config)
        
        return {
            "requires_deployment": requires_deployment,
            "requires_restart": requires_restart,
            "new_data_sources": new_data_sources,
            "modified_data_sources": modified_data_sources,
            "deployment_recommendations": deployment_recommendations,
            "optimization_suggestions": optimization_suggestions,
            "risk_assessment": risk_assessment,
        }
    
    def _check_database_driver_installed(self, db_type: str) -> bool:
        """Check if database driver is installed"""
        driver_imports = {
            "oracle": "oracledb",
            "mssql": "pyodbc",
            "postgresql": "asyncpg",
            "excel": "pandas"
        }
        
        if db_type in driver_imports:
            try:
                __import__(driver_imports[db_type])
                return True
            except ImportError:
                return False
        return True
    def _generate_optimization_suggestions(self, config: E2ETraceConfiguration) -> List[str]:
        """Generate agentic optimization suggestions"""
        suggestions = []
        
        # Connection pool optimization
        for ds in config.data_sources:
            if "advanced_config" in ds and "connection_pool" in ds["advanced_config"]:
                pool_config = ds["advanced_config"]["connection_pool"]
                if pool_config.get("max_connections", 20) > 50:
                    suggestions.append(f"Consider reducing connection pool size for {ds['name']}")
        
        # Caching recommendations
        if not config.deployment.cache_dependencies:
            suggestions.append("Enable dependency caching for faster deployments")
        
        # Security recommendations
        if not config.security or not config.security.get("encryption", {}).get("encrypt_at_rest"):
            suggestions.append("Enable encryption at rest for enhanced security")
        
        return suggestions
    
    def _assess_configuration_risk(self, config: E2ETraceConfiguration) -> str:
        """Assess configuration risk level"""
        risk_score = 0
        # Check for production environment without security
        if config.metadata.environment == "production":
            if not config.security:
                risk_score += 3
            else:
                if not config.security.get("encryption", {}).get("encrypt_at_rest"):
                    risk_score += 2
                if not config.security.get("access_control", {}).get("enable_rbac"):
                    risk_score += 1
        
        # Check for large connection pools
        for ds in config.data_sources:
            if "advanced_config" in ds:
                max_conn = ds["advanced_config"].get("connection_pool", {}).get("max_connections", 20)
                if max_conn > 100:
                    risk_score += 1
        
        if risk_score >= 4:
            return "high"
        elif risk_score >= 2:
            return "medium"
        else:
            return "low"
    
    async def _trigger_deployment(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger backend deployment based on configuration analysis"""
        try:
            deployment_strategy = getattr(getattr(self.current_config, 'deployment', None), 'deployment_strategy', None)
            install_types = getattr(getattr(self.current_config, 'deployment', None), 'install_types', None)
            
            # Determine deployment command based on strategy
            if not isinstance(install_types, list):
                install_types = ["all"]
            if deployment_strategy == "progressive":
                cmd = self._build_progressive_deployment_command(install_types)
            elif deployment_strategy == "offline":
                cmd = self._build_offline_deployment_command(install_types)
            elif deployment_strategy == "enterprise":
                cmd = self._build_enterprise_deployment_command(install_types)
            else:
                cmd = self._build_progressive_deployment_command(install_types)
            
            # Update deployment status
            self.deployment_status.status = "running"
            self.deployment_status.started_at = datetime.now()
            
            # Notify WebSocket clients about deployment start
            await self._notify_websocket_clients({
                "type": "deployment_started",
                "data": {
                    "strategy": deployment_strategy,
                    "command": " ".join(cmd),
                    "analysis": analysis
                }
            })
            
            # Execute deployment command asynchronously
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=Path(__file__).parent
            )
            
            stdout, stderr = await process.communicate()
            
            # Update deployment status
            if process.returncode == 0:
                self.deployment_status.status = "completed"
                self.deployment_status.completed_at = datetime.now()
                status = "success"
                message = "Deployment completed successfully"
            else:
                self.deployment_status.status = "failed"
                self.deployment_status.completed_at = datetime.now()
                status = "error"
                message = f"Deployment failed: {stderr.decode()}"
            
            result = {
                "status": status,
                "message": message,
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "return_code": process.returncode,
                "strategy": deployment_strategy
            }
            
            # Notify WebSocket clients about deployment completion
            await self._notify_websocket_clients({
                "type": "deployment_completed",
                "data": result
            })
            
            return result
            
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Deployment failed: %s", e)
            self.deployment_status.status = "failed"
            self.deployment_status.completed_at = datetime.now()
            
            error_result = {
                "status": "error",
                "message": f"Deployment failed: {str(e)}",
                "strategy": deployment_strategy
            }
            
            await self._notify_websocket_clients({
                "type": "deployment_failed",
                "data": error_result
            })
            
            return error_result
    
    def _build_progressive_deployment_command(self, install_types: List[str]) -> List[str]:
        """Build progressive deployment command"""
        if "all" in install_types:
            return ["python", "install-database-support-advanced.ps1", "-InstallType", "all"]
        else:
            return ["python", "install-database-support-advanced.ps1", "-InstallType", install_types[0]]
    
    def _build_offline_deployment_command(self, install_types: List[str]) -> List[str]:
        """Build offline deployment command"""
        cmd = self._build_progressive_deployment_command(install_types)
        cmd.extend(["-OfflineMode"])
        return cmd
    
    def _build_enterprise_deployment_command(self, install_types: List[str]) -> List[str]:
        """Build enterprise deployment command"""
        cmd = self._build_progressive_deployment_command(install_types)
        cmd.extend(["-Enterprise"])
        return cmd
    
    async def _notify_websocket_clients(self, message: Dict[str, Any]) -> None:
        """Notify all connected WebSocket clients"""
        if self.websocket_connections:
            message_str = json.dumps(message, default=str)
            disconnected = []
            
            for websocket in self.websocket_connections:
                try:
                    await websocket.send_text(message_str)
                except Exception:  # pylint: disable=broad-exception-caught
                    disconnected.append(websocket)
            
            # Remove disconnected clients
            for ws in disconnected:
                self.websocket_connections.remove(ws)
    
    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = base.copy()
        
        for key, value in update.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    async def add_websocket_connection(self, websocket: WebSocket) -> None:
        """Add WebSocket connection for real-time updates"""
        await websocket.accept()
        self.websocket_connections.append(websocket)
        
        # Send current configuration
        if self.current_config:
            await websocket.send_text(json.dumps({
                "type": "configuration_loaded",
                "data": self.current_config.dict()
            }, default=str))
    
    def remove_websocket_connection(self, websocket: WebSocket) -> None:
        """Remove WebSocket connection"""
        if websocket in self.websocket_connections:
            self.websocket_connections.remove(websocket)
    
    async def get_configuration(self) -> Dict[str, Any]:
        """Get current configuration"""
        if self.current_config:
            return self.current_config.dict()
        return {}
    
    async def get_deployment_status(self) -> Dict[str, Any]:
        """Get current deployment status"""
        return self.deployment_status.dict()
    
    async def trigger_deployment(self, deployment_config: Dict[str, Any], 
                               _background_tasks: BackgroundTasks) -> Dict[str, Any]:
        """Trigger deployment with custom configuration"""
        # Update deployment config if provided
        if deployment_config and self.current_config and hasattr(self.current_config, 'deployment') and self.current_config.deployment:
            for key, value in deployment_config.items():
                if hasattr(self.current_config.deployment, key):
                    setattr(self.current_config.deployment, key, value)
        
        # Trigger deployment in background
        analysis = {"requires_deployment": True, "trigger": "manual"}
        result = await self._trigger_deployment(analysis)
        
        return {
            "status": "success",
            "message": "Deployment triggered successfully",
            "deployment": result
        }
    
    async def get_analytics(self) -> Dict[str, Any]:
        """Get configuration analytics and insights"""
        if not self.current_config or not hasattr(self.current_config, 'data_sources') or not isinstance(self.current_config.data_sources, list):
            return {}
        updated_at = getattr(getattr(self.current_config, 'metadata', None), 'updated_at', None)
        last_updated = updated_at.isoformat() if isinstance(updated_at, datetime) else None
        analytics = {
            "total_data_sources": len(self.current_config.data_sources),
            "data_source_types": {},
            "deployment_strategy": getattr(getattr(self.current_config, 'deployment', None), 'deployment_strategy', None),
            "auto_deploy_enabled": getattr(getattr(self.current_config, 'deployment', None), 'auto_deploy', None),
            "environment": getattr(getattr(self.current_config, 'metadata', None), 'environment', None),
            "last_updated": last_updated,
            "agentic_features": {
                "orchestration_enabled": getattr(getattr(self.current_config, 'agentic_orchestration', None), 'enabled', None),
                "workflow_count": len(getattr(getattr(self.current_config, 'agentic_orchestration', None), 'workflows', [])),
                "orchestration_mode": getattr(getattr(self.current_config, 'agentic_orchestration', None), 'orchestration_mode', None)
            },
            "security_score": self._calculate_security_score(),
            "optimization_score": self._calculate_optimization_score(),
            "recommendations": self._generate_optimization_suggestions(self.current_config)
        }
        # Count data source types
        if isinstance(analytics["data_source_types"], dict):
            for ds in self.current_config.data_sources:
                ds_type = ds.get("type", "unknown")
                analytics["data_source_types"][ds_type] = analytics["data_source_types"].get(ds_type, 0) + 1
        return analytics
    
    def _calculate_security_score(self) -> int:
        """Calculate security score (0-100)"""
        score = 50  # Base score
        
        if self.current_config and getattr(self.current_config, 'security', None):
            security = self.current_config.security
            if isinstance(security, dict):
                # Encryption checks
                if security.get("encryption", {}) and security.get("encryption", {}).get("encrypt_at_rest"):
                    score += 15
                if security.get("encryption", {}) and security.get("encryption", {}).get("encrypt_in_transit"):
                    score += 15
                # Access control checks
                if security.get("access_control", {}) and security.get("access_control", {}).get("enable_rbac"):
                    score += 10
                if security.get("access_control", {}) and security.get("access_control", {}).get("enable_mfa"):
                    score += 10
        
        return min(score, 100)
    
    def _calculate_optimization_score(self) -> int:
        """Calculate optimization score (0-100)"""
        score = 50  # Base score
        
        # Deployment optimizations
        if self.current_config and getattr(self.current_config, 'deployment', None) and getattr(self.current_config.deployment, 'cache_dependencies', False):
            score += 10
        # Connection pool optimizations
        optimized_pools = 0
        data_sources = getattr(self.current_config, 'data_sources', []) if self.current_config else []
        for ds in data_sources:
            if "advanced_config" in ds and "connection_pool" in ds["advanced_config"]:
                pool_config = ds["advanced_config"]["connection_pool"]
                # Check for reasonable pool sizes
                if 1 <= pool_config.get("min_connections", 1) <= 10 and \
                   10 <= pool_config.get("max_connections", 20) <= 50:
                    optimized_pools += 1
        if data_sources:
            pool_optimization_score = int((optimized_pools / len(data_sources)) * 20)
            score += pool_optimization_score
        # Query optimization checks
        query_optimized = 0
        for ds in data_sources:
            if "advanced_config" in ds and "query_optimization" in ds["advanced_config"]:
                query_config = ds["advanced_config"]["query_optimization"]
                if query_config.get("enable_query_cache") and query_config.get("enable_prepared_statements"):
                    query_optimized += 1
        if data_sources:
            query_optimization_score = int((query_optimized / len(data_sources)) * 20)
            score += query_optimization_score
        return min(score, 100)
    
    async def get_data_sources(self) -> List[Dict[str, Any]]:
        """Get all configured data sources"""
        if self.current_config:
            return self.current_config.data_sources
        return []
    
    async def add_data_source(self, data_source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new data source"""
        try:
            # Generate ID if not provided
            if "id" not in data_source_config:
                data_source_config["id"] = f"ds_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Add to configuration
            if self.current_config and hasattr(self.current_config, 'data_sources'):
                if not isinstance(self.current_config.data_sources, list):
                    self.current_config.data_sources = []
                self.current_config.data_sources.append(data_source_config)
            if self.current_config and getattr(self.current_config, 'metadata', None) is not None:
                self.current_config.metadata.updated_at = datetime.now()
            
            # Save configuration
            self._save_configuration()
            
            # Notify WebSocket clients
            await self._notify_websocket_clients({
                "type": "data_source_added",
                "data": {"data_source": data_source_config}
            })
            
            return {
                "status": "success",
                "message": "Data source added successfully",
                "data": {"config": self.current_config.dict() if self.current_config else {}}
            }
            
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error adding data source: %s", e)
            raise HTTPException(status_code=500, detail=str(e)) from e
    
    async def update_data_source(self, source_id: str, data_source_config: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing data source"""
        try:
            # Find and update data source
            if self.current_config and hasattr(self.current_config, 'data_sources'):
                if not isinstance(self.current_config.data_sources, list):
                    self.current_config.data_sources = []
                for i, ds in enumerate(self.current_config.data_sources):
                    if ds.get("id") == source_id:
                        # Preserve ID
                        data_source_config["id"] = source_id
                        self.current_config.data_sources[i] = data_source_config
                        if hasattr(self.current_config, 'metadata') and self.current_config.metadata:
                            self.current_config.metadata.updated_at = datetime.now()
                        # Save configuration
                        self._save_configuration()
                        # Notify WebSocket clients
                        await self._notify_websocket_clients({
                            "type": "data_source_updated",
                            "data": {"data_source": data_source_config}
                        })
                        return {
                            "status": "success",
                            "message": "Data source updated successfully",
                            "data": {"config": self.current_config.dict()}
                        }
            
            raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
            
        except HTTPException:
            raise
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error updating data source: %s", e)
            raise HTTPException(status_code=500, detail=str(e)) from e
    
    async def delete_data_source(self, source_id: str) -> Dict[str, Any]:
        """Delete a data source"""
        try:
            # Find and remove data source
            if self.current_config and hasattr(self.current_config, 'data_sources'):
                if not isinstance(self.current_config.data_sources, list):
                    self.current_config.data_sources = []
                for i, ds in enumerate(self.current_config.data_sources):
                    if ds.get("id") == source_id:
                        self.current_config.data_sources.pop(i)
                        if hasattr(self.current_config, 'metadata') and self.current_config.metadata:
                            self.current_config.metadata.updated_at = datetime.now()
                        # Save configuration
                        self._save_configuration()
                        # Notify WebSocket clients
                        await self._notify_websocket_clients({
                            "type": "data_source_deleted",
                            "data": {"data_source_id": source_id}
                        })
                        return {
                            "status": "success",
                            "message": "Data source deleted successfully",
                            "data": {"config": self.current_config.dict()}
                        }
            
            raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
            
        except HTTPException:
            raise
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error deleting data source: %s", e)
            raise HTTPException(status_code=500, detail=str(e)) from e
    
    async def test_data_source_connection(self, source_id: str) -> Dict[str, Any]:
        """Test connection for a specific data source"""
        try:
            # Find data source
            data_source = None
            if self.current_config and hasattr(self.current_config, 'data_sources'):
                if not isinstance(self.current_config.data_sources, list):
                    self.current_config.data_sources = []
                for ds in self.current_config.data_sources:
                    if ds.get("id") == source_id:
                        data_source = ds
                        break
            
            if not data_source:
                raise HTTPException(status_code=404, detail=f"Data source {source_id} not found")
            
            # Test connection using adapter factory
            adapter = self.adapter_factory.create_adapter(data_source["type"], data_source.get("connection", {}))
            if adapter:
                test_result = await adapter.test_connection()
                success = bool(test_result.get("success")) if isinstance(test_result, dict) else bool(test_result)
                
                # Update data source status
                if self.current_config and hasattr(self.current_config, 'data_sources') and isinstance(self.current_config.data_sources, list):
                    for ds in self.current_config.data_sources:
                        if ds.get("id") == source_id:
                            ds["status"] = "active" if success else "error"
                            break
                
                self._save_configuration()
                
                return {
                    "status": "success" if success else "error",
                    "message": test_result.get("message", "Connection test completed") if isinstance(test_result, dict) else "Connection test completed",
                    "data": test_result if isinstance(test_result, dict) else {"success": success}
                }
            else:
                return {
                    "status": "error",
                    "message": f"No adapter available for {data_source['type']}"
                }
                
        except HTTPException:
            raise
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error testing data source connection: %s", e)
            return {
                "status": "error",
                "message": str(e)
            }
    
    async def export_configuration(self) -> Dict[str, Any]:
        """Export current configuration"""
        if self.current_config:
            config_data = self.current_config.dict()
            config_data["exported_at"] = datetime.now().isoformat()
            config_data["export_version"] = "2.0.0"
            return config_data
        return {}
    
    async def import_configuration(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Import configuration from data"""
        try:
            # Validate imported configuration
            if "configuration" in config_data:
                config_data = config_data["configuration"]
            
            # Create configuration object
            imported_config = E2ETraceConfiguration(**config_data)
            
            # Update current configuration
            self.current_config = imported_config
            self.current_config.metadata.updated_at = datetime.now()
            
            # Save configuration
            self._save_configuration()
            
            # Notify WebSocket clients
            await self._notify_websocket_clients({
                "type": "configuration_imported",
                "data": {"config": self.current_config.dict()}
            })
            
            return {
                "status": "success",
                "message": "Configuration imported successfully",
                "data": {"config": self.current_config.dict()}
            }
            
        except ValidationError as e:
            raise HTTPException(status_code=400, detail=f"Invalid configuration format: {e}") from e
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error importing configuration: %s", e)
            raise HTTPException(status_code=500, detail=str(e)) from e
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        checks: Dict[str, Any] = {}
        health_status: Dict[str, Any] = {
            "service": "agentic_configuration_manager",
            "status": "healthy",
            "checks": checks,
            "timestamp": datetime.now().isoformat()
        }
        
        # Check configuration file access
        try:
            checks["config_file"] = {
                "status": "ok" if self.config_file.exists() else "warning",
                "message": "Configuration file accessible" if self.config_file.exists() else "Configuration file not found"
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            checks["config_file"] = {
                "status": "error",
                "message": str(e)
            }
        
        # Check schema file access
        try:
            checks["schema_file"] = {
                "status": "ok" if self.schema_file.exists() else "warning",
                "message": "Schema file accessible" if self.schema_file.exists() else "Schema file not found"
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            checks["schema_file"] = {
                "status": "error",
                "message": str(e)
            }
        
        # Check current configuration
        checks["current_config"] = {
            "status": "ok" if self.current_config else "warning",
            "message": "Configuration loaded" if self.current_config else "No configuration loaded"
        }
        
        # Check database adapters
        try:
            checks["database_adapters"] = {
                "status": "ok",
                "message": "Adapter factory initialized"
            }
        except Exception as e:  # pylint: disable=broad-exception-caught
            checks["database_adapters"] = {
                "status": "error",
                "message": str(e)
            }
        
        # Overall status
        error_checks = [check for check in checks.values() if check.get("status") == "error"]
        if error_checks:
            health_status["status"] = "unhealthy"
        elif any(check.get("status") == "warning" for check in checks.values()):
            health_status["status"] = "degraded"
        
        return health_status

# Utility function to ensure all expected list fields in analysis are lists.
def coerce_analysis_lists(analysis: Dict[str, Any]) -> None:
    for key in ["new_data_sources", "modified_data_sources", "deployment_recommendations", "optimization_suggestions"]:
        if key in analysis and not isinstance(analysis[key], list):
            analysis[key] = []

# ============= SINGLETON INSTANCE =============

# Create global config manager instance
config_manager = AgenticConfigurationManager()

# Export for use in other modules
__all__ = ["AgenticConfigurationManager", "config_manager"]
