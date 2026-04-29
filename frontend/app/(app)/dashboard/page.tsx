"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { AlertTriangle, Factory, ShoppingCart, Truck, Clock } from "lucide-react";

interface Resumo {
  ops_abertas: number;
  pedidos_pendentes_expedicao: number;
  lotes_no_banho: number;
  lotes_banho_atrasados: number;
  vendas_mes: number;
  data: string;
}

function StatCard({ title, value, icon: Icon, color, alert }: {
  title: string; value: number | string; icon: any; color: string; alert?: boolean;
}) {
  return (
    <div className={`card p-5 flex items-start gap-4 ${alert ? "border-l-4 border-red-500" : ""}`}>
      <div className={`p-2 rounded-lg ${color}`}>
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <p className="text-sm text-gray-500">{title}</p>
        <p className="text-2xl font-bold mt-0.5">{value}</p>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const [resumo, setResumo] = useState<Resumo | null>(null);

  useEffect(() => {
    api.get("/dashboard/resumo").then((r) => setResumo(r.data));
  }, []);

  if (!resumo) return <div className="text-gray-400">Carregando...</div>;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
      <p className="text-sm text-gray-400 mb-6">
        {new Date(resumo.data).toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" })}
      </p>

      <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        <StatCard
          title="OPs em andamento"
          value={resumo.ops_abertas}
          icon={Factory}
          color="bg-primary"
        />
        <StatCard
          title="Pedidos p/ expedir"
          value={resumo.pedidos_pendentes_expedicao}
          icon={Truck}
          color="bg-orange-500"
          alert={resumo.pedidos_pendentes_expedicao > 5}
        />
        <StatCard
          title="Lotes no banho"
          value={resumo.lotes_no_banho}
          icon={Clock}
          color="bg-purple-600"
        />
        <StatCard
          title="Banhos atrasados"
          value={resumo.lotes_banho_atrasados}
          icon={AlertTriangle}
          color="bg-red-600"
          alert={resumo.lotes_banho_atrasados > 0}
        />
        <StatCard
          title="Vendas do mês"
          value={new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(resumo.vendas_mes)}
          icon={ShoppingCart}
          color="bg-green-600"
        />
      </div>

      {resumo.lotes_banho_atrasados > 0 && (
        <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
          <AlertTriangle size={18} className="text-red-600 flex-shrink-0" />
          <p className="text-sm text-red-700">
            <strong>{resumo.lotes_banho_atrasados}</strong> lote(s) de beneficiamento com prazo de retorno vencido.{" "}
            <a href="/beneficiamento" className="underline font-medium">Ver lotes</a>
          </p>
        </div>
      )}
    </div>
  );
}
