"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import api from "@/lib/api";
import { ChevronLeft, AlertTriangle } from "lucide-react";

interface ItemLote {
  id: number;
  produto_enviado_id: number;
  produto_retorno_id: number | null;
  quantidade_enviada: number;
  quantidade_retornada: number | null;
  quantidade_rejeitada: number | null;
  retornado: boolean;
}

interface Lote {
  id: number;
  numero: string;
  prestador_id: number;
  tipo_beneficiamento: string | null;
  data_remessa: string;
  data_previsao_retorno: string | null;
  data_retorno_real: string | null;
  cfop_remessa: string;
  cfop_retorno: string;
  status: string;
  valor_servico: number | null;
  valor_insumos: number | null;
  nf_retorno_numero: string | null;
  observacoes: string | null;
  itens: ItemLote[];
}

interface Produto { id: number; codigo: string; descricao: string; }
interface Prestador { id: number; razao_social: string; }

const STATUS_BADGE: Record<string, string> = {
  ABERTO: "badge-gray",
  ENVIADO: "badge-blue",
  AGUARDANDO_RETORNO: "badge-yellow",
  RETORNADO_PARCIAL: "badge-yellow",
  RETORNADO: "badge-green",
  CANCELADO: "badge-red",
};

const STATUS_LABEL: Record<string, string> = {
  ABERTO: "Aberto",
  ENVIADO: "Enviado",
  AGUARDANDO_RETORNO: "Aguardando Retorno",
  RETORNADO_PARCIAL: "Retorno Parcial",
  RETORNADO: "Retornado",
  CANCELADO: "Cancelado",
};

