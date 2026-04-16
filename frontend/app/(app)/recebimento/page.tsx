"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Plus, X, Trash2 } from "lucide-react";

interface NFEntrada {
  id: number;
  numero_nf: string;
  tipo_entrada: string;
  fornecedor_id: number | null;
  data_emissao: string;
  data_entrada: string;
  valor_total: number;
  status: string;
}

interface Fornecedor { id: number; razao_social: string; }
interface Produto { id: number; codigo: string; descricao: string; }
interface Localizacao { id: number; codigo: string; descricao: string; }

interface ItemForm {
  produto_id: string;
  localizacao_id: string;
  quantidade: string;
  preco_unitario: string;
  cfop: string;
  aliq_icms: string;
  aliq_ipi: string;
}

const STATUS_BADGE: Record<string, string> = {
  LANCADA: "badge-blue",
  CONFERIDA: "badge-green",
  CANCELADA: "badge-gray",
};

const TIPOS_ENTRADA = [
  { value: "COMPRA_MP", label: "Compra de Matéria-Prima" },
  { value: "COMPRA_REVENDA", label: "Compra para Revenda" },
  { value: "RETORNO_BANHO", label: "Retorno de Beneficiamento" },
  { value: "DEVOLUCAO_VENDA", label: "Devolução de Venda" },
];

const EMPTY_FORM = {
  tipo_entrada: "COMPRA_MP",
  fornecedor_id: "",
  numero_nf: "",
  serie: "1",
  data_emissao: new Date().toISOString().slice(0, 10),
  data_entrada: new Date().toISOString().slice(0, 10),
  cfop_entrada: "1101",
  valor_frete: "0",
  observacoes: "",
};

const EMPTY_ITEM: ItemForm = {
  produto_id: "",
  localizacao_id: "",
  quantidade: "1",
  preco_unitario: "0",
  cfop: "1101",
  aliq_icms: "12",
  aliq_ipi: "0",
};

