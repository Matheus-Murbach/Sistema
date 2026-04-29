"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Plus, X, Trash2 } from "lucide-react";

interface PedidoCompra {
  id: number;
  numero: string;
  fornecedor_id: number;
  status: string;
  valor_total: number;
  data_emissao: string;
  data_previsao: string | null;
  condicao_pagamento: string | null;
}

interface Fornecedor {
  id: number;
  razao_social: string;
}

interface Produto {
  id: number;
  codigo: string;
  descricao: string;
}

interface ItemForm {
  produto_id: string;
  quantidade: string;
  preco_unitario: string;
}

const STATUS_BADGE: Record<string, string> = {
  ABERTO: "badge-blue",
  ENVIADO: "badge-yellow",
  RECEBIDO: "badge-green",
  CANCELADO: "badge-gray",
};

const STATUS_LABEL: Record<string, string> = {
  ABERTO: "Aberto",
  ENVIADO: "Enviado",
  RECEBIDO: "Recebido",
  CANCELADO: "Cancelado",
};

const FILTROS = ["TODOS", "ABERTO", "ENVIADO", "RECEBIDO"];

const EMPTY_FORM = {
  fornecedor_id: "",
  data_emissao: new Date().toISOString().slice(0, 10),
  data_previsao: "",
  condicao_pagamento: "",
  observacoes: "",
};

const EMPTY_ITEM: ItemForm = { produto_id: "", quantidade: "1", preco_unitario: "0" };

