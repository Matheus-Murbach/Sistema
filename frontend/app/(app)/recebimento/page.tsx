"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Plus, Trash2, ChevronDown, ChevronUp, Package } from "lucide-react";

interface Fornecedor { id: number; razao_social: string; }
interface Produto { id: number; codigo: string; descricao: string; aliq_icms: number; aliq_ipi: number; aliq_pis: number; aliq_cofins: number; }
interface Localizacao { id: number; codigo: string; descricao: string; }
interface NFEntrada { id: number; numero_nf: string; fornecedor_id: number | null; data_entrada: string; valor_total_produtos: number; tipo_entrada: string; }

interface ItemForm {
  produto_id: string;
  localizacao_id: string;
  quantidade: string;
  preco_unitario: string;
  aliq_icms: string;
  aliq_ipi: string;
  aliq_pis: string;
  aliq_cofins: string;
  expandido: boolean;
}

const CFOP_MAP: Record<string, string> = {
  COMPRA_MP: "1101",
  COMPRA_REVENDA: "1102",
  RETORNO_BANHO: "1902",
  DEVOLUCAO_VENDA: "1201",
};

export default function RecebimentoPage() {
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [localizacoes, setLocalizacoes] = useState<Localizacao[]>([]);
  const [notas, setNotas] = useState<NFEntrada[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");

  const [form, setForm] = useState({
    tipo_entrada: "COMPRA_MP",
    fornecedor_id: "",
    numero_nf: "",
    serie: "1",
    data_emissao: new Date().toISOString().slice(0, 10),
    data_entrada: new Date().toISOString().slice(0, 10),
    valor_frete: "0",
    observacoes: "",
  });

  const [itens, setItens] = useState<ItemForm[]>([{
    produto_id: "", localizacao_id: "", quantidade: "1", preco_unitario: "0",
    aliq_icms: "0", aliq_ipi: "0", aliq_pis: "0", aliq_cofins: "0", expandido: false,
  }]);

  useEffect(() => {
    api.get("/parceiros/fornecedores/", { params: { limit: 200 } }).then(r => setFornecedores(r.data));
    api.get("/produtos/", { params: { limit: 200 } }).then(r => setProdutos(r.data));
    api.get("/estoque/localizacoes").then(r => setLocalizacoes(r.data));
    api.get("/recebimento/", { params: { limit: 50 } }).then(r => setNotas(r.data));
  }, []);

  function addItem() {
    setItens([...itens, {
      produto_id: "", localizacao_id: "", quantidade: "1", preco_unitario: "0",
      aliq_icms: "0", aliq_ipi: "0", aliq_pis: "0", aliq_cofins: "0", expandido: false,
    }]);
  }

  function removeItem(i: number) { setItens(itens.filter((_, idx) => idx !== i)); }

  function updateItem(i: number, field: keyof Omit<ItemForm, "expandido">, value: string) {
    const n = [...itens];
    n[i] = { ...n[i], [field]: value };
    if (field === "produto_id") {
      const p = produtos.find(p => String(p.id) === value);
      if (p) {
        n[i].aliq_icms = String(p.aliq_icms || 0);
        n[i].aliq_ipi = String(p.aliq_ipi || 0);
        n[i].aliq_pis = String(p.aliq_pis || 0);
        n[i].aliq_cofins = String(p.aliq_cofins || 0);
      }
    }
    setItens(n);
  }

  function toggleExpandido(i: number) {
    const n = [...itens];
    n[i] = { ...n[i], expandido: !n[i].expandido };
    setItens(n);
  }

  const totalItens = itens.reduce((acc, it) => acc + (parseFloat(it.quantidade) || 0) * (parseFloat(it.preco_unitario) || 0), 0);
  const totalGeral = totalItens + (parseFloat(form.valor_frete) || 0);
  const moeda = (v: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);
  const fornNome = (id: number | null) => fornecedores.find(f => f.id === id)?.razao_social || "—";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!itens[0]?.produto_id) { setErro("Adicione ao menos um item"); return; }
    setSaving(true); setErro("");
    try {
      await api.post("/recebimento/", {
        tipo_entrada: form.tipo_entrada,
        fornecedor_id: form.fornecedor_id ? Number(form.fornecedor_id) : null,
        numero_nf: form.numero_nf,
        serie: form.serie || null,
        data_emissao: form.data_emissao,
        data_entrada: form.data_entrada,
        cfop_entrada: CFOP_MAP[form.tipo_entrada] || null,
        valor_frete: parseFloat(form.valor_frete) || 0,
        observacoes: form.observacoes || null,
        itens: itens.filter(it => it.produto_id).map(it => ({
          produto_id: Number(it.produto_id),
          localizacao_id: Number(it.localizacao_id),
          cfop: CFOP_MAP[form.tipo_entrada] || null,
          quantidade: parseFloat(it.quantidade),
          preco_unitario: parseFloat(it.preco_unitario),
          aliq_icms: parseFloat(it.aliq_icms) || 0,
          aliq_ipi: parseFloat(it.aliq_ipi) || 0,
          aliq_pis: parseFloat(it.aliq_pis) || 0,
          aliq_cofins: parseFloat(it.aliq_cofins) || 0,
        })),
      });
      const r = await api.get("/recebimento/", { params: { limit: 50 } });
      setNotas(r.data);
      setShowForm(false);
      setForm({ tipo_entrada: "COMPRA_MP", fornecedor_id: "", numero_nf: "", serie: "1", data_emissao: new Date().toISOString().slice(0, 10), data_entrada: new Date().toISOString().slice(0, 10), valor_frete: "0", observacoes: "" });
      setItens([{ produto_id: "", localizacao_id: "", quantidade: "1", preco_unitario: "0", aliq_icms: "0", aliq_ipi: "0", aliq_pis: "0", aliq_cofins: "0", expandido: false }]);
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao registrar entrada");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-4xl">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Recebimento</h1>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancelar" : "+ Nova Entrada"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="card p-6 mb-6 space-y-4">
          <h2 className="font-semibold text-gray-700">Registrar Entrada de Estoque</h2>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Tipo de Entrada *</label>
              <select className="input" value={form.tipo_entrada} onChange={e => setForm({ ...form, tipo_entrada: e.target.value })}>
                <option value="COMPRA_MP">Compra — Matéria-Prima</option>
                <option value="COMPRA_REVENDA">Compra — Revenda</option>
                <option value="RETORNO_BANHO">Retorno de Beneficiamento</option>
                <option value="DEVOLUCAO_VENDA">Devolução de Venda</option>
              </select>
            </div>
            <div>
              <label className="label">Fornecedor</label>
              <select className="input" value={form.fornecedor_id} onChange={e => setForm({ ...form, fornecedor_id: e.target.value })}>
                <option value="">Selecione...</option>
                {fornecedores.map(f => <option key={f.id} value={f.id}>{f.razao_social}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Número da NF *</label>
              <input className="input" required value={form.numero_nf} onChange={e => setForm({ ...form, numero_nf: e.target.value })} placeholder="000001" />
            </div>
            <div>
              <label className="label">Série</label>
              <input className="input" value={form.serie} onChange={e => setForm({ ...form, serie: e.target.value })} placeholder="1" />
            </div>
            <div>
              <label className="label">Data de Emissão *</label>
              <input className="input" type="date" required value={form.data_emissao} onChange={e => setForm({ ...form, data_emissao: e.target.value })} />
            </div>
            <div>
              <label className="label">Data de Entrada *</label>
              <input className="input" type="date" required value={form.data_entrada} onChange={e => setForm({ ...form, data_entrada: e.target.value })} />
            </div>
            <div>
              <label className="label">Frete (R$)</label>
              <input className="input" type="number" step="0.01" min="0" value={form.valor_frete} onChange={e => setForm({ ...form, valor_frete: e.target.value })} />
            </div>
          </div>

          {/* Itens */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-medium text-gray-700">Itens</h3>
              <button type="button" onClick={addItem} className="text-amber-600 text-sm hover:underline flex items-center gap-1">
                <Plus size={13} /> Adicionar item
              </button>
            </div>
            <div className="space-y-2">
              {itens.map((item, i) => {
                const subtotal = (parseFloat(item.quantidade) || 0) * (parseFloat(item.preco_unitario) || 0);
                return (
                  <div key={i} className="border border-gray-200 rounded-lg bg-gray-50">
                    <div className="flex gap-2 items-end p-3">
                      <div className="flex-1">
                        {i === 0 && <label className="label">Produto</label>}
                        <select className="input" value={item.produto_id} onChange={e => updateItem(i, "produto_id", e.target.value)}>
                          <option value="">Selecione...</option>
                          {produtos.map(p => <option key={p.id} value={p.id}>{p.codigo} — {p.descricao}</option>)}
                        </select>
                      </div>
                      <div className="w-36">
                        {i === 0 && <label className="label">Localização</label>}
                        <select className="input" value={item.localizacao_id} onChange={e => updateItem(i, "localizacao_id", e.target.value)}>
                          <option value="">Local...</option>
                          {localizacoes.map(l => <option key={l.id} value={l.id}>{l.codigo}</option>)}
                        </select>
                      </div>
                      <div className="w-24">
                        {i === 0 && <label className="label">Qtd</label>}
                        <input className="input" type="number" step="0.001" min="0.001" value={item.quantidade} onChange={e => updateItem(i, "quantidade", e.target.value)} />
                      </div>
                      <div className="w-32">
                        {i === 0 && <label className="label">Preço Unit.</label>}
                        <input className="input" type="number" step="0.01" min="0" value={item.preco_unitario} onChange={e => updateItem(i, "preco_unitario", e.target.value)} />
                      </div>
                      <div className="w-28 text-right">
                        {i === 0 && <label className="label">Subtotal</label>}
                        <div className="py-2 font-semibold text-gray-700">{moeda(subtotal)}</div>
                      </div>
                      <button type="button" onClick={() => toggleExpandido(i)} className="text-gray-400 hover:text-gray-600 mt-4" title="Alíquotas fiscais">
                        {item.expandido ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                      </button>
                      <button type="button" onClick={() => removeItem(i)} className="text-red-400 hover:text-red-600 mt-4">
                        <Trash2 size={15} />
                      </button>
                    </div>
                    {item.expandido && (
                      <div className="px-3 pb-3 pt-1 border-t border-gray-200 bg-white rounded-b-lg">
                        <p className="text-xs text-gray-400 mb-2">Alíquotas fiscais (crédito na entrada)</p>
                        <div className="grid grid-cols-4 gap-2">
                          {(["aliq_icms", "aliq_ipi", "aliq_pis", "aliq_cofins"] as const).map(f => (
                            <div key={f}>
                              <label className="label">{f.replace("aliq_", "").toUpperCase()} %</label>
                              <input className="input" type="number" step="0.01" min="0" max="100"
                                value={item[f]}
                                onChange={e => updateItem(i, f, e.target.value)}
                              />
                            </div>
                          ))}
                        </div>
                        <div className="flex gap-4 mt-2 text-xs">
                          {parseFloat(item.aliq_icms) > 0 && <span className="text-orange-600">ICMS crédito: {moeda(subtotal * parseFloat(item.aliq_icms) / 100)}</span>}
                          {parseFloat(item.aliq_ipi) > 0 && <span className="text-amber-600">IPI: {moeda(subtotal * parseFloat(item.aliq_ipi) / 100)}</span>}
                          {(parseFloat(item.aliq_pis) + parseFloat(item.aliq_cofins)) > 0 && (
                            <span className="text-purple-600">PIS/COFINS: {moeda(subtotal * (parseFloat(item.aliq_pis) + parseFloat(item.aliq_cofins)) / 100)}</span>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="flex justify-end gap-8 text-sm border-t pt-3">
            <span className="text-gray-500">Produtos: <strong>{moeda(totalItens)}</strong></span>
            {parseFloat(form.valor_frete) > 0 && <span className="text-gray-500">Frete: <strong>{moeda(parseFloat(form.valor_frete))}</strong></span>}
            <span className="text-gray-900 font-bold">Total: {moeda(totalGeral)}</span>
          </div>

          {erro && <p className="text-sm text-red-600 bg-red-50 p-3 rounded">{erro}</p>}
          <div className="flex justify-end gap-3">
            <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>Cancelar</button>
            <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Salvando..." : "Registrar Entrada"}</button>
          </div>
        </form>
      )}

      <div className="card">
        <div className="p-4 border-b flex items-center gap-2">
          <Package size={16} className="text-gray-400" />
          <h2 className="font-semibold text-gray-700">Entradas Registradas</h2>
        </div>
        {notas.length === 0 ? (
          <p className="p-6 text-center text-gray-400">Nenhuma entrada registrada ainda.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-gray-500 font-medium">NF</th>
                <th className="px-4 py-2 text-left text-gray-500 font-medium">Tipo</th>
                <th className="px-4 py-2 text-left text-gray-500 font-medium">Fornecedor</th>
                <th className="px-4 py-2 text-left text-gray-500 font-medium">Data Entrada</th>
                <th className="px-4 py-2 text-right text-gray-500 font-medium">Total Produtos</th>
              </tr>
            </thead>
            <tbody>
              {notas.map(n => (
                <tr key={n.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono">{n.numero_nf}</td>
                  <td className="px-4 py-2">
                    <span className="badge-blue text-xs">{n.tipo_entrada.replace(/_/g, " ")}</span>
                  </td>
                  <td className="px-4 py-2 text-gray-600">{fornNome(n.fornecedor_id)}</td>
                  <td className="px-4 py-2 text-gray-500">{new Date(n.data_entrada).toLocaleDateString("pt-BR")}</td>
                  <td className="px-4 py-2 text-right font-semibold">{moeda(n.valor_total_produtos || 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
