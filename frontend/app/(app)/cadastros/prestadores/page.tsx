"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Search, Plus, X, ChevronLeft } from "lucide-react";

interface Prestador {
  id: number;
  razao_social: string;
  nome_fantasia: string | null;
  cnpj_cpf: string;
  uf: string | null;
  telefone: string | null;
  tipo_beneficiamento: string | null;
  prazo_retorno_dias: number;
  percentual_perda_esperado: number;
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
  tipo_beneficiamento: "",
  prazo_retorno_dias: "7",
  percentual_perda_esperado: "0",
};

export default function PrestadoresPage() {
  const [prestadores, setPrestadores] = useState<Prestador[]>([]);
  const [busca, setBusca] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<Record<string, string>>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");

  const fetchPrestadores = () => {
    api.get("/prestadores/", { params: { q: busca || undefined, limit: 100 } })
      .then((r) => setPrestadores(r.data));
  };

  useEffect(() => { fetchPrestadores(); }, [busca]);

  function openNovo() {
    setEditId(null);
    setForm(EMPTY_FORM);
    setErro("");
    setShowModal(true);
  }

  function openEditar(p: Prestador) {
    setEditId(p.id);
    setForm({
      razao_social: p.razao_social,
      nome_fantasia: p.nome_fantasia || "",
      cnpj_cpf: p.cnpj_cpf,
      ie: "",
      uf: p.uf || "",
      municipio: "",
      telefone: p.telefone || "",
      email: "",
      crt: "3",
      tipo_beneficiamento: p.tipo_beneficiamento || "",
      prazo_retorno_dias: String(p.prazo_retorno_dias),
      percentual_perda_esperado: String(p.percentual_perda_esperado),
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
        prazo_retorno_dias: Number(form.prazo_retorno_dias),
        percentual_perda_esperado: parseFloat(form.percentual_perda_esperado),
      };
      if (editId) {
        await api.put(`/prestadores/${editId}`, payload);
      } else {
        await api.post("/prestadores/", payload);
      }
      setShowModal(false);
      fetchPrestadores();
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao salvar prestador");
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
        <h1 className="text-2xl font-bold flex-1">Prestadores de Beneficiamento</h1>
        <button className="btn-primary" onClick={openNovo}>
          <Plus size={16} /> Novo Prestador
        </button>
      </div>

      <div className="relative mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          className="input pl-9"
          placeholder="Buscar por razão social ou CNPJ..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3 font-medium text-gray-600">Razão Social</th>
              <th className="text-left p-3 font-medium text-gray-600">CNPJ</th>
              <th className="text-left p-3 font-medium text-gray-600">Tipo Banho</th>
              <th className="text-right p-3 font-medium text-gray-600">Prazo Retorno</th>
              <th className="text-right p-3 font-medium text-gray-600">% Perda</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {prestadores.map((p) => (
              <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3">
                  <div className="font-medium">{p.razao_social}</div>
                  {p.nome_fantasia && <div className="text-xs text-gray-400">{p.nome_fantasia}</div>}
                </td>
                <td className="p-3 font-mono text-xs">{p.cnpj_cpf}</td>
                <td className="p-3 text-gray-600">{p.tipo_beneficiamento || "—"}</td>
                <td className="p-3 text-right text-gray-500">{p.prazo_retorno_dias} dias</td>
                <td className="p-3 text-right text-gray-500">{p.percentual_perda_esperado}%</td>
                <td className="p-3 text-right">
                  <button onClick={() => openEditar(p)} className="text-blue-600 text-xs hover:underline">
                    Editar
                  </button>
                </td>
              </tr>
            ))}
            {prestadores.length === 0 && (
              <tr>
                <td colSpan={6} className="p-8 text-center text-gray-400">Nenhum prestador encontrado</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-lg max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg">{editId ? "Editar Prestador" : "Novo Prestador"}</h2>
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
                  <label className="label">CNPJ *</label>
                  <input className="input font-mono" value={form.cnpj_cpf} required
                    onChange={(e) => setForm({ ...form, cnpj_cpf: e.target.value })} />
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
              <div>
                <label className="label">Tipo de Beneficiamento</label>
                <input className="input" placeholder="Ex: Galvanização, Niquelação, Zinco" value={form.tipo_beneficiamento}
                  onChange={(e) => setForm({ ...form, tipo_beneficiamento: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Prazo Retorno (dias)</label>
                  <input className="input" type="number" min="1" value={form.prazo_retorno_dias}
                    onChange={(e) => setForm({ ...form, prazo_retorno_dias: e.target.value })} />
                </div>
                <div>
                  <label className="label">% Perda Esperada</label>
                  <input className="input" type="number" step="0.1" min="0" value={form.percentual_perda_esperado}
                    onChange={(e) => setForm({ ...form, percentual_perda_esperado: e.target.value })} />
                </div>
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
