"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import api from "@/lib/api";
import { ChevronLeft } from "lucide-react";

interface ItemLote {
  id: number;
  produto_enviado_id: number;
  produto_retorno_id: number | null;
  quantidade_enviada: number;
  retornado: boolean;
}

interface Lote {
  id: number;
  numero: string;
  prestador_id: number;
  tipo_beneficiamento: string | null;
  status: string;
  itens: ItemLote[];
}

interface Produto { id: number; codigo: string; descricao: string; }
interface Localizacao { id: number; codigo: string; descricao: string; }

interface ItemRetornoForm {
  item_id: number;
  quantidade_retornada: string;
  quantidade_rejeitada: string;
  localizacao_retorno_id: string;
  observacao: string;
}

export default function RetornoLotePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [lote, setLote] = useState<Lote | null>(null);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [localizacoes, setLocalizacoes] = useState<Localizacao[]>([]);

  const [form, setForm] = useState({
    data_retorno: new Date().toISOString().slice(0, 10),
    nf_retorno_numero: "",
    nf_retorno_chave: "",
    valor_servico: "0",
    valor_insumos: "0",
  });
  const [itensForm, setItensForm] = useState<ItemRetornoForm[]>([]);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api.get(`/beneficiamento/${id}`).then((r) => {
      const l: Lote = r.data;
      setLote(l);
      // Inicializa form de retorno com todos os itens pendentes
      const pendentes = (l.itens ?? []).filter((it) => !it.retornado);
      setItensForm(
        pendentes.map((it) => ({
          item_id: it.id,
          quantidade_retornada: String(it.quantidade_enviada),
          quantidade_rejeitada: "0",
          localizacao_retorno_id: "",
          observacao: "",
        }))
      );
    });
    api.get("/produtos/", { params: { limit: 200 } }).then((r) => setProdutos(r.data));
    api.get("/estoque/localizacoes").then((r) => setLocalizacoes(r.data)).catch(() => {});
  }, [id]);

  function nomeProduto(pid: number) {
    const p = produtos.find((p) => p.id === pid);
    return p ? `${p.codigo} — ${p.descricao}` : `Produto #${pid}`;
  }

  function updateItem(i: number, field: keyof ItemRetornoForm, value: string) {
    const n = [...itensForm];
    n[i] = { ...n[i], [field]: value };
    setItensForm(n);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErro("");
    try {
      await api.post(`/beneficiamento/${id}/retorno`, {
        data_retorno: form.data_retorno,
        nf_retorno_numero: form.nf_retorno_numero || null,
        nf_retorno_chave: form.nf_retorno_chave || null,
        valor_servico: parseFloat(form.valor_servico) || 0,
        valor_insumos: parseFloat(form.valor_insumos) || 0,
        itens: itensForm.map((it) => ({
          item_id: it.item_id,
          quantidade_retornada: parseFloat(it.quantidade_retornada) || 0,
          quantidade_rejeitada: parseFloat(it.quantidade_rejeitada) || 0,
          localizacao_retorno_id: it.localizacao_retorno_id ? Number(it.localizacao_retorno_id) : null,
          observacao: it.observacao || null,
        })),
      });
      router.push(`/beneficiamento/${id}`);
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao registrar retorno");
    } finally {
      setSaving(false);
    }
  }

  if (!lote) return <div className="text-gray-400">Carregando...</div>;

  const itensPendentes = (lote.itens ?? []).filter((it) => !it.retornado);

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <a href={`/beneficiamento/${id}`} className="text-gray-400 hover:text-gray-600">
          <ChevronLeft size={20} />
        </a>
        <div>
          <h1 className="text-2xl font-bold">Registrar Retorno</h1>
          <p className="text-sm text-gray-500 mt-0.5">{lote.numero} — {lote.tipo_beneficiamento || "Beneficiamento"}</p>
        </div>
      </div>

      {itensPendentes.length === 0 && (
        <div className="card p-8 text-center text-gray-400">
          Todos os itens deste lote já foram retornados.
        </div>
      )}

      {itensPendentes.length > 0 && (
        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Dados da NF de retorno */}
          <div className="card p-6 space-y-4">
            <h2 className="font-semibold text-gray-700">Dados do Retorno</h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">Data de Retorno *</label>
                <input className="input" type="date" required value={form.data_retorno}
                  onChange={(e) => setForm({ ...form, data_retorno: e.target.value })} />
              </div>
              <div>
                <label className="label">Nº da NF de Retorno</label>
                <input className="input font-mono" value={form.nf_retorno_numero}
                  onChange={(e) => setForm({ ...form, nf_retorno_numero: e.target.value })} />
              </div>
              <div>
                <label className="label">Valor do Serviço (R$)</label>
                <input className="input" type="number" step="0.01" min="0" value={form.valor_servico}
                  onChange={(e) => setForm({ ...form, valor_servico: e.target.value })} />
              </div>
              <div>
                <label className="label">Valor dos Insumos (R$)</label>
                <input className="input" type="number" step="0.01" min="0" value={form.valor_insumos}
                  onChange={(e) => setForm({ ...form, valor_insumos: e.target.value })} />
              </div>
            </div>
          </div>

          {/* Itens pendentes */}
          <div className="card p-6 space-y-4">
            <h2 className="font-semibold text-gray-700">
              Itens Pendentes ({itensPendentes.length})
            </h2>

            {itensForm.map((itemForm, i) => {
              const itemLote = itensPendentes.find((it) => it.id === itemForm.item_id)!;
              const maxRetorno = Number(itemLote.quantidade_enviada);
              return (
                <div key={itemForm.item_id} className="p-4 bg-gray-50 rounded-lg space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-sm">{nomeProduto(itemLote.produto_enviado_id)}</p>
                      {itemLote.produto_retorno_id && (
                        <p className="text-xs text-gray-500">
                          → Retorna como: {nomeProduto(itemLote.produto_retorno_id)}
                        </p>
                      )}
                    </div>
                    <span className="text-xs text-gray-500">
                      Enviado: <strong>{maxRetorno.toLocaleString("pt-BR")}</strong>
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="label">Qtd Retornada *</label>
                      <input className="input" type="number" step="0.001" min="0" max={maxRetorno}
                        value={itemForm.quantidade_retornada}
                        onChange={(e) => updateItem(i, "quantidade_retornada", e.target.value)} />
                    </div>
                    <div>
                      <label className="label">Qtd Rejeitada</label>
                      <input className="input" type="number" step="0.001" min="0"
                        value={itemForm.quantidade_rejeitada}
                        onChange={(e) => updateItem(i, "quantidade_rejeitada", e.target.value)} />
                    </div>
                    <div className="col-span-2">
                      <label className="label">Localização de Destino</label>
                      <select className="input" value={itemForm.localizacao_retorno_id}
                        onChange={(e) => updateItem(i, "localizacao_retorno_id", e.target.value)}>
                        <option value="">Localização original do lote</option>
                        {localizacoes.map((l) => (
                          <option key={l.id} value={l.id}>{l.codigo} — {l.descricao}</option>
                        ))}
                      </select>
                    </div>
                    <div className="col-span-2">
                      <label className="label">Observação</label>
                      <input className="input" placeholder="Ex: 3 peças com defeito superficial"
                        value={itemForm.observacao}
                        onChange={(e) => updateItem(i, "observacao", e.target.value)} />
                    </div>
                  </div>

                  {/* Indicador de perda */}
                  {parseFloat(itemForm.quantidade_retornada) + parseFloat(itemForm.quantidade_rejeitada) < maxRetorno && (
                    <p className="text-xs text-orange-600">
                      ⚠ Perda de{" "}
                      {(maxRetorno - parseFloat(itemForm.quantidade_retornada || "0") - parseFloat(itemForm.quantidade_rejeitada || "0")).toLocaleString("pt-BR")}{" "}
                      unidades não contabilizada
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          {erro && <p className="text-sm text-red-600 bg-red-50 p-3 rounded">{erro}</p>}

          <div className="flex justify-end gap-3">
            <a href={`/beneficiamento/${id}`} className="btn-secondary">Cancelar</a>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? "Registrando..." : "Confirmar Retorno"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
