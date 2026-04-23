"""
Testes de integração — Fluxo de Produção via API (PCP).

Endpoints cobertos:
  POST /producao/                    → Cria OP (ABERTA)
  POST /producao/{id}/iniciar        → Consome MP do estoque (EM_PRODUCAO)
  POST /producao/{id}/concluir       → Registra produzido + refugo (CONCLUIDA)
  POST /producao/conversao-rapida    → Conversão instantânea MP→PA em operação única

Regras verificadas:
  - Ciclo completo ABERTA → EM_PRODUCAO → CONCLUIDA
  - Iniciar OP consome MP do estoque imediatamente
  - Concluir OP registra quantidade produzida e refugo com yield_percent
  - OP já EM_PRODUCAO não pode ser reiniciada (422)
  - MP insuficiente impede início da OP (422)
  - Conversão rápida: consome MP e cria PA em uma única chamada
  - Conversão rápida com localização automática (sem informar localizacao_mp_id)
  - Conversão rápida com MP insuficiente retorna 422
  - Todos os mutadores exigem autenticação (401 sem token)
"""
import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from app.models.produto import Produto, UnidadeMedida
from app.models.estoque import LocalizacaoEstoque
from app.models.maquina import Maquina
from app.services.estoque_service import movimentar


async def _setup_producao(test_engine):
    """Cria MP, produto acabado, localização, máquina e saldo inicial de MP."""
    Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        un = UnidadeMedida(codigo="UN", descricao="Unidade")
        session.add(un)
        await session.flush()

        mp = Produto(
            codigo="MP-ACO",
            descricao="Barra de Aço 1/2",
            tipo="MATERIA_PRIMA",
            unidade_id=un.id,
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("0"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
        )
        acabado = Produto(
            codigo="PA-PARAF",
            descricao="Parafuso M8 Zincado",
            tipo="PRODUTO_BENEFICIADO",
            unidade_id=un.id,
            aliq_icms=Decimal("12"),
            aliq_ipi=Decimal("0"),
            aliq_pis=Decimal("0.65"),
            aliq_cofins=Decimal("3.00"),
        )
        session.add(mp)
        session.add(acabado)

        loc = LocalizacaoEstoque(codigo="B-01", descricao="Linha de Produção 1")
        maquina = Maquina(codigo="M-01", nome="Prensa Hidráulica")
        session.add(loc)
        session.add(maquina)
        await session.flush()

        # Coloca 500 unidades de MP no estoque
        await movimentar(
            session, mp.id, loc.id,
            tipo="ENTRADA_COMPRA",
            quantidade=Decimal("500"),
        )
        await session.commit()

        return {
            "mp_id": mp.id,
            "acabado_id": acabado.id,
            "loc_id": loc.id,
            "maquina_id": maquina.id,
        }


class TestCriarOP:
    async def test_criar_op_basica(self, client, auth_headers, test_engine):
        ids = await _setup_producao(test_engine)

        r = await client.post("/api/v1/producao/", json={
            "produto_id": ids["acabado_id"],
            "maquina_id": ids["maquina_id"],
            "quantidade_planejada": "100",
            "localizacao_saida_id": ids["loc_id"],
            "materiais": [
                {"produto_id": ids["mp_id"], "quantidade_necessaria": "100"}
            ],
        }, headers=auth_headers)
        assert r.status_code == 201
        body = r.json()
        assert body["status"] == "ABERTA"
        assert body["produto_id"] == ids["acabado_id"]
        assert float(body["quantidade_planejada"]) == 100.0

    async def test_criar_op_sem_auth_retorna_401(self, client, test_engine):
        ids = await _setup_producao(test_engine)
        r = await client.post("/api/v1/producao/", json={
            "produto_id": ids["acabado_id"],
            "quantidade_planejada": "10",
            "materiais": [],
        })
        assert r.status_code == 401


class TestListarOPs:
    async def test_listar_ops_vazio(self, client):
        r = await client.get("/api/v1/producao/")
        assert r.status_code == 200
        assert r.json() == []

    async def test_listar_ops_com_filtro_status(self, client, auth_headers, test_engine):
        ids = await _setup_producao(test_engine)

        # Cria uma OP
        await client.post("/api/v1/producao/", json={
            "produto_id": ids["acabado_id"],
            "quantidade_planejada": "50",
            "localizacao_saida_id": ids["loc_id"],
            "materiais": [],
        }, headers=auth_headers)

        r = await client.get("/api/v1/producao/?status=ABERTA")
        assert r.status_code == 200
        assert len(r.json()) == 1

        r2 = await client.get("/api/v1/producao/?status=CONCLUIDA")
        assert r.status_code == 200
        assert len(r2.json()) == 0

    async def test_detalhar_op_inexistente_404(self, client):
        r = await client.get("/api/v1/producao/99999")
        assert r.status_code == 404


class TestFluxoProducao:
    async def test_ciclo_completo_criar_iniciar_concluir(
        self, client, auth_headers, test_engine
    ):
        """
        Fluxo completo de alta rotatividade:
          ABERTA → iniciar (consome MP) → EM_PRODUCAO → concluir → CONCLUIDA
        O estoque de MP deve diminuir e o de produto acabado deve aumentar.
        """
        ids = await _setup_producao(test_engine)

        # 1. Criar OP
        r_op = await client.post("/api/v1/producao/", json={
            "produto_id": ids["acabado_id"],
            "maquina_id": ids["maquina_id"],
            "quantidade_planejada": "100",
            "localizacao_saida_id": ids["loc_id"],
            "materiais": [
                {"produto_id": ids["mp_id"], "quantidade_necessaria": "100"}
            ],
        }, headers=auth_headers)
        assert r_op.status_code == 201
        op_id = r_op.json()["id"]

        # 2. Iniciar OP → consome 100 unidades de MP
        r_iniciar = await client.post(f"/api/v1/producao/{op_id}/iniciar", json=[
            {
                "produto_id": ids["mp_id"],
                "localizacao_id": ids["loc_id"],
                "quantidade": "100",
            }
        ], headers=auth_headers)
        assert r_iniciar.status_code == 200
        assert r_iniciar.json()["status"] == "EM_PRODUCAO"

        # 3. Concluir OP → 97 produzidos, 3 refugo
        r_concluir = await client.post(f"/api/v1/producao/{op_id}/concluir", json={
            "quantidade_produzida": "97",
            "quantidade_refugo": "3",
            "localizacao_saida_id": ids["loc_id"],
        }, headers=auth_headers)
        assert r_concluir.status_code == 200
        body_conclusao = r_concluir.json()
        assert body_conclusao["status"] == "CONCLUIDA"
        assert float(body_conclusao["quantidade_produzida"]) == 97.0
        assert float(body_conclusao["quantidade_refugo"]) == 3.0
        assert round(body_conclusao["yield_percent"], 2) == 97.0  # 97/100 × 100

    async def test_iniciar_op_consome_estoque_mp(self, client, auth_headers, test_engine):
        """Após iniciar a OP, o saldo de MP deve ser reduzido imediatamente."""
        from app.services.estoque_service import get_saldo_total_disponivel
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

        ids = await _setup_producao(test_engine)
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        # Saldo inicial: 500
        async with Session() as session:
            saldo_antes = await get_saldo_total_disponivel(session, ids["mp_id"])
        assert saldo_antes == Decimal("500")

        # Criar e iniciar OP consumindo 200 unidades
        r_op = await client.post("/api/v1/producao/", json={
            "produto_id": ids["acabado_id"],
            "quantidade_planejada": "200",
            "localizacao_saida_id": ids["loc_id"],
            "materiais": [
                {"produto_id": ids["mp_id"], "quantidade_necessaria": "200"}
            ],
        }, headers=auth_headers)
        op_id = r_op.json()["id"]

        await client.post(f"/api/v1/producao/{op_id}/iniciar", json=[
            {"produto_id": ids["mp_id"], "localizacao_id": ids["loc_id"], "quantidade": "200"}
        ], headers=auth_headers)

        # Saldo após: 300
        async with Session() as session:
            saldo_apos = await get_saldo_total_disponivel(session, ids["mp_id"])
        assert saldo_apos == Decimal("300")

    async def test_iniciar_op_que_nao_existe_retorna_404(self, client, auth_headers):
        r = await client.post("/api/v1/producao/99999/iniciar", json=[], headers=auth_headers)
        assert r.status_code == 404

    async def test_iniciar_op_ja_em_producao_retorna_422(
        self, client, auth_headers, test_engine
    ):
        """Tentar iniciar uma OP que já está EM_PRODUCAO deve retornar 422."""
        ids = await _setup_producao(test_engine)

        r_op = await client.post("/api/v1/producao/", json={
            "produto_id": ids["acabado_id"],
            "quantidade_planejada": "10",
            "localizacao_saida_id": ids["loc_id"],
            "materiais": [],
        }, headers=auth_headers)
        op_id = r_op.json()["id"]

        # Primeiro iniciar — OK
        await client.post(f"/api/v1/producao/{op_id}/iniciar", json=[], headers=auth_headers)

        # Segundo iniciar — deve falhar
        r = await client.post(f"/api/v1/producao/{op_id}/iniciar", json=[], headers=auth_headers)
        assert r.status_code == 422

    async def test_concluir_sem_localizacao_retorna_422(
        self, client, auth_headers, test_engine
    ):
        """Concluir OP sem localização de saída deve retornar 422."""
        ids = await _setup_producao(test_engine)

        r_op = await client.post("/api/v1/producao/", json={
            "produto_id": ids["acabado_id"],
            "quantidade_planejada": "10",
            # Sem localizacao_saida_id
            "materiais": [],
        }, headers=auth_headers)
        op_id = r_op.json()["id"]

        # Iniciar
        await client.post(f"/api/v1/producao/{op_id}/iniciar", json=[], headers=auth_headers)

        # Concluir sem localização
        r = await client.post(f"/api/v1/producao/{op_id}/concluir", json={
            "quantidade_produzida": "10",
        }, headers=auth_headers)
        assert r.status_code == 422

    async def test_iniciar_op_com_mp_insuficiente_retorna_422(
        self, client, auth_headers, test_engine
    ):
        """Tentar consumir mais MP do que disponível deve retornar 422."""
        ids = await _setup_producao(test_engine)

        r_op = await client.post("/api/v1/producao/", json={
            "produto_id": ids["acabado_id"],
            "quantidade_planejada": "1000",
            "localizacao_saida_id": ids["loc_id"],
            "materiais": [],
        }, headers=auth_headers)
        op_id = r_op.json()["id"]

        # Tenta consumir 600 quando só há 500
        r = await client.post(f"/api/v1/producao/{op_id}/iniciar", json=[
            {
                "produto_id": ids["mp_id"],
                "localizacao_id": ids["loc_id"],
                "quantidade": "600",  # Mais do que os 500 disponíveis!
            }
        ], headers=auth_headers)
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Conversão Rápida (MP → PA em operação única)
# ---------------------------------------------------------------------------

class TestConversaoRapida:
    async def test_conversao_basica_retorna_resumo(self, client, auth_headers, test_engine):
        """Conversão rápida retorna resumo com número da OP e quantidades processadas."""
        ids = await _setup_producao(test_engine)

        r = await client.post("/api/v1/producao/conversao-rapida", json={
            "produto_mp_id": ids["mp_id"],
            "localizacao_mp_id": ids["loc_id"],
            "quantidade_mp": "100",
            "produto_pa_id": ids["acabado_id"],
            "localizacao_pa_id": ids["loc_id"],
            "quantidade_pa": "100",
        }, headers=auth_headers)

        assert r.status_code == 201
        body = r.json()
        assert "op_numero" in body
        assert body["op_numero"].startswith("OP-")
        assert body["quantidade_mp_consumida"] == 100.0
        assert body["quantidade_pa_produzida"] == 100.0

    async def test_conversao_reduz_saldo_mp(self, client, auth_headers, test_engine):
        """Após conversão, saldo de MP deve diminuir pela quantidade consumida."""
        from app.services.estoque_service import get_saldo_total_disponivel

        ids = await _setup_producao(test_engine)
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        async with Session() as session:
            saldo_antes = await get_saldo_total_disponivel(session, ids["mp_id"])
        assert saldo_antes == Decimal("500")

        await client.post("/api/v1/producao/conversao-rapida", json={
            "produto_mp_id": ids["mp_id"],
            "localizacao_mp_id": ids["loc_id"],
            "quantidade_mp": "150",
            "produto_pa_id": ids["acabado_id"],
            "localizacao_pa_id": ids["loc_id"],
            "quantidade_pa": "150",
        }, headers=auth_headers)

        async with Session() as session:
            saldo_apos = await get_saldo_total_disponivel(session, ids["mp_id"])
        assert saldo_apos == Decimal("350")

    async def test_conversao_aumenta_saldo_pa(self, client, auth_headers, test_engine):
        """Após conversão, saldo do PA deve aumentar pela quantidade produzida."""
        from app.services.estoque_service import get_saldo_total_disponivel

        ids = await _setup_producao(test_engine)
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

        await client.post("/api/v1/producao/conversao-rapida", json={
            "produto_mp_id": ids["mp_id"],
            "localizacao_mp_id": ids["loc_id"],
            "quantidade_mp": "80",
            "produto_pa_id": ids["acabado_id"],
            "localizacao_pa_id": ids["loc_id"],
            "quantidade_pa": "80",
        }, headers=auth_headers)

        async with Session() as session:
            saldo_pa = await get_saldo_total_disponivel(session, ids["acabado_id"])
        assert saldo_pa == Decimal("80")

    async def test_conversao_sem_localizacao_usa_automatica(self, client, auth_headers, test_engine):
        """Sem informar localizacao_mp_id, o sistema usa a 1ª localização disponível."""
        ids = await _setup_producao(test_engine)

        r = await client.post("/api/v1/producao/conversao-rapida", json={
            "produto_mp_id": ids["mp_id"],
            "quantidade_mp": "10",
            "produto_pa_id": ids["acabado_id"],
            "quantidade_pa": "10",
        }, headers=auth_headers)

        assert r.status_code == 201

    async def test_conversao_mp_insuficiente_retorna_422(self, client, auth_headers, test_engine):
        """Tentar converter mais MP do que disponível deve retornar 422."""
        ids = await _setup_producao(test_engine)

        r = await client.post("/api/v1/producao/conversao-rapida", json={
            "produto_mp_id": ids["mp_id"],
            "localizacao_mp_id": ids["loc_id"],
            "quantidade_mp": "9999",  # Muito mais do que os 500 disponíveis
            "produto_pa_id": ids["acabado_id"],
            "localizacao_pa_id": ids["loc_id"],
            "quantidade_pa": "9999",
        }, headers=auth_headers)

        assert r.status_code == 422

    async def test_conversao_sem_auth_retorna_401(self, client):
        """Conversão rápida exige autenticação."""
        r = await client.post("/api/v1/producao/conversao-rapida", json={
            "produto_mp_id": 1,
            "quantidade_mp": "10",
            "produto_pa_id": 2,
            "quantidade_pa": "10",
        })
        assert r.status_code == 401

    async def test_conversao_registra_op_na_listagem_como_concluida(self, client, auth_headers, test_engine):
        """OP criada pela conversão rápida deve aparecer na listagem com status CONCLUIDA."""
        ids = await _setup_producao(test_engine)

        r = await client.post("/api/v1/producao/conversao-rapida", json={
            "produto_mp_id": ids["mp_id"],
            "localizacao_mp_id": ids["loc_id"],
            "quantidade_mp": "50",
            "produto_pa_id": ids["acabado_id"],
            "localizacao_pa_id": ids["loc_id"],
            "quantidade_pa": "50",
        }, headers=auth_headers)
        assert r.status_code == 201
        op_numero = r.json()["op_numero"]

        r_lista = await client.get("/api/v1/producao/?status=CONCLUIDA")
        assert r_lista.status_code == 200
        ops = r_lista.json()
        assert len(ops) == 1
        assert ops[0]["numero"] == op_numero
