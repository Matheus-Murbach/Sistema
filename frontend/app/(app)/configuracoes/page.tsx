"use client";
import { useState } from "react";
import api from "@/lib/api";
import { Settings, User, Plus, X, CheckCircle2 } from "lucide-react";

const CRT_LABEL: Record<string, string> = {
  "1": "1 — Simples Nacional",
  "2": "2 — Simples Nacional (excesso de sublimite)",
  "3": "3 — Regime Normal (Lucro Presumido / Real)",
};

const EMPTY_USUARIO = { nome: "", email: "", senha: "", perfil: "operador" };

export default function ConfiguracoesPage() {
  const [showModalUsuario, setShowModalUsuario] = useState(false);
  const [formUsuario, setFormUsuario] = useState(EMPTY_USUARIO);
  const [saving, setSaving] = useState(false);
  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  async function handleCriarUsuario(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErro("");
    setSucesso("");
    try {
      await api.post("/auth/usuarios", formUsuario);
      setSucesso(`Usuário "${formUsuario.nome}" criado com sucesso.`);
      setFormUsuario(EMPTY_USUARIO);
      setShowModalUsuario(false);
    } catch (err: any) {
      setErro(err?.response?.data?.detail || "Erro ao criar usuário");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <div className="flex items-center gap-3 mb-6">
        <Settings size={22} className="text-gray-500" />
        <h1 className="text-2xl font-bold">Configurações</h1>
      </div>

      {sucesso && (
        <div className="mb-4 p-4 bg-green-50 border border-green-200 rounded-lg flex items-center gap-3 text-sm text-green-800">
          <CheckCircle2 size={16} className="flex-shrink-0" />
          {sucesso}
        </div>
      )}

      {/* Empresa */}
      <div className="card p-6 mb-4">
        <h2 className="font-semibold text-gray-700 mb-4">Dados da Empresa</h2>
        <p className="text-sm text-gray-500 mb-4">
          As informações da empresa são configuradas via variáveis de ambiente no arquivo{" "}
          <code className="bg-gray-100 px-1 rounded font-mono text-xs">.env</code>.
          Reinicie o serviço após qualquer alteração.
        </p>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
          {[
            { label: "EMPRESA_RAZAO_SOCIAL", desc: "Razão social para NF-e" },
            { label: "EMPRESA_CNPJ", desc: "CNPJ (apenas números)" },
            { label: "EMPRESA_IE", desc: "Inscrição estadual" },
            { label: "EMPRESA_UF", desc: "UF do estabelecimento (ex: SP)" },
            { label: "EMPRESA_MUNICIPIO", desc: "Município" },
            { label: "EMPRESA_CEP", desc: "CEP (apenas números)" },
            { label: "EMPRESA_CRT", desc: `Regime tributário (${Object.keys(CRT_LABEL).join("/")})` },
            { label: "EMPRESA_EMAIL", desc: "E-mail de contato" },
          ].map(({ label, desc }) => (
            <div key={label}>
              <code className="text-xs font-mono text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded">
                {label}
              </code>
              <p className="text-xs text-gray-400 mt-0.5">{desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Integrações */}
      <div className="card p-6 mb-4">
        <h2 className="font-semibold text-gray-700 mb-4">Integrações</h2>
        <div className="space-y-3 text-sm">
          <div className="flex items-start justify-between p-3 bg-gray-50 rounded-lg">
            <div>
              <p className="font-medium">Focus NF-e</p>
              <p className="text-xs text-gray-400 mt-0.5">
                Emissão de NF-e via SEFAZ. Configure{" "}
                <code className="font-mono text-xs bg-gray-100 px-1 rounded">FOCUS_NFE_TOKEN</code> e{" "}
                <code className="font-mono text-xs bg-gray-100 px-1 rounded">FOCUS_NFE_URL</code>.
              </p>
            </div>
          </div>
          <div className="flex items-start justify-between p-3 bg-gray-50 rounded-lg">
            <div>
              <p className="font-medium">IBPT (Alíquotas por NCM)</p>
              <p className="text-xs text-gray-400 mt-0.5">
                Busca automática de alíquotas ao cadastrar produtos. Configure{" "}
                <code className="font-mono text-xs bg-gray-100 px-1 rounded">IBPT_TOKEN</code> e{" "}
                <code className="font-mono text-xs bg-gray-100 px-1 rounded">IBPT_CNPJ</code>.
              </p>
            </div>
          </div>
          <div className="flex items-start justify-between p-3 bg-gray-50 rounded-lg">
            <div>
              <p className="font-medium">Certificado Digital</p>
              <p className="text-xs text-gray-400 mt-0.5">
                Configure{" "}
                <code className="font-mono text-xs bg-gray-100 px-1 rounded">CERTIFICADO_TIPO</code> (A1/A3),{" "}
                <code className="font-mono text-xs bg-gray-100 px-1 rounded">CERTIFICADO_PATH</code> e{" "}
                <code className="font-mono text-xs bg-gray-100 px-1 rounded">CERTIFICADO_SENHA</code>.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Usuários */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-700">Usuários</h2>
          <button className="btn-primary text-sm py-1.5" onClick={() => setShowModalUsuario(true)}>
            <Plus size={14} /> Novo Usuário
          </button>
        </div>
        <p className="text-sm text-gray-500">
          Crie usuários adicionais para operadores e administradores. Perfis disponíveis:{" "}
          <strong>admin</strong> (acesso total) e <strong>operador</strong> (acesso operacional).
        </p>
        <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-xs text-yellow-800">
          Somente administradores podem criar novos usuários. A senha inicial deve ser trocada pelo usuário no primeiro acesso.
        </div>
      </div>

      {/* Modal Novo Usuário */}
      {showModalUsuario && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="card w-full max-w-md p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-lg flex items-center gap-2">
                <User size={18} /> Novo Usuário
              </h2>
              <button onClick={() => { setShowModalUsuario(false); setErro(""); }}
                className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCriarUsuario} className="space-y-4">
              <div>
                <label className="label">Nome *</label>
                <input className="input" value={formUsuario.nome} required
                  onChange={(e) => setFormUsuario({ ...formUsuario, nome: e.target.value })} />
              </div>
              <div>
                <label className="label">E-mail *</label>
                <input className="input" type="email" value={formUsuario.email} required
                  onChange={(e) => setFormUsuario({ ...formUsuario, email: e.target.value })} />
              </div>
              <div>
                <label className="label">Senha inicial *</label>
                <input className="input" type="password" minLength={6} value={formUsuario.senha} required
                  onChange={(e) => setFormUsuario({ ...formUsuario, senha: e.target.value })} />
              </div>
              <div>
                <label className="label">Perfil</label>
                <select className="input" value={formUsuario.perfil}
                  onChange={(e) => setFormUsuario({ ...formUsuario, perfil: e.target.value })}>
                  <option value="operador">Operador</option>
                  <option value="admin">Administrador</option>
                </select>
              </div>

              {erro && <p className="text-sm text-red-600 bg-red-50 p-2 rounded">{erro}</p>}

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" className="btn-secondary"
                  onClick={() => { setShowModalUsuario(false); setErro(""); }}>
                  Cancelar
                </button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? "Criando..." : "Criar Usuário"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
