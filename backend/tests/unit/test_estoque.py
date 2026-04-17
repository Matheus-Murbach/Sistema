"""
TDD — Testes unitários do serviço de estoque.

Comportamentos críticos:
  - Saldo nunca pode ir negativo (qualquer tipo de saída)
  - Reserva falha se não houver saldo disponível suficiente
  - Movimentação registra histórico imutável
  - Liberar reserva devolve para DISPONIVEL
  - Consumir reserva baixa o RESERVADO sem devolver ao DISPONIVEL

Estes testes usam um banco in-memory (SQLite) para rodar rápido sem Docker.
"""

import pytest
import pytest_asyncio
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.core.database import Base
from app.models.estoque import SaldoEstoque, MovimentacaoEstoque, ReservaEstoque
from app.models.produto import Produto, UnidadeMedida
from app.models.venda import PedidoVenda
from app.models.parceiro import Cliente
from app.services.estoque_service import (
    movimentar,
    get_saldo,
    get_saldo_total_disponivel,
    reservar_estoque,
    liberar_reserva,
)
from fastapi import HTTPException
import datetime


# ---------------------------------------------------------------------------
# Setup do banco in-memory para testes
# ---------------------------------------------------------------------------

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="function")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture(scope="function")
async def db(engine):
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session


@pytest.fixture(scope="function")
async def produto_e_localizacao(db):
    """Cria produto e localização de estoque básicos para os testes."""
    from app.models.estoque import LocalizacaoEstoque

    unidade = UnidadeMedida(codigo="UN", descricao="Unidade")
    db.add(unidade)
    await db.flush()

    produto = Produto(
        codigo="PROD-001",
        descricao="Produto Teste",
        tipo="MATERIA_PRIMA",
        unidade_id=unidade.id,
        aliq_icms=Decimal("12"),
        aliq_ipi=Decimal("0"),
        aliq_pis=Decimal("0.65"),
        aliq_cofins=Decimal("3.00"),
        mva=Decimal("0"),
        preco_custo=Decimal("10.00"),
        preco_venda=Decimal("15.00"),
    )
    db.add(produto)

    loc = LocalizacaoEstoque(codigo="A-01", descricao="Prateleira A-01")
    db.add(loc)
    await db.flush()

    return produto, loc


# ---------------------------------------------------------------------------
# get_saldo
# ---------------------------------------------------------------------------

class TestGetSaldo:
    async def test_saldo_zerado_quando_nao_existe(self, db, produto_e_localizacao):
        produto, loc = produto_e_localizacao
        saldo = await get_saldo(db, produto.id, loc.id, "DISPONIVEL")
        assert saldo == Decimal("0")

    async def test_saldo_retorna_quantidade_correta(self, db, produto_e_localizacao):
        produto, loc = produto_e_localizacao
        saldo_obj = SaldoEstoque(
            produto_id=produto.id,
            localizacao_id=loc.id,
            status="DISPONIVEL",
            quantidade=Decimal("50"),
        )
        db.add(saldo_obj)
        await db.flush()

        saldo = await get_saldo(db, produto.id, loc.id, "DISPONIVEL")
        assert saldo == Decimal("50")


# ---------------------------------------------------------------------------
# movimentar — Entradas
# ---------------------------------------------------------------------------

class TestMovimentarEntrada:
    async def test_entrada_cria_saldo(self, db, produto_e_localizacao):
        produto, loc = produto_e_localizacao
        mov = await movimentar(
            db, produto.id, loc.id,
            tipo="ENTRADA_COMPRA",
            quantidade=Decimal("100"),
        )
        await db.commit()

        saldo = await get_saldo(db, produto.id, loc.id)
        assert saldo == Decimal("100")

    async def test_entrada_acumula_saldo(self, db, produto_e_localizacao):
        produto, loc = produto_e_localizacao
        await movimentar(db, produto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("50"))
        await movimentar(db, produto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("30"))
        await db.commit()

        saldo = await get_saldo(db, produto.id, loc.id)
        assert saldo == Decimal("80")

    async def test_movimentacao_registra_saldo_apos(self, db, produto_e_localizacao):
        produto, loc = produto_e_localizacao
        mov = await movimentar(db, produto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("40"))
        await db.commit()
        assert mov.saldo_apos == Decimal("40")

    async def test_movimentacao_registra_tipo(self, db, produto_e_localizacao):
        produto, loc = produto_e_localizacao
        mov = await movimentar(db, produto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("10"))
        await db.commit()
        assert mov.tipo == "ENTRADA_COMPRA"


