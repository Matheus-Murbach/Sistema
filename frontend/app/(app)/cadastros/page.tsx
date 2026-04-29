"use client";
import { Package, Users, Truck, Wrench } from "lucide-react";

const secoes = [
  {
    href: "/cadastros/produtos",
    icon: Package,
    titulo: "Produtos",
    descricao: "Matérias-primas, produtos acabados e itens de revenda",
    cor: "bg-amber-500",
  },
  {
    href: "/cadastros/clientes",
    icon: Users,
    titulo: "Clientes",
    descricao: "Clientes pessoa física e jurídica",
    cor: "bg-green-600",
  },
  {
    href: "/cadastros/fornecedores",
    icon: Truck,
    titulo: "Fornecedores",
    descricao: "Fornecedores de matéria-prima e itens de revenda",
    cor: "bg-orange-500",
  },
  {
    href: "/cadastros/prestadores",
    icon: Wrench,
    titulo: "Prestadores de Beneficiamento",
    descricao: "Empresas que realizam banho (galvanização, niquelação, zinco)",
    cor: "bg-purple-600",
  },
];

export default function CadastrosPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Cadastros</h1>
      <p className="text-sm text-gray-500 mb-8">Gerencie produtos, clientes, fornecedores e prestadores de serviço.</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {secoes.map((s) => (
          <a
            key={s.href}
            href={s.href}
            className="card p-6 flex items-start gap-4 hover:shadow-md transition-shadow cursor-pointer"
          >
            <div className={`p-3 rounded-lg ${s.cor}`}>
              <s.icon size={22} className="text-white" />
            </div>
            <div>
              <h2 className="font-semibold text-gray-900">{s.titulo}</h2>
              <p className="text-sm text-gray-500 mt-1">{s.descricao}</p>
            </div>
          </a>
        ))}
      </div>
    </div>
  );
}
