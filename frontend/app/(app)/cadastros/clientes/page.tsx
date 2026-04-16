"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Search, Plus, X, ChevronLeft } from "lucide-react";

interface Cliente {
  id: number;
  razao_social: string;
  nome_fantasia: string | null;
  cnpj_cpf: string;
  uf: string | null;
  telefone: string | null;
  email: string | null;
  consumidor_final: boolean;
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
  consumidor_final: "false",
  condicao_pagamento: "",
};

export default function ClientesPage() {
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [busca, setBusca] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<Record<string, string>>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");

  const fetchClientes = () => {
    api.get("/parceiros/clientes/", { params: { q: busca || undefined, limit: 100 } })
      .then((r) => setClientes(r.data));
  };

  useEffect(() => { fetchClientes(); }, [busca]);

  function openNovo() {
    setEditId(null);
    setForm(EMPTY_FORM);
    setErro("");
    setShowModal(true);
  }

  function openEditar(c: Cliente) {
    setEditId(c.id);
    setForm({
      razao_social: c.razao_social,
      nome_fantasia: c.nome_fantasia || "",
      cnpj_cpf: c.cnpj_cpf,
      ie: "",
      uf: c.uf || "",
      municipio: "",
      telefone: c.telefone || "",
      email: c.email || "",
      crt: "3",
      consumidor_final: String(c.consumidor_final),
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
      const payload = {
        ...form,
        consumidor_final: form.consumidor_final === "true",
      };
      if (editId) {
        await api.put(`/parceiros/clientes/${editId}`, payload);
      } else {
        await api.post("/parceiros/clientes/", payload);
      }
      setShowModal(false);
      fetchClientes();
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao salvar cliente");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <a href="/cadastros" className="text-gray-400 hover:text-gray-600">
          <ChevronLeft size={20} />
        </a>
        <h1 className="text-2xl font-bold flex-1">Clientes</h1>
        <button className="btn-primary" onClick={openNovo}>
          <Plus size={16} /> Novo Cliente
        </button>
      </div>

      <div className="relative mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          className="input pl-9"
          placeholder="Buscar por razão social ou CNPJ/CPF..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3 font-medium text-gray-600">Razão Social</th>
              <th className="text-left p-3 font-medium text-gray-600">CNPJ / CPF</th>
              <th className="text-left p-3 font-medium text-gray-600">UF</th>
              <th className="text-left p-3 font-medium text-gray-600">Telefone</th>
              <th className="text-left p-3 font-medium text-gray-600">Cons. Final</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {clientes.map((c) => (
              <tr key={c.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3">
                  <div className="font-medium">{c.razao_social}</div>
                  {c.nome_fantasia && (
                    <div className="text-xs text-gray-400">{c.nome_fantasia}</div>
                  )}
                </td>
                <td className="p-3 font-mono text-xs">{c.cnpj_cpf}</td>
                <td className="p-3">{c.uf || "—"}</td>
                <td className="p-3 text-gray-500">{c.telefone || "—"}</td>
                <td className="p-3">
                  <span className={c.consumidor_final ? "badge-blue" : "badge-gray"}>
                    {c.consumidor_final ? "Sim" : "Não"}
                  </span>
                </td>
                <td className="p-3 text-right">
                  <button onClick={() => openEditar(c)} className="text-blue-600 text-xs hover:underline">
                    Editar
                  </button>
                </td>
              </tr>
            ))}
            {clientes.length === 0 && (
              <tr>
                <td colSpan={6} className="p-8 text-center text-gray-400">Nenhum cliente encontrado</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-lg max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg">{editId ? "Editar Cliente" : "Novo Cliente"}</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
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
                  <label className="label">CNPJ / CPF *</label>
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
                  <label className="label">Regime Tributário (CRT)</label>
                  <select className="input" value={form.crt}
                    onChange={(e) => setForm({ ...form, crt: e.target.value })}>
                    <option value="1">1 — Simples Nacional</option>
                    <option value="2">2 — SN excesso sublimite</option>
                    <option value="3">3 — Regime Normal</option>
                  </select>
                </div>
                <div>
                  <label className="label">Consumidor Final</label>
                  <select className="input" value={form.consumidor_final}
                    onChange={(e) => setForm({ ...form, consumidor_final: e.target.value })}>
                    <option value="false">Não</option>
                    <option value="true">Sim</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="label">Condição de Pagamento</label>
                <input className="input" placeholder="Ex: 30/60 DDL" value={form.condicao_pagamento}
                  onChange={(e) => setForm({ ...form, condicao_pagamento: e.target.value })} />
              </div>

              {erro && <p className="text-sm text-red-600 bg-red-50 p-2 rounded">{erro}</p>}

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
