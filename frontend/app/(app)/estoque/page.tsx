"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Package, AlertTriangle, Search } from "lucide-react";

interface ProntaEntrega {
  produto_id: number;
  codigo: string;
  descricao: string;
  quantidade_disponivel: number;
}

interface Alerta {
  produto_id: number;
  codigo: string;
  descricao: string;
  estoque_minimo: number;
  estoque_atual: number;
  deficit: number;
}

export default function EstoquePage() {
  const [prontaEntrega, setProntaEntrega] = useState<ProntaEntrega[]>([]);
  const [alertas, setAlertas] = useState<Alerta[]>([]);
  const [busca, setBusca] = useState("");
  const [tab, setTab] = useState<"pronta" | "alertas">("pronta");

  useEffect(() => {
    api.get("/estoque/pronta-entrega", { params: { q: busca || undefined } })
      .then((r) => setProntaEntrega(r.data));
    api.get("/estoque/alertas-estoque-minimo")
      .then((r) => setAlertas(r.data));
  }, [busca]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Estoque</h1>
        {alertas.length > 0 && (
          <span className="badge-red gap-1">
            <AlertTriangle size={12} />
            {alertas.length} alerta{alertas.length > 1 ? "s" : ""} de estoque mínimo
          </span>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-4 border-b">
        {(["pronta", "alertas"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t ? "border-primary-hover text-primary-dark" : "border-transparent text-muted hover:text-gray-700"
            }`}
          >
            {t === "pronta" ? `Pronta Entrega (${prontaEntrega.length})` : `Alertas (${alertas.length})`}
          </button>
        ))}
      </div>

      {tab === "pronta" && (
        <>
          <div className="relative mb-4">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
            <input
              className="input pl-9"
              placeholder="Buscar por código ou descrição..."
              value={busca}
              onChange={(e) => setBusca(e.target.value)}
            />
          </div>
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-page border-b">
                <tr>
                  <th className="text-left p-3 font-medium text-gray-600">Código</th>
                  <th className="text-left p-3 font-medium text-gray-600">Descrição</th>
                  <th className="text-right p-3 font-medium text-gray-600">Disponível</th>
                </tr>
              </thead>
              <tbody>
                {prontaEntrega.map((item) => (
                  <tr key={item.produto_id} className="border-b last:border-0 hover:bg-page">
                    <td className="p-3 font-mono text-xs">{item.codigo}</td>
                    <td className="p-3">{item.descricao}</td>
                    <td className="p-3 text-right font-bold text-success-dark">
                      {Number(item.quantidade_disponivel).toLocaleString("pt-BR")}
                    </td>
                  </tr>
                ))}
                {prontaEntrega.length === 0 && (
                  <tr><td colSpan={3} className="p-8 text-center text-muted">Nenhum item disponível</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === "alertas" && (
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-page border-b">
              <tr>
                <th className="text-left p-3 font-medium text-gray-600">Código</th>
                <th className="text-left p-3 font-medium text-gray-600">Descrição</th>
                <th className="text-right p-3 font-medium text-gray-600">Atual</th>
                <th className="text-right p-3 font-medium text-gray-600">Mínimo</th>
                <th className="text-right p-3 font-medium text-gray-600">Déficit</th>
              </tr>
            </thead>
            <tbody>
              {alertas.map((a) => (
                <tr key={a.produto_id} className="border-b last:border-0 hover:bg-page">
                  <td className="p-3 font-mono text-xs">{a.codigo}</td>
                  <td className="p-3">{a.descricao}</td>
                  <td className="p-3 text-right text-danger font-bold">{a.estoque_atual}</td>
                  <td className="p-3 text-right text-muted">{a.estoque_minimo}</td>
                  <td className="p-3 text-right text-danger-dark font-bold">-{a.deficit}</td>
                </tr>
              ))}
              {alertas.length === 0 && (
                <tr><td colSpan={5} className="p-8 text-center text-muted">
                  Nenhum alerta de estoque mínimo
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
