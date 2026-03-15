# TELOS Integration Architecture -- Vultr Cloud

## Kubernetes Sidecar Deployment Model

TELOS deploys as a sidecar container within the same Kubernetes pod as the customer's AI agent. This is the standard Kubernetes sidecar pattern -- no custom networking, no service mesh dependency, no changes to the customer's agent code.

```
+-------------------------------------------------------+
|  Vultr Kubernetes Pod                                  |
|                                                        |
|  +---------------------+    +----------------------+   |
|  |  Agent Container    |    |  TELOS Sidecar       |   |
|  |  (Customer AI)      |    |  (Governance)        |   |
|  |                     |    |                      |   |
|  |  - LLM inference    |    |  - 4-layer cascade   |   |
|  |  - Tool execution   |--->|  - Boundary enforce  |   |
|  |  - Business logic   |    |  - Audit writer      |   |
|  |                     |<---|  - Drift detection    |   |
|  +---------------------+    +----------------------+   |
|         |                           |                  |
|    GPU Instance                Audit Volume            |
|    (A100/H100/L40S)           (Block Storage PVC)      |
+-------------------------------------------------------+
```

## IPC Mechanism

Communication between the agent container and the TELOS sidecar uses **localhost IPC** -- the standard Kubernetes pod networking model where containers in the same pod share a network namespace.

- **No network hops** -- localhost within the pod
- **No service mesh required** -- no Istio, no Linkerd, no Envoy
- **No DNS resolution** -- direct localhost address
- **No TLS overhead** -- intra-pod traffic is internal

## Resource Footprint

The TELOS sidecar is deliberately lightweight so it never competes with the customer's GPU workload:

| Resource | TELOS Sidecar | Typical AI Agent |
|----------|---------------|------------------|
| RAM | 256MB | 8-32GB+ |
| CPU | 0.25 cores | 2-8 cores |
| GPU | None (CPU-only) | A100/H100/L40S |
| Model | 24MB ONNX (MiniLM) | 7B-70B+ parameters |
| Storage | Audit PVC (grows ~1KB/event) | Model weights, data |

The sidecar runs entirely on CPU. GPU resources are 100% available for the customer's AI workload.

## Latency Budget

| Operation | Latency |
|-----------|---------|
| TELOS governance decision | <30ms |
| Typical LLM inference round-trip | 100-500ms |
| Governance overhead as % of inference | 6-30% |

Governance latency is a fraction of the inference latency the agent already incurs. In practice, the governance check runs while the agent is waiting for the next inference response.

## VKE Pod Specification

Example Vultr Kubernetes Engine (VKE) pod spec with TELOS sidecar:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: governed-agent
  labels:
    telos.ai/governed: "true"
spec:
  containers:
    - name: agent
      image: customer/ai-agent:latest
      resources:
        requests:
          nvidia.com/gpu: 1
          memory: "16Gi"
          cpu: "4"
      env:
        - name: TELOS_GOVERNANCE_URL
          value: "http://localhost:8100"

    - name: telos-sidecar
      image: telos/governance-sidecar:latest
      resources:
        requests:
          memory: "256Mi"
          cpu: "250m"
        limits:
          memory: "512Mi"
          cpu: "500m"
      volumeMounts:
        - name: audit-volume
          mountPath: /var/telos/audit
        - name: config-volume
          mountPath: /etc/telos

  volumes:
    - name: audit-volume
      persistentVolumeClaim:
        claimName: telos-audit-pvc
    - name: config-volume
      configMap:
        name: telos-governance-config
```

## Audit Persistence

The audit trail is written to a Vultr Block Storage PVC that persists independently of pod lifecycle:

- **Survives pod restarts** -- audit data is on persistent block storage, not ephemeral
- **Survives node failures** -- Vultr Block Storage replicates across the storage cluster
- **Exportable** -- standard JSONL format, readable by any log aggregation tool
- **Immutable append** -- the audit writer only appends, never overwrites

## Vultr-Specific Advantages

- **GPU instances for AI, CPU for governance** -- TELOS sidecar runs on the CPU cores included with every GPU instance. No additional GPU allocation needed.
- **Block Storage for audit** -- Vultr Block Storage provides the persistent volume for audit trails. Scales independently of compute.
- **VKE native** -- standard Kubernetes sidecar pattern works with VKE out of the box. No custom operators or CRDs required.
- **Multi-region** -- deploy governed agents in any Vultr region. Audit trails can be aggregated centrally or kept region-local for data residency compliance.
