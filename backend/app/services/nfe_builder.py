"""
Constrói o payload JSON para o Focus NF-e a partir dos dados do pedido de venda.
Referência: https://focusnfe.com.br/doc/#notas-fiscais_nfe_post
"""
from decimal import Decimal
from datetime import datetime, timezone
from app.models.expedicao import NotaFiscalSaida
from app.core.config import settings


def build_payload_nfe(nf: NotaFiscalSaida, pedido, cliente, itens_com_impostos: list[dict]) -> dict:
    """
    Monta o dict que será enviado ao Focus NF-e.
    itens_com_impostos: lista com dados do produto + impostos calculados.
    """
    agora = datetime.now(timezone.utc).astimezone()
    data_emissao = agora.strftime("%Y-%m-%dT%H:%M:%S-03:00")

    payload = {
        "natureza_operacao": nf.natureza_operacao,
        "forma_pagamento": 0,  # 0=À vista (simplificado; expandir para parcelado)
        "tipo_documento": 1,  # 1=Saída
        "local_destino": 1 if cliente.uf == settings.EMPRESA_UF else 2,  # 1=intra, 2=inter, 3=exterior
        "data_emissao": data_emissao,
        "data_entrada_saida": data_emissao,
        "tipo_impressao_danfe": 1,  # 1=Retrato
        "forma_emissao": "1",  # 1=Emissão normal
        "finalidade_emissao": nf.finalidade,
        "processo_emissao": "0",
        "versao_processo_emissao": "1.0",
        "informacoes_adicionais_contribuinte": pedido.observacoes or "",

        # Emitente
        "cnpj_emitente": settings.EMPRESA_CNPJ,
        "nome_emitente": settings.EMPRESA_RAZAO_SOCIAL,
        "nome_fantasia_emitente": settings.EMPRESA_NOME_FANTASIA,
        "logradouro_emitente": settings.EMPRESA_LOGRADOURO,
        "numero_emitente": settings.EMPRESA_NUMERO,
        "bairro_emitente": settings.EMPRESA_BAIRRO,
        "municipio_emitente": settings.EMPRESA_MUNICIPIO,
        "uf_emitente": settings.EMPRESA_UF,
        "cep_emitente": settings.EMPRESA_CEP,
        "telefone_emitente": settings.EMPRESA_TELEFONE,
        "ie_emitente": settings.EMPRESA_IE,
        "crt": settings.EMPRESA_CRT,

        # Destinatário
        "nome_destinatario": cliente.razao_social,
        "email_destinatario": cliente.email or "",
        "logradouro_destinatario": cliente.logradouro or "",
        "numero_destinatario": cliente.numero or "",
        "bairro_destinatario": cliente.bairro or "",
        "municipio_destinatario": cliente.municipio or "",
        "uf_destinatario": cliente.uf or "",
        "cep_destinatario": cliente.cep or "",
        "ie_destinatario": cliente.ie or "ISENTO",
        "indicador_ie_destinatario": 9 if not cliente.ie else 1,  # 9=Não contribuinte
        "consumidor_final": 1 if cliente.consumidor_final else 0,

        # Frete
        "modalidade_frete": int(pedido.frete_por_conta or "0"),
        "valor_frete": float(pedido.valor_frete or 0),

        # Totais
        "icms_valor_total": float(nf.valor_icms),
        "valor_produtos": float(nf.valor_produtos),
        "valor_frete": float(nf.valor_frete),
        "valor_desconto": float(nf.valor_desconto),
        "valor_total": float(nf.valor_total),
        "pis_valor_total": float(nf.valor_pis),
        "cofins_valor_total": float(nf.valor_cofins),

        "items": _build_itens(itens_com_impostos),
    }

    # CPF ou CNPJ
    cnpj_cpf = (cliente.cnpj_cpf or "").replace(".", "").replace("-", "").replace("/", "").strip()
    if len(cnpj_cpf) == 14:
        payload["cnpj_destinatario"] = cnpj_cpf
    else:
        payload["cpf_destinatario"] = cnpj_cpf

    return payload


def _build_itens(itens: list[dict]) -> list[dict]:
    result = []
    for i, item in enumerate(itens, start=1):
        produto = item["produto"]
        impostos = item["impostos"]
        crt = settings.EMPRESA_CRT

        d = {
            "numero_item": i,
            "codigo_produto": produto.codigo,
            "descricao": produto.descricao,
            "cfop": impostos.cfop,
            "unidade_comercial": item["unidade"],
            "quantidade_comercial": float(item["quantidade"]),
            "valor_unitario_comercial": float(item["preco_unitario"]),
            "valor_bruto": float(item["valor_bruto"]),
            "codigo_ncm": produto.ncm or "00000000",
            "codigo_cest": produto.cest or "",
            "origem_mercadoria": produto.origem or "0",
            "valor_desconto": float(item.get("desconto", 0)),
        }

        # ICMS
        if crt in ("1", "2"):
            d["icms_situacao_tributaria"] = impostos.cst_icms or "400"
            d["icms_modalidade_base_calculo"] = 3
            d["icms_valor"] = 0
        else:
            d["icms_situacao_tributaria"] = impostos.cst_icms or "00"
            d["icms_modalidade_base_calculo"] = 3
            d["icms_base_calculo"] = float(impostos.base_icms)
            d["icms_aliquota"] = float(impostos.aliq_icms)
            d["icms_valor"] = float(impostos.valor_icms)

        # ICMS-ST
        if impostos.valor_icms_st > 0:
            d["icms_modalidade_base_calculo_st"] = 4
            d["icms_base_calculo_st"] = float(impostos.base_icms_st)
            d["icms_aliquota_st"] = float(impostos.aliq_icms)
            d["icms_valor_st"] = float(impostos.valor_icms_st)

        # IPI
        if impostos.valor_ipi > 0:
            d["ipi_situacao_tributaria"] = impostos.cst_ipi or "00"
            d["ipi_base_calculo"] = float(impostos.base_ipi)
            d["ipi_aliquota"] = float(impostos.aliq_ipi)
            d["ipi_valor"] = float(impostos.valor_ipi)
        else:
            d["ipi_situacao_tributaria"] = impostos.cst_ipi or "99"

        # PIS
        d["pis_situacao_tributaria"] = impostos.cst_pis or "07"
        if impostos.valor_pis > 0:
            d["pis_base_calculo"] = float(impostos.base_pis)
            d["pis_aliquota_percentual"] = float(impostos.aliq_pis)
            d["pis_valor"] = float(impostos.valor_pis)

        # COFINS
        d["cofins_situacao_tributaria"] = impostos.cst_cofins or "07"
        if impostos.valor_cofins > 0:
            d["cofins_base_calculo"] = float(impostos.base_cofins)
            d["cofins_aliquota_percentual"] = float(impostos.aliq_cofins)
            d["cofins_valor"] = float(impostos.valor_cofins)

        result.append(d)
    return result