export default function DetalheLotePage() {
  const { id } = useParams<{ id: string }>();
  const [lote, setLote] = useState<Lote | null>(null);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [prestadores, setPrestadores] = useState<Prestador[]>([]);

  useEffect(() => {
    api.get(`/beneficiamento/${id}`).then((r) => setLote(r.data));
    api.get("/produtos/", { params: { limit: 200 } }).then((r) => setProdutos(r.data));
    api.get("/parceiros/prestadores/", { params: { limit: 200 } }).then((r) => setPrestadores(r.data));
  }, [id]);

  function nomeProduto(pid: number) {
    const p = produtos.find((p) => p.id === pid);
    return p ? `${p.codigo} — ${p.descricao}` : `Produto #${pid}`;
  }

  function nomePrestador(pid: number) {
    return prestadores.find((p) => p.id === pid)?.razao_social || `Prestador #${pid}`;
  }

  if (!lote) return <div className="text-gray-400">Carregando...</div>;

  const hoje = new Date();
  const previsao = lote.data_previsao_retorno ? new Date(lote.data_previsao_retorno) : null;
  const atrasado = previsao && previsao < hoje && !["RETORNADO", "CANCELADO"].includes(lote.status);

  const totalEnviado = lote.itens?.reduce((a, it) => a + Number(it.quantidade_enviada), 0) ?? 0;
  const totalRetornado = lote.itens?.reduce((a, it) => a + Number(it.quantidade_retornada ?? 0), 0) ?? 0;
  const totalRejeitado = lote.itens?.reduce((a, it) => a + Number(it.quantidade_rejeitada ?? 0), 0) ?? 0;
  const pctRetorno = totalEnviado > 0 ? ((totalRetornado / totalEnviado) * 100).toFixed(1) : "—";

  const moeda = (v: number) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  const podRetornar = ["ENVIADO", "AGUARDANDO_RETORNO", "RETORNADO_PARCIAL"].includes(lote.status);

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <a href="/beneficiamento" className="text-gray-400 hover:text-gray-600">
          <ChevronLeft size={20} />
        </a>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{lote.numero}</h1>
          <p className="text-sm text-gray-500 mt-0.5">{nomePrestador(lote.prestador_id)}</p>
        </div>
        <span className={STATUS_BADGE[lote.status] || "badge-gray"}>
          {STATUS_LABEL[lote.status] || lote.status}
        </span>
      </div>

      {atrasado && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
          <AlertTriangle size={16} className="text-red-600 flex-shrink-0" />
          <p className="text-sm text-red-700">
            Lote com retorno atrasado desde{" "}
            <strong>{previsao!.toLocaleDateString("pt-BR")}</strong>.
          </p>
        </div>
      )}

      {/* Cards de resumo */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="card p-4 text-center">
          <p className="text-xs text-gray-500 mb-1">Enviado</p>
          <p className="text-2xl font-bold text-gray-900">{totalEnviado.toLocaleString("pt-BR")}</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-xs text-gray-500 mb-1">Retornado</p>
          <p className="text-2xl font-bold text-green-700">{totalRetornado.toLocaleString("pt-BR")}</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-xs text-gray-500 mb-1">Rejeitado</p>
          <p className="text-2xl font-bold text-red-600">{totalRejeitado.toLocaleString("pt-BR")}</p>
        </div>
      </div>

      {/* Informações gerais */}
      <div className="card p-6 mb-6 grid grid-cols-2 gap-4 text-sm">
        <div>
          <p className="text-gray-500">Tipo de Beneficiamento</p>
          <p className="font-medium">{lote.tipo_beneficiamento || "—"}</p>
        </div>
        <div>
          <p className="text-gray-500">Data de Remessa</p>
          <p className="font-medium">{new Date(lote.data_remessa).toLocaleDateString("pt-BR")}</p>
        </div>
        <div>
          <p className="text-gray-500">Previsão de Retorno</p>
          <p className={`font-medium ${atrasado ? "text-red-600" : ""}`}>
            {previsao ? previsao.toLocaleDateString("pt-BR") : "—"}
          </p>
        </div>
        <div>
          <p className="text-gray-500">Retorno Real</p>
          <p className="font-medium">
            {lote.data_retorno_real
              ? new Date(lote.data_retorno_real).toLocaleDateString("pt-BR")
              : "—"}
          </p>
        </div>
        <div>
          <p className="text-gray-500">CFOP Remessa / Retorno</p>
          <p className="font-mono font-medium">{lote.cfop_remessa} / {lote.cfop_retorno}</p>
        </div>
        <div>
          <p className="text-gray-500">NF de Retorno</p>
          <p className="font-medium">{lote.nf_retorno_numero || "—"}</p>
        </div>
        {lote.valor_servico != null && (
          <div>
            <p className="text-gray-500">Valor do Serviço</p>
            <p className="font-medium">{moeda(Number(lote.valor_servico))}</p>
          </div>
        )}
        {lote.valor_insumos != null && Number(lote.valor_insumos) > 0 && (
          <div>
            <p className="text-gray-500">Valor dos Insumos</p>
            <p className="font-medium">{moeda(Number(lote.valor_insumos))}</p>
          </div>
        )}
        {lote.observacoes && (
          <div className="col-span-2">
            <p className="text-gray-500">Observações</p>
            <p className="font-medium">{lote.observacoes}</p>
          </div>
        )}
      </div>

      {/* Itens */}
      <div className="card overflow-hidden mb-6">
        <div className="p-4 border-b bg-gray-50 flex items-center justify-between">
          <h2 className="font-semibold text-gray-700">Itens do Lote</h2>
          {totalEnviado > 0 && (
            <span className="text-xs text-gray-500">
              Retorno: {pctRetorno}%
            </span>
          )}
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3 font-medium text-gray-600">Produto Enviado</th>
              <th className="text-left p-3 font-medium text-gray-600">Produto Retorno</th>
              <th className="text-right p-3 font-medium text-gray-600">Enviado</th>
              <th className="text-right p-3 font-medium text-gray-600">Retornado</th>
              <th className="text-right p-3 font-medium text-gray-600">Rejeitado</th>
              <th className="text-left p-3 font-medium text-gray-600">Status</th>
            </tr>
          </thead>
          <tbody>
            {(lote.itens ?? []).map((item) => (
              <tr key={item.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3">{nomeProduto(item.produto_enviado_id)}</td>
                <td className="p-3 text-gray-500">
                  {item.produto_retorno_id ? nomeProduto(item.produto_retorno_id) : "Mesmo produto"}
                </td>
                <td className="p-3 text-right">{Number(item.quantidade_enviada).toLocaleString("pt-BR")}</td>
                <td className="p-3 text-right text-green-700">
                  {item.quantidade_retornada != null
                    ? Number(item.quantidade_retornada).toLocaleString("pt-BR")
                    : "—"}
                </td>
                <td className="p-3 text-right text-red-600">
                  {item.quantidade_rejeitada != null && Number(item.quantidade_rejeitada) > 0
                    ? Number(item.quantidade_rejeitada).toLocaleString("pt-BR")
                    : "—"}
                </td>
                <td className="p-3">
                  {item.retornado ? (
                    <span className="badge-green">Retornado</span>
                  ) : (
                    <span className="badge-yellow">Pendente</span>
                  )}
                </td>
              </tr>
            ))}
            {(!lote.itens || lote.itens.length === 0) && (
              <tr>
                <td colSpan={6} className="p-6 text-center text-gray-400">Sem itens</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {podRetornar && (
        <div className="flex justify-end">
          <a href={`/beneficiamento/${lote.id}/retorno`} className="btn-primary">
            Registrar Retorno
          </a>
        </div>
      )}
    </div>
  );
}
