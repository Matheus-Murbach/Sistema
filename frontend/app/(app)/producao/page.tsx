"use client";
import { useEffect, useState } from "react";
import api from "@/lib/api";
import { Plus, X, Play, CheckCircle2 } from "lucide-react";

interface OrdemProducao {
  id: number;
  numero: string;
  produto_id: number;
  maquina_id: number | null;
  quantidade_planejada: number;
  quantidade_produzida: number | null;
  quantidade_refugo: number | null;
  status: string;
  data_planejada: string | null;
  data_inicio: string | null;
  data_conclusao: string | null;
}

interface Produto { id: number; codigo: string; descricao: string; }
interface Localizacao { id: number; codigo: string; descricao: string; }

interface ConsumoForm { produto_id: string; localizacao_id: string; quantidade: string; }

const STATUS_BADGE: Record<string, string> = {
  ABERTA: "badge-blue",
  EM_PRODUCAO: "badge-yellow",
  CONCLUIDA: "badge-green",
  CANCELADA: "badge-gray",
};

const STATUS_LABEL: Record<string, string> = {
  ABERTA: "Aberta",
  EM_PRODUCAO: "Em Produção",
  CONCLUIDA: "Concluída",
  CANCELADA: "Cancelada",
};

const FILTROS = ["TODOS", "ABERTA", "EM_PRODUCAO", "CONCLUIDA"];

