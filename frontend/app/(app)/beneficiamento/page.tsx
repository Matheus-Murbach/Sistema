"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Clock, AlertTriangle, CheckCircle2 } from "lucide-react";

interface Lote {
  id: number;
  numero: string;
  tipo_beneficiamento: string;
  data_remessa: string;
  data_previsao_retorno: string | null;
  status: string;
}

const STATUS_BADGE: Record<string, string> = {
  ABERTO: "badge-gray",
  ENVIADO: "badge-blue",
  AGUARDANDO_RETORNO: "badge-yellow",
  RETORNADO_PARCIAL: "badge-yellow",
  RETORNADO: "badge-green",
  CANCELADO: "badge-red",
};

export default function BeneficiamentoPage() {
  const [lotes, setLotes] = useState<Lote[]>([]);
  const [filtro, setFiltro] = useState("em-transito");

  useEffect(() => {
    const endpoint = filtro === "em-transito"
      ? "/beneficiamento/em-transito"
      : `/beneficiamento/?status=${filtro}`;
    api.get(endpoint).then((r) => setLotes(Array.isArray(r.data) ? r.data : []));
  }, [filtro]);

  const hoje = new Date();

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Beneficiamento Externo (Banho)</h1>
        <a href="/beneficiamento/novo" className="btn-primary">+ Novo Lote</a>
      </div>

      {/* Filtros */}
      <div className="flex gap-2 mb-4">
        {["em-transito", "RETORNADO"].map((f) => (
          <button
            key={f}
            onClick={() => setFiltro(f)}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              filtro === f ? "bg-primary-hover text-white" : "bg-surface border text-gray-600 hover:bg-page"
            }`}
          >
            {f === "em-transito" ? "Em Trânsito" : "Retornados"}
          </button>
        ))}
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-page border-b">
            <tr>
              <th className="text-left p-3 font-medium text-gray-600">Lote</th>
              <th className="text-left p-3 font-medium text-gray-600">Tipo</th>
              <th className="text-left p-3 font-medium text-gray-600">Data Envio</th>
              <th className="text-left p-3 font-medium text-gray-600">Previsão Retorno</th>
              <th className="text-left p-3 font-medium text-gray-600">Status</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {lotes.map((lote) => {
              const previsao = lote.data_previsao_retorno ? new Date(lote.data_previsao_retorno) : null;
              const atrasado = previsao && previsao < hoje && lote.status !== "RETORNADO";
              return (
                <tr key={lote.id} className="border-b last:border-0 hover:bg-page">
                  <td className="p-3 font-mono text-xs font-bold">{lote.numero}</td>
                  <td className="p-3">{lote.tipo_beneficiamento || "—"}</td>
                  <td className="p-3">{new Date(lote.data_remessa).toLocaleDateString("pt-BR")}</td>
                  <td className="p-3">
                    {previsao ? (
                      <span className={`flex items-center gap-1 ${atrasado ? "text-danger font-bold" : ""}`}>
                        {atrasado && <AlertTriangle size={12} />}
                        {previsao.toLocaleDateString("pt-BR")}
                        {atrasado && " (atrasado)"}
                      </span>
                    ) : "—"}
                  </td>
                  <td className="p-3">
                    <span className={STATUS_BADGE[lote.status] || "badge-gray"}>{lote.status}</span>
                  </td>
                  <td className="p-3 text-right">
                    <a href={`/beneficiamento/${lote.id}`} className="text-primary text-xs hover:underline">
                      Detalhes
                    </a>
                    {lote.status === "ENVIADO" && (
                      <a href={`/beneficiamento/${lote.id}/retorno`} className="text-success text-xs hover:underline ml-3">
                        Registrar Retorno
                      </a>
                    )}
                  </td>
                </tr>
              );
            })}
            {lotes.length === 0 && (
              <tr><td colSpan={6} className="p-8 text-center text-muted">
                Nenhum lote encontrado
              </td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
