"use client";
/**
 * Interface de Picking com leitor de código de barras.
 *
 * Design: tela simples, elementos grandes, feedback visual imediato (verde/vermelho/amarelo).
 * O leitor USB/Bluetooth age como teclado — o input captura automaticamente cada leitura.
 * Não precisa clicar no campo: o foco é mantido automaticamente.
 */
import { useEffect, useRef, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import api from "@/lib/api";
import { CheckCircle2, XCircle, AlertCircle, ScanLine } from "lucide-react";

interface ItemConferencia {
  id: number;
  produto_id: number;
  produto?: { codigo: string; descricao: string };
  quantidade_esperada: number;
  quantidade_conferida: number;
  status: "PENDENTE" | "OK" | "DIVERGENCIA_QUANTIDADE" | "ITEM_ERRADO";
}

interface Conferencia {
  id: number;
  pedido_venda_id: number;
  status: string;
  percentual_concluido: number;
  itens: ItemConferencia[];
}

interface ScanResult {
  resultado: string;
  mensagem: string;
  produto?: string;
  cor: "verde" | "vermelho" | "amarelo" | "cinza";
}

const COR_BG = {
  verde: "bg-green-500",
  vermelho: "bg-red-500",
  amarelo: "bg-yellow-400",
  cinza: "bg-gray-300",
};

export default function PickingPage() {
  const { conferencia_id } = useParams<{ conferencia_id: string }>();
  const [conferencia, setConferencia] = useState<Conferencia | null>(null);
  const [lastResult, setLastResult] = useState<ScanResult | null>(null);
  const [scanInput, setScanInput] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const loadConferencia = useCallback(async () => {
    const r = await api.get(`/picking/${conferencia_id}`);
    setConferencia(r.data);
  }, [conferencia_id]);

  useEffect(() => {
    loadConferencia();
  }, [loadConferencia]);

  // Mantém foco no input (para que o scanner funcione sem clicar)
  useEffect(() => {
    const focusInput = () => inputRef.current?.focus();
    focusInput();
    document.addEventListener("click", focusInput);
    return () => document.removeEventListener("click", focusInput);
  }, []);

  // WebSocket para feedback em tempo real (opcional, fallback para REST)
  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const wsUrl = `${apiBase.replace(/^https/, "wss").replace(/^http/, "ws")}/api/v1/picking/${conferencia_id}/ws`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setLastResult({
        resultado: data.resultado,
        mensagem: `${data.produto || ""}: ${data.resultado === "OK" ? "OK ✓" : data.resultado}`,
        produto: data.produto,
        cor: data.cor || "cinza",
      });
      loadConferencia();
    };

    return () => ws.close();
  }, [conferencia_id, loadConferencia]);

  const handleScan = async (e: React.FormEvent) => {
    e.preventDefault();
    const codigo = scanInput.trim();
    if (!codigo) return;

    setScanInput("");
    setLoading(true);

    try {
      // Tenta via WebSocket se conectado, senão usa REST
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ codigo, quantidade: 1 }));
      } else {
        const r = await api.post(`/picking/${conferencia_id}/scan`, null, {
          params: { codigo, quantidade: 1 },
        });
        const d = r.data;
        const cor =
          d.resultado === "OK" ? "verde"
          : d.resultado === "PARCIAL" ? "amarelo"
          : "vermelho";
        setLastResult({ resultado: d.resultado, mensagem: d.mensagem, cor });
        await loadConferencia();
      }
    } catch {
      setLastResult({ resultado: "ERRO", mensagem: "Erro ao processar leitura", cor: "vermelho" });
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  if (!conferencia) return <div className="p-8 text-gray-400 text-lg">Carregando conferência...</div>;

  const pct = Math.round(Number(conferencia.percentual_concluido));
  const concluido = conferencia.status === "CONCLUIDO";

  return (
    <div className="max-w-2xl mx-auto">
      {/* Cabeçalho */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Picking — Pedido #{conferencia.pedido_venda_id}</h1>
          <p className="text-sm text-gray-500 mt-0.5">Conferência #{conferencia_id}</p>
        </div>
        {concluido && (
          <span className="badge-green text-base px-4 py-1">✓ Concluído</span>
        )}
      </div>

      {/* Barra de progresso */}
      <div className="card p-4 mb-6">
        <div className="flex justify-between text-sm mb-2">
          <span className="font-medium">Progresso</span>
          <span className="font-bold text-lg">{pct}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-4">
          <div
            className={`h-4 rounded-full transition-all duration-300 ${pct === 100 ? "bg-green-500" : "bg-blue-600"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Área de resultado da última leitura */}
      {lastResult && (
        <div className={`rounded-xl p-6 mb-6 text-white text-center text-xl font-bold transition-all ${COR_BG[lastResult.cor]}`}>
          {lastResult.cor === "verde" && <CheckCircle2 size={48} className="mx-auto mb-2" />}
          {lastResult.cor === "vermelho" && <XCircle size={48} className="mx-auto mb-2" />}
          {lastResult.cor === "amarelo" && <AlertCircle size={48} className="mx-auto mb-2" />}
          {lastResult.mensagem}
        </div>
      )}

      {/* Input do scanner (captura leitura automaticamente) */}
      {!concluido && (
        <form onSubmit={handleScan} className="mb-6">
          <div className="flex items-center gap-3 card p-4">
            <ScanLine size={24} className="text-blue-600 flex-shrink-0" />
            <input
              ref={inputRef}
              value={scanInput}
              onChange={(e) => setScanInput(e.target.value)}
              placeholder="Aguardando leitura do scanner..."
              className="flex-1 text-lg font-mono border-none outline-none bg-transparent"
              autoComplete="off"
              disabled={loading}
            />
            <button type="submit" className="btn-primary" disabled={loading || !scanInput}>
              OK
            </button>
          </div>
          <p className="text-xs text-gray-400 mt-2 text-center">
            O campo captura automaticamente a leitura do scanner. Não precisa clicar.
          </p>
        </form>
      )}

      {/* Lista de itens */}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left p-3 font-medium text-gray-600">Produto</th>
              <th className="text-center p-3 font-medium text-gray-600">Esperado</th>
              <th className="text-center p-3 font-medium text-gray-600">Conferido</th>
              <th className="text-center p-3 font-medium text-gray-600">Status</th>
            </tr>
          </thead>
          <tbody>
            {conferencia.itens.map((item) => (
              <tr key={item.id} className="border-b last:border-0 hover:bg-gray-50">
                <td className="p-3">
                  <p className="font-medium">{item.produto?.descricao || `Produto #${item.produto_id}`}</p>
                  <p className="text-xs text-gray-400">{item.produto?.codigo}</p>
                </td>
                <td className="p-3 text-center font-mono">{item.quantidade_esperada}</td>
                <td className="p-3 text-center font-mono font-bold">{item.quantidade_conferida}</td>
                <td className="p-3 text-center">
                  {item.status === "OK" && <span className="badge-green">✓ OK</span>}
                  {item.status === "PENDENTE" && <span className="badge-gray">Pendente</span>}
                  {item.status === "DIVERGENCIA_QUANTIDADE" && <span className="badge-red">Divergência</span>}
                  {item.status === "ITEM_ERRADO" && <span className="badge-red">Item errado</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {concluido && (
        <div className="mt-6 p-6 bg-green-50 border border-green-200 rounded-xl text-center">
          <CheckCircle2 size={48} className="text-green-600 mx-auto mb-3" />
          <h2 className="text-xl font-bold text-green-800">Conferência Concluída!</h2>
          <p className="text-sm text-green-600 mt-1">Todos os itens foram conferidos corretamente.</p>
          <a href="/expedicao" className="btn-primary mt-4 inline-flex">
            Ir para Expedição →
          </a>
        </div>
      )}
    </div>
  );
}
