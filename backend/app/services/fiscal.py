"""
Serviço de cálculo fiscal.

Suporta os 3 regimes tributários:
  CRT 1/2 = Simples Nacional → usa CSOSN, alíquotas simplificadas, sem crédito PIS/COFINS
  CRT 3   = Regime Normal (Lucro Presumido ou Lucro Real) → CST, créditos integrais

Alíquotas de ICMS interestaduais (tabela padrão):
  Sul/Sudeste → Norte/Nordeste/Centro-Oeste: 7%
  Norte/Nordeste/Centro-Oeste/ES → Sul/Sudeste: 12%
  Dentro do mesmo estado: alíquota interna do estado
"""
from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, field
from typing import Optional
from app.core.config import settings


# Tabela de alíquotas interestaduais ICMS
_ALIQ_INTER: dict[str, dict[str, Decimal]] = {
    # Estado de origem → estado de destino → alíquota
    # Simplificado: Sul/Sudeste (SP,RJ,MG,RS,PR,SC,ES) = 12% recebendo; demais = 7% recebendo
    "DEFAULT_PARA_SUL_SUDESTE": Decimal("12"),
    "DEFAULT_PARA_OUTROS": Decimal("7"),
}

_ESTADOS_SUL_SUDESTE = {"SP", "RJ", "MG", "RS", "PR", "SC", "ES"}


def aliquota_icms_interestadual(uf_origem: str, uf_destino: str) -> Decimal:
    """Retorna a alíquota de ICMS interestadual entre dois estados."""
    if uf_origem == uf_destino:
        return Decimal("12")  # interna padrão (cada empresa deve configurar a real)
    if uf_destino in _ESTADOS_SUL_SUDESTE:
        return Decimal("12")
    return Decimal("7")


