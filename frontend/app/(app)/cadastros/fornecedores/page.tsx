"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Search, Plus, X, ChevronLeft } from "lucide-react";

interface Fornecedor {
  id: number;
  razao_social: string;
  nome_fantasia: string | null;
  cnpj_cpf: string;
  uf: string | null;
  telefone: string | null;
  prazo_entrega_dias: number;
  ativo: boolean;
}

const EMPTY_FORM = {
  razao_social: "",
  nome_fantasia: "",
  cnpj_cpf: "",
  ie: "",
  uf: "",
  municipio: "",
  telefone: "",
  email: "",
  crt: "3",
  prazo_entrega_dias: "0",
  condicao_pagamento: "",
};

export default function FornecedoresPage() {
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [busca, setBusca] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<Record<string, string>>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");

  const fetchFornecedores = () => {
    api.get("/parceiros/fornecedores/", { params: { q: busca || undefined, limit: 100 } })
      .then((r) => setFornecedores(r.data));
  };

  useEffect(() => { fetchFornecedores(); }, [busca]);

  function openNovo() {
    setEditId(null);
    setForm(EMPTY_FORM);
    setErro("");
    setShowModal(true);
  }

  function openEditar(f: Fornecedor) {
    setEditId(f.id);
    setForm({
      razao_social: f.razao_social,
      nome_fantasia: f.nome_fantasia || "",
      cnpj_cpf: f.cnpj_cpf,
      ie: "",
      uf: f.uf || "",
      municipio: "",
      telefone: f.telefone || "",
      email: "",
      crt: "3",
      prazo_entrega_dias: String(f.prazo_entrega_dias),
      condicao_pagamento: "",
    });
    setErro("");
    setShowModal(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErro("");
    try {
      const payload = { ...form, prazo_entrega_dias: Number(form.prazo_entrega_dias) };
      if (editId) {
        await api.put(`/parceiros/fornecedores/${editId}`, payload);
      } else {
        await api.post("/parceiros/fornecedores/", payload);
      }
      setShowModal(false);
      fetchFornecedores();
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao salvar fornecedor");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <a href="/cadastros" className="text-muted hover:text-gray-600">
          <ChevronLeft size={20} />
        </a>
        <h1 className="text-2xl font-bold flex-1">Fornecedores</h1>
        <button className="btn-primary" onClick={openNovo}>
          <Plus size={16} /> Novo Fornecedor
        </button>
      </div>

      <div className="relative mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
        <input
          className="input pl-9"
          placeholder="Buscar por razão social ou CNPJ..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-page border-b">
            <tr>
              <th className="text-left p-3 font-medium text-gray-600">Razão Social</th>
              <th className="text-left p-3 font-medium text-gray-600">CNPJ</th>
              <th className="text-left p-3 font-medium text-gray-600">UF</th>
              <th className="text-left p-3 font-medium text-gray-600">Telefone</th>
              <th className="text-right p-3 font-medium text-gray-600">Prazo Entrega</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {fornecedores.map((f) => (
              <tr key={f.id} className="border-b last:border-0 hover:bg-page">
                <td className="p-3">
                  <div className="font-medium">{f.razao_social}</div>
                  {f.nome_fantasia && <div className="text-xs text-muted">{f.nome_fantasia}</div>}
                </td>
                <td className="p-3 font-mono text-xs">{f.cnpj_cpf}</td>
                <td className="p-3">{f.uf || "—"}</td>
                <td className="p-3 text-muted">{f.telefone || "—"}</td>
                <td className="p-3 text-right text-muted">
                  {f.prazo_entrega_dias > 0 ? `${f.prazo_entrega_dias} dias` : "—"}
                </td>
                <td className="p-3 text-right">
                  <button onClick={() => openEditar(f)} className="text-primary text-xs hover:underline">
                    Editar
                  </button>
                </td>
              </tr>
            ))}
            {fornecedores.length === 0 && (
              <tr>
                <td colSpan={6} className="p-8 text-center text-muted">Nenhum fornecedor encontrado</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-lg max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg">{editId ? "Editar Fornecedor" : "Novo Fornecedor"}</h2>
              <button onClick={() => setShowModal(false)} className="text-muted hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="label">Razão Social *</label>
                <input className="input" value={form.razao_social} required
                  onChange={(e) => setForm({ ...form, razao_social: e.target.value })} />
              </div>
              <div>
                <label className="label">Nome Fantasia</label>
                <input className="input" value={form.nome_fantasia}
                  onChange={(e) => setForm({ ...form, nome_fantasia: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">CNPJ *</label>
                  <input className="input font-mono" value={form.cnpj_cpf} required
                    onChange={(e) => setForm({ ...form, cnpj_cpf: e.target.value })} />
                </div>
                <div>
                  <label className="label">Inscrição Estadual</label>
                  <input className="input" value={form.ie}
                    onChange={(e) => setForm({ ...form, ie: e.target.value })} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Município</label>
                  <input className="input" value={form.municipio}
                    onChange={(e) => setForm({ ...form, municipio: e.target.value })} />
                </div>
                <div>
                  <label className="label">UF</label>
                  <input className="input uppercase" maxLength={2} value={form.uf}
                    onChange={(e) => setForm({ ...form, uf: e.target.value.toUpperCase() })} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Telefone</label>
                  <input className="input" value={form.telefone}
                    onChange={(e) => setForm({ ...form, telefone: e.target.value })} />
                </div>
                <div>
                  <label className="label">E-mail</label>
                  <input className="input" type="email" value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Prazo de Entrega (dias)</label>
                  <input className="input" type="number" min="0" value={form.prazo_entrega_dias}
                    onChange={(e) => setForm({ ...form, prazo_entrega_dias: e.target.value })} />
                </div>
                <div>
                  <label className="label">Condição de Pagamento</label>
                  <input className="input" placeholder="Ex: 30 dias" value={form.condicao_pagamento}
                    onChange={(e) => setForm({ ...form, condicao_pagamento: e.target.value })} />
                </div>
              </div>

              {erro && <p className="text-sm text-danger bg-danger-tint p-2 rounded">{erro}</p>}

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" className="btn-secondary" onClick={() => setShowModal(false)}>Cancelar</button>
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
