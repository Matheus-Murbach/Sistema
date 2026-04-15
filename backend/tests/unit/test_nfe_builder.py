"""
TDD — Testes do builder de NF-e.

Valida que o payload gerado para o Focus NF-e tem todos os campos
obrigatórios e os valores corretos. Estes testes evitam rejeição
no SEFAZ por campos faltando ou com formato errado.
"""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock
from datetime import datetime, timezone

from app.services.nfe_builder import build_payload_nfe, _build_itens
from app.services.fiscal import calcular_impostos_saida


def _make_produto(
    codigo="PROD-001",
    descricao="Produto Teste",
    ncm="73181500",
    origem="0",
    cst_icms="00",
    csosn=None,
    cst_ipi="99",
    cst_pis="01",
    cst_cofins="01",
    aliq_icms=Decimal("12"),
    aliq_ipi=Decimal("0"),
    aliq_pis=Decimal("0.65"),
    aliq_cofins=Decimal("3.00"),
    mva=Decimal("0"),
    cest=None,
):
    p = MagicMock()
    p.codigo = codigo
    p.descricao = descricao
    p.ncm = ncm
    p.origem = origem
    p.cst_icms = cst_icms
    p.csosn = csosn
    p.cst_ipi = cst_ipi
    p.cst_pis = cst_pis
    p.cst_cofins = cst_cofins
    p.aliq_icms = aliq_icms
    p.aliq_ipi = aliq_ipi
    p.aliq_pis = aliq_pis
    p.aliq_cofins = aliq_cofins
    p.mva = mva
    p.cest = cest
    return p


def _make_cliente(
    razao_social="Cliente Teste Ltda",
    cnpj_cpf="12.345.678/0001-99",
    logradouro="Rua Teste",
    numero="100",
    bairro="Centro",
    municipio="São Paulo",
    uf="SP",
    cep="01310-100",
    ie="123456789",
    consumidor_final=False,
    email="cliente@teste.com.br",
):
    c = MagicMock()
    c.razao_social = razao_social
    c.cnpj_cpf = cnpj_cpf.replace(".", "").replace("-", "").replace("/", "")
    c.logradouro = logradouro
    c.numero = numero
    c.bairro = bairro
    c.municipio = municipio
    c.uf = uf
    c.cep = cep
    c.ie = ie
    c.consumidor_final = consumidor_final
    c.email = email
    return c


def _make_nf(
    natureza_operacao="VENDA DE MERCADORIA",
    finalidade="1",
    valor_icms=Decimal("120.00"),
    valor_ipi=Decimal("0"),
    valor_pis=Decimal("6.50"),
    valor_cofins=Decimal("30.00"),
    valor_icms_st=Decimal("0"),
    valor_difal=Decimal("0"),
    valor_produtos=Decimal("1000.00"),
    valor_frete=Decimal("0"),
    valor_desconto=Decimal("0"),
    valor_total=Decimal("1000.00"),
    focus_referencia="NF-TEST-001",
):
    nf = MagicMock()
    nf.natureza_operacao = natureza_operacao
    nf.finalidade = finalidade
    nf.valor_icms = valor_icms
    nf.valor_ipi = valor_ipi
    nf.valor_pis = valor_pis
    nf.valor_cofins = valor_cofins
    nf.valor_icms_st = valor_icms_st
    nf.valor_difal = valor_difal
    nf.valor_produtos = valor_produtos
    nf.valor_frete = valor_frete
    nf.valor_desconto = valor_desconto
    nf.valor_total = valor_total
    nf.focus_referencia = focus_referencia
    return nf


def _make_pedido(observacoes=None, frete_por_conta="0", valor_frete=Decimal("0")):
    p = MagicMock()
    p.observacoes = observacoes
    p.frete_por_conta = frete_por_conta
    p.valor_frete = valor_frete
    return p


# ---------------------------------------------------------------------------
# Campos obrigatórios no payload raiz
# ---------------------------------------------------------------------------

