"""
Testes de integração — Fluxo de Produção via API (PCP).

Verifica o ciclo completo de alta rotatividade:
  1. POST /producao/       → Cria OP (ABERTA)
  2. POST /iniciar         → Consome MP do estoque (EM_PRODUCAO)
  3. POST /concluir        → Registra produzido + refugo, entra no estoque (CONCLUIDA)

Também testa: listagem, detalhe, erros de status inválido.
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
