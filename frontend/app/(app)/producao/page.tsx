"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Zap, CheckCircle2 } from "lucide-react";

interface Produto { id: number; codigo: string; descricao: string; tipo: string; }
interface Localizacao { id: number; codigo: string; descricao: string; }
interface OP {
  id: number; numero: string; produto_id: number; status: string;
  quantidade_planejada: number; quantidade_produzida: number | null;
  criado_em: string;
}

export default function ProducaoPage() {
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [localizacoes, setLocalizacoes] = useState<Localizacao[]>([]);
  const [ops, setOps] = useState<OP[]>([]);
  const [converting, setConverting] = useState(false);
  const [sucesso, setSucesso] = useState("");
  const [erro, setErro] = useState("");

  const [conv, setConv] = useState({
    produto_mp_id: "",
    quantidade_mp: "1",
    produto_pa_id: "",
    quantidade_pa: "1",
    localizacao_mp_id: "",
    localizacao_pa_id: "",
    observacao: "",
  });

  const produtosMP = produtos.filter(p => p.tipo === "MATERIA_PRIMA");
  const produtosPA = produtos.filter(p => ["PRODUTO_ACABADO", "PRODUTO_BENEFICIADO", "SEMI_ACABADO", "REVENDA"].includes(p.tipo));

  useEffect(() => {
    api.get("/produtos/", { params: { limit: 200 } }).then(r => setProdutos(r.data));
    api.get("/estoque/localizacoes").then(r => setLocalizacoes(r.data));
    api.get("/producao/", { params: { status: "CONCLUIDA", limit: 30 } }).then(r => setOps(r.data));
  }, []);

  const prodNome = (id: number) => {
    const p = produtos.find(p => p.id === id);
    return p ? `${p.codigo} — ${p.descricao}` : String(id);
  };

  async function handleConverter(e: React.FormEvent) {
    e.preventDefault();
    if (!conv.produto_mp_id || !conv.produto_pa_id) { setErro("Selecione a MP e o PA"); return; }
    setConverting(true); setErro(""); setSucesso("");
    try {
      const res = await api.post("/producao/conversao-rapida", {
        produto_mp_id: Number(conv.produto_mp_id),
        localizacao_mp_id: conv.localizacao_mp_id ? Number(conv.localizacao_mp_id) : null,
        quantidade_mp: parseFloat(conv.quantidade_mp),
        produto_pa_id: Number(conv.produto_pa_id),
        localizacao_pa_id: conv.localizacao_pa_id ? Number(conv.localizacao_pa_id) : null,
        quantidade_pa: parseFloat(conv.quantidade_pa),
        observacao: conv.observacao || null,
      });
      setSucesso(`Conversão registrada: ${res.data.op_numero} — ${res.data.quantidade_pa_produzida} unidades de PA no estoque`);
      setConv({ produto_mp_id: "", quantidade_mp: "1", produto_pa_id: "", quantidade_pa: "1", localizacao_mp_id: "", localizacao_pa_id: "", observacao: "" });
      const r = await api.get("/producao/", { params: { status: "CONCLUIDA", limit: 30 } });
      setOps(r.data);
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro na conversão");
    } finally {
      setConverting(false);
    }
  }

  return (
    <div className="max-w-4xl">
      <div className="flex items-center gap-3 mb-6">
        <h1 className="text-2xl font-bold">PCP — Produção</h1>
      </div>

      {/* Formulário de conversão rápida */}
      <div className="card p-6 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Zap size={18} className="text-warning" />
          <h2 className="font-semibold text-gray-700">Conversão Rápida — MP → Produto Acabado</h2>
        </div>
        <form onSubmit={handleConverter} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            {/* MP */}
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Consome</h3>
              <div>
                <label className="label">Matéria-Prima *</label>
                <select className="input" required value={conv.produto_mp_id} onChange={e => setConv({ ...conv, produto_mp_id: e.target.value })}>
                  <option value="">Selecione a MP...</option>
                  {produtosMP.map(p => <option key={p.id} value={p.id}>{p.codigo} — {p.descricao}</option>)}
                </select>
              </div>
              <div>
                <label className="label">Quantidade MP *</label>
                <input className="input" type="number" step="0.001" min="0.001" required
                  value={conv.quantidade_mp} onChange={e => setConv({ ...conv, quantidade_mp: e.target.value })} />
              </div>
              <div>
                <label className="label">Localização (opcional)</label>
                <select className="input" value={conv.localizacao_mp_id} onChange={e => setConv({ ...conv, localizacao_mp_id: e.target.value })}>
                  <option value="">Automático</option>
                  {localizacoes.map(l => <option key={l.id} value={l.id}>{l.codigo}</option>)}
                </select>
              </div>
            </div>
            {/* PA */}
            <div className="space-y-3">
              <h3 className="text-sm font-medium text-gray-500 uppercase tracking-wide">Produz</h3>
              <div>
                <label className="label">Produto Acabado *</label>
                <select className="input" required value={conv.produto_pa_id} onChange={e => setConv({ ...conv, produto_pa_id: e.target.value })}>
                  <option value="">Selecione o PA...</option>
                  {produtosPA.map(p => <option key={p.id} value={p.id}>{p.codigo} — {p.descricao}</option>)}
                </select>
              </div>
              <div>
                <label className="label">Quantidade PA *</label>
                <input className="input" type="number" step="0.001" min="0.001" required
                  value={conv.quantidade_pa} onChange={e => setConv({ ...conv, quantidade_pa: e.target.value })} />
              </div>
              <div>
                <label className="label">Localização destino (opcional)</label>
                <select className="input" value={conv.localizacao_pa_id} onChange={e => setConv({ ...conv, localizacao_pa_id: e.target.value })}>
                  <option value="">Mesma da MP</option>
                  {localizacoes.map(l => <option key={l.id} value={l.id}>{l.codigo}</option>)}
                </select>
              </div>
            </div>
          </div>
          <div>
            <label className="label">Observação</label>
            <input className="input" value={conv.observacao} onChange={e => setConv({ ...conv, observacao: e.target.value })} placeholder="Ex: turno da tarde, máquina 02..." />
          </div>
          {erro && <p className="text-sm text-danger bg-danger-tint p-3 rounded">{erro}</p>}
          {sucesso && (
            <div className="flex items-center gap-2 text-sm text-success-dark bg-success-tint p-3 rounded">
              <CheckCircle2 size={16} /> {sucesso}
            </div>
          )}
          <div className="flex justify-end">
            <button type="submit" className="btn-primary flex items-center gap-2" disabled={converting}>
              <Zap size={15} /> {converting ? "Convertendo..." : "Converter Agora"}
            </button>
          </div>
        </form>
      </div>

      {/* Histórico */}
      <div className="card">
        <div className="p-4 border-b">
          <h2 className="font-semibold text-gray-700">Conversões Recentes</h2>
        </div>
        {ops.length === 0 ? (
          <p className="p-6 text-center text-gray-400">Nenhuma conversão registrada ainda.</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-gray-500 font-medium">OP</th>
                <th className="px-4 py-2 text-left text-gray-500 font-medium">Produto Acabado</th>
                <th className="px-4 py-2 text-right text-gray-500 font-medium">Qtd Produzida</th>
                <th className="px-4 py-2 text-left text-gray-500 font-medium">Data</th>
                <th className="px-4 py-2 text-left text-gray-500 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {ops.map(op => (
                <tr key={op.id} className="border-t hover:bg-gray-50">
                  <td className="px-4 py-2 font-mono text-xs">{op.numero}</td>
                  <td className="px-4 py-2 text-gray-700">{prodNome(op.produto_id)}</td>
                  <td className="px-4 py-2 text-right font-semibold">{op.quantidade_produzida ?? op.quantidade_planejada}</td>
                  <td className="px-4 py-2 text-gray-500">{new Date(op.criado_em).toLocaleDateString("pt-BR")}</td>
                  <td className="px-4 py-2">
                    <span className="badge-green text-xs">CONCLUÍDA</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
