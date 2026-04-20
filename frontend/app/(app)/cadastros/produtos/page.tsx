"use client";
import { useEffect, useRef, useState } from "react";
import api from "@/lib/api";
import { Search, Plus, X, ChevronLeft, Upload, Download, ChevronDown, ChevronUp } from "lucide-react";

interface Produto {
  id: number;
  codigo: string;
  descricao: string;
  tipo: string;
  unidade_id: number;
  ncm: string | null;
  preco_venda: number;
  estoque_minimo: number;
  aliq_icms: number;
  aliq_ipi: number;
  aliq_pis: number;
  aliq_cofins: number;
  ativo: boolean;
}

interface UnidadeMedida {
  id: number;
  codigo: string;
  descricao: string;
}

const TIPOS = [
  { value: "MATERIA_PRIMA", label: "Matéria-Prima" },
  { value: "PRODUTO_ACABADO", label: "Produto Acabado" },
  { value: "PRODUTO_BENEFICIADO", label: "Produto Beneficiado" },
  { value: "SEMI_ACABADO", label: "Semi-Acabado" },
  { value: "REVENDA", label: "Revenda" },
];

const TIPO_BADGE: Record<string, string> = {
  MATERIA_PRIMA: "badge-blue",
  PRODUTO_ACABADO: "badge-green",
  PRODUTO_BENEFICIADO: "badge-green",
  SEMI_ACABADO: "badge-yellow",
  REVENDA: "badge-gray",
};

const TIPO_LABEL: Record<string, string> = {
  MATERIA_PRIMA: "MP",
  PRODUTO_ACABADO: "PA",
  PRODUTO_BENEFICIADO: "PB",
  SEMI_ACABADO: "SA",
  REVENDA: "RV",
};

const EMPTY_FORM = {
  codigo: "",
  descricao: "",
  tipo: "MATERIA_PRIMA",
  unidade_id: "",
  ncm: "",
  codigo_barras: "",
  preco_custo: "0",
  preco_venda: "0",
  estoque_minimo: "0",
  estoque_maximo: "0",
  aliq_icms: "0",
  aliq_ipi: "0",
  aliq_pis: "0.65",
  aliq_cofins: "3.00",
};

const CSV_HEADER = "codigo,descricao,tipo,unidade,preco_custo,preco_venda,estoque_minimo,aliq_icms,aliq_ipi,aliq_pis,aliq_cofins,ncm";
const CSV_EXEMPLO = [
  "MP-001,Aco 1020 Barra,MATERIA_PRIMA,KG,5.50,0,10,12,0,0.65,3,",
  "PA-001,Parafuso Zincado M8,PRODUTO_ACABADO,UN,0,25.00,50,12,0,0.65,3,73181600",
  "RV-001,Produto Revenda XYZ,REVENDA,UN,10,18.00,5,12,0,0.65,3,",
].join("\n");

function parseCsv(text: string): Record<string, string>[] {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return [];
  const headers = lines[0].split(",").map((h) => h.trim().replace(/^"|"$/g, ""));
  return lines.slice(1).filter((l) => l.trim()).map((line) => {
    const cols: string[] = [];
    let cur = "";
    let inQuote = false;
    for (const ch of line) {
      if (ch === '"') { inQuote = !inQuote; continue; }
      if (ch === "," && !inQuote) { cols.push(cur); cur = ""; continue; }
      cur += ch;
    }
    cols.push(cur);
    return Object.fromEntries(headers.map((h, i) => [h, (cols[i] ?? "").trim()]));
  });
}