class TestPayloadCamposObrigatorios:
    def _payload_basico(self):
        produto = _make_produto()
        cliente = _make_cliente()
        nf = _make_nf()
        pedido = _make_pedido()

        impostos = calcular_impostos_saida(
            valor_produto=Decimal("1000"),
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("0"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
            mva=Decimal("0"),
            uf_destino="SP",
            consumidor_final=False,
            crt_empresa="3",
            cst_icms="00",
            csosn=None,
            cst_ipi="99",
            cst_pis="01",
            cst_cofins="01",
        )

        itens = [{"produto": produto, "impostos": impostos,
                  "quantidade": Decimal("10"), "preco_unitario": Decimal("100"),
                  "valor_bruto": Decimal("1000"), "unidade": "UN", "desconto": Decimal("0")}]

        return build_payload_nfe(nf, pedido, cliente, itens)

    def test_payload_tem_natureza_operacao(self):
        p = self._payload_basico()
        assert "natureza_operacao" in p
        assert p["natureza_operacao"] == "VENDA DE MERCADORIA"

    def test_payload_tem_cnpj_emitente(self):
        p = self._payload_basico()
        assert "cnpj_emitente" in p

    def test_payload_tem_nome_emitente(self):
        p = self._payload_basico()
        assert "nome_emitente" in p

    def test_payload_tem_destinatario(self):
        p = self._payload_basico()
        assert ("cnpj_destinatario" in p or "cpf_destinatario" in p)

    def test_payload_tem_items(self):
        p = self._payload_basico()
        assert "items" in p
        assert len(p["items"]) > 0

    def test_payload_valor_total_correto(self):
        p = self._payload_basico()
        assert p["valor_total"] == 1000.0


# ---------------------------------------------------------------------------
# Itens do payload
# ---------------------------------------------------------------------------

class TestPayloadItens:
    def _impostos_basicos(self, crt="3"):
        return calcular_impostos_saida(
            valor_produto=Decimal("1000"),
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("10"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
            mva=Decimal("0"),
            uf_destino="SP",
            consumidor_final=False,
            crt_empresa=crt,
            cst_icms="00",
            csosn="400" if crt in ("1", "2") else None,
            cst_ipi="00",
            cst_pis="01",
            cst_cofins="01",
        )

    def test_item_tem_codigo_produto(self):
        produto = _make_produto(codigo="ABC-123")
        impostos = self._impostos_basicos()
        itens = _build_itens([{"produto": produto, "impostos": impostos,
                                "quantidade": Decimal("5"), "preco_unitario": Decimal("200"),
                                "valor_bruto": Decimal("1000"), "unidade": "UN", "desconto": Decimal("0")}])
        assert itens[0]["codigo_produto"] == "ABC-123"

    def test_item_tem_ncm(self):
        produto = _make_produto(ncm="73181500")
        impostos = self._impostos_basicos()
        itens = _build_itens([{"produto": produto, "impostos": impostos,
                                "quantidade": Decimal("1"), "preco_unitario": Decimal("1000"),
                                "valor_bruto": Decimal("1000"), "unidade": "UN", "desconto": Decimal("0")}])
        assert itens[0]["codigo_ncm"] == "73181500"

    def test_item_sem_ncm_usa_padrao_8_zeros(self):
        produto = _make_produto(ncm=None)
        impostos = self._impostos_basicos()
        itens = _build_itens([{"produto": produto, "impostos": impostos,
                                "quantidade": Decimal("1"), "preco_unitario": Decimal("100"),
                                "valor_bruto": Decimal("100"), "unidade": "UN", "desconto": Decimal("0")}])
        assert itens[0]["codigo_ncm"] == "00000000"

    def test_item_regime_normal_tem_icms_calculado(self):
        produto = _make_produto()
        impostos = self._impostos_basicos(crt="3")
        itens = _build_itens([{"produto": produto, "impostos": impostos,
                                "quantidade": Decimal("1"), "preco_unitario": Decimal("1000"),
                                "valor_bruto": Decimal("1000"), "unidade": "UN", "desconto": Decimal("0")}])
        assert itens[0].get("icms_valor", 0) == float(impostos.valor_icms)

    def test_item_simples_nacional_icms_zero(self):
        produto = _make_produto(csosn="400")
        impostos = self._impostos_basicos(crt="1")
        itens = _build_itens([{"produto": produto, "impostos": impostos,
                                "quantidade": Decimal("1"), "preco_unitario": Decimal("1000"),
                                "valor_bruto": Decimal("1000"), "unidade": "UN", "desconto": Decimal("0")}])
        assert itens[0].get("icms_valor", 0) == 0

    def test_item_tem_pis_quando_tributado(self):
        produto = _make_produto()
        impostos = self._impostos_basicos()
        itens = _build_itens([{"produto": produto, "impostos": impostos,
                                "quantidade": Decimal("1"), "preco_unitario": Decimal("1000"),
                                "valor_bruto": Decimal("1000"), "unidade": "UN", "desconto": Decimal("0")}])
        assert "pis_situacao_tributaria" in itens[0]

    def test_item_numero_sequencial_comeca_em_1(self):
        produto = _make_produto()
        impostos = self._impostos_basicos()
        item_data = {"produto": produto, "impostos": impostos,
                     "quantidade": Decimal("1"), "preco_unitario": Decimal("100"),
                     "valor_bruto": Decimal("100"), "unidade": "UN", "desconto": Decimal("0")}
        itens = _build_itens([item_data, item_data])
        assert itens[0]["numero_item"] == 1
        assert itens[1]["numero_item"] == 2


# ---------------------------------------------------------------------------
# Destinatário: CNPJ vs CPF
# ---------------------------------------------------------------------------

class TestDestinatarioCNPJCPF:
    def _build(self, cnpj_cpf):
        cliente = _make_cliente(cnpj_cpf=cnpj_cpf)
        nf = _make_nf()
        pedido = _make_pedido()
        produto = _make_produto()
        impostos = calcular_impostos_saida(
            valor_produto=Decimal("1000"), aliq_icms=Decimal("12"), aliq_ipi=Decimal("0"),
            aliq_pis=Decimal("0.65"), aliq_cofins=Decimal("3"), mva=Decimal("0"),
            uf_destino="SP", consumidor_final=False, crt_empresa="3",
            cst_icms="00", csosn=None, cst_ipi="99", cst_pis="01", cst_cofins="01",
        )
        itens = [{"produto": produto, "impostos": impostos, "quantidade": Decimal("1"),
                  "preco_unitario": Decimal("1000"), "valor_bruto": Decimal("1000"),
                  "unidade": "UN", "desconto": Decimal("0")}]
        return build_payload_nfe(nf, pedido, cliente, itens)

    def test_cnpj_14_digitos_vai_como_cnpj_destinatario(self):
        p = self._build("12345678000199")
        assert "cnpj_destinatario" in p
        assert "cpf_destinatario" not in p

    def test_cpf_11_digitos_vai_como_cpf_destinatario(self):
        p = self._build("12345678901")
        assert "cpf_destinatario" in p
        assert "cnpj_destinatario" not in p
