param(
  [Parameter(Mandatory = $true)]
  [string]$RunId
)

$ErrorActionPreference = 'Stop'

if (-not $env:DATABASE_URL) {
  throw 'DATABASE_URL is required (postgresql://user:pass@host:port/dbname)'
}
if (-not $env:NEO4J_URI -or -not $env:NEO4J_USERNAME -or -not $env:NEO4J_PASSWORD) {
  throw 'NEO4J_URI, NEO4J_USERNAME, and NEO4J_PASSWORD are required'
}

# Use local mode by default; override with SPARK_MASTER if desired.
$master = if ($env:SPARK_MASTER) { $env:SPARK_MASTER } else { 'local[*]' }

$sparkSubmit = 'spark-submit'

& $sparkSubmit `
  --master $master `
  --conf spark.sql.session.timeZone=UTC `
  sync_plm_run_to_neo4j.py `
  --run-id $RunId
