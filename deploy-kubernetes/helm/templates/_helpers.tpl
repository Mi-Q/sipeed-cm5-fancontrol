{{/*
Expand the name of the chart.
*/}}
{{- define "sipeed-cm5-fancontrol.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "sipeed-cm5-fancontrol.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "sipeed-cm5-fancontrol.labels" -}}
helm.sh/chart: {{ include "sipeed-cm5-fancontrol.chart" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}