export default function RecebimentoPage() {
  const [notas, setNotas] = useState<NFEntrada[]>([]);
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [localizacoes, setLocalizacoes] = useState<Localizacao[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<Record<string, string>>(EMPTY_FORM);
  const [itens, setItens] = useState<ItemForm[]>([{ ...EMPTY_ITEM }]);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");

  const fetchNotas = () => {
    api.get("/recebimento/").then((r) => setNotas(r.data));
  };

  useEffect(() => {
    fetchNotas();
    api.get("/parceiros/fornecedores/", { params: { limit: 200 } }).then((r) => setFornecedores(r.data));
    api.get("/produtos/", { params: { limit: 200 } }).then((r) => setProdutos(r.data));
    api.get("/estoque/localizacoes").then((r) => setLocalizacoes(r.data)).catch(() => {});
  }, []);

  function openNovo() {
    setForm({ ...EMPTY_FORM, data_emissao: new Date().toISOString().slice(0, 10), data_entrada: new Date().toISOString().slice(0, 10) });
    setItens([{ ...EMPTY_ITEM }]);
    setErro("");
    setShowModal(true);
  }

  function addItem() { setItens([...itens, { ...EMPTY_ITEM }]); }
  function removeItem(i: number) { setItens(itens.filter((_, idx) => idx !== i)); }
  function updateItem(i: number, field: keyof ItemForm, value: string) {
    const novo = [...itens];
    novo[i] = { ...novo[i], [field]: value };
    setItens(novo);
  }

  const totalNF = itens.reduce((acc, it) => {
    return acc + (parseFloat(it.quantidade) || 0) * (parseFloat(it.preco_unitario) || 0);
  }, 0);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!itens[0]?.produto_id) { setErro("Adicione ao menos um item"); return; }
    setSaving(true);
    setErro("");
    try {
      await api.post("/recebimento/", {
        tipo_entrada: form.tipo_entrada,
        fornecedor_id: form.fornecedor_id ? Number(form.fornecedor_id) : null,
        numero_nf: form.numero_nf,
        serie: form.serie || null,
        data_emissao: form.data_emissao,
        data_entrada: form.data_entrada,
        cfop_entrada: form.cfop_entrada || null,
        valor_frete: parseFloat(form.valor_frete) || 0,
        observacoes: form.observacoes || null,
        itens: itens.map((it) => ({
          produto_id: Number(it.produto_id),
          localizacao_id: Number(it.localizacao_id) || 1,
          quantidade: parseFloat(it.quantidade),
          preco_unitario: parseFloat(it.preco_unitario),
          cfop: it.cfop || null,
          aliq_icms: parseFloat(it.aliq_icms) || 0,
          aliq_ipi: parseFloat(it.aliq_ipi) || 0,
          aliq_pis: 0.65,
          aliq_cofins: 3.0,
        })),
      });
      setShowModal(false);
      fetchNotas();
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao registrar entrada");
    } finally {
      setSaving(false);
    }
  }

  const moeda = (v: number) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  const tipoLabel = (t: string) => TIPOS_ENTRADA.find((x) => x.value === t)?.label || t;

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Recebimento de NF</h1>
        <button className="btn-primary" onClick={openNovo}>
          <Plus size={16} /> Registrar Entrada
        </button>
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3 font-medium text-gray-600">NF</th>
              <th className="text-left p-3 font-medium text-gray-600">Tipo</th>
              <th className="text-left p-3 font-medium text-gray-600">Fornecedor</th>
              <th className="text-left p-3 font-medium text-gray-600">Entrada</th>
              <th className="text-left p-3 font-medium text-gray-600">Status</th>
              <th className="text-right p-3 font-medium text-gray-600">Total</th>
            </tr>
          </thead>
          <tbody>
            {notas.map((n) => (
              <tr key={n.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3 font-mono text-xs font-bold">{n.numero_nf}</td>
                <td className="p-3 text-gray-600">{tipoLabel(n.tipo_entrada)}</td>
                <td className="p-3 text-gray-700">
                  {n.fornecedor_id
                    ? fornecedores.find((f) => f.id === n.fornecedor_id)?.razao_social || `#${n.fornecedor_id}`
                    : "—"}
                </td>
                <td className="p-3">{new Date(n.data_entrada).toLocaleDateString("pt-BR")}</td>
                <td className="p-3">
                  <span className={STATUS_BADGE[n.status] || "badge-gray"}>{n.status}</span>
                </td>
                <td className="p-3 text-right font-medium">{moeda(Number(n.valor_total))}</td>
              </tr>
            ))}
            {notas.length === 0 && (
              <tr>
                <td colSpan={6} className="p-8 text-center text-gray-400">
                  Nenhuma nota de entrada registrada
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-3xl max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg">Registrar Entrada de NF</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Tipo de Entrada *</label>
                  <select className="input" value={form.tipo_entrada}
                    onChange={(e) => setForm({ ...form, tipo_entrada: e.target.value })}>
                    {TIPOS_ENTRADA.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Fornecedor</label>
                  <select className="input" value={form.fornecedor_id}
                    onChange={(e) => setForm({ ...form, fornecedor_id: e.target.value })}>
                    <option value="">Selecione...</option>
                    {fornecedores.map((f) => (
                      <option key={f.id} value={f.id}>{f.razao_social}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Número da NF *</label>
                  <input className="input font-mono" value={form.numero_nf} required
                    onChange={(e) => setForm({ ...form, numero_nf: e.target.value })} />
                </div>
                <div>
                  <label className="label">Série</label>
                  <input className="input" value={form.serie}
                    onChange={(e) => setForm({ ...form, serie: e.target.value })} />
                </div>
                <div>
                  <label className="label">Data de Emissão *</label>
                  <input className="input" type="date" value={form.data_emissao} required
                    onChange={(e) => setForm({ ...form, data_emissao: e.target.value })} />
                </div>
                <div>
                  <label className="label">Data de Entrada *</label>
                  <input className="input" type="date" value={form.data_entrada} required
                    onChange={(e) => setForm({ ...form, data_entrada: e.target.value })} />
                </div>
                <div>
                  <label className="label">CFOP</label>
                  <input className="input font-mono" value={form.cfop_entrada}
                    onChange={(e) => setForm({ ...form, cfop_entrada: e.target.value })} />
                </div>
                <div>
                  <label className="label">Valor Frete</label>
                  <input className="input" type="number" step="0.01" min="0" value={form.valor_frete}
                    onChange={(e) => setForm({ ...form, valor_frete: e.target.value })} />
                </div>
              </div>

              {/* Itens */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="label mb-0">Itens da NF *</label>
                  <button type="button" onClick={addItem} className="text-blue-600 text-xs hover:underline">
                    + Adicionar item
                  </button>
                </div>
                <div className="space-y-2">
                  {itens.map((item, i) => (
                    <div key={i} className="p-3 bg-gray-50 rounded-lg space-y-2">
                      <div className="flex gap-2">
                        <div className="flex-1">
                          <label className="label">Produto</label>
                          <select className="input" value={item.produto_id}
                            onChange={(e) => updateItem(i, "produto_id", e.target.value)}>
                            <option value="">Selecione...</option>
                            {produtos.map((p) => (
                              <option key={p.id} value={p.id}>{p.codigo} — {p.descricao}</option>
                            ))}
                          </select>
                        </div>
                        <div className="flex-1">
                          <label className="label">Localização</label>
                          <select className="input" value={item.localizacao_id}
                            onChange={(e) => updateItem(i, "localizacao_id", e.target.value)}>
                            <option value="">Selecione...</option>
                            {localizacoes.map((l) => (
                              <option key={l.id} value={l.id}>{l.codigo} — {l.descricao}</option>
                            ))}
                          </select>
                        </div>
                        <button type="button" onClick={() => removeItem(i)}
                          className="text-red-400 hover:text-red-600 self-end pb-2">
                          <Trash2 size={16} />
                        </button>
                      </div>
                      <div className="grid grid-cols-4 gap-2">
                        <div>
                          <label className="label">Qtd</label>
                          <input className="input" type="number" step="0.001" value={item.quantidade}
                            onChange={(e) => updateItem(i, "quantidade", e.target.value)} />
                        </div>
                        <div>
                          <label className="label">Preço Unit.</label>
                          <input className="input" type="number" step="0.01" value={item.preco_unitario}
                            onChange={(e) => updateItem(i, "preco_unitario", e.target.value)} />
                        </div>
                        <div>
                          <label className="label">ICMS %</label>
                          <input className="input" type="number" step="0.01" value={item.aliq_icms}
                            onChange={(e) => updateItem(i, "aliq_icms", e.target.value)} />
                        </div>
                        <div>
                          <label className="label">IPI %</label>
                          <input className="input" type="number" step="0.01" value={item.aliq_ipi}
                            onChange={(e) => updateItem(i, "aliq_ipi", e.target.value)} />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="text-right mt-2 text-sm font-medium text-gray-700">
                  Total produtos: {moeda(totalNF)}
                </div>
              </div>

              {erro && <p className="text-sm text-red-600 bg-red-50 p-2 rounded">{erro}</p>}

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" className="btn-secondary" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? "Registrando..." : "Registrar Entrada"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
