"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Send, CheckCircle2, ChevronDown, ChevronUp } from "lucide-react";

interface Pedido {
  id: number; numero: string; cliente_id: number; status: string;
  valor_total: number; criado_em: string; transportadora?: string;
}
interface Cliente { id: number; razao_social: string; }
interface PedidoExpedido { id: number; numero: string; cliente_id: number; valor_total: number; criado_em: string; }

export default function ExpedicaoPage() {
  const [prontos, setProntos] = useState<Pedido[]>([]);
  const [expedidos, setExpedidos] = useState<PedidoExpedido[]>([]);
  const [clientes, setClientes] = useState<Record<number, string>>({});
  const [expandido, setExpandido] = useState<number | null>(null);
  const [forms, setForms] = useState<Record<number, { transportadora: string; numero_nf: string; observacoes: string }>>({});
  const [expedindo, setExpedindo] = useState<number | null>(null);
  const [erro, setErro] = useState("");

  async function carregar() {
    const [r1, r2, rc] = await Promise.all([
      api.get("/vendas/", { params: { status: "PICKING_OK", limit: 50 } }),
      api.get("/vendas/", { params: { status: "EXPEDIDO", limit: 30 } }),
      api.get("/parceiros/clientes/", { params: { limit: 200 } }),
    ]);
    setProntos(r1.data);
    setExpedidos(r2.data);
    const mapa: Record<number, string> = {};
    for (const c of rc.data as Cliente[]) mapa[c.id] = c.razao_social;
    setClientes(mapa);
  }

  useEffect(() => { carregar(); }, []);

  function toggleExpand(id: number) {
    setExpandido(expandido === id ? null : id);
    if (!forms[id]) {
      setForms(f => ({ ...f, [id]: { transportadora: "", numero_nf: "", observacoes: "" } }));
    }
  }

  function updateForm(id: number, field: string, value: string) {
    setForms(f => ({ ...f, [id]: { ...f[id], [field]: value } }));
  }

  async function expedir(pedidoId: number) {
    setExpedindo(pedidoId); setErro("");
    try {
      await api.post(`/expedicao/${pedidoId}/expedir`, forms[pedidoId] || {});
      await carregar();
      setExpandido(null);
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao expedir pedido");
    } finally {
      setExpedindo(null);
    }
  }

  const moeda = (v: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Send size={22} /> Expedição
        </h1>
        <button onClick={carregar} className="btn-secondary text-sm">Atualizar</button>
      </div>

      {erro && <p className="text-sm text-danger bg-danger-tint p-3 rounded mb-4">{erro}</p>}

      {/* Prontos para expedir */}
      <div className="mb-8">
        <h2 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
          Prontos para Expedir
          {prontos.length > 0 && (
            <span className="bg-success-subtle text-success-dark text-xs font-bold px-2 py-0.5 rounded-full">{prontos.length}</span>
          )}
        </h2>
        {prontos.length === 0 ? (
          <div className="card p-8 text-center text-gray-400">
            <CheckCircle2 size={32} className="mx-auto mb-2 text-gray-300" />
            <p>Nenhum pedido pronto para expedição.</p>
            <p className="text-sm mt-1">Pedidos concluídos na separação aparecerão aqui.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {prontos.map(p => {
              const form = forms[p.id] || { transportadora: "", numero_nf: "", observacoes: "" };
              const isExpanded = expandido === p.id;
              return (
                <div key={p.id} className="border border-gray-200 rounded-lg overflow-hidden">
                  <div
                    className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50"
                    onClick={() => toggleExpand(p.id)}
                  >
                    <div>
                      <span className="font-mono font-semibold text-gray-800">{p.numero}</span>
                      <span className="text-gray-500 ml-3">{clientes[p.cliente_id] || "—"}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="font-semibold text-gray-700">{moeda(p.valor_total)}</span>
                      <span className="text-xs text-gray-400">{new Date(p.criado_em).toLocaleDateString("pt-BR")}</span>
                      {isExpanded ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="border-t bg-gray-50 p-4">
                      <div className="grid grid-cols-2 gap-3 mb-3">
                        <div>
                          <label className="label">Transportadora</label>
                          <input className="input" value={form.transportadora}
                            onChange={e => updateForm(p.id, "transportadora", e.target.value)}
                            placeholder="Nome da transportadora" />
                        </div>
                        <div>
                          <label className="label">Número da NF (opcional)</label>
                          <input className="input" value={form.numero_nf}
                            onChange={e => updateForm(p.id, "numero_nf", e.target.value)}
                            placeholder="000001" />
                        </div>
                        <div className="col-span-2">
                          <label className="label">Observações</label>
                          <input className="input" value={form.observacoes}
                            onChange={e => updateForm(p.id, "observacoes", e.target.value)}
                            placeholder="Observações da expedição..." />
                        </div>
                      </div>
                      <div className="flex justify-end">
                        <button
                          onClick={() => expedir(p.id)}
                          disabled={expedindo === p.id}
                          className="btn-primary flex items-center gap-2"
                        >
                          <Send size={14} />
                          {expedindo === p.id ? "Expedindo..." : "Confirmar Expedição"}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Histórico */}
      {expedidos.length > 0 && (
        <div className="card">
          <div className="p-4 border-b">
            <h2 className="font-semibold text-gray-700 text-sm">Expedidos Recentemente</h2>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-gray-500 font-medium">Pedido</th>
                <th className="px-4 py-2 text-left text-gray-500 font-medium">Cliente</th>
                <th className="px-4 py-2 text-right text-gray-500 font-medium">Valor</th>
                <th className="px-4 py-2 text-left text-gray-500 font-medium">Data</th>
              </tr>
            </thead>
            <tbody>
              {expedidos.map(p => (
                <tr key={p.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-xs">{p.numero}</td>
                  <td className="px-4 py-2 text-gray-600">{clientes[p.cliente_id] || "—"}</td>
                  <td className="px-4 py-2 text-right font-semibold">{moeda(p.valor_total)}</td>
                  <td className="px-4 py-2 text-gray-500">{new Date(p.criado_em).toLocaleDateString("pt-BR")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
