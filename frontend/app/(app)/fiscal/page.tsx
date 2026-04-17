"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { TrendingUp, TrendingDown, DollarSign } from "lucide-react";

interface NFEntrada {
  id: number; numero_nf: string; tipo_entrada: string;
  data_entrada: string; valor_total_produtos: number;
  valor_icms_credito: number; valor_ipi_credito: number;
  valor_pis_credito: number; valor_cofins_credito: number;
}

interface NFSaida {
  id: number; status_sefaz: string; data_emissao: string;
  valor_produtos: number; valor_icms: number; valor_ipi: number;
  valor_pis: number; valor_cofins: number; valor_total: number;
}

export default function FiscalPage() {
  const [mes, setMes] = useState(new Date().toISOString().slice(0, 7));
  const [entradas, setEntradas] = useState<NFEntrada[]>([]);
  const [saidas, setSaidas] = useState<NFSaida[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.get("/recebimento/", { params: { limit: 200 } }),
      api.get("/expedicao/", { params: { limit: 200 } }),
    ]).then(([r1, r2]) => {
      setEntradas(r1.data);
      setSaidas(r2.data);
    }).finally(() => setLoading(false));
  }, []);

  // Filtra pelo mês selecionado
  const entradasMes = entradas.filter(n => n.data_entrada?.startsWith(mes));
  const saidasMes = saidas.filter(n => n.data_emissao?.startsWith(mes));

  const somaEntradas = {
    produtos: entradasMes.reduce((a, n) => a + (n.valor_total_produtos || 0), 0),
    icms: entradasMes.reduce((a, n) => a + (n.valor_icms_credito || 0), 0),
    ipi: entradasMes.reduce((a, n) => a + (n.valor_ipi_credito || 0), 0),
    pis: entradasMes.reduce((a, n) => a + (n.valor_pis_credito || 0), 0),
    cofins: entradasMes.reduce((a, n) => a + (n.valor_cofins_credito || 0), 0),
  };

  const somaSaidas = {
    produtos: saidasMes.reduce((a, n) => a + (n.valor_produtos || 0), 0),
    icms: saidasMes.reduce((a, n) => a + (n.valor_icms || 0), 0),
    ipi: saidasMes.reduce((a, n) => a + (n.valor_ipi || 0), 0),
    pis: saidasMes.reduce((a, n) => a + (n.valor_pis || 0), 0),
    cofins: saidasMes.reduce((a, n) => a + (n.valor_cofins || 0), 0),
  };

  const saldoIcms = somaEntradas.icms - somaSaidas.icms;
  const saldoIpi = somaEntradas.ipi - somaSaidas.ipi;
  const saldoPisCofins = (somaEntradas.pis + somaEntradas.cofins) - (somaSaidas.pis + somaSaidas.cofins);

  const moeda = (v: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  const CardFiscal = ({ label, credito, debito, saldo }: { label: string; credito: number; debito: number; saldo: number }) => (
    <div className="card p-4">
      <div className="text-sm text-gray-500 font-medium mb-3">{label}</div>
      <div className="flex justify-between text-sm mb-1">
        <span className="text-green-600 flex items-center gap-1"><TrendingDown size={13} /> Crédito</span>
        <span className="font-semibold text-green-700">{moeda(credito)}</span>
      </div>
      <div className="flex justify-between text-sm mb-2">
        <span className="text-red-500 flex items-center gap-1"><TrendingUp size={13} /> Débito</span>
        <span className="font-semibold text-red-600">{moeda(debito)}</span>
      </div>
      <div className="border-t pt-2 flex justify-between text-sm font-bold">
        <span className={saldo >= 0 ? "text-green-700" : "text-red-600"}>
          {saldo >= 0 ? "Saldo credor" : "Saldo devedor"}
        </span>
        <span className={saldo >= 0 ? "text-green-700" : "text-red-600"}>{moeda(Math.abs(saldo))}</span>
      </div>
    </div>
  );

  return (
    <div className="max-w-5xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <DollarSign size={24} /> Dashboard Fiscal
        </h1>
        <div className="flex items-center gap-2">
          <label className="label mb-0">Mês:</label>
          <input type="month" className="input w-40" value={mes} onChange={e => setMes(e.target.value)} />
        </div>
      </div>

      {loading ? (
        <p className="text-gray-400">Carregando...</p>
      ) : (
        <>
          {/* Cards de resumo */}
          <div className="grid grid-cols-3 gap-4 mb-6">
            <CardFiscal label="ICMS" credito={somaEntradas.icms} debito={somaSaidas.icms} saldo={saldoIcms} />
            <CardFiscal label="IPI" credito={somaEntradas.ipi} debito={somaSaidas.ipi} saldo={saldoIpi} />
            <CardFiscal label="PIS / COFINS" credito={somaEntradas.pis + somaEntradas.cofins} debito={somaSaidas.pis + somaSaidas.cofins} saldo={saldoPisCofins} />
          </div>

          {/* Resumo geral do mês */}
          <div className="grid grid-cols-2 gap-4 mb-6">
            <div className="card p-4">
              <p className="text-sm text-gray-500 mb-1">Total compras (entradas)</p>
              <p className="text-2xl font-bold text-gray-800">{moeda(somaEntradas.produtos)}</p>
              <p className="text-xs text-gray-400 mt-1">{entradasMes.length} NF(s) de entrada no mês</p>
            </div>
            <div className="card p-4">
              <p className="text-sm text-gray-500 mb-1">Total vendas expedidas (saídas)</p>
              <p className="text-2xl font-bold text-gray-800">{moeda(somaSaidas.produtos)}</p>
              <p className="text-xs text-gray-400 mt-1">{saidasMes.length} NF(s) de saída no mês</p>
            </div>
          </div>

          {/* Tabela entradas */}
          <div className="card mb-6">
            <div className="p-4 border-b">
              <h2 className="font-semibold text-gray-700 text-sm">NFs de Entrada — {mes}</h2>
            </div>
            {entradasMes.length === 0 ? (
              <p className="p-4 text-center text-gray-400 text-sm">Nenhuma NF de entrada neste mês.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-gray-500 font-medium">NF</th>
                    <th className="px-4 py-2 text-left text-gray-500 font-medium">Tipo</th>
                    <th className="px-4 py-2 text-right text-gray-500 font-medium">Produtos</th>
                    <th className="px-4 py-2 text-right text-orange-500 font-medium">ICMS Créd.</th>
                    <th className="px-4 py-2 text-right text-blue-500 font-medium">IPI Créd.</th>
                    <th className="px-4 py-2 text-right text-purple-500 font-medium">PIS/COFINS Créd.</th>
                  </tr>
                </thead>
                <tbody>
                  {entradasMes.map(n => (
                    <tr key={n.id} className="border-t hover:bg-gray-50">
                      <td className="px-4 py-2 font-mono">{n.numero_nf}</td>
                      <td className="px-4 py-2 text-gray-500 text-xs">{n.tipo_entrada.replace(/_/g, " ")}</td>
                      <td className="px-4 py-2 text-right">{moeda(n.valor_total_produtos || 0)}</td>
                      <td className="px-4 py-2 text-right text-orange-600">{moeda(n.valor_icms_credito || 0)}</td>
                      <td className="px-4 py-2 text-right text-blue-600">{moeda(n.valor_ipi_credito || 0)}</td>
                      <td className="px-4 py-2 text-right text-purple-600">{moeda((n.valor_pis_credito || 0) + (n.valor_cofins_credito || 0))}</td>
                    </tr>
                  ))}
                  <tr className="border-t bg-gray-50 font-semibold">
                    <td colSpan={2} className="px-4 py-2 text-gray-600">Total</td>
                    <td className="px-4 py-2 text-right">{moeda(somaEntradas.produtos)}</td>
                    <td className="px-4 py-2 text-right text-orange-600">{moeda(somaEntradas.icms)}</td>
                    <td className="px-4 py-2 text-right text-blue-600">{moeda(somaEntradas.ipi)}</td>
                    <td className="px-4 py-2 text-right text-purple-600">{moeda(somaEntradas.pis + somaEntradas.cofins)}</td>
                  </tr>
                </tbody>
              </table>
            )}
          </div>

          {/* Tabela saídas */}
          <div className="card">
            <div className="p-4 border-b">
              <h2 className="font-semibold text-gray-700 text-sm">NFs de Saída — {mes}</h2>
            </div>
            {saidasMes.length === 0 ? (
              <p className="p-4 text-center text-gray-400 text-sm">Nenhuma NF de saída neste mês.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left text-gray-500 font-medium">Status</th>
                    <th className="px-4 py-2 text-left text-gray-500 font-medium">Data</th>
                    <th className="px-4 py-2 text-right text-gray-500 font-medium">Produtos</th>
                    <th className="px-4 py-2 text-right text-orange-500 font-medium">ICMS Déb.</th>
                    <th className="px-4 py-2 text-right text-blue-500 font-medium">IPI Déb.</th>
                    <th className="px-4 py-2 text-right text-purple-500 font-medium">PIS/COFINS Déb.</th>
                    <th className="px-4 py-2 text-right text-gray-500 font-medium">Total NF</th>
                  </tr>
                </thead>
                <tbody>
                  {saidasMes.map(n => (
                    <tr key={n.id} className="border-t hover:bg-gray-50">
                      <td className="px-4 py-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${n.status_sefaz === "AUTORIZADA" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"}`}>
                          {n.status_sefaz}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-gray-500">{new Date(n.data_emissao).toLocaleDateString("pt-BR")}</td>
                      <td className="px-4 py-2 text-right">{moeda(n.valor_produtos || 0)}</td>
                      <td className="px-4 py-2 text-right text-orange-600">{moeda(n.valor_icms || 0)}</td>
                      <td className="px-4 py-2 text-right text-blue-600">{moeda(n.valor_ipi || 0)}</td>
                      <td className="px-4 py-2 text-right text-purple-600">{moeda((n.valor_pis || 0) + (n.valor_cofins || 0))}</td>
                      <td className="px-4 py-2 text-right font-semibold">{moeda(n.valor_total || 0)}</td>
                    </tr>
                  ))}
                  <tr className="border-t bg-gray-50 font-semibold">
                    <td colSpan={2} className="px-4 py-2 text-gray-600">Total</td>
                    <td className="px-4 py-2 text-right">{moeda(somaSaidas.produtos)}</td>
                    <td className="px-4 py-2 text-right text-orange-600">{moeda(somaSaidas.icms)}</td>
                    <td className="px-4 py-2 text-right text-blue-600">{moeda(somaSaidas.ipi)}</td>
                    <td className="px-4 py-2 text-right text-purple-600">{moeda(somaSaidas.pis + somaSaidas.cofins)}</td>
                    <td className="px-4 py-2 text-right"></td>
                  </tr>
                </tbody>
              </table>
            )}
          </div>
        </>
      )}
    </div>
  );
}