@dataclass
class ImpostosItem:
    """Resultado do cálculo de impostos de um item."""
    base_icms: Decimal = Decimal("0")
    aliq_icms: Decimal = Decimal("0")
    valor_icms: Decimal = Decimal("0")

    base_icms_st: Decimal = Decimal("0")
    valor_icms_st: Decimal = Decimal("0")

    base_ipi: Decimal = Decimal("0")
    aliq_ipi: Decimal = Decimal("0")
    valor_ipi: Decimal = Decimal("0")

    base_pis: Decimal = Decimal("0")
    aliq_pis: Decimal = Decimal("0")
    valor_pis: Decimal = Decimal("0")

    base_cofins: Decimal = Decimal("0")
    aliq_cofins: Decimal = Decimal("0")
    valor_cofins: Decimal = Decimal("0")

    valor_difal: Decimal = Decimal("0")

    cfop: str = ""
    cst_icms: str = ""
    cst_ipi: str = ""
    cst_pis: str = ""
    cst_cofins: str = ""

    def _round(self, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def total_impostos(self) -> Decimal:
        return self._round(
            self.valor_icms + self.valor_icms_st + self.valor_ipi
            + self.valor_pis + self.valor_cofins + self.valor_difal
        )


def calcular_impostos_saida(
    valor_produto: Decimal,
    aliq_icms: Decimal,
    aliq_ipi: Decimal,
    aliq_pis: Decimal,
    aliq_cofins: Decimal,
    mva: Decimal,
    uf_destino: str,
    consumidor_final: bool,
    crt_empresa: str,
    cst_icms: str,
    csosn: Optional[str],
    cst_ipi: str,
    cst_pis: str,
    cst_cofins: str,
) -> ImpostosItem:
    """
    Calcula impostos de saída para um item da NF-e.

    Para Simples Nacional (CRT 1/2): ICMS coberto pelo SIMPLES, IPI/PIS/COFINS
    podem ser cobrados dependendo da atividade.
    Para Regime Normal (CRT 3): cálculo completo CST.
    """
    r = ImpostosItem()
    r.cst_ipi = cst_ipi
    r.cst_pis = cst_pis
    r.cst_cofins = cst_cofins

    uf_empresa = settings.EMPRESA_UF
    interestadual = uf_destino != uf_empresa

    # --- CFOP ---
    if interestadual:
        r.cfop = "6102"  # Venda mercadoria interestadual (padrão; ajustar por produto)
    else:
        r.cfop = "5102"  # Venda mercadoria intraestadual

    # --- ICMS ---
    if crt_empresa in ("1", "2"):
        # Simples Nacional: ICMS recolhido no DAS; CST = usa CSOSN
        r.cst_icms = csosn or "400"
        r.aliq_icms = Decimal("0")
        r.base_icms = valor_produto
        r.valor_icms = Decimal("0")
    else:
        # Regime Normal
        r.cst_icms = cst_icms or "00"
        if interestadual:
            r.aliq_icms = aliquota_icms_interestadual(uf_empresa, uf_destino)
        else:
            r.aliq_icms = aliq_icms
        r.base_icms = valor_produto
        r.valor_icms = (r.base_icms * r.aliq_icms / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)

        # DIFAL - EC 87/2015: venda para consumidor final de outro estado
        if interestadual and consumidor_final:
            aliq_interna_destino = aliq_icms  # deveria buscar a alíquota interna do estado destino
            aliq_inter = aliquota_icms_interestadual(uf_empresa, uf_destino)
            diferencial = aliq_interna_destino - aliq_inter
            if diferencial > 0:
                r.valor_difal = (valor_produto * diferencial / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)

    # --- ICMS-ST ---
    if mva > 0 and aliq_icms > 0:
        base_st = valor_produto * (1 + mva / 100)
        valor_st_total = (base_st * aliq_icms / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
        r.valor_icms_st = max(Decimal("0"), valor_st_total - r.valor_icms)
        r.base_icms_st = base_st.quantize(Decimal("0.01"), ROUND_HALF_UP)

    # --- IPI ---
    # IPI só incide em produtos industrializados (saída de estabelecimento industrial)
    if cst_ipi in ("00", "49", "50") and aliq_ipi > 0:
        r.base_ipi = valor_produto
        r.aliq_ipi = aliq_ipi
        r.valor_ipi = (r.base_ipi * r.aliq_ipi / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)

    # --- PIS / COFINS ---
    # CST 01 = alíquota normal; CST 07/08/09 = operação isenta ou não tributada
    if cst_pis in ("01", "02") and aliq_pis > 0:
        r.base_pis = valor_produto
        r.aliq_pis = aliq_pis
        r.valor_pis = (r.base_pis * r.aliq_pis / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)

    if cst_cofins in ("01", "02") and aliq_cofins > 0:
        r.base_cofins = valor_produto
        r.aliq_cofins = aliq_cofins
        r.valor_cofins = (r.base_cofins * r.aliq_cofins / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)

    return r


def calcular_creditos_entrada(
    valor_produto: Decimal,
    aliq_icms: Decimal,
    aliq_ipi: Decimal,
    aliq_pis: Decimal,
    aliq_cofins: Decimal,
    tipo_entrada: str,  # COMPRA_MP | COMPRA_REVENDA
    crt_empresa: str,
) -> dict:
    """
    Calcula créditos fiscais na entrada de mercadorias.

    Simples Nacional (CRT 1/2): sem crédito de ICMS/PIS/COFINS
    Regime Normal (CRT 3):
      - Compra de MP: crédito de IPI, ICMS, PIS, COFINS
      - Compra para revenda: crédito de ICMS e PIS/COFINS (sem IPI)
    """
    creditos = {
        "credito_icms": Decimal("0"),
        "credito_ipi": Decimal("0"),
        "credito_pis": Decimal("0"),
        "credito_cofins": Decimal("0"),
    }

    if crt_empresa in ("1", "2"):
        return creditos  # Simples: sem crédito

    r = ROUND_HALF_UP
    q = Decimal("0.01")

    # ICMS - crédito em compras (Regime Normal)
    creditos["credito_icms"] = (valor_produto * aliq_icms / 100).quantize(q, r)

    if tipo_entrada == "COMPRA_MP":
        # IPI gera crédito apenas na compra de insumos para industrialização
        creditos["credito_ipi"] = (valor_produto * aliq_ipi / 100).quantize(q, r)

    # PIS/COFINS: Lucro Real tem crédito não-cumulativo (9,25%)
    # Lucro Presumido: PIS/COFINS cumulativo (3,65%), sem crédito
    # Por ora, deixamos configurável no produto; aqui calculamos se informado
    if aliq_pis > 0:
        creditos["credito_pis"] = (valor_produto * aliq_pis / 100).quantize(q, r)
    if aliq_cofins > 0:
        creditos["credito_cofins"] = (valor_produto * aliq_cofins / 100).quantize(q, r)

    return creditos
