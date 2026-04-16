"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { ClipboardCheck, ArrowRight } from "lucide-react";

interface PedidoVenda {
  id: number;
  numero: string;
  cliente_id: number;
  status: string;
  valor_total: number;
  data_emissao: string;
  data_previsao_entrega: string | null;
}

interface Cliente { id: number; razao_social: string; }

const STATUS_BADGE: Record<string, string> = {
  CONFIRMADO: "badge-blue",
  EM_PICKING: "badge-yellow",
};

const STATUS_LABEL: Record<string, string> = {
  CONFIRMADO: "Aguardando Picking",
  EM_PICKING: "Em Picking",
};

export default function PickingLandingPage() {
  const [pedidos, setPedidos] = useState<PedidoVenda[]>([]);
  const [clientes, setClientes] = useState<Cliente[]>([]);

  useEffect(() => {
    Promise.all([
      api.get("/vendas/", { params: { status: "CONFIRMADO", limit: 50 } }),
      api.get("/vendas/", { params: { status: "EM_PICKING", limit: 50 } }),
    ]).then(([r1, r2]) => {
      // EM_PICKING first (in progress), then CONFIRMADO (waiting)
      setPedidos([...r2.data, ...r1.data]);
    });
    api.get("/clientes/", { params: { limit: 200 } }).then((r) => setClientes(r.data));
  }, []);

  function nomeCliente(id: number) {
    return clientes.find((c) => c.id === id)?.razao_social || `Cliente #${id}`;
  }

  const moeda = (v: number) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  const emPicking = pedidos.filter((p) => p.status === "EM_PICKING");
  const aguardando = pedidos.filter((p) => p.status === "CONFIRMADO");

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Picking</h1>
          <p className="text-sm text-gray-500 mt-1">
            Selecione um pedido para iniciar ou continuar a separação.
          </p>
        </div>
        {emPicking.length > 0 && (
          <span className="badge-yellow">{emPicking.length} em andamento</span>
        )}
      </div>

      {pedidos.length === 0 && (
        <div className="card p-12 text-center">
          <ClipboardCheck size={40} className="text-gray-300 mx-auto mb-3" />
          <p className="text-gray-400 font-medium">Nenhum pedido aguardando picking</p>
          <p className="text-sm text-gray-400 mt-1">
            Confirme um pedido em{" "}
            <a href="/vendas" className="text-blue-600 hover:underline">Vendas</a>{" "}
            para que ele apareça aqui.
          </p>
        </div>
      )}

      {emPicking.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Em Andamento
          </h2>
          <div className="space-y-2">
            {emPicking.map((p) => (
              <a
                key={p.id}
                href={`/picking/${p.id}`}
                className="card p-4 flex items-center gap-4 hover:shadow-md transition-shadow cursor-pointer border-l-4 border-yellow-400"
              >
                <ClipboardCheck size={20} className="text-yellow-500 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-gray-700">{p.numero}</span>
                    <span className={STATUS_BADGE[p.status]}>{STATUS_LABEL[p.status]}</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-0.5 truncate">{nomeCliente(p.cliente_id)}</p>
                </div>
                <div className="text-right flex-shrink-0">
                  <p className="font-medium text-gray-900">{moeda(Number(p.valor_total))}</p>
                  {p.data_previsao_entrega && (
                    <p className="text-xs text-gray-400 mt-0.5">
                      Entrega: {new Date(p.data_previsao_entrega).toLocaleDateString("pt-BR")}
                    </p>
                  )}
                </div>
                <ArrowRight size={16} className="text-gray-400 flex-shrink-0" />
              </a>
            ))}
          </div>
        </div>
      )}

      {aguardando.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Aguardando Separação
          </h2>
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="text-left p-3 font-medium text-gray-600">Pedido</th>
                  <th className="text-left p-3 font-medium text-gray-600">Cliente</th>
                  <th className="text-left p-3 font-medium text-gray-600">Emissão</th>
                  <th className="text-left p-3 font-medium text-gray-600">Entrega</th>
                  <th className="text-right p-3 font-medium text-gray-600">Total</th>
                  <th className="p-3"></th>
                </tr>
              </thead>
              <tbody>
                {aguardando.map((p) => (
                  <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
                    <td className="p-3 font-mono text-xs font-bold">{p.numero}</td>
                    <td className="p-3">{nomeCliente(p.cliente_id)}</td>
                    <td className="p-3 text-gray-500">
                      {new Date(p.data_emissao).toLocaleDateString("pt-BR")}
                    </td>
                    <td className="p-3 text-gray-500">
                      {p.data_previsao_entrega
                        ? new Date(p.data_previsao_entrega).toLocaleDateString("pt-BR")
                        : "—"}
                    </td>
                    <td className="p-3 text-right font-medium">
                      {moeda(Number(p.valor_total))}
                    </td>
                    <td className="p-3 text-right">
                      <a
                        href={`/picking/${p.id}`}
                        className="btn-primary text-xs py-1 px-3 inline-flex items-center gap-1"
                      >
                        <ClipboardCheck size={12} /> Iniciar
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