export default function ProducaoPage() {
  const [ops, setOps] = useState<OrdemProducao[]>([]);
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [localizacoes, setLocalizacoes] = useState<Localizacao[]>([]);
  const [filtro, setFiltro] = useState("TODOS");

  // Modal Iniciar OP
  const [opIniciar, setOpIniciar] = useState<OrdemProducao | null>(null);
  const [consumos, setConsumos] = useState<ConsumoForm[]>([{ produto_id: "", localizacao_id: "", quantidade: "1" }]);

  // Modal Concluir OP
  const [opConcluir, setOpConcluir] = useState<OrdemProducao | null>(null);
  const [qtdProduzida, setQtdProduzida] = useState("");
  const [qtdRefugo, setQtdRefugo] = useState("0");
  const [locSaida, setLocSaida] = useState("");

  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");

  const fetchOps = () => {
    const params: Record<string, string> = {};
    if (filtro !== "TODOS") params.status = filtro;
    api.get("/producao/", { params }).then((r) => setOps(r.data));
  };

  useEffect(() => { fetchOps(); }, [filtro]);

  useEffect(() => {
    api.get("/produtos/", { params: { limit: 200 } }).then((r) => setProdutos(r.data));
    api.get("/estoque/localizacoes").then((r) => setLocalizacoes(r.data)).catch(() => {});
  }, []);

  function nomeProduto(id: number) {
    const p = produtos.find((p) => p.id === id);
    return p ? `${p.codigo} — ${p.descricao}` : `Produto #${id}`;
  }

  // Iniciar OP
  function abrirIniciar(op: OrdemProducao) {
    setOpIniciar(op);
    setConsumos([{ produto_id: "", localizacao_id: "", quantidade: "1" }]);
    setErro("");
  }

  async function handleIniciar(e: React.FormEvent) {
    e.preventDefault();
    if (!opIniciar) return;
    setSaving(true);
    setErro("");
    try {
      await api.post(`/producao/${opIniciar.id}/iniciar`, consumos.map((c) => ({
        produto_id: Number(c.produto_id),
        localizacao_id: Number(c.localizacao_id) || 1,
        quantidade: parseFloat(c.quantidade),
      })));
      setOpIniciar(null);
      fetchOps();
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao iniciar OP");
    } finally {
      setSaving(false);
    }
  }

  // Concluir OP
  function abrirConcluir(op: OrdemProducao) {
    setOpConcluir(op);
    setQtdProduzida(String(op.quantidade_planejada));
    setQtdRefugo("0");
    setLocSaida("");
    setErro("");
  }

  async function handleConcluir(e: React.FormEvent) {
    e.preventDefault();
    if (!opConcluir) return;
    setSaving(true);
    setErro("");
    try {
      await api.post(`/producao/${opConcluir.id}/concluir`, {
        quantidade_produzida: parseFloat(qtdProduzida),
        quantidade_refugo: parseFloat(qtdRefugo) || 0,
        localizacao_saida_id: locSaida ? Number(locSaida) : null,
      });
      setOpConcluir(null);
      fetchOps();
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao concluir OP");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">PCP — Produção</h1>
        <a href="/producao/nova" className="btn-primary">
          <Plus size={16} /> Nova OP
        </a>
      </div>

      <div className="flex gap-2 mb-4">
        {FILTROS.map((f) => (
          <button key={f} onClick={() => setFiltro(f)}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              filtro === f ? "bg-blue-700 text-white" : "bg-white border text-gray-600 hover:bg-gray-50"
            }`}>
            {f === "TODOS" ? "Todas" : STATUS_LABEL[f]}
          </button>
        ))}
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3 font-medium text-gray-600">OP</th>
              <th className="text-left p-3 font-medium text-gray-600">Produto</th>
              <th className="text-right p-3 font-medium text-gray-600">Qtd Plan.</th>
              <th className="text-right p-3 font-medium text-gray-600">Produzido</th>
              <th className="text-left p-3 font-medium text-gray-600">Status</th>
              <th className="text-left p-3 font-medium text-gray-600">Data</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {ops.map((op) => (
              <tr key={op.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3 font-mono text-xs font-bold">{op.numero}</td>
                <td className="p-3">{nomeProduto(op.produto_id)}</td>
                <td className="p-3 text-right">{Number(op.quantidade_planejada).toLocaleString("pt-BR")}</td>
                <td className="p-3 text-right text-gray-500">
                  {op.quantidade_produzida != null
                    ? Number(op.quantidade_produzida).toLocaleString("pt-BR")
                    : "—"}
                </td>
                <td className="p-3">
                  <span className={STATUS_BADGE[op.status] || "badge-gray"}>
                    {STATUS_LABEL[op.status] || op.status}
                  </span>
                </td>
                <td className="p-3 text-gray-500">
                  {op.data_planejada
                    ? new Date(op.data_planejada).toLocaleDateString("pt-BR")
                    : "—"}
                </td>
                <td className="p-3 text-right flex gap-2 justify-end">
                  {op.status === "ABERTA" && (
                    <button onClick={() => abrirIniciar(op)}
                      className="flex items-center gap-1 text-blue-600 text-xs hover:underline">
                      <Play size={12} /> Iniciar
                    </button>
                  )}
                  {op.status === "EM_PRODUCAO" && (
                    <button onClick={() => abrirConcluir(op)}
                      className="flex items-center gap-1 text-green-600 text-xs hover:underline">
                      <CheckCircle2 size={12} /> Concluir
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {ops.length === 0 && (
              <tr>
                <td colSpan={7} className="p-8 text-center text-gray-400">
                  Nenhuma ordem de produção encontrada
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Modal Iniciar OP */}
      {opIniciar && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-lg p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg">Iniciar OP — {opIniciar.numero}</h2>
              <button onClick={() => setOpIniciar(null)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            <p className="text-sm text-gray-500 mb-4">
              Informe os materiais a serem consumidos do estoque agora.
            </p>
            <form onSubmit={handleIniciar} className="space-y-3">
              {consumos.map((c, i) => (
                <div key={i} className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="label">Produto (MP)</label>
                    <select className="input" value={c.produto_id}
                      onChange={(e) => {
                        const n = [...consumos]; n[i].produto_id = e.target.value; setConsumos(n);
                      }}>
                      <option value="">Selecione...</option>
                      {produtos.map((p) => (
                        <option key={p.id} value={p.id}>{p.codigo} — {p.descricao}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="label">Localização</label>
                    <select className="input" value={c.localizacao_id}
                      onChange={(e) => {
                        const n = [...consumos]; n[i].localizacao_id = e.target.value; setConsumos(n);
                      }}>
                      <option value="">Selecione...</option>
                      {localizacoes.map((l) => (
                        <option key={l.id} value={l.id}>{l.codigo}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label className="label">Quantidade</label>
                    <input className="input" type="number" step="0.001" value={c.quantidade}
                      onChange={(e) => {
                        const n = [...consumos]; n[i].quantidade = e.target.value; setConsumos(n);
                      }} />
                  </div>
                </div>
              ))}
              <button type="button" onClick={() => setConsumos([...consumos, { produto_id: "", localizacao_id: "", quantidade: "1" }])}
                className="text-blue-600 text-xs hover:underline">
                + Adicionar material
              </button>

              {erro && <p className="text-sm text-red-600 bg-red-50 p-2 rounded">{erro}</p>}

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" className="btn-secondary" onClick={() => setOpIniciar(null)}>Cancelar</button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? "Iniciando..." : "Iniciar OP"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal Concluir OP */}
      {opConcluir && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg">Concluir OP — {opConcluir.numero}</h2>
              <button onClick={() => setOpConcluir(null)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleConcluir} className="space-y-4">
              <div>
                <label className="label">Qtd Produzida *</label>
                <input className="input" type="number" step="0.001" required
                  value={qtdProduzida} onChange={(e) => setQtdProduzida(e.target.value)} />
              </div>
              <div>
                <label className="label">Qtd Refugo</label>
                <input className="input" type="number" step="0.001" min="0"
                  value={qtdRefugo} onChange={(e) => setQtdRefugo(e.target.value)} />
              </div>
              <div>
                <label className="label">Localização de Saída *</label>
                <select className="input" required value={locSaida} onChange={(e) => setLocSaida(e.target.value)}>
                  <option value="">Selecione...</option>
                  {localizacoes.map((l) => (
                    <option key={l.id} value={l.id}>{l.codigo} — {l.descricao}</option>
                  ))}
                </select>
              </div>

              {erro && <p className="text-sm text-red-600 bg-red-50 p-2 rounded">{erro}</p>}

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" className="btn-secondary" onClick={() => setOpConcluir(null)}>Cancelar</button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? "Concluindo..." : "Concluir OP"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