# ---------------------------------------------------------------------------
# movimentar — Saídas e Saldo Negativo (regra crítica)
# ---------------------------------------------------------------------------

class TestMovimentarSaida:
    async def test_saida_reduz_saldo(self, db, produto_e_localizacao):
        produto, loc = produto_e_localizacao
        await movimentar(db, produto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("100"))
        await movimentar(db, produto.id, loc.id, tipo="SAIDA_PRODUCAO", quantidade=Decimal("-30"))
        await db.commit()

        saldo = await get_saldo(db, produto.id, loc.id)
        assert saldo == Decimal("70")

    async def test_saida_maior_que_saldo_levanta_excecao(self, db, produto_e_localizacao):
        """Saída que deixaria saldo negativo DEVE falhar com HTTPException 422."""
        produto, loc = produto_e_localizacao
        await movimentar(db, produto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("10"))
        await db.commit()

        with pytest.raises(HTTPException) as exc_info:
            await movimentar(db, produto.id, loc.id, tipo="SAIDA_PRODUCAO", quantidade=Decimal("-50"))

        assert exc_info.value.status_code == 422

    async def test_saida_exata_do_saldo_permitida(self, db, produto_e_localizacao):
        """Saída exatamente igual ao saldo deve ser permitida (resultado = 0)."""
        produto, loc = produto_e_localizacao
        await movimentar(db, produto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("25"))
        await movimentar(db, produto.id, loc.id, tipo="SAIDA_VENDA", quantidade=Decimal("-25"))
        await db.commit()

        saldo = await get_saldo(db, produto.id, loc.id)
        assert saldo == Decimal("0")

    async def test_saldo_nunca_negativo_estoque_zerado(self, db, produto_e_localizacao):
        """Sem saldo existente, qualquer saída deve falhar."""
        produto, loc = produto_e_localizacao
        with pytest.raises(HTTPException) as exc_info:
            await movimentar(db, produto.id, loc.id, tipo="SAIDA_PRODUCAO", quantidade=Decimal("-1"))
        assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# get_saldo_total_disponivel
# ---------------------------------------------------------------------------

class TestSaldoTotalDisponivel:
    async def test_soma_todas_localizacoes(self, db, produto_e_localizacao):
        from app.models.estoque import LocalizacaoEstoque
        produto, loc1 = produto_e_localizacao

        loc2 = LocalizacaoEstoque(codigo="B-02", descricao="Prateleira B-02")
        db.add(loc2)
        await db.flush()

        await movimentar(db, produto.id, loc1.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("30"))
        await movimentar(db, produto.id, loc2.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("20"))
        await db.commit()

        total = await get_saldo_total_disponivel(db, produto.id)
        assert total == Decimal("50")

    async def test_nao_soma_status_reservado(self, db, produto_e_localizacao):
        """Saldo RESERVADO não deve entrar no total DISPONIVEL."""
        produto, loc = produto_e_localizacao
        # Adiciona diretamente saldo em diferentes status
        db.add(SaldoEstoque(produto_id=produto.id, localizacao_id=loc.id, quantidade=Decimal("60"), status="DISPONIVEL"))
        db.add(SaldoEstoque(produto_id=produto.id, localizacao_id=loc.id, quantidade=Decimal("20"), status="RESERVADO"))
        await db.commit()

        total = await get_saldo_total_disponivel(db, produto.id)
        assert total == Decimal("60")


# ---------------------------------------------------------------------------
# reservar_estoque
# ---------------------------------------------------------------------------

