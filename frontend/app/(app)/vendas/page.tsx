"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Plus, ClipboardCheck, X } from "lucide-react";

interface PedidoVenda {
  id: number;
  numero: string;
  cliente_id: number;
  status: string;
  valor_total: number;
  data_emissao: string;
  data_previsao_entrega: string | null;
  condicao_pagamento: string | null;
}

interface Cliente { id: number; razao_social: string; }

const STATUS_BADGE: Record<string, string> = {
  ORCAMENTO: "badge-gray",
  CONFIRMADO: "badge-blue",
  EM_PICKING: "badge-yellow",
  PICKING_OK: "badge-yellow",
  EXPEDIDO: "badge-green",
  CANCELADO: "badge-red",
};

const STATUS_LABEL: Record<string, string> = {
  ORCAMENTO: "Orçamento",
  CONFIRMADO: "Confirmado",
  EM_PICKING: "Em Picking",
  PICKING_OK: "Picking OK",
  EXPEDIDO: "Expedido",
  CANCELADO: "Cancelado",
};

const FILTROS = ["TODOS", "ORCAMENTO", "CONFIRMADO", "EM_PICKING", "EXPEDIDO"];

export default function VendasPage() {
  const [pedidos, setPedidos] = useState<PedidoVenda[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [filtro, setFiltro] = useState("TODOS");
  const [confirmandoId, setConfirmandoId] = useState<number | null>(null);
  const [cancelandoId, setCancelandoId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchPedidos = () => {
    const params: Record<string, string> = {};
    if (filtro !== "TODOS") params.status = filtro;
    api.get("/vendas/", { params }).then((r) => setPedidos(r.data));
  };

  useEffect(() => { fetchPedidos(); }, [filtro]);

  useEffect(() => {
    api.get("/clientes/", { params: { limit: 200 } }).then((r) => setClientes(r.data));
  }, []);

  function nomeCliente(id: number) {
    return clientes.find((c) => c.id === id)?.razao_social || `Cliente #${id}`;
  }

  async function confirmar(id: number) {
    setLoading(true);
    try {
      await api.post(`/vendas/${id}/confirmar`);
      fetchPedidos();
    } finally {
      setConfirmandoId(null);
      setLoading(false);
    }
  }

  async function cancelar(id: number) {
    setLoading(true);
    try {
      await api.post(`/vendas/${id}/cancelar`);
      fetchPedidos();
    } finally {
      setCancelandoId(null);
      setLoading(false);
    }
  }

  const moeda = (v: number) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Vendas</h1>
        <a href="/vendas/novo" className="btn-primary">
          <Plus size={16} /> Novo Pedido
        </a>
      </div>

      <div className="flex gap-2 mb-4 flex-wrap">
        {FILTROS.map((f) => (
          <button key={f} onClick={() => setFiltro(f)}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              filtro === f ? "bg-blue-700 text-white" : "bg-white border text-gray-600 hover:bg-gray-50"
            }`}>
            {f === "TODOS" ? "Todos" : STATUS_LABEL[f]}
          </button>
        ))}
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3 font-medium text-gray-600">Número</th>
              <th className="text-left p-3 font-medium text-gray-600">Cliente</th>
              <th className="text-left p-3 font-medium text-gray-600">Emissão</th>
              <th className="text-left p-3 font-medium text-gray-600">Entrega</th>
              <th className="text-left p-3 font-medium text-gray-600">Status</th>
              <th className="text-right p-3 font-medium text-gray-600">Total</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {pedidos.map((p) => (
              <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3 font-mono text-xs font-bold">{p.numero}</td>
                <td className="p-3">{nomeCliente(p.cliente_id)}</td>
                <td className="p-3">{new Date(p.data_emissao).toLocaleDateString("pt-BR")}</td>
                <td className="p-3 text-gray-500">
                  {p.data_previsao_entrega
                    ? new Date(p.data_previsao_entrega).toLocaleDateString("pt-BR")
                    : "—"}
                </td>
                <td className="p-3">
                  <span className={STATUS_BADGE[p.status] || "badge-gray"}>
                    {STATUS_LABEL[p.status] || p.status}
                  </span>
                </td>
                <td className="p-3 text-right font-medium">{moeda(Number(p.valor_total))}</td>
                <td className="p-3 text-right">
                  {p.status === "ORCAMENTO" && (
                    <button onClick={() => setConfirmandoId(p.id)}
                      className="text-blue-600 text-xs hover:underline mr-3">
                      Confirmar
                    </button>
                  )}
                  {(p.status === "CONFIRMADO" || p.status === "EM_PICKING") && (
                    <a href={`/picking/${p.id}`}
                      className="flex items-center gap-1 text-purple-600 text-xs hover:underline mr-3 inline-flex">
                      <ClipboardCheck size={12} /> Picking
                    </a>
                  )}
                  {!["EXPEDIDO", "CANCELADO"].includes(p.status) && (
                    <button onClick={() => setCancelandoId(p.id)}
                      className="text-red-500 text-xs hover:underline">
                      Cancelar
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {pedidos.length === 0 && (
              <tr>
                <td colSpan={7} className="p-8 text-center text-gray-400">
                  Nenhum pedido encontrado
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Diálogo Confirmar */}
      {confirmandoId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-sm p-6">
            <h2 className="font-semibold text-lg mb-2">Confirmar Pedido?</h2>
            <p className="text-sm text-gray-500 mb-6">
              O estoque disponível será reservado automaticamente para este pedido.
            </p>
            <div className="flex justify-end gap-3">
              <button className="btn-secondary" onClick={() => setConfirmandoId(null)}>Cancelar</button>
              <button className="btn-primary" disabled={loading}
                onClick={() => confirmar(confirmandoId)}>
                {loading ? "Confirmando..." : "Confirmar"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Diálogo Cancelar */}
      {cancelandoId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-sm p-6">
            <h2 className="font-semibold text-lg mb-2">Cancelar Pedido?</h2>
            <p className="text-sm text-gray-500 mb-6">
              As reservas de estoque serão liberadas. Esta ação não pode ser desfeita.
            </p>
            <div className="flex justify-end gap-3">
              <button className="btn-secondary" onClick={() => setCancelandoId(null)}>Voltar</button>
              <button className="btn-danger" disabled={loading}
                onClick={() => cancelar(cancelandoId)}>
                {loading ? "Cancelando..." : "Cancelar Pedido"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
