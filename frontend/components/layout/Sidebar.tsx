"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard, Package, Truck, Wrench, BarChart3, ShoppingCart,
  ClipboardCheck, Send, Users, Settings, Factory, ArrowDownToLine, TrendingUp,
} from "lucide-react";
import { clsx } from "clsx";

const nav = [
  { href: "/dashboard",       label: "Dashboard",         icon: LayoutDashboard },
  { href: "/recebimento",     label: "Recebimento",        icon: ArrowDownToLine },
  { href: "/beneficiamento",  label: "Beneficiamento",     icon: Wrench },
  { href: "/producao",        label: "PCP - Produção",     icon: Factory },
  { href: "/estoque",         label: "Estoque",            icon: Package },
  { href: "/compras",         label: "Compras",            icon: ShoppingCart },
  { href: "/vendas",          label: "Vendas",             icon: BarChart3 },
  { href: "/picking",         label: "Picking",            icon: ClipboardCheck },
  { href: "/expedicao",       label: "Expedição Saída",    icon: Send },
  { href: "/fiscal",          label: "Dashboard Fiscal",   icon: TrendingUp },
  { href: "/cadastros",       label: "Cadastros",          icon: Users },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-60 min-h-screen bg-gray-900 text-gray-300 flex flex-col">
      <div className="px-4 py-5 border-b border-gray-700">
        <h1 className="text-white font-bold text-lg">Sistema ERP</h1>
        <p className="text-xs text-gray-400 mt-0.5">Industrial</p>
      </div>
      <nav className="flex-1 py-4">
        {nav.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={clsx(
              "flex items-center gap-3 px-4 py-2.5 text-sm transition-colors hover:bg-gray-700 hover:text-white",
              pathname.startsWith(href) && "bg-amber-600 text-white"
            )}
          >
            <Icon size={16} />
            {label}
          </Link>
        ))}
      </nav>
      <div className="px-4 py-3 border-t border-gray-700">
        <Link href="/configuracoes" className="flex items-center gap-2 text-xs text-gray-400 hover:text-white">
          <Settings size={14} />
          Configurações
        </Link>
      </div>
    </aside>
  );
}