export default function ComprasPage() {
  const [pedidos, setPedidos] = useState<PedidoCompra[]>([]);
  const [fornecedores, setFornecedores] = useState<Fornecedor[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [filtro, setFiltro] = useState("TODOS");
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<Record<string, string>>(EMPTY_FORM);
  const [itens, setItens] = useState<ItemForm[]>([{ ...EMPTY_ITEM }]);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");

  const fetchPedidos = () => {
    const params: Record<string, string> = {};
    if (filtro !== "TODOS") params.status = filtro;
    api.get("/compras/", { params }).then((r) => setPedidos(r.data));
  };

  useEffect(() => { fetchPedidos(); }, [filtro]);

  useEffect(() => {
    api.get("/parceiros/fornecedores/", { params: { limit: 200 } }).then((r) => setFornecedores(r.data));
    api.get("/produtos/", { params: { limit: 200 } }).then((r) => setProdutos(r.data));
  }, []);

  function openNovo() {
    setForm({ ...EMPTY_FORM, data_emissao: new Date().toISOString().slice(0, 10) });
    setItens([{ ...EMPTY_ITEM }]);
    setErro("");
    setShowModal(true);
  }

  function addItem() {
    setItens([...itens, { ...EMPTY_ITEM }]);
  }

  function removeItem(i: number) {
    setItens(itens.filter((_, idx) => idx !== i));
  }

  function updateItem(i: number, field: keyof ItemForm, value: string) {
    const novo = [...itens];
    novo[i] = { ...novo[i], [field]: value };
    setItens(novo);
  }

  const totalPedido = itens.reduce((acc, it) => {
    return acc + (parseFloat(it.quantidade) || 0) * (parseFloat(it.preco_unitario) || 0);
  }, 0);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (itens.length === 0 || !itens[0].produto_id) {
      setErro("Adicione ao menos um item");
      return;
    }
    setSaving(true);
    setErro("");
    try {
      await api.post("/compras/", {
        fornecedor_id: Number(form.fornecedor_id),
        data_emissao: form.data_emissao,
        data_previsao: form.data_previsao || null,
        condicao_pagamento: form.condicao_pagamento || null,
        observacoes: form.observacoes || null,
        itens: itens.map((it) => ({
          produto_id: Number(it.produto_id),
          quantidade: parseFloat(it.quantidade),
          preco_unitario: parseFloat(it.preco_unitario),
        })),
      });
      setShowModal(false);
      fetchPedidos();
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao criar pedido");
    } finally {
      setSaving(false);
    }
  }

  async function atualizarStatus(id: number, status: string) {
    await api.put(`/compras/${id}/status`, null, { params: { novo_status: status } });
    fetchPedidos();
  }

  const moeda = (v: number) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Compras</h1>
        <button className="btn-primary" onClick={openNovo}>
          <Plus size={16} /> Novo Pedido
        </button>
      </div>

      {/* Filtros */}
      <div className="flex gap-2 mb-4">
        {FILTROS.map((f) => (
          <button
            key={f}
            onClick={() => setFiltro(f)}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              filtro === f
                ? "bg-primary-hover text-white"
                : "bg-white border text-gray-600 hover:bg-gray-50"
            }`}
          >
            {f === "TODOS" ? "Todos" : STATUS_LABEL[f]}
          </button>
        ))}
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3 font-medium text-gray-600">Número</th>
              <th className="text-left p-3 font-medium text-gray-600">Fornecedor</th>
              <th className="text-left p-3 font-medium text-gray-600">Emissão</th>
              <th className="text-left p-3 font-medium text-gray-600">Previsão</th>
              <th className="text-left p-3 font-medium text-gray-600">Status</th>
              <th className="text-right p-3 font-medium text-gray-600">Total</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {pedidos.map((p) => (
              <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3 font-mono text-xs font-bold">{p.numero}</td>
                <td className="p-3 text-gray-700">
                  {fornecedores.find((f) => f.id === p.fornecedor_id)?.razao_social ||
                    `Fornecedor #${p.fornecedor_id}`}
                </td>
                <td className="p-3">{new Date(p.data_emissao).toLocaleDateString("pt-BR")}</td>
                <td className="p-3 text-gray-500">
                  {p.data_previsao
                    ? new Date(p.data_previsao).toLocaleDateString("pt-BR")
                    : "—"}
                </td>
                <td className="p-3">
                  <span className={STATUS_BADGE[p.status] || "badge-gray"}>
                    {STATUS_LABEL[p.status] || p.status}
                  </span>
                </td>
                <td className="p-3 text-right font-medium">{moeda(Number(p.valor_total))}</td>
                <td className="p-3 text-right">
                  {p.status === "ABERTO" && (
                    <button
                      onClick={() => atualizarStatus(p.id, "ENVIADO")}
                      className="text-primary text-xs hover:underline mr-3"
                    >
                      Marcar Enviado
                    </button>
                  )}
                  {p.status === "ENVIADO" && (
                    <a
                      href="/recebimento"
                      className="text-success text-xs hover:underline mr-3"
                    >
                      Receber NF
                    </a>
                  )}
                </td>
              </tr>
            ))}
            {pedidos.length === 0 && (
              <tr>
                <td colSpan={7} className="p-8 text-center text-gray-400">
                  Nenhum pedido encontrado
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Modal Novo Pedido */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg">Novo Pedido de Compra</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="label">Fornecedor *</label>
                  <select className="input" value={form.fornecedor_id} required
                    onChange={(e) => setForm({ ...form, fornecedor_id: e.target.value })}>
                    <option value="">Selecione...</option>
                    {fornecedores.map((f) => (
                      <option key={f.id} value={f.id}>{f.razao_social}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Data de Emissão *</label>
                  <input className="input" type="date" value={form.data_emissao} required
                    onChange={(e) => setForm({ ...form, data_emissao: e.target.value })} />
                </div>
                <div>
                  <label className="label">Previsão de Entrega</label>
                  <input className="input" type="date" value={form.data_previsao}
                    onChange={(e) => setForm({ ...form, data_previsao: e.target.value })} />
                </div>
                <div>
                  <label className="label">Condição de Pagamento</label>
                  <input className="input" placeholder="Ex: 30/60 dias" value={form.condicao_pagamento}
                    onChange={(e) => setForm({ ...form, condicao_pagamento: e.target.value })} />
                </div>
                <div>
                  <label className="label">Observações</label>
                  <input className="input" value={form.observacoes}
                    onChange={(e) => setForm({ ...form, observacoes: e.target.value })} />
                </div>
              </div>

              {/* Itens */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <label className="label mb-0">Itens *</label>
                  <button type="button" onClick={addItem} className="text-primary text-xs hover:underline">
                    + Adicionar item
                  </button>
                </div>
                <div className="space-y-2">
                  {itens.map((item, i) => (
                    <div key={i} className="flex gap-2 items-end">
                      <div className="flex-1">
                        {i === 0 && <label className="label">Produto</label>}
                        <select className="input" value={item.produto_id}
                          onChange={(e) => updateItem(i, "produto_id", e.target.value)}>
                          <option value="">Selecione...</option>
                          {produtos.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.codigo} — {p.descricao}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="w-24">
                        {i === 0 && <label className="label">Qtd</label>}
                        <input className="input" type="number" step="0.001" min="0.001"
                          value={item.quantidade}
                          onChange={(e) => updateItem(i, "quantidade", e.target.value)} />
                      </div>
                      <div className="w-32">
                        {i === 0 && <label className="label">Preço Unit.</label>}
                        <input className="input" type="number" step="0.01" min="0"
                          value={item.preco_unitario}
                          onChange={(e) => updateItem(i, "preco_unitario", e.target.value)} />
                      </div>
                      <button type="button" onClick={() => removeItem(i)}
                        className="text-danger hover:text-danger pb-2">
                        <Trash2 size={16} />
                      </button>
                    </div>
                  ))}
                </div>
                <div className="text-right mt-2 text-sm font-medium text-gray-700">
                  Total: {moeda(totalPedido)}
                </div>
              </div>

              {erro && <p className="text-sm text-danger bg-danger-tint p-2 rounded">{erro}</p>}

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" className="btn-secondary" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? "Salvando..." : "Criar Pedido"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
