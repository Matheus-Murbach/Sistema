"""
TDD — Testes unitários do serviço fiscal.

Cada teste define um comportamento esperado ANTES de olhar para a implementação.
Estes testes são a especificação do sistema tributário.

Regras testadas:
  - ICMS intraestadual vs interestadual (7% ou 12%)
  - DIFAL para consumidor final de outro estado
  - ICMS-ST com MVA (base ST = valor × (1 + MVA/100))
  - IPI somente em CST industrializado (00, 49, 50)
  - PIS/COFINS somente quando CST tributado (01, 02)
  - Simples Nacional (CRT 1/2): sem crédito na entrada, ICMS = 0 na saída
  - Regime Normal (CRT 3): cálculos completos
  - Créditos na entrada: conforme regime e tipo de compra
"""

import pytest
from decimal import Decimal
from app.services.fiscal import (
    calcular_impostos_saida,
    calcular_creditos_entrada,
    aliquota_icms_interestadual,
    ImpostosItem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def impostos_padrao(
    valor=Decimal("1000.00"),
    aliq_icms=Decimal("12"),
    aliq_ipi=Decimal("10"),
    aliq_pis=Decimal("0.65"),
    aliq_cofins=Decimal("3.00"),
    mva=Decimal("0"),
    uf_destino="SP",
    consumidor_final=False,
    crt="3",
    cst_icms="00",
    csosn=None,
    cst_ipi="00",
    cst_pis="01",
    cst_cofins="01",
):
    return calcular_impostos_saida(
        valor_produto=valor,
        aliq_icms=aliq_icms,
        aliq_ipi=aliq_ipi,
        aliq_pis=aliq_pis,
        aliq_cofins=aliq_cofins,
        mva=mva,
        uf_destino=uf_destino,
        consumidor_final=consumidor_final,
        crt_empresa=crt,
        cst_icms=cst_icms,
        csosn=csosn,
        cst_ipi=cst_ipi,
        cst_pis=cst_pis,
        cst_cofins=cst_cofins,
    )


# ---------------------------------------------------------------------------
# ICMS — Alíquota Interestadual
# ---------------------------------------------------------------------------

class TestAliquotaInterestadual:
    def test_intraestadual_mesmo_estado(self):
        """Mesma UF = alíquota interna (retorna 12 como padrão)."""
        aliq = aliquota_icms_interestadual("SP", "SP")
        assert aliq == Decimal("12")

    def test_interestadual_para_sul_sudeste(self):
        """De qualquer estado para SP/RJ/MG/RS/PR/SC/ES = 12%."""
        for uf_destino in ["SP", "RJ", "MG", "RS", "PR", "SC", "ES"]:
            aliq = aliquota_icms_interestadual("CE", uf_destino)
            assert aliq == Decimal("12"), f"Esperado 12% para CE→{uf_destino}"

    def test_interestadual_para_norte_nordeste(self):
        """De Sul/Sudeste para Norte/Nordeste/CO = 7%."""
        for uf_destino in ["AM", "PA", "CE", "BA", "GO", "MT", "MS"]:
            aliq = aliquota_icms_interestadual("SP", uf_destino)
            assert aliq == Decimal("7"), f"Esperado 7% para SP→{uf_destino}"


# ---------------------------------------------------------------------------
# ICMS — Saída Regime Normal (CRT 3)
# ---------------------------------------------------------------------------

class TestICMSSaidaRegimeNormal:
    def test_icms_intraestadual_calculado(self):
        """Venda intraestadual: ICMS = valor × alíquota / 100."""
        r = impostos_padrao(valor=Decimal("1000"), aliq_icms=Decimal("12"), uf_destino="SP", crt="3")
        assert r.valor_icms == Decimal("120.00")
        assert r.aliq_icms == Decimal("12")

    def test_icms_base_igual_ao_valor_produto(self):
        """Base de cálculo ICMS = valor do produto (sem inclusão de IPI na base neste modelo)."""
        r = impostos_padrao(valor=Decimal("500"), aliq_icms=Decimal("12"), crt="3")
        assert r.base_icms == Decimal("500")

    def test_cfop_intraestadual(self):
        """Venda dentro do estado usa CFOP 5102."""
        r = impostos_padrao(uf_destino="SP", crt="3")  # empresa é SP
        assert r.cfop == "5102"

    def test_cfop_interestadual(self):
        """Venda para outro estado usa CFOP 6102."""
        r = impostos_padrao(uf_destino="RJ", crt="3")
        assert r.cfop == "6102"

    def test_icms_interestadual_aliquota_reduzida(self):
        """Venda SP→AM: alíquota deve ser 7%."""
        r = impostos_padrao(valor=Decimal("1000"), aliq_icms=Decimal("12"), uf_destino="AM", crt="3")
        assert r.aliq_icms == Decimal("7")
        assert r.valor_icms == Decimal("70.00")

    def test_cst_icms_preservado(self):
        """CST informado deve ser mantido no resultado."""
        r = impostos_padrao(cst_icms="10", crt="3")
        assert r.cst_icms == "10"


# ---------------------------------------------------------------------------
# ICMS — Simples Nacional (CRT 1/2)
# ---------------------------------------------------------------------------

class TestICMSSimlesNacional:
    def test_simples_icms_zero_na_saida(self):
        """No Simples Nacional, ICMS é recolhido no DAS — valor na NF = 0."""
        r = impostos_padrao(crt="1", csosn="400")
        assert r.valor_icms == Decimal("0")
        assert r.aliq_icms == Decimal("0")

    def test_simples_usa_csosn_nao_cst(self):
        """Simples usa CSOSN (ex: 400) e não CST ICMS."""
        r = impostos_padrao(crt="1", csosn="102")
        assert r.cst_icms == "102"  # CSOSN aplicado como cst_icms no resultado

    def test_simples_crt2_igual_crt1_para_icms(self):
        """CRT 2 (Simples Excesso) tem mesmo comportamento de ICMS."""
        r = impostos_padrao(crt="2", csosn="400")
        assert r.valor_icms == Decimal("0")


# ---------------------------------------------------------------------------
# DIFAL — EC 87/2015
# ---------------------------------------------------------------------------

class TestDIFAL:
    def test_difal_consumidor_final_interestadual(self):
        """Venda interestadual para consumidor final deve gerar DIFAL."""
        r = impostos_padrao(
            valor=Decimal("1000"),
            aliq_icms=Decimal("18"),  # alíquota interna do destino (simplificado)
            uf_destino="AM",          # interestadual, vai usar 7% na saída
            consumidor_final=True,
            crt="3",
        )
        # DIFAL = (aliq_interna_destino - aliq_inter) × base
        # = (18 - 7) × 1000 / 100 = 110
        assert r.valor_difal == Decimal("110.00")

    def test_sem_difal_para_contribuinte(self):
        """Venda interestadual para contribuinte (empresa) não gera DIFAL."""
        r = impostos_padrao(
            uf_destino="AM",
            consumidor_final=False,
            crt="3",
        )
        assert r.valor_difal == Decimal("0")

    def test_sem_difal_intraestadual(self):
        """Venda dentro do estado: sem DIFAL mesmo para consumidor final."""
        r = impostos_padrao(uf_destino="SP", consumidor_final=True, crt="3")
        assert r.valor_difal == Decimal("0")


# ---------------------------------------------------------------------------
# ICMS-ST — Substituição Tributária com MVA
# ---------------------------------------------------------------------------

class TestICMSST:
    def test_icms_st_com_mva(self):
        """Base ST = valor × (1 + MVA/100); valor ST = base_ST × aliq - valor_ICMS_proprio."""
        r = impostos_padrao(
            valor=Decimal("1000"),
            aliq_icms=Decimal("12"),
            mva=Decimal("40"),
            uf_destino="SP",
            crt="3",
        )
        # base_st = 1000 × 1.40 = 1400
        # valor_st_total = 1400 × 12% = 168
        # icms_proprio = 1000 × 12% = 120
        # valor_icms_st = 168 - 120 = 48
        assert r.base_icms_st == Decimal("1400.00")
        assert r.valor_icms_st == Decimal("48.00")

    def test_sem_icms_st_quando_mva_zero(self):
        """Sem MVA = sem ST."""
        r = impostos_padrao(mva=Decimal("0"), crt="3")
        assert r.valor_icms_st == Decimal("0")

    def test_icms_st_nao_negativo(self):
        """Valor ST nunca pode ser negativo (quando ICMS próprio >= total ST)."""
        r = impostos_padrao(
            valor=Decimal("1000"),
            aliq_icms=Decimal("12"),
            mva=Decimal("0"),  # sem MVA real, força edge case
            crt="3",
        )
        assert r.valor_icms_st >= Decimal("0")


# ---------------------------------------------------------------------------
# IPI
# ---------------------------------------------------------------------------

class TestIPI:
    def test_ipi_calculado_para_cst_00(self):
        """CST IPI 00 (tributado normal) deve calcular IPI."""
        r = impostos_padrao(
            valor=Decimal("1000"),
            aliq_ipi=Decimal("10"),
            cst_ipi="00",
            crt="3",
        )
        assert r.valor_ipi == Decimal("100.00")
        assert r.aliq_ipi == Decimal("10")

    def test_ipi_zero_para_cst_49(self):
        """CST IPI 49 (saída tributada, mas alíquota 0) — sem IPI."""
        r = impostos_padrao(aliq_ipi=Decimal("0"), cst_ipi="49", crt="3")
        assert r.valor_ipi == Decimal("0")

    def test_ipi_zero_para_cst_99(self):
        """CST IPI 99 (outras saídas) — sem IPI."""
        r = impostos_padrao(aliq_ipi=Decimal("10"), cst_ipi="99", crt="3")
        assert r.valor_ipi == Decimal("0")

    def test_ipi_preserva_cst(self):
        r = impostos_padrao(cst_ipi="50", crt="3")
        assert r.cst_ipi == "50"


# ---------------------------------------------------------------------------
# PIS / COFINS
# ---------------------------------------------------------------------------

class TestPISCOFINS:
    def test_pis_cst01_calculado(self):
        """CST PIS 01 (cumulativo/não-cumulativo tributado) deve calcular PIS."""
        r = impostos_padrao(
            valor=Decimal("1000"),
            aliq_pis=Decimal("0.65"),
            cst_pis="01",
            crt="3",
        )
        assert r.valor_pis == Decimal("6.50")

    def test_cofins_cst01_calculado(self):
        r = impostos_padrao(
            valor=Decimal("1000"),
            aliq_cofins=Decimal("3.00"),
            cst_cofins="01",
            crt="3",
        )
        assert r.valor_cofins == Decimal("30.00")

    def test_pis_cst07_zero(self):
        """CST PIS 07 (operação isenta) = sem PIS."""
        r = impostos_padrao(aliq_pis=Decimal("0.65"), cst_pis="07", crt="3")
        assert r.valor_pis == Decimal("0")

    def test_cofins_cst09_zero(self):
        """CST COFINS 09 (outras isentas) = sem COFINS."""
        r = impostos_padrao(aliq_cofins=Decimal("3.00"), cst_cofins="09", crt="3")
        assert r.valor_cofins == Decimal("0")


# ---------------------------------------------------------------------------
# Créditos na Entrada
# ---------------------------------------------------------------------------

class TestCreditosEntrada:
    def test_regime_normal_compra_mp_gera_credito_ipi(self):
        """Compra de MP no Regime Normal gera crédito de IPI."""
        c = calcular_creditos_entrada(
            valor_produto=Decimal("1000"),
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("10"),
            aliq_pis=Decimal("1.65"),
            aliq_cofins=Decimal("7.60"),
            tipo_entrada="COMPRA_MP",
            crt_empresa="3",
        )
        assert c["credito_ipi"] == Decimal("100.00")
        assert c["credito_icms"] == Decimal("120.00")

    def test_regime_normal_revenda_nao_gera_credito_ipi(self):
        """Compra para revenda NO Regime Normal NÃO gera crédito de IPI."""
        c = calcular_creditos_entrada(
            valor_produto=Decimal("1000"),
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("10"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
            tipo_entrada="COMPRA_REVENDA",
            crt_empresa="3",
        )
        assert c["credito_ipi"] == Decimal("0")
        assert c["credito_icms"] == Decimal("120.00")

    def test_simples_nacional_sem_credito_algum(self):
        """No Simples Nacional (CRT 1), entrada não gera NENHUM crédito fiscal."""
        c = calcular_creditos_entrada(
            valor_produto=Decimal("1000"),
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("10"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
            tipo_entrada="COMPRA_MP",
            crt_empresa="1",
        )
        assert c["credito_icms"] == Decimal("0")
        assert c["credito_ipi"] == Decimal("0")
        assert c["credito_pis"] == Decimal("0")
        assert c["credito_cofins"] == Decimal("0")

    def test_simples_crt2_sem_credito(self):
        """CRT 2 também sem crédito."""
        c = calcular_creditos_entrada(
            valor_produto=Decimal("1000"),
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("10"),
            aliq_pis=Decimal("0"),
            aliq_cofins=Decimal("0"),
            tipo_entrada="COMPRA_MP",
            crt_empresa="2",
        )
        assert c["credito_icms"] == Decimal("0")

    def test_credito_pis_cofins_quando_informado(self):
        """Crédito de PIS/COFINS quando alíquota informada e regime normal."""
        c = calcular_creditos_entrada(
            valor_produto=Decimal("1000"),
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("0"),
            aliq_pis=Decimal("1.65"),
            aliq_cofins=Decimal("7.60"),
            tipo_entrada="COMPRA_MP",
            crt_empresa="3",
        )
        assert c["credito_pis"] == Decimal("16.50")
        assert c["credito_cofins"] == Decimal("76.00")


# ---------------------------------------------------------------------------
# Arredondamento (nunca pode ter mais de 2 casas decimais na NF)
# ---------------------------------------------------------------------------

class TestArredondamento:
    def test_icms_arredondado_2_decimais(self):
        r = impostos_padrao(valor=Decimal("333.33"), aliq_icms=Decimal("12"), crt="3")
        str_valor = str(r.valor_icms)
        partes = str_valor.split(".")
        if len(partes) > 1:
            assert len(partes[1]) <= 2

    def test_ipi_arredondado_2_decimais(self):
        r = impostos_padrao(valor=Decimal("333.33"), aliq_ipi=Decimal("10"), cst_ipi="00", crt="3")
        str_valor = str(r.valor_ipi)
        partes = str_valor.split(".")
        if len(partes) > 1:
            assert len(partes[1]) <= 2

    def test_total_impostos_e_soma_dos_componentes(self):
        """total_impostos() deve ser a soma correta de todos os componentes."""
        r = impostos_padrao(
            valor=Decimal("1000"),
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("10"),
            aliq_pis=Decimal("1.65"),
            aliq_cofins=Decimal("7.60"),
            mva=Decimal("0"),
            cst_ipi="00",
            cst_pis="01",
            cst_cofins="01",
            crt="3",
        )
        esperado = r.valor_icms + r.valor_ipi + r.valor_pis + r.valor_cofins + r.valor_icms_st + r.valor_difal
        assert r.total_impostos() == esperado
