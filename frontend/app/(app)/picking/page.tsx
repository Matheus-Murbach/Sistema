"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Play, CheckCircle2, Clock, Package } from "lucide-react";

interface Pedido {
  id: number; numero: string; cliente_id: number; status: string;
  valor_total: number; criado_em: string;
  itens?: { produto_id: number; quantidade: number; }[];
}
interface Cliente { id: number; razao_social: string; }

export default function PickingPage() {
  const [paraIniciar, setParaIniciar] = useState<Pedido[]>([]);
  const [emAndamento, setEmAndamento] = useState<Pedido[]>([]);
  const [prontos, setProntos] = useState<Pedido[]>([]);
  const [clientes, setClientes] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(true);
  const [processando, setProcessando] = useState<number | null>(null);
  const [erro, setErro] = useState("");

  async function carregar() {
    setLoading(true);
    try {
      const [r1, r2, r3, rc] = await Promise.all([
        api.get("/vendas/", { params: { status: "CONFIRMADO", limit: 50 } }),
        api.get("/vendas/", { params: { status: "EM_PICKING", limit: 50 } }),
        api.get("/vendas/", { params: { status: "PICKING_OK", limit: 50 } }),
        api.get("/parceiros/clientes/", { params: { limit: 200 } }),
      ]);
      setParaIniciar(r1.data);
      setEmAndamento(r2.data);
      setProntos(r3.data);
      const mapa: Record<number, string> = {};
      for (const c of rc.data as Cliente[]) mapa[c.id] = c.razao_social;
      setClientes(mapa);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { carregar(); }, []);

  async function iniciarPicking(pedidoId: number) {
    setProcessando(pedidoId); setErro("");
    try {
      await api.post(`/picking/${pedidoId}/iniciar`);
      await carregar();
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao iniciar picking");
    } finally {
      setProcessando(null);
    }
  }

  async function concluirPicking(pedidoId: number) {
    setProcessando(pedidoId); setErro("");
    try {
      await api.post(`/picking/${pedidoId}/concluir`);
      await carregar();
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao concluir picking");
    } finally {
      setProcessando(null);
    }
  }

  const moeda = (v: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  const CardPedido = ({ pedido, acao }: { pedido: Pedido; acao?: React.ReactNode }) => (
    <div className="flex items-center justify-between p-3 border border-gray-200 rounded-lg bg-surface hover:bg-page">
      <div>
        <span className="font-mono text-sm font-semibold text-gray-800">{pedido.numero}</span>
        <span className="text-muted text-sm ml-3">{clientes[pedido.cliente_id] || "—"}</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="text-gray-600 text-sm font-medium">{moeda(pedido.valor_total)}</span>
        <span className="text-xs text-muted">{new Date(pedido.criado_em).toLocaleDateString("pt-BR")}</span>
        {acao}
      </div>
    </div>
  );

  if (loading) return <p className="text-muted p-6">Carregando...</p>;

  return (
    <div className="max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Separação de Pedidos</h1>
        <button onClick={carregar} className="btn-secondary text-sm">Atualizar</button>
      </div>

      {erro && <p className="text-sm text-danger bg-danger-tint p-3 rounded mb-4">{erro}</p>}

      {/* Para Iniciar */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Clock size={16} className="text-primary" />
          <h2 className="font-semibold text-gray-700">Para Iniciar</h2>
          {paraIniciar.length > 0 && (
            <span className="bg-primary-subtle text-primary-dark text-xs font-bold px-2 py-0.5 rounded-full">{paraIniciar.length}</span>
          )}
        </div>
        {paraIniciar.length === 0 ? (
          <p className="text-sm text-muted pl-6">Nenhum pedido aguardando separação.</p>
        ) : (
          <div className="space-y-2">
            {paraIniciar.map(p => (
              <CardPedido key={p.id} pedido={p} acao={
                <button
                  onClick={() => iniciarPicking(p.id)}
                  disabled={processando === p.id}
                  className="btn-primary text-xs flex items-center gap-1 py-1.5"
                >
                  <Play size={12} /> {processando === p.id ? "..." : "Iniciar"}
                </button>
              } />
            ))}
          </div>
        )}
      </div>

      {/* Em Andamento */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Package size={16} className="text-warning" />
          <h2 className="font-semibold text-gray-700">Em Andamento</h2>
          {emAndamento.length > 0 && (
            <span className="bg-warning-subtle text-warning-dark text-xs font-bold px-2 py-0.5 rounded-full">{emAndamento.length}</span>
          )}
        </div>
        {emAndamento.length === 0 ? (
          <p className="text-sm text-muted pl-6">Nenhum pedido em separação.</p>
        ) : (
          <div className="space-y-2">
            {emAndamento.map(p => (
              <div key={p.id} className="border border-warning-subtle bg-warning-tint rounded-lg p-3 flex items-center justify-between">
                <div>
                  <span className="font-mono text-sm font-semibold text-gray-800">{p.numero}</span>
                  <span className="text-muted text-sm ml-3">{clientes[p.cliente_id] || "—"}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-gray-600 text-sm font-medium">{moeda(p.valor_total)}</span>
                  <button
                    onClick={() => concluirPicking(p.id)}
                    disabled={processando === p.id}
                    className="text-xs px-3 py-1.5 rounded-md bg-success text-white hover:bg-success-dark flex items-center gap-1"
                  >
                    <CheckCircle2 size={12} /> {processando === p.id ? "..." : "Concluir"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Prontos na Fábrica */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <CheckCircle2 size={16} className="text-success" />
          <h2 className="font-semibold text-gray-700">Prontos / Na Fábrica</h2>
          {prontos.length > 0 && (
            <span className="bg-success-subtle text-success-dark text-xs font-bold px-2 py-0.5 rounded-full">{prontos.length}</span>
          )}
        </div>
        {prontos.length === 0 ? (
          <p className="text-sm text-muted pl-6">Nenhum pedido aguardando expedição.</p>
        ) : (
          <div className="space-y-2">
            {prontos.map(p => (
              <div key={p.id} className="border border-success-subtle bg-success-tint rounded-lg p-3 flex items-center justify-between">
                <div>
                  <span className="font-mono text-sm font-semibold text-gray-800">{p.numero}</span>
                  <span className="text-muted text-sm ml-3">{clientes[p.cliente_id] || "—"}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-gray-600 text-sm font-medium">{moeda(p.valor_total)}</span>
                  <span className="text-xs text-success-dark bg-success-subtle px-2 py-0.5 rounded-full font-medium">Aguardando expedição</span>
                  <a href="/expedicao" className="text-xs text-primary hover:underline">Expedir →</a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
