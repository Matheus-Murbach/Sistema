"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Search, Plus, X, ChevronLeft } from "lucide-react";

interface Produto {
  id: number;
  codigo: string;
  descricao: string;
  tipo: string;
  unidade_id: number;
  ncm: string | null;
  preco_venda: number;
  estoque_minimo: number;
  ativo: boolean;
}

interface UnidadeMedida {
  id: number;
  codigo: string;
  descricao: string;
}

const TIPOS = [
  { value: "MATERIA_PRIMA", label: "Matéria-Prima" },
  { value: "PRODUTO_ACABADO", label: "Produto Acabado" },
  { value: "PRODUTO_BENEFICIADO", label: "Produto Beneficiado" },
  { value: "SEMI_ACABADO", label: "Semi-Acabado" },
  { value: "REVENDA", label: "Revenda" },
];

const TIPO_BADGE: Record<string, string> = {
  MATERIA_PRIMA: "badge-blue",
  PRODUTO_ACABADO: "badge-green",
  PRODUTO_BENEFICIADO: "badge-green",
  SEMI_ACABADO: "badge-yellow",
  REVENDA: "badge-gray",
};

const TIPO_LABEL: Record<string, string> = {
  MATERIA_PRIMA: "MP",
  PRODUTO_ACABADO: "PA",
  PRODUTO_BENEFICIADO: "PB",
  SEMI_ACABADO: "SA",
  REVENDA: "RV",
};

const EMPTY_FORM = {
  codigo: "",
  descricao: "",
  tipo: "MATERIA_PRIMA",
  unidade_id: "",
  ncm: "",
  codigo_barras: "",
  preco_custo: "0",
  preco_venda: "0",
  estoque_minimo: "0",
  estoque_maximo: "0",
};

export default function ProdutosPage() {
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [unidades, setUnidades] = useState<UnidadeMedida[]>([]);
  const [busca, setBusca] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<Record<string, string>>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");

  const fetchProdutos = () => {
    api.get("/produtos/", { params: { q: busca || undefined, limit: 100 } })
      .then((r) => setProdutos(r.data));
  };

  useEffect(() => {
    fetchProdutos();
    api.get("/produtos/unidades-medida").then((r) => setUnidades(r.data)).catch(() => {});
  }, [busca]);

  function openNovo() {
    setEditId(null);
    setForm(EMPTY_FORM);
    setErro("");
    setShowModal(true);
  }

  function openEditar(p: Produto) {
    setEditId(p.id);
    setForm({
      codigo: p.codigo,
      descricao: p.descricao,
      tipo: p.tipo,
      unidade_id: String(p.unidade_id),
      ncm: p.ncm || "",
      codigo_barras: "",
      preco_custo: "0",
      preco_venda: String(p.preco_venda),
      estoque_minimo: String(p.estoque_minimo),
      estoque_maximo: "0",
    });
    setErro("");
    setShowModal(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErro("");
    try {
      const payload = {
        ...form,
        unidade_id: Number(form.unidade_id) || 1,
        preco_custo: parseFloat(form.preco_custo) || 0,
        preco_venda: parseFloat(form.preco_venda) || 0,
        estoque_minimo: parseFloat(form.estoque_minimo) || 0,
        estoque_maximo: parseFloat(form.estoque_maximo) || 0,
      };
      if (editId) {
        await api.put(`/produtos/${editId}`, payload);
      } else {
        await api.post("/produtos/", payload);
      }
      setShowModal(false);
      fetchProdutos();
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao salvar produto");
    } finally {
      setSaving(false);
    }
  }

  const moeda = (v: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <a href="/cadastros" className="text-gray-400 hover:text-gray-600">
          <ChevronLeft size={20} />
        </a>
        <h1 className="text-2xl font-bold flex-1">Produtos</h1>
        <button className="btn-primary" onClick={openNovo}>
          <Plus size={16} /> Novo Produto
        </button>
      </div>

      <div className="relative mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          className="input pl-9"
          placeholder="Buscar por código ou descrição..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3 font-medium text-gray-600">Código</th>
              <th className="text-left p-3 font-medium text-gray-600">Descrição</th>
              <th className="text-left p-3 font-medium text-gray-600">Tipo</th>
              <th className="text-left p-3 font-medium text-gray-600">NCM</th>
              <th className="text-right p-3 font-medium text-gray-600">Preço Venda</th>
              <th className="text-right p-3 font-medium text-gray-600">Est. Mín.</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {produtos.map((p) => (
              <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3 font-mono text-xs font-bold">{p.codigo}</td>
                <td className="p-3">{p.descricao}</td>
                <td className="p-3">
                  <span className={TIPO_BADGE[p.tipo] || "badge-gray"}>
                    {TIPO_LABEL[p.tipo] || p.tipo}
                  </span>
                </td>
                <td className="p-3 font-mono text-xs text-gray-500">{p.ncm || "—"}</td>
                <td className="p-3 text-right">{moeda(Number(p.preco_venda))}</td>
                <td className="p-3 text-right text-gray-500">{p.estoque_minimo}</td>
                <td className="p-3 text-right">
                  <button
                    onClick={() => openEditar(p)}
                    className="text-amber-600 text-xs hover:underline"
                  >
                    Editar
                  </button>
                </td>
              </tr>
            ))}
            {produtos.length === 0 && (
              <tr>
                <td colSpan={7} className="p-8 text-center text-gray-400">
                  Nenhum produto encontrado
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-lg max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg">{editId ? "Editar Produto" : "Novo Produto"}</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Código *</label>
                  <input className="input" value={form.codigo} required
                    onChange={(e) => setForm({ ...form, codigo: e.target.value })} />
                </div>
                <div>
                  <label className="label">Código de Barras</label>
                  <input className="input" value={form.codigo_barras}
                    onChange={(e) => setForm({ ...form, codigo_barras: e.target.value })} />
                </div>
              </div>

              <div>
                <label className="label">Descrição *</label>
                <input className="input" value={form.descricao} required
                  onChange={(e) => setForm({ ...form, descricao: e.target.value })} />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Tipo *</label>
                  <select className="input" value={form.tipo}
                    onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
                    {TIPOS.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Unidade *</label>
                  <select className="input" value={form.unidade_id} required
                    onChange={(e) => setForm({ ...form, unidade_id: e.target.value })}>
                    <option value="">Selecione...</option>
                    {unidades.map((u) => (
                      <option key={u.id} value={u.id}>{u.codigo} — {u.descricao}</option>
                    ))}
                    {unidades.length === 0 && <option value="1">UN — Unidade</option>}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">NCM</label>
                  <input className="input font-mono" placeholder="00000000" value={form.ncm}
                    onChange={(e) => setForm({ ...form, ncm: e.target.value })} />
                </div>
                <div>
                  <label className="label">Est. Mínimo</label>
                  <input className="input" type="number" step="0.001" value={form.estoque_minimo}
                    onChange={(e) => setForm({ ...form, estoque_minimo: e.target.value })} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Preço de Custo</label>
                  <input className="input" type="number" step="0.01" value={form.preco_custo}
                    onChange={(e) => setForm({ ...form, preco_custo: e.target.value })} />
                </div>
                <div>
                  <label className="label">Preço de Venda</label>
                  <input className="input" type="number" step="0.01" value={form.preco_venda}
                    onChange={(e) => setForm({ ...form, preco_venda: e.target.value })} />
                </div>
              </div>

              {erro && <p className="text-sm text-red-600 bg-red-50 p-2 rounded">{erro}</p>}

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" className="btn-secondary" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? "Salvando..." : "Salvar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
