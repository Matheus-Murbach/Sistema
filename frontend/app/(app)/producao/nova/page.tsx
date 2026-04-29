"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { ChevronLeft, Plus, Trash2 } from "lucide-react";

interface Produto { id: number; codigo: string; descricao: string; tipo: string; }
interface Localizacao { id: number; codigo: string; descricao: string; }

interface MaterialForm { produto_id: string; quantidade_necessaria: string; }

export default function NovaOPPage() {
  const router = useRouter();
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [localizacoes, setLocalizacoes] = useState<Localizacao[]>([]);

  const [form, setForm] = useState({
    produto_id: "",
    quantidade_planejada: "",
    data_planejada: "",
    localizacao_saida_id: "",
    observacoes: "",
  });
  const [materiais, setMateriais] = useState<MaterialForm[]>([{ produto_id: "", quantidade_necessaria: "1" }]);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api.get("/produtos/", { params: { limit: 200 } }).then((r) => setProdutos(r.data));
    api.get("/estoque/localizacoes").then((r) => setLocalizacoes(r.data)).catch(() => {});
  }, []);

  const produtosPA = produtos.filter((p) =>
    ["PRODUTO_ACABADO", "PRODUTO_BENEFICIADO", "SEMI_ACABADO"].includes(p.tipo)
  );
  const produtosMP = produtos.filter((p) => p.tipo === "MATERIA_PRIMA");

  function addMaterial() {
    setMateriais([...materiais, { produto_id: "", quantidade_necessaria: "1" }]);
  }

  function removeMaterial(i: number) {
    setMateriais(materiais.filter((_, idx) => idx !== i));
  }

  function updateMaterial(i: number, field: keyof MaterialForm, value: string) {
    const n = [...materiais];
    n[i] = { ...n[i], [field]: value };
    setMateriais(n);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.produto_id || !form.quantidade_planejada) {
      setErro("Preencha o produto e a quantidade planejada");
      return;
    }
    setSaving(true);
    setErro("");
    try {
      const r = await api.post("/producao/", {
        produto_id: Number(form.produto_id),
        quantidade_planejada: parseFloat(form.quantidade_planejada),
        data_planejada: form.data_planejada ? new Date(form.data_planejada).toISOString() : null,
        localizacao_saida_id: form.localizacao_saida_id ? Number(form.localizacao_saida_id) : null,
        observacoes: form.observacoes || null,
        materiais: materiais
          .filter((m) => m.produto_id)
          .map((m) => ({
            produto_id: Number(m.produto_id),
            quantidade_necessaria: parseFloat(m.quantidade_necessaria),
          })),
      });
      router.push("/producao");
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao criar OP");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <a href="/producao" className="text-gray-400 hover:text-gray-600">
          <ChevronLeft size={20} />
        </a>
        <h1 className="text-2xl font-bold">Nova Ordem de Produção</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="card p-6 space-y-4">
          <h2 className="font-semibold text-gray-700">Dados da OP</h2>

          <div>
            <label className="label">Produto a Produzir *</label>
            <select className="input" value={form.produto_id} required
              onChange={(e) => setForm({ ...form, produto_id: e.target.value })}>
              <option value="">Selecione o produto acabado...</option>
              {produtosPA.map((p) => (
                <option key={p.id} value={p.id}>{p.codigo} — {p.descricao}</option>
              ))}
              {produtosPA.length === 0 && produtos.map((p) => (
                <option key={p.id} value={p.id}>{p.codigo} — {p.descricao}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Quantidade Planejada *</label>
              <input className="input" type="number" step="0.001" min="0.001" required
                value={form.quantidade_planejada}
                onChange={(e) => setForm({ ...form, quantidade_planejada: e.target.value })} />
            </div>
            <div>
              <label className="label">Data Planejada</label>
              <input className="input" type="datetime-local" value={form.data_planejada}
                onChange={(e) => setForm({ ...form, data_planejada: e.target.value })} />
            </div>
          </div>

          <div>
            <label className="label">Localização de Saída (estoque produto acabado)</label>
            <select className="input" value={form.localizacao_saida_id}
              onChange={(e) => setForm({ ...form, localizacao_saida_id: e.target.value })}>
              <option value="">Selecione...</option>
              {localizacoes.map((l) => (
                <option key={l.id} value={l.id}>{l.codigo} — {l.descricao}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="label">Observações</label>
            <textarea className="input" rows={2} value={form.observacoes}
              onChange={(e) => setForm({ ...form, observacoes: e.target.value })} />
          </div>
        </div>

        {/* Lista de Materiais (BOM) */}
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-700">Materiais (BOM)</h2>
            <button type="button" onClick={addMaterial} className="text-amber-600 text-sm hover:underline flex items-center gap-1">
              <Plus size={14} /> Adicionar material
            </button>
          </div>

          {materiais.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">Nenhum material adicionado. A OP pode ser iniciada sem BOM.</p>
          )}

          <div className="space-y-3">
            {materiais.map((m, i) => (
              <div key={i} className="flex gap-3 items-end">
                <div className="flex-1">
                  {i === 0 && <label className="label">Matéria-Prima</label>}
                  <select className="input" value={m.produto_id}
                    onChange={(e) => updateMaterial(i, "produto_id", e.target.value)}>
                    <option value="">Selecione...</option>
                    {produtosMP.map((p) => (
                      <option key={p.id} value={p.id}>{p.codigo} — {p.descricao}</option>
                    ))}
                    {produtosMP.length === 0 && produtos.map((p) => (
                      <option key={p.id} value={p.id}>{p.codigo} — {p.descricao}</option>
                    ))}
                  </select>
                </div>
                <div className="w-32">
                  {i === 0 && <label className="label">Qtd Necessária</label>}
                  <input className="input" type="number" step="0.001" min="0.001"
                    value={m.quantidade_necessaria}
                    onChange={(e) => updateMaterial(i, "quantidade_necessaria", e.target.value)} />
                </div>
                <button type="button" onClick={() => removeMaterial(i)}
                  className="text-red-400 hover:text-red-600 pb-2">
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
          </div>
        </div>

        {erro && <p className="text-sm text-red-600 bg-red-50 p-3 rounded">{erro}</p>}

        <div className="flex justify-end gap-3">
          <a href="/producao" className="btn-secondary">Cancelar</a>
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "Criando..." : "Criar Ordem de Produção"}
          </button>
        </div>
      </form>
    </div>
  );
}
