"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { ChevronLeft, Plus, Trash2 } from "lucide-react";

interface Prestador { id: number; razao_social: string; tipo_beneficiamento: string | null; }
interface Produto { id: number; codigo: string; descricao: string; }
interface Localizacao { id: number; codigo: string; descricao: string; }

interface ItemForm {
  produto_enviado_id: string;
  produto_retorno_id: string;
  localizacao_saida_id: string;
  localizacao_retorno_id: string;
  quantidade_enviada: string;
}

const EMPTY_ITEM: ItemForm = {
  produto_enviado_id: "",
  produto_retorno_id: "",
  localizacao_saida_id: "",
  localizacao_retorno_id: "",
  quantidade_enviada: "1",
};

export default function NovoBeneficiamentoPage() {
  const router = useRouter();
  const [prestadores, setPrestadores] = useState<Prestador[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [localizacoes, setLocalizacoes] = useState<Localizacao[]>([]);

  const [form, setForm] = useState({
    prestador_id: "",
    tipo_beneficiamento: "",
    data_remessa: new Date().toISOString().slice(0, 10),
    data_previsao_retorno: "",
    cfop_remessa: "5901",
    cfop_retorno: "5902",
    observacoes: "",
  });
  const [itens, setItens] = useState<ItemForm[]>([{ ...EMPTY_ITEM }]);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api.get("/parceiros/prestadores/", { params: { limit: 200 } }).then((r) => setPrestadores(r.data));
    api.get("/produtos/", { params: { limit: 200 } }).then((r) => setProdutos(r.data));
    api.get("/estoque/localizacoes").then((r) => setLocalizacoes(r.data)).catch(() => {});
  }, []);

  // Auto-preenche tipo_beneficiamento ao selecionar prestador
  function onPrestadorChange(id: string) {
    const p = prestadores.find((p) => String(p.id) === id);
    setForm({ ...form, prestador_id: id, tipo_beneficiamento: p?.tipo_beneficiamento || "" });
  }

  function addItem() { setItens([...itens, { ...EMPTY_ITEM }]); }
  function removeItem(i: number) { setItens(itens.filter((_, idx) => idx !== i)); }
  function updateItem(i: number, field: keyof ItemForm, value: string) {
    const n = [...itens];
    n[i] = { ...n[i], [field]: value };
    setItens(n);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.prestador_id) { setErro("Selecione o prestador de beneficiamento"); return; }
    if (!itens[0]?.produto_enviado_id) { setErro("Adicione ao menos um item"); return; }
    setSaving(true);
    setErro("");
    try {
      await api.post("/beneficiamento/", {
        prestador_id: Number(form.prestador_id),
        tipo_beneficiamento: form.tipo_beneficiamento || null,
        data_remessa: form.data_remessa,
        data_previsao_retorno: form.data_previsao_retorno || null,
        cfop_remessa: form.cfop_remessa,
        cfop_retorno: form.cfop_retorno,
        observacoes: form.observacoes || null,
        itens: itens
          .filter((it) => it.produto_enviado_id)
          .map((it) => ({
            produto_enviado_id: Number(it.produto_enviado_id),
            produto_retorno_id: it.produto_retorno_id ? Number(it.produto_retorno_id) : null,
            localizacao_saida_id: Number(it.localizacao_saida_id) || 1,
            localizacao_retorno_id: it.localizacao_retorno_id ? Number(it.localizacao_retorno_id) : null,
            quantidade_enviada: parseFloat(it.quantidade_enviada),
          })),
      });
      router.push("/beneficiamento");
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao criar lote");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <a href="/beneficiamento" className="text-muted hover:text-gray-600">
          <ChevronLeft size={20} />
        </a>
        <h1 className="text-2xl font-bold">Novo Lote de Beneficiamento</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Cabeçalho do lote */}
        <div className="card p-6 space-y-4">
          <h2 className="font-semibold text-gray-700">Dados da Remessa</h2>

          <div>
            <label className="label">Prestador de Beneficiamento *</label>
            <select className="input" value={form.prestador_id} required
              onChange={(e) => onPrestadorChange(e.target.value)}>
              <option value="">Selecione o prestador...</option>
              {prestadores.map((p) => (
                <option key={p.id} value={p.id}>{p.razao_social}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Tipo de Beneficiamento</label>
              <input className="input" placeholder="Ex: Niquelação, Galvanização, Zinco"
                value={form.tipo_beneficiamento}
                onChange={(e) => setForm({ ...form, tipo_beneficiamento: e.target.value })} />
            </div>
            <div>
              <label className="label">Data de Remessa *</label>
              <input className="input" type="date" required value={form.data_remessa}
                onChange={(e) => setForm({ ...form, data_remessa: e.target.value })} />
            </div>
            <div>
              <label className="label">Previsão de Retorno</label>
              <input className="input" type="date" value={form.data_previsao_retorno}
                onChange={(e) => setForm({ ...form, data_previsao_retorno: e.target.value })} />
            </div>
            <div>
              <label className="label">CFOP Remessa</label>
              <input className="input font-mono" value={form.cfop_remessa}
                onChange={(e) => setForm({ ...form, cfop_remessa: e.target.value })} />
            </div>
          </div>

          <div>
            <label className="label">Observações</label>
            <textarea className="input" rows={2} value={form.observacoes}
              onChange={(e) => setForm({ ...form, observacoes: e.target.value })} />
          </div>
        </div>

        {/* Itens */}
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-700">Itens para Beneficiar</h2>
            <button type="button" onClick={addItem}
              className="text-primary text-sm hover:underline flex items-center gap-1">
              <Plus size={14} /> Adicionar item
            </button>
          </div>

          <div className="space-y-4">
            {itens.map((item, i) => (
              <div key={i} className="p-4 bg-page rounded-lg space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-muted">Item {i + 1}</span>
                  {itens.length > 1 && (
                    <button type="button" onClick={() => removeItem(i)}
                      className="text-danger hover:text-danger">
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="label">Produto Enviado (bruto) *</label>
                    <select className="input" value={item.produto_enviado_id}
                      onChange={(e) => updateItem(i, "produto_enviado_id", e.target.value)}>
                      <option value="">Selecione...</option>
                      {produtos.map((p) => (
                        <option key={p.id} value={p.id}>{p.codigo} — {p.descricao}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="label">Produto de Retorno (beneficiado)</label>
                    <select className="input" value={item.produto_retorno_id}
                      onChange={(e) => updateItem(i, "produto_retorno_id", e.target.value)}>
                      <option value="">Mesmo produto</option>
                      {produtos.map((p) => (
                        <option key={p.id} value={p.id}>{p.codigo} — {p.descricao}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="label">Localização de Saída *</label>
                    <select className="input" value={item.localizacao_saida_id}
                      onChange={(e) => updateItem(i, "localizacao_saida_id", e.target.value)}>
                      <option value="">Selecione...</option>
                      {localizacoes.map((l) => (
                        <option key={l.id} value={l.id}>{l.codigo} — {l.descricao}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="label">Localização de Retorno</label>
                    <select className="input" value={item.localizacao_retorno_id}
                      onChange={(e) => updateItem(i, "localizacao_retorno_id", e.target.value)}>
                      <option value="">Mesma localização</option>
                      {localizacoes.map((l) => (
                        <option key={l.id} value={l.id}>{l.codigo} — {l.descricao}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="label">Quantidade Enviada *</label>
                    <input className="input" type="number" step="0.001" min="0.001"
                      value={item.quantidade_enviada}
                      onChange={(e) => updateItem(i, "quantidade_enviada", e.target.value)} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {erro && <p className="text-sm text-danger bg-danger-tint p-3 rounded">{erro}</p>}

        <div className="flex justify-end gap-3">
          <a href="/beneficiamento" className="btn-secondary">Cancelar</a>
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "Criando..." : "Criar Lote e Enviar para Banho"}
          </button>
        </div>
      </form>
    </div>
  );
}
