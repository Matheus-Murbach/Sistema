"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Send, FileText, RefreshCw } from "lucide-react";

interface NFSaida {
  id: number;
  pedido_venda_id: number;
  cliente_id: number;
  numero: string | null;
  chave_acesso: string | null;
  status_sefaz: string;
  valor_total: number;
  data_emissao: string;
  focus_referencia: string | null;
}

interface PedidoVenda {
  id: number;
  numero: string;
  cliente_id: number;
  status: string;
  valor_total: number;
}

interface Cliente { id: number; razao_social: string; }

const STATUS_BADGE: Record<string, string> = {
  RASCUNHO: "badge-gray",
  AGUARDANDO: "badge-yellow",
  AUTORIZADA: "badge-green",
  REJEITADA: "badge-red",
  CANCELADA: "badge-gray",
};

const STATUS_LABEL: Record<string, string> = {
  RASCUNHO: "Rascunho",
  AGUARDANDO: "Aguardando SEFAZ",
  AUTORIZADA: "Autorizada",
  REJEITADA: "Rejeitada",
  CANCELADA: "Cancelada",
};

export default function ExpedicaoPage() {
  const [nfs, setNfs] = useState<NFSaida[]>([]);
  const [pedidosProntos, setPedidosProntos] = useState<PedidoVenda[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [tab, setTab] = useState<"prontos" | "nfs">("prontos");
  const [emitindo, setEmitindo] = useState<number | null>(null);
  const [consultando, setConsultando] = useState<number | null>(null);
  const [erro, setErro] = useState<string>("");
  const [sucesso, setSucesso] = useState<string>("");

  const fetchNfs = () => {
    api.get("/expedicao/").then((r) => setNfs(r.data));
  };

  const fetchPedidosProntos = () => {
    // Pedidos em PICKING_OK ou CONFIRMADO prontos para expedir
    Promise.all([
      api.get("/vendas/", { params: { status: "PICKING_OK" } }),
      api.get("/vendas/", { params: { status: "CONFIRMADO" } }),
    ]).then(([r1, r2]) => {
      setPedidosProntos([...r1.data, ...r2.data]);
    });
  };

  useEffect(() => {
    fetchNfs();
    fetchPedidosProntos();
    api.get("/parceiros/clientes/", { params: { limit: 200 } }).then((r) => setClientes(r.data));
  }, []);

  function nomeCliente(id: number) {
    return clientes.find((c) => c.id === id)?.razao_social || `Cliente #${id}`;
  }

  async function emitirNfe(pedidoId: number) {
    setEmitindo(pedidoId);
    setErro("");
    setSucesso("");
    try {
      const r = await api.post(`/expedicao/${pedidoId}/emitir`);
      const { status_sefaz, valor_total, resumo_fiscal } = r.data;
      setSucesso(
        `NF-e transmitida — Status: ${status_sefaz} | Total: ${moeda(valor_total)} | ICMS: ${moeda(resumo_fiscal.icms)}`
      );
      fetchNfs();
      fetchPedidosProntos();
      setTab("nfs");
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao emitir NF-e");
    } finally {
      setEmitindo(null);
    }
  }

  async function consultarStatus(nfId: number) {
    setConsultando(nfId);
    try {
      await api.get(`/expedicao/${nfId}/status`);
      fetchNfs();
    } finally {
      setConsultando(null);
    }
  }

  const moeda = (v: number) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Expedição de Saída</h1>
        {pedidosProntos.length > 0 && (
          <span className="badge-yellow">{pedidosProntos.length} pedido(s) pronto(s) para expedir</span>
        )}
      </div>

      {sucesso && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg text-sm text-green-800">
          {sucesso}
        </div>
      )}
      {erro && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {erro}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 mb-4 border-b">
        {(["prontos", "nfs"] as const).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t
                ? "border-blue-600 text-blue-700"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}>
            {t === "prontos"
              ? `Prontos para Expedir (${pedidosProntos.length})`
              : `NF-e Emitidas (${nfs.length})`}
          </button>
        ))}
      </div>

      {tab === "prontos" && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left p-3 font-medium text-gray-600">Pedido</th>
                <th className="text-left p-3 font-medium text-gray-600">Cliente</th>
                <th className="text-left p-3 font-medium text-gray-600">Status</th>
                <th className="text-right p-3 font-medium text-gray-600">Valor</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {pedidosProntos.map((p) => (
                <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="p-3 font-mono text-xs font-bold">{p.numero}</td>
                  <td className="p-3">{nomeCliente(p.cliente_id)}</td>
                  <td className="p-3">
                    <span className={p.status === "PICKING_OK" ? "badge-green" : "badge-blue"}>
                      {p.status === "PICKING_OK" ? "Picking OK" : "Confirmado"}
                    </span>
                  </td>
                  <td className="p-3 text-right font-medium">{moeda(Number(p.valor_total))}</td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => emitirNfe(p.id)}
                      disabled={emitindo === p.id}
                      className="btn-primary text-xs py-1 px-3"
                    >
                      {emitindo === p.id ? (
                        "Transmitindo..."
                      ) : (
                        <span className="flex items-center gap-1"><Send size={12} /> Emitir NF-e</span>
                      )}
                    </button>
                  </td>
                </tr>
              ))}
              {pedidosProntos.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-8 text-center text-gray-400">
                    Nenhum pedido pronto para expedição
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {tab === "nfs" && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left p-3 font-medium text-gray-600">NF-e</th>
                <th className="text-left p-3 font-medium text-gray-600">Pedido</th>
                <th className="text-left p-3 font-medium text-gray-600">Cliente</th>
                <th className="text-left p-3 font-medium text-gray-600">Emissão</th>
                <th className="text-left p-3 font-medium text-gray-600">Status SEFAZ</th>
                <th className="text-right p-3 font-medium text-gray-600">Total</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {nfs.map((nf) => (
                <tr key={nf.id} className="border-b last:border-0 hover:bg-gray-50">
                  <td className="p-3 font-mono text-xs">
                    {nf.numero ? (
                      <span className="font-bold">{nf.numero}</span>
                    ) : (
                      <span className="text-gray-400">Pendente</span>
                    )}
                  </td>
                  <td className="p-3 font-mono text-xs text-gray-500">#{nf.pedido_venda_id}</td>
                  <td className="p-3">{nomeCliente(nf.cliente_id)}</td>
                  <td className="p-3">{new Date(nf.data_emissao).toLocaleDateString("pt-BR")}</td>
                  <td className="p-3">
                    <span className={STATUS_BADGE[nf.status_sefaz] || "badge-gray"}>
                      {STATUS_LABEL[nf.status_sefaz] || nf.status_sefaz}
                    </span>
                  </td>
                  <td className="p-3 text-right font-medium">{moeda(Number(nf.valor_total))}</td>
                  <td className="p-3 text-right flex gap-2 justify-end">
                    {["AGUARDANDO", "RASCUNHO"].includes(nf.status_sefaz) && (
                      <button
                        onClick={() => consultarStatus(nf.id)}
                        disabled={consultando === nf.id}
                        className="text-blue-600 text-xs hover:underline flex items-center gap-1"
                      >
                        <RefreshCw size={11} className={consultando === nf.id ? "animate-spin" : ""} />
                        Atualizar
                      </button>
                    )}
                    {nf.status_sefaz === "AUTORIZADA" && (
                      <a
                        href={`/api/v1/expedicao/${nf.id}/danfe`}
                        target="_blank"
                        rel="noreferrer"
                        className="text-green-600 text-xs hover:underline flex items-center gap-1"
                      >
                        <FileText size={11} /> DANFE
                      </a>
                    )}
                  </td>
                </tr>
              ))}
              {nfs.length === 0 && (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-gray-400">
                    Nenhuma NF-e emitida
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