export default function ProdutosPage() {
  const [produtos, setProdutos] = useState<Produto[]>([]);
  const [unidades, setUnidades] = useState<UnidadeMedida[]>([]);
  const [busca, setBusca] = useState("");
  const [showModal, setShowModal] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [form, setForm] = useState<Record<string, string>>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");
  const [showFiscal, setShowFiscal] = useState(false);
  const [ncmDescricao, setNcmDescricao] = useState("");
  const [ncmLoading, setNcmLoading] = useState(false);
  const [csvRows, setCsvRows] = useState<Record<string, string>[]>([]);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState<{ criados: number; duplicados: number; erros: { codigo?: string; erro: string }[] } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchProdutos = () => {
    api.get("/produtos/", { params: { q: busca || undefined, limit: 100 } })
      .then((r) => setProdutos(r.data));
  };

  useEffect(() => {
    fetchProdutos();
    api.get("/produtos/unidades-medida").then((r) => setUnidades(r.data)).catch(() => {});
  }, [busca]);

  function openNovo() {
    setEditId(null);
    setForm(EMPTY_FORM);
    setErro("");
    setNcmDescricao("");
    setShowFiscal(false);
    setShowModal(true);
  }

  function openEditar(p: Produto) {
    setEditId(p.id);
    setForm({
      codigo: p.codigo,
      descricao: p.descricao,
      tipo: p.tipo,
      unidade_id: String(p.unidade_id),
      ncm: p.ncm || "",
      codigo_barras: "",
      preco_custo: "0",
      preco_venda: String(p.preco_venda),
      estoque_minimo: String(p.estoque_minimo),
      estoque_maximo: "0",
      aliq_icms: String(p.aliq_icms ?? "0"),
      aliq_ipi: String(p.aliq_ipi ?? "0"),
      aliq_pis: String(p.aliq_pis ?? "0.65"),
      aliq_cofins: String(p.aliq_cofins ?? "3.00"),
    });
    setNcmDescricao("");
    setErro("");
    const temFiscal = Number(p.aliq_icms) > 0 || Number(p.aliq_ipi) > 0 || !!p.ncm;
    setShowFiscal(temFiscal);
    setShowModal(true);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErro("");
    try {
      const payload = {
        ...form,
        unidade_id: Number(form.unidade_id) || 1,
        preco_custo: parseFloat(form.preco_custo) || 0,
        preco_venda: parseFloat(form.preco_venda) || 0,
        estoque_minimo: parseFloat(form.estoque_minimo) || 0,
        estoque_maximo: parseFloat(form.estoque_maximo) || 0,
        aliq_icms: parseFloat(form.aliq_icms) || 0,
        aliq_ipi: parseFloat(form.aliq_ipi) || 0,
        aliq_pis: parseFloat(form.aliq_pis) || 0,
        aliq_cofins: parseFloat(form.aliq_cofins) || 0,
      };
      if (editId) {
        await api.put(`/produtos/${editId}`, payload);
      } else {
        await api.post("/produtos/", payload);
      }
      setShowModal(false);
      fetchProdutos();
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao salvar produto");
    } finally {
      setSaving(false);
    }
  }

  async function buscarNcm() {
    const ncmClean = form.ncm.replace(/\D/g, "");
    if (ncmClean.length !== 8) return;
    setNcmLoading(true);
    setNcmDescricao("");
    try {
      const r = await api.get(`/produtos/ncm/${ncmClean}`);
      setNcmDescricao(r.data.descricao);
    } catch (err: any) {
      const msg = err?.response?.data?.detail;
      setNcmDescricao(msg || "NCM não encontrado na tabela TIPI");
    } finally {
      setNcmLoading(false);
    }
  }

  function downloadTemplate() {
    const content = [CSV_HEADER, CSV_EXEMPLO].join("\n");
    const blob = new Blob(["\uFEFF" + content], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "template_produtos.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleCsvFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = (ev.target?.result as string).replace(/^\uFEFF/, "");
      setCsvRows(parseCsv(text));
      setImportResult(null);
    };
    reader.readAsText(file, "utf-8");
  }

  async function handleImport() {
    if (!csvRows.length) return;
    setImportLoading(true);
    setImportResult(null);
    try {
      const produtos = csvRows.map((row) => ({
        codigo: row.codigo || "",
        descricao: row.descricao || "",
        tipo: row.tipo || "MATERIA_PRIMA",
        unidade: row.unidade || "UN",
        preco_custo: parseFloat(row.preco_custo) || 0,
        preco_venda: parseFloat(row.preco_venda) || 0,
        estoque_minimo: parseFloat(row.estoque_minimo) || 0,
        aliq_icms: parseFloat(row.aliq_icms) || 0,
        aliq_ipi: parseFloat(row.aliq_ipi) || 0,
        aliq_pis: parseFloat(row.aliq_pis) || 0.65,
        aliq_cofins: parseFloat(row.aliq_cofins) || 3,
        ncm: row.ncm || null,
      }));
      const r = await api.post("/produtos/importar", { produtos });
      setImportResult(r.data);
      if (r.data.criados > 0) fetchProdutos();
    } catch (err: any) {
      setImportResult({
        criados: 0,
        duplicados: 0,
        erros: [{ erro: err?.response?.data?.detail || "Erro na importação" }],
      });
    } finally {
      setImportLoading(false);
    }
  }

  const moeda = (v: number) =>
    new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(v);

  const ncmValido = form.ncm.replace(/\D/g, "").length === 8;

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <a href="/cadastros" className="text-gray-400 hover:text-gray-600">
          <ChevronLeft size={20} />
        </a>
        <h1 className="text-2xl font-bold flex-1">Produtos</h1>
        <button className="btn-secondary flex items-center gap-2" onClick={() => { setShowImport(true); setCsvRows([]); setImportResult(null); }}>
          <Upload size={16} /> Importar CSV
        </button>
        <button className="btn-primary flex items-center gap-2" onClick={openNovo}>
          <Plus size={16} /> Novo Produto
        </button>
      </div>

      <div className="relative mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          className="input pl-9"
          placeholder="Buscar por código ou descrição..."
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
        />
      </div>

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3 font-medium text-gray-600">Código</th>
              <th className="text-left p-3 font-medium text-gray-600">Descrição</th>
              <th className="text-left p-3 font-medium text-gray-600">Tipo</th>
              <th className="text-left p-3 font-medium text-gray-600">NCM</th>
              <th className="text-right p-3 font-medium text-gray-600">Preço Venda</th>
              <th className="text-right p-3 font-medium text-gray-600">Est. Mín.</th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {produtos.map((p) => (
              <tr key={p.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3 font-mono text-xs font-bold">{p.codigo}</td>
                <td className="p-3">{p.descricao}</td>
                <td className="p-3">
                  <span className={TIPO_BADGE[p.tipo] || "badge-gray"}>
                    {TIPO_LABEL[p.tipo] || p.tipo}
                  </span>
                </td>
                <td className="p-3 font-mono text-xs text-gray-500">{p.ncm || "—"}</td>
                <td className="p-3 text-right">{moeda(Number(p.preco_venda))}</td>
                <td className="p-3 text-right text-gray-500">{p.estoque_minimo}</td>
                <td className="p-3 text-right">
                  <button onClick={() => openEditar(p)} className="text-blue-600 text-xs hover:underline">
                    Editar
                  </button>
                </td>
              </tr>
            ))}
            {produtos.length === 0 && (
              <tr>
                <td colSpan={7} className="p-8 text-center text-gray-400">
                  Nenhum produto encontrado
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Modal criar/editar produto */}
      {showModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-lg max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg">{editId ? "Editar Produto" : "Novo Produto"}</h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Código *</label>
                  <input className="input" value={form.codigo} required
                    onChange={(e) => setForm({ ...form, codigo: e.target.value })} />
                </div>
                <div>
                  <label className="label">Código de Barras</label>
                  <input className="input" value={form.codigo_barras}
                    onChange={(e) => setForm({ ...form, codigo_barras: e.target.value })} />
                </div>
              </div>

              <div>
                <label className="label">Descrição *</label>
                <input className="input" value={form.descricao} required
                  onChange={(e) => setForm({ ...form, descricao: e.target.value })} />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Tipo *</label>
                  <select className="input" value={form.tipo}
                    onChange={(e) => setForm({ ...form, tipo: e.target.value })}>
                    {TIPOS.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Unidade *</label>
                  <select className="input" value={form.unidade_id} required
                    onChange={(e) => setForm({ ...form, unidade_id: e.target.value })}>
                    <option value="">Selecione...</option>
                    {unidades.map((u) => (
                      <option key={u.id} value={u.id}>{u.codigo} — {u.descricao}</option>
                    ))}
                    {unidades.length === 0 && <option value="1">UN — Unidade</option>}
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Est. Mínimo</label>
                  <input className="input" type="number" step="0.001" value={form.estoque_minimo}
                    onChange={(e) => setForm({ ...form, estoque_minimo: e.target.value })} />
                </div>
                <div>
                  <label className="label">Est. Máximo</label>
                  <input className="input" type="number" step="0.001" value={form.estoque_maximo}
                    onChange={(e) => setForm({ ...form, estoque_maximo: e.target.value })} />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="label">Preço de Custo</label>
                  <input className="input" type="number" step="0.01" value={form.preco_custo}
                    onChange={(e) => setForm({ ...form, preco_custo: e.target.value })} />
                </div>
                <div>
                  <label className="label">Preço de Venda</label>
                  <input className="input" type="number" step="0.01" value={form.preco_venda}
                    onChange={(e) => setForm({ ...form, preco_venda: e.target.value })} />
                </div>
              </div>

              {/* Dados Fiscais — colapsável */}
              <div className="border rounded-lg overflow-hidden">
                <button
                  type="button"
                  className="w-full flex items-center justify-between px-4 py-2 bg-gray-50 text-sm font-medium text-gray-700 hover:bg-gray-100"
                  onClick={() => setShowFiscal(!showFiscal)}
                >
                  <span>Dados Fiscais (NCM e alíquotas)</span>
                  {showFiscal ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </button>

                {showFiscal && (
                  <div className="p-4 space-y-4">
                    <div>
                      <label className="label">NCM</label>
                      <div className="flex gap-2">
                        <input
                          className="input font-mono flex-1"
                          placeholder="00000000"
                          maxLength={10}
                          value={form.ncm}
                          onChange={(e) => {
                            setForm({ ...form, ncm: e.target.value });
                            setNcmDescricao("");
                          }}
                        />
                        {ncmValido && (
                          <button
                            type="button"
                            className="btn-secondary text-xs px-3 whitespace-nowrap"
                            onClick={buscarNcm}
                            disabled={ncmLoading}
                          >
                            {ncmLoading ? "Buscando..." : "Buscar"}
                          </button>
                        )}
                      </div>
                      {ncmDescricao && (
                        <p className="text-xs mt-1 text-gray-600 bg-gray-50 px-2 py-1 rounded">
                          {ncmDescricao}
                        </p>
                      )}
                      {ncmDescricao && (
                        <p className="text-xs mt-1 text-amber-600">
                          Alíquotas devem ser confirmadas com seu contador.
                        </p>
                      )}
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="label">ICMS (%)</label>
                        <input className="input" type="number" step="0.01" value={form.aliq_icms}
                          onChange={(e) => setForm({ ...form, aliq_icms: e.target.value })} />
                      </div>
                      <div>
                        <label className="label">IPI (%)</label>
                        <input className="input" type="number" step="0.01" value={form.aliq_ipi}
                          onChange={(e) => setForm({ ...form, aliq_ipi: e.target.value })} />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="label">PIS (%)</label>
                        <input className="input" type="number" step="0.01" value={form.aliq_pis}
                          onChange={(e) => setForm({ ...form, aliq_pis: e.target.value })} />
                      </div>
                      <div>
                        <label className="label">COFINS (%)</label>
                        <input className="input" type="number" step="0.01" value={form.aliq_cofins}
                          onChange={(e) => setForm({ ...form, aliq_cofins: e.target.value })} />
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {erro && <p className="text-sm text-red-600 bg-red-50 p-2 rounded">{erro}</p>}

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" className="btn-secondary" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? "Salvando..." : "Salvar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal importação CSV */}
      {showImport && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg">Importar Produtos via CSV</h2>
              <button onClick={() => setShowImport(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <div className="space-y-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
                <p className="font-medium mb-1">Como usar:</p>
                <ol className="list-decimal list-inside space-y-1 text-blue-700">
                  <li>Baixe o template CSV abaixo</li>
                  <li>Preencha com seus produtos (baseie-se no seu Excel)</li>
                  <li>Faça upload e confira o preview</li>
                  <li>Clique em Importar — produtos já cadastrados são ignorados</li>
                </ol>
              </div>

              <button className="btn-secondary flex items-center gap-2 text-sm" onClick={downloadTemplate}>
                <Download size={15} /> Baixar Template CSV
              </button>

              <div>
                <label className="label">Arquivo CSV</label>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.txt"
                  className="block w-full text-sm text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded file:border-0 file:text-sm file:bg-gray-100 file:text-gray-700 hover:file:bg-gray-200 cursor-pointer"
                  onChange={handleCsvFile}
                />
              </div>

              {csvRows.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-gray-700 mb-2">
                    Preview — {csvRows.length} produto(s) no arquivo:
                  </p>
                  <div className="overflow-x-auto border rounded-lg">
                    <table className="w-full text-xs">
                      <thead className="bg-gray-50 border-b">
                        <tr>
                          <th className="text-left px-3 py-2 font-medium text-gray-600">Código</th>
                          <th className="text-left px-3 py-2 font-medium text-gray-600">Descrição</th>
                          <th className="text-left px-3 py-2 font-medium text-gray-600">Tipo</th>
                          <th className="text-left px-3 py-2 font-medium text-gray-600">Un.</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">Custo</th>
                          <th className="text-right px-3 py-2 font-medium text-gray-600">Venda</th>
                          <th className="text-left px-3 py-2 font-medium text-gray-600">NCM</th>
                        </tr>
                      </thead>
                      <tbody>
                        {csvRows.slice(0, 10).map((row, i) => (
                          <tr key={i} className="border-b last:border-0">
                            <td className="px-3 py-1.5 font-mono font-bold">{row.codigo}</td>
                            <td className="px-3 py-1.5 max-w-[160px] truncate">{row.descricao}</td>
                            <td className="px-3 py-1.5 text-gray-500">{row.tipo || "MP"}</td>
                            <td className="px-3 py-1.5">{row.unidade || "UN"}</td>
                            <td className="px-3 py-1.5 text-right">{row.preco_custo || "0"}</td>
                            <td className="px-3 py-1.5 text-right">{row.preco_venda || "0"}</td>
                            <td className="px-3 py-1.5 font-mono text-gray-400">{row.ncm || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {csvRows.length > 10 && (
                      <p className="text-xs text-gray-400 px-3 py-2">
                        ... e mais {csvRows.length - 10} produto(s)
                      </p>
                    )}
                  </div>
                </div>
              )}

              {importResult && (
                <div className={`rounded-lg p-4 text-sm ${importResult.erros.length > 0 && importResult.criados === 0 ? "bg-red-50 border border-red-200" : "bg-green-50 border border-green-200"}`}>
                  <p className="font-medium mb-1">Resultado da importação:</p>
                  <p className="text-green-700">✓ {importResult.criados} produto(s) criado(s)</p>
                  {importResult.duplicados > 0 && (
                    <p className="text-gray-600">— {importResult.duplicados} já existiam (ignorados)</p>
                  )}
                  {importResult.erros.length > 0 && (
                    <div className="mt-2">
                      <p className="text-red-700 font-medium">Erros ({importResult.erros.length}):</p>
                      {importResult.erros.map((e, i) => (
                        <p key={i} className="text-red-600 text-xs">
                          {e.codigo ? `${e.codigo}: ` : ""}{e.erro}
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button className="btn-secondary" onClick={() => setShowImport(false)}>
                  Fechar
                </button>
                {csvRows.length > 0 && !importResult && (
                  <button
                    className="btn-primary flex items-center gap-2"
                    onClick={handleImport}
                    disabled={importLoading}
                  >
                    <Upload size={15} />
                    {importLoading ? "Importando..." : `Importar ${csvRows.length} produto(s)`}
                  </button>
                )}
                {importResult && importResult.criados > 0 && (
                  <button className="btn-secondary" onClick={() => { setCsvRows([]); setImportResult(null); if (fileInputRef.current) fileInputRef.current.value = ""; }}>
                    Importar outro arquivo
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
