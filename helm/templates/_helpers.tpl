{{/*
The service name — uses .Values.name if set, otherwise falls back to the Helm release name.
This lets you do: helm install devops-ai-assistant ./helm -f values/devops-ai-assistant.yaml
and the name comes from the values file, not the release name.
*/}}
{{- define "ai-platform.name" -}}
{{- .Values.name | default .Release.Name }}
{{- end }}

{{/*
Standard K8s recommended labels — applied to every resource.
app.kubernetes.io/* labels let kubectl filter across resource types:
  kubectl get all -l app.kubernetes.io/name=devops-ai-assistant
*/}}
{{- define "ai-platform.labels" -}}
app.kubernetes.io/name: {{ include "ai-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels — used in spec.selector and podAntiAffinity.
Kept separate from labels because selector is immutable after creation.
*/}}
{{- define "ai-platform.selectorLabels" -}}
app.kubernetes.io/name: {{ include "ai-platform.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
