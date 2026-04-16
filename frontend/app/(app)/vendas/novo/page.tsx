"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import { ChevronLeft, Plus, Trash2 } from "lucide-react";

interface Cliente { id: number; razao_social: string; }
interface Produto { id: number; codigo: string; descricao: string; preco_venda: number; }

interface ItemForm {
  produto_id: string;
  quantidade: string;
  preco_unitario: string;
  desconto_percent: string;
}

export default function NovoVendaPage() {
  const router = useRouter();
  const [clientes, setClientes] = useState<Cliente[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);

  const [form, setForm] = useState({
    cliente_id: "",
    data_emissao: new Date().toISOString().slice(0, 10),
    data_previsao_entrega: "",
    condicao_pagamento: "",
    transportadora: "",
    frete_por_conta: "0",
    valor_frete: "0",
    observacoes: "",
  });
  const [itens, setItens] = useState<ItemForm[]>([
    { produto_id: "", quantidade: "1", preco_unitario: "0", desconto_percent: "0" },
  ]);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");

  useEffect(() => {
    api.get("/parceiros/clientes/", { params: { limit: 200 } }).then((r) => setClientes(r.data));
    api.get("/produtos/", { params: { limit: 200 } }).then((r) => setProdutos(r.data));
  }, []);

  function addItem() {
    setItens([...itens, { produto_id: "", quantidade: "1", preco_unitario: "0", desconto_percent: "0" }]);
  }

  function removeItem(i: number) {
    setItens(itens.filter((_, idx) => idx !== i));
  }

  function updateItem(i: number, field: keyof ItemForm, value: string) {
    const n = [...itens];
    n[i] = { ...n[i], [field]: value };
    // Auto-preenche preço quando produto é selecionado
    if (field === "produto_id") {
      const p = produtos.find((p) => String(p.id) === value);
      if (p) n[i].preco_unitario = String(p.preco_venda);
    }
    setItens(n);
  }

  const totalItens = itens.reduce((acc, it) => {
    const base = (parseFloat(it.quantidade) || 0) * (parseFloat(it.preco_unitario) || 0);
    const desc = base * ((parseFloat(it.desconto_percent) || 0) / 100);
    return acc + base - desc;
  }, 0);

  const totalGeral = totalItens + (parseFloat(form.valor_frete) || 0);

  const moeda = (v: number) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.cliente_id) { setErro("Selecione o cliente"); return; }
    if (!itens[0]?.produto_id) { setErro("Adicione ao menos um item"); return; }
    setSaving(true);
    setErro("");
    try {
      await api.post("/vendas/", {
        cliente_id: Number(form.cliente_id),
        data_emissao: form.data_emissao,
        data_previsao_entrega: form.data_previsao_entrega || null,
        condicao_pagamento: form.condicao_pagamento || null,
        transportadora: form.transportadora || null,
        frete_por_conta: form.frete_por_conta,
        valor_frete: parseFloat(form.valor_frete) || 0,
        observacoes: form.observacoes || null,
        itens: itens
          .filter((it) => it.produto_id)
          .map((it) => ({
            produto_id: Number(it.produto_id),
            quantidade: parseFloat(it.quantidade),
            preco_unitario: parseFloat(it.preco_unitario),
            desconto_percent: parseFloat(it.desconto_percent) || 0,
          })),
      });
      router.push("/vendas");
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao criar pedido");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-3xl">
      <div className="flex items-center gap-3 mb-6">
        <a href="/vendas" className="text-gray-400 hover:text-gray-600">
          <ChevronLeft size={20} />
        </a>
        <h1 className="text-2xl font-bold">Novo Pedido de Venda</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Cabeçalho */}
        <div className="card p-6 space-y-4">
          <h2 className="font-semibold text-gray-700">Dados do Pedido</h2>

          <div>
            <label className="label">Cliente *</label>
            <select className="input" value={form.cliente_id} required
              onChange={(e) => setForm({ ...form, cliente_id: e.target.value })}>
              <option value="">Selecione o cliente...</option>
              {clientes.map((c) => (
                <option key={c.id} value={c.id}>{c.razao_social}</option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Data de Emissão *</label>
              <input className="input" type="date" value={form.data_emissao} required
                onChange={(e) => setForm({ ...form, data_emissao: e.target.value })} />
            </div>
            <div>
              <label className="label">Previsão de Entrega</label>
              <input className="input" type="date" value={form.data_previsao_entrega}
                onChange={(e) => setForm({ ...form, data_previsao_entrega: e.target.value })} />
            </div>
            <div>
              <label className="label">Condição de Pagamento</label>
              <input className="input" placeholder="Ex: 30/60 DDL" value={form.condicao_pagamento}
                onChange={(e) => setForm({ ...form, condicao_pagamento: e.target.value })} />
            </div>
            <div>
              <label className="label">Transportadora</label>
              <input className="input" value={form.transportadora}
                onChange={(e) => setForm({ ...form, transportadora: e.target.value })} />
            </div>
            <div>
              <label className="label">Frete por Conta</label>
              <select className="input" value={form.frete_por_conta}
                onChange={(e) => setForm({ ...form, frete_por_conta: e.target.value })}>
                <option value="0">0 — Emitente</option>
                <option value="1">1 — Destinatário</option>
                <option value="9">9 — Sem frete</option>
              </select>
            </div>
            <div>
              <label className="label">Valor do Frete</label>
              <input className="input" type="number" step="0.01" min="0" value={form.valor_frete}
                onChange={(e) => setForm({ ...form, valor_frete: e.target.value })} />
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
            <h2 className="font-semibold text-gray-700">Itens do Pedido</h2>
            <button type="button" onClick={addItem}
              className="text-blue-600 text-sm hover:underline flex items-center gap-1">
              <Plus size={14} /> Adicionar item
            </button>
          </div>

          <div className="space-y-3">
            {itens.map((item, i) => (
              <div key={i} className="p-3 bg-gray-50 rounded-lg">
                <div className="flex gap-2 items-end">
                  <div className="flex-1">
                    {i === 0 && <label className="label">Produto</label>}
                    <select className="input" value={item.produto_id}
                      onChange={(e) => updateItem(i, "produto_id", e.target.value)}>
                      <option value="">Selecione...</option>
                      {produtos.map((p) => (
                        <option key={p.id} value={p.id}>{p.codigo} — {p.descricao}</option>
                      ))}
                    </select>
                  </div>
                  <div className="w-24">
                    {i === 0 && <label className="label">Qtd</label>}
                    <input className="input" type="number" step="0.001" min="0.001" value={item.quantidade}
                      onChange={(e) => updateItem(i, "quantidade", e.target.value)} />
                  </div>
                  <div className="w-32">
                    {i === 0 && <label className="label">Preço Unit.</label>}
                    <input className="input" type="number" step="0.01" min="0" value={item.preco_unitario}
                      onChange={(e) => updateItem(i, "preco_unitario", e.target.value)} />
                  </div>
                  <div className="w-24">
                    {i === 0 && <label className="label">Desc. %</label>}
                    <input className="input" type="number" step="0.01" min="0" max="100" value={item.desconto_percent}
                      onChange={(e) => updateItem(i, "desconto_percent", e.target.value)} />
                  </div>
                  <div className="w-28 text-right">
                    {i === 0 && <label className="label">Subtotal</label>}
                    <div className="py-2 text-sm font-medium">
                      {moeda(
                        (parseFloat(item.quantidade) || 0) *
                        (parseFloat(item.preco_unitario) || 0) *
                        (1 - (parseFloat(item.desconto_percent) || 0) / 100)
                      )}
                    </div>
                  </div>
                  <button type="button" onClick={() => removeItem(i)}
                    className="text-red-400 hover:text-red-600 pb-2">
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 pt-4 border-t space-y-1 text-sm text-right">
            <div className="text-gray-500">Produtos: {moeda(totalItens)}</div>
            <div className="text-gray-500">Frete: {moeda(parseFloat(form.valor_frete) || 0)}</div>
            <div className="text-lg font-bold text-gray-900">Total: {moeda(totalGeral)}</div>
          </div>
        </div>

        {erro && <p className="text-sm text-red-600 bg-red-50 p-3 rounded">{erro}</p>}

        <div className="flex justify-end gap-3">
          <a href="/vendas" className="btn-secondary">Cancelar</a>
          <button type="submit" className="btn-primary" disabled={saving}>
            {saving ? "Criando..." : "Criar Orçamento"}
          </button>
        </div>
      </form>
    </div>
  );
}
