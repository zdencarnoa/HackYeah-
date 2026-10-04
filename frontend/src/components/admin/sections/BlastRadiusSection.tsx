"use client";

/**
 * What one employee's account could reach if it were compromised (D's simulated
 * blast radius), drawn left to right: employee → identity provider → services →
 * data and people. The reachable path lights up column by column; the rest of the
 * organization stays dimmed for context.
 */

import "@xyflow/react/dist/style.css";

import { Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { useMemo } from "react";

import type { BlastNodeKind, BlastRadius, Sensitivity } from "@/lib/contracts";
import { blastRadius } from "@/lib/demo/selectors";

const COLUMN_X = [0, 230, 470, 730];
const ROW_HEIGHT = 66;
const NODE_WIDTH = 190;
const LIGHT_UP_STEP_S = 0.3;

const KIND_LABEL: Record<BlastNodeKind, string> = {
  employee: "Employee",
  identity_provider: "Identity provider",
  service: "Service",
  data: "Data",
  people: "People",
};

const COLUMN: Record<BlastNodeKind, number> = { employee: 0, identity_provider: 1, service: 2, data: 3, people: 3 };

interface BlastNodeData extends Record<string, unknown> {
  label: string;
  kind: BlastNodeKind;
  sensitivity: Sensitivity | null;
  atRisk: boolean;
}

type BlastNode = Node<BlastNodeData, "blast">;

const nodeTypes = { blast: BlastNodeView };

export function BlastRadiusSection({ employeeId }: { employeeId: string }) {
  const radius = useMemo(() => blastRadius(employeeId), [employeeId]);
  const { nodes, edges } = useMemo(() => layout(radius), [radius]);
  const reachable = radius.nodes.filter((n) => n.at_risk && n.kind !== "employee").length;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span>
          <span className="font-semibold text-critical">{reachable}</span> parts of the organization reachable from
          this account
        </span>
        <span className="flex items-center gap-3">
          <Legend className="border-critical/60 bg-critical/15">May be exposed</Legend>
          <Legend className="border-line bg-panel opacity-50">Not reachable</Legend>
        </span>
      </div>

      <div className="h-[380px] w-full overflow-hidden rounded-xl border border-line bg-panel-2/40">
        <ReactFlow
          key={employeeId}
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          colorMode="dark"
          fitView
          fitViewOptions={{ padding: 0.12 }}
          minZoom={0.3}
          maxZoom={1.5}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          zoomOnScroll={false}
          preventScrolling={false}
          style={{ background: "transparent" }}
        >
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      <p className="text-sm leading-relaxed text-ink">{radius.explanation}</p>
      <p className="text-xs text-muted">Simulated organization graph. It shows what an account could reach, not what an attacker did.</p>
    </div>
  );
}

function BlastNodeView({ data }: NodeProps<BlastNode>) {
  const column = COLUMN[data.kind];
  return (
    <div
      className={`rounded-lg border px-3 py-2 transition-opacity ${
        data.atRisk
          ? "border-critical/60 bg-critical/12 shadow-[0_0_22px_-6px_var(--critical)]"
          : "border-line bg-panel opacity-45"
      }`}
      style={{
        width: NODE_WIDTH,
        animation: data.atRisk ? `slide-in 0.45s ease-out ${column * LIGHT_UP_STEP_S}s both` : undefined,
      }}
    >
      {data.kind !== "employee" && <Handle type="target" position={Position.Left} isConnectable={false} style={HIDDEN} />}
      <div className="flex items-center justify-between gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">{KIND_LABEL[data.kind]}</span>
        {data.sensitivity && <SensitivityDot sensitivity={data.sensitivity} />}
      </div>
      <div className={`mt-0.5 text-[13px] font-medium leading-tight ${data.atRisk ? "text-ink" : "text-muted"}`}>{data.label}</div>
      {data.kind !== "data" && data.kind !== "people" && (
        <Handle type="source" position={Position.Right} isConnectable={false} style={HIDDEN} />
      )}
    </div>
  );
}

const HIDDEN = { opacity: 0, pointerEvents: "none" } as const;

function SensitivityDot({ sensitivity }: { sensitivity: Sensitivity }) {
  const color = { low: "bg-low", medium: "bg-medium", high: "bg-critical" }[sensitivity];
  return (
    <span className="flex items-center gap-1 text-[10px] text-muted" title={`${sensitivity} sensitivity`}>
      <span className={`size-1.5 rounded-full ${color}`} />
      {sensitivity}
    </span>
  );
}

function Legend({ className, children }: { className: string; children: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`inline-block h-2.5 w-4 rounded-sm border ${className}`} />
      {children}
    </span>
  );
}

/**
 * Layered layout: one column per kind. Services take one row each (reachable
 * first), their data and people sit in the next column on the same rows, and the
 * employee and identity provider are centred on the left.
 */
function layout(radius: BlastRadius): { nodes: BlastNode[]; edges: Edge[] } {
  const byId = new Map(radius.nodes.map((n) => [n.id, n]));
  const services = radius.nodes
    .filter((n) => n.kind === "service")
    .sort((a, b) => Number(b.at_risk) - Number(a.at_risk));
  const rows = new Map<string, number>();
  let cursor = 0;
  for (const service of services) {
    rows.set(service.id, cursor);
    const children = radius.edges.filter((e) => e.source === service.id && byId.has(e.target)).map((e) => e.target);
    children.forEach((child, i) => rows.set(child, cursor + i));
    cursor += Math.max(1, children.length);
  }
  const middle = ((cursor - 1) / 2) * ROW_HEIGHT;

  const nodes: BlastNode[] = radius.nodes.map((n) => ({
    id: n.id,
    type: "blast",
    position: {
      x: COLUMN_X[COLUMN[n.kind]],
      y: n.kind === "employee" || n.kind === "identity_provider" ? middle : (rows.get(n.id) ?? 0) * ROW_HEIGHT,
    },
    data: { label: n.label, kind: n.kind, sensitivity: n.sensitivity, atRisk: n.at_risk },
    draggable: false,
    selectable: false,
  }));

  const edges: Edge[] = radius.edges.map((e) => {
    const lit = Boolean(byId.get(e.source)?.at_risk && byId.get(e.target)?.at_risk);
    return {
      id: `${e.source}->${e.target}`,
      source: e.source,
      target: e.target,
      animated: lit,
      selectable: false,
      style: lit
        ? { stroke: "var(--critical)", strokeWidth: 2 }
        : { stroke: "var(--line)", strokeWidth: 1.25, opacity: 0.7 },
      ariaLabel: `${byId.get(e.source)?.label} ${e.relation} ${byId.get(e.target)?.label}`,
    };
  });
  return { nodes, edges };
}
