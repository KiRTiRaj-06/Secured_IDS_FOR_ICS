param(
    [Parameter(Mandatory = $true)]
    [string] $Pcap
)

$ErrorActionPreference = "Stop"
$resolvedPcap = (Resolve-Path -LiteralPath $Pcap).Path
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
$pcapDirectory = Split-Path -Parent $resolvedPcap
$pcapName = Split-Path -Leaf $resolvedPcap
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$zeekOutput = Join-Path $projectRoot "output\zeek-$timestamp"
$suricataOutput = Join-Path $projectRoot "output\suricata-$timestamp"
New-Item -ItemType Directory -Force -Path $zeekOutput, $suricataOutput | Out-Null

$pcapMount = "${pcapDirectory}:/pcap:ro"
$zeekMount = "${zeekOutput}:/logs"
$suricataMount = "${suricataOutput}:/logs"

Write-Host "Running Zeek offline against $resolvedPcap"
$zeekImage = "ics-ids-zeek:local"
docker build -f (Join-Path $projectRoot "Dockerfile.zeek") -t $zeekImage $projectRoot
if ($LASTEXITCODE -ne 0) { throw "Zeek image build returned exit code $LASTEXITCODE" }
docker run --rm -v $pcapMount -v $zeekMount -w /logs $zeekImage zeek -e "redef LogAscii::use_json = T;" -Cr "/pcap/$pcapName" icsnpp-dnp3
if ($LASTEXITCODE -ne 0) { throw "Zeek returned exit code $LASTEXITCODE" }

Write-Host "Running Suricata offline against $resolvedPcap"
docker run --rm -v $pcapMount -v $suricataMount jasonish/suricata:8.0.2 -r "/pcap/$pcapName" -l /logs
if ($LASTEXITCODE -ne 0) { throw "Suricata returned exit code $LASTEXITCODE" }

$outputDirectory = Join-Path $projectRoot "output"+$outputMount = "${outputDirectory}:/data"
$suricataEve = "/data/$(Split-Path -Leaf $suricataOutput)/eve.json"
$zeekControl = "/data/$(Split-Path -Leaf $zeekOutput)/dnp3_control.log"
docker compose -f (Join-Path $projectRoot "compose.yaml") run --rm --no-deps -v $outputMount detector python -m ics_ids.ingest_sensor_logs --suricata $suricataEve --dnp3-control $zeekControl --alerts /data/alerts.jsonl
if ($LASTEXITCODE -ne 0) { throw "Sensor alert normalization returned exit code $LASTEXITCODE" }

Write-Host "Zeek logs: $zeekOutput"
Write-Host "Suricata EVE/logs: $suricataOutput"