class TestReservaEstoque:
    async def _setup_pedido(self, db):
        """Cria um pedido de venda mínimo para usar como referência."""
        cliente = Cliente(
            razao_social="Cliente Teste",
            cnpj_cpf="12.345.678/0001-99",
        )
        db.add(cliente)
        await db.flush()

        pedido = PedidoVenda(
            numero="PV-TESTE-001",
            cliente_id=cliente.id,
            status="CONFIRMADO",
            data_emissao=datetime.date.today(),
        )
        db.add(pedido)
        await db.flush()
        return pedido

    async def test_reserva_move_disponivel_para_reservado(self, db, produto_e_localizacao):
        produto, loc = produto_e_localizacao
        pedido = await self._setup_pedido(db)

        await movimentar(db, produto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("100"))
        await reservar_estoque(db, produto.id, loc.id, Decimal("30"), pedido.id)
        await db.commit()

        disponivel = await get_saldo(db, produto.id, loc.id, "DISPONIVEL")
        reservado = await get_saldo(db, produto.id, loc.id, "RESERVADO")

        assert disponivel == Decimal("70")
        assert reservado == Decimal("30")

    async def test_reserva_falha_sem_saldo_suficiente(self, db, produto_e_localizacao):
        """Reserva mais do que disponível deve falhar."""
        produto, loc = produto_e_localizacao
        pedido = await self._setup_pedido(db)

        await movimentar(db, produto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("10"))
        await db.commit()

        with pytest.raises(HTTPException) as exc_info:
            await reservar_estoque(db, produto.id, loc.id, Decimal("50"), pedido.id)

        assert exc_info.value.status_code == 422

    async def test_reserva_cria_registro_de_reserva(self, db, produto_e_localizacao):
        produto, loc = produto_e_localizacao
        pedido = await self._setup_pedido(db)

        await movimentar(db, produto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("50"))
        await reservar_estoque(db, produto.id, loc.id, Decimal("20"), pedido.id)
        await db.commit()

        r = await db.execute(
            select(ReservaEstoque).where(
                ReservaEstoque.pedido_venda_id == pedido.id,
                ReservaEstoque.status == "ATIVA",
            )
        )
        reserva = r.scalar_one_or_none()
        assert reserva is not None
        assert reserva.quantidade == Decimal("20")


# ---------------------------------------------------------------------------
# liberar_reserva
# ---------------------------------------------------------------------------

class TestLiberarReserva:
    async def _setup_com_reserva(self, db, produto, loc, qtd_reserva=Decimal("30")):
        cliente = Cliente(razao_social="Cliente", cnpj_cpf="00.000.000/0001-00")
        db.add(cliente)
        await db.flush()
        pedido = PedidoVenda(
            numero="PV-LIB-001", cliente_id=cliente.id,
            status="CONFIRMADO", data_emissao=datetime.date.today()
        )
        db.add(pedido)
        await db.flush()

        await movimentar(db, produto.id, loc.id, tipo="ENTRADA_COMPRA", quantidade=Decimal("100"))
        await reservar_estoque(db, produto.id, loc.id, qtd_reserva, pedido.id)
        await db.commit()
        return pedido

    async def test_liberar_cancelamento_devolve_ao_disponivel(self, db, produto_e_localizacao):
        """consumir=False: cancelamento → estoque volta para DISPONIVEL."""
        produto, loc = produto_e_localizacao
        pedido = await self._setup_com_reserva(db, produto, loc, Decimal("30"))

        await liberar_reserva(db, pedido.id, consumir=False)
        await db.commit()

        disponivel = await get_saldo(db, produto.id, loc.id, "DISPONIVEL")
        reservado = await get_saldo(db, produto.id, loc.id, "RESERVADO")

        assert disponivel == Decimal("100")
        assert reservado == Decimal("0")

    async def test_consumir_baixa_reservado_sem_voltar_ao_disponivel(self, db, produto_e_localizacao):
        """consumir=True: expedição → RESERVADO baixa, DISPONIVEL não volta."""
        produto, loc = produto_e_localizacao
        pedido = await self._setup_com_reserva(db, produto, loc, Decimal("30"))

        await liberar_reserva(db, pedido.id, consumir=True)
        await db.commit()

        disponivel = await get_saldo(db, produto.id, loc.id, "DISPONIVEL")
        reservado = await get_saldo(db, produto.id, loc.id, "RESERVADO")

        assert disponivel == Decimal("70")   # não voltou
        assert reservado == Decimal("0")     # baixou

    async def test_reserva_fica_como_consumida_apos_expedicao(self, db, produto_e_localizacao):
        produto, loc = produto_e_localizacao
        pedido = await self._setup_com_reserva(db, produto, loc)

        await liberar_reserva(db, pedido.id, consumir=True)
        await db.commit()

        r = await db.execute(
            select(ReservaEstoque).where(ReservaEstoque.pedido_venda_id == pedido.id)
        )
        reserva = r.scalar_one_or_none()
        assert reserva.status == "CONSUMIDA"

    async def test_reserva_fica_como_liberada_apos_cancelamento(self, db, produto_e_localizacao):
        produto, loc = produto_e_localizacao
        pedido = await self._setup_com_reserva(db, produto, loc)

        await liberar_reserva(db, pedido.id, consumir=False)
        await db.commit()

        r = await db.execute(
            select(ReservaEstoque).where(ReservaEstoque.pedido_venda_id == pedido.id)
        )
        reserva = r.scalar_one_or_none()
        assert reserva.status == "LIBERADA"
