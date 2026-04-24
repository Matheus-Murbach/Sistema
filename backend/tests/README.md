# Documentação da Suite de Testes

## Visão Geral

| Métrica | Valor |
|---------|-------|
| Total de testes | **258** |
| Testes unitários | **68** |
| Testes de integração | **190** |
| Cobertura de módulos | 13 arquivos de teste |
| Tempo médio de execução | ~42 segundos (suite completa) |
| Framework | pytest 8.3 + pytest-asyncio (modo AUTO) |
| Banco de testes | SQLite in-memory (StaticPool) |

Todos os testes devem passar sem dependências externas (banco PostgreSQL, Redis, SEFAZ, BrasilAPI). Chamadas a APIs externas são interceptadas com `unittest.mock`.

---

## Estrutura de Diretórios

```
backend/tests/
├── conftest.py                          # Variáveis de ambiente para todos os testes
├── integration/
│   ├── conftest.py                      # Fixtures compartilhadas (client, auth, engine)
│   ├── test_api_crud.py                 # Health, Auth, Produtos, Parceiros, Estoque, Dashboard
│   ├── test_api_beneficiamento.py       # Lotes de beneficiamento externo (banho)
│   ├── test_api_compras.py              # Pedidos de compra a fornecedores
│   ├── test_api_expedicao.py            # Expedição de pedidos e preview fiscal
│   ├── test_api_picking.py              # Montagem de pedidos com scanner
│   ├── test_api_producao.py             # Ordens de produção e conversão rápida MP→PA
│   ├── test_api_produtos_importar.py    # Importação em lote e consulta NCM
│   ├── test_api_recebimento.py          # Recebimento de NFs e entrada de estoque
│   ├── test_api_vendas.py               # Pedidos de venda, reservas, cancelamentos
│   ├── test_fluxo_banho.py              # Fluxo completo de beneficiamento (banco próprio)
│   └── test_security.py                # Autenticação, injeção SQL, XSS, integridade
└── unit/
    ├── test_estoque.py                  # Serviço de estoque (movimentações, reservas)
    ├── test_fiscal.py                   # Serviço fiscal (ICMS, IPI, PIS/COFINS, DIFAL, ST)
    └── test_nfe_builder.py              # Builder de payload NF-e para o Focus NF-e
```

---

## Infraestrutura de Testes

### conftest.py (raiz)

Define variáveis de ambiente fixas para toda a suite, garantindo comportamento determinístico independente do `.env` local:

```python
os.environ.setdefault("EMPRESA_UF", "SP")       # UF da empresa = SP (base para cálculo ICMS)
os.environ.setdefault("EMPRESA_CRT", "3")        # Regime Normal (Lucro Presumido)
os.environ.setdefault("SECRET_KEY", "test-secret-key-nao-usar-em-producao")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
```

Também importa `app.models` para garantir que todos os modelos SQLAlchemy estejam registrados em `Base.metadata` antes de qualquer `create_all`.

### integration/conftest.py — Fixtures Compartilhadas

Todas as fixtures têm `scope="function"`: banco limpo por teste, sem vazamento de estado entre casos.

#### `test_engine`
Cria uma engine SQLite in-memory com `StaticPool`. O `StaticPool` é essencial: força que todas as conexões criadas para aquela engine (pela API e pelos helpers de setup) usem exatamente a mesma conexão física. Sem isso, os dados inseridos diretamente no banco seriam invisíveis para a API (cada `connect()` abriria um banco diferente em memória).

```python
eng = create_async_engine(TEST_DB_URL, echo=False, poolclass=StaticPool)
async with eng.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

#### `client`
`httpx.AsyncClient` com `ASGITransport` apontando para a aplicação FastAPI. O `get_db` da aplicação é sobrescrito via `dependency_overrides` para usar a mesma session da `test_engine`, garantindo que dados criados nos helpers apareçam nas chamadas HTTP.

#### `auth_headers`
Cria um usuário `admin@teste.com` / `senha123` diretamente no banco e gera um JWT válido. Retorna `{"Authorization": "Bearer <token>"}` pronto para uso nos testes de endpoints autenticados.

#### `unidade_padrao`
Cria `UnidadeMedida(codigo="UN")` e retorna seu `id`. Necessária como dependência ao criar produtos via API.

#### `localizacao_padrao`
Cria `LocalizacaoEstoque(codigo="A-01")` e retorna seu `id`.

### Como Rodar

```bash
# Suite completa
python -m pytest tests/ -v

# Somente unitários (rápido, sem HTTP)
python -m pytest tests/unit/ -v

# Somente integração
python -m pytest tests/integration/ -v

# Um arquivo específico
python -m pytest tests/integration/test_security.py -v

# Com cobertura
python -m pytest tests/ --cov=app --cov-report=term-missing

# Parar no primeiro erro
python -m pytest tests/ -x --tb=short
```

---

## Testes Unitários

Os testes unitários não fazem chamadas HTTP e não dependem de fixtures de banco compartilhadas — cada arquivo cria sua própria engine in-memory isolada. São rápidos e executam em menos de 2 segundos.

---

### `unit/test_fiscal.py` — 34 testes

**Módulo testado:** `app/services/fiscal.py`
**Funções:** `calcular_impostos_saida()`, `calcular_creditos_entrada()`, `aliquota_icms_interestadual()`
**Retorno:** dataclass `ImpostosItem` com campos `valor_icms`, `valor_ipi`, `valor_pis`, `valor_cofins`, `valor_icms_st`, `valor_difal`, `base_icms`, `base_icms_st`, `aliq_icms`, `cfop`, `cst_icms`, `cst_ipi`, `total_impostos()`

O helper `impostos_padrao()` encapsula a chamada com defaults razoáveis, permitindo sobrescrever apenas o parâmetro em teste.

#### `TestAliquotaInterestadual` (3 testes)

Testa a função pura `aliquota_icms_interestadual(uf_origem, uf_destino)`:

| Teste | Entrada | Saída esperada | Regra |
|-------|---------|----------------|-------|
| `test_intraestadual_mesmo_estado` | `"SP"→"SP"` | `Decimal("12")` | Mesma UF = alíquota interna |
| `test_interestadual_para_sul_sudeste` | `"CE"→"SP/RJ/MG/RS/PR/SC/ES"` | `Decimal("12")` | Destinos ricos = 12% |
| `test_interestadual_para_norte_nordeste` | `"SP"→"AM/PA/CE/BA/GO/MT/MS"` | `Decimal("7")` | Destinos menos desenvolvidos = 7% |

#### `TestICMSSaidaRegimeNormal` (6 testes)

Valida o cálculo de ICMS na saída para Regime Normal (CRT 3):

- **`test_icms_intraestadual_calculado`**: R$1.000 × 12% = R$120,00 exatos.
- **`test_icms_base_igual_ao_valor_produto`**: `base_icms` deve ser o valor do produto (sem IPI na base neste modelo).
- **`test_cfop_intraestadual`**: Venda dentro de SP → CFOP `5102`.
- **`test_cfop_interestadual`**: Venda SP→RJ → CFOP `6102`.
- **`test_icms_interestadual_aliquota_reduzida`**: SP→AM aplica 7%, resultando em R$70,00 sobre R$1.000.
- **`test_cst_icms_preservado`**: O CST informado (`"10"`) é propagado para o resultado sem modificação.

#### `TestICMSSimlesNacional` (3 testes)

Simples Nacional (CRT 1 e 2): ICMS recolhido no DAS, não destacado na NF-e.

- **`test_simples_icms_zero_na_saida`**: `valor_icms == Decimal("0")` e `aliq_icms == Decimal("0")`.
- **`test_simples_usa_csosn_nao_cst`**: CSOSN `"102"` é aplicado como `cst_icms` no resultado.
- **`test_simples_crt2_igual_crt1_para_icms`**: CRT 2 tem mesmo tratamento que CRT 1 para ICMS.

#### `TestDIFAL` (3 testes)

DIFAL (EC 87/2015): diferencial de alíquota em vendas interestaduais para consumidor final.

- **`test_difal_consumidor_final_interestadual`**: SP→AM, consumidor final. Alíquota interna destino = 18%, interestadual = 7%. `valor_difal = (18 - 7) × 1000 / 100 = R$110,00`.
- **`test_sem_difal_para_contribuinte`**: Venda para empresa contribuinte → `valor_difal == 0`.
- **`test_sem_difal_intraestadual`**: Dentro do mesmo estado não há DIFAL mesmo para consumidor final.

#### `TestICMSST` (3 testes)

ICMS-ST com MVA (Margem de Valor Agregado). Fórmula: `base_st = valor × (1 + MVA/100)`, `valor_st = base_st × aliq - icms_proprio`.

- **`test_icms_st_com_mva`**: R$1.000, MVA=40%. `base_st = 1.400`. `valor_st_total = 168`. `icms_proprio = 120`. `valor_icms_st = R$48,00`.
- **`test_sem_icms_st_quando_mva_zero`**: MVA=0 → `valor_icms_st == 0`.
- **`test_icms_st_nao_negativo`**: Garante que o resultado nunca seja negativo por arredondamento.

#### `TestIPI` (4 testes)

IPI incide somente em produtos industrializados com CST específico:

- **`test_ipi_calculado_para_cst_00`**: CST `"00"` → R$1.000 × 10% = R$100,00.
- **`test_ipi_zero_para_cst_49`**: CST `"49"` (saída sem débito) → IPI = 0 independente da alíquota.
- **`test_ipi_zero_para_cst_99`**: CST `"99"` (outras saídas) → IPI = 0 mesmo com alíquota 10%.
- **`test_ipi_preserva_cst`**: CST `"50"` é propagado sem modificação.

#### `TestPISCOFINS` (4 testes)

- **`test_pis_cst01_calculado`**: CST `"01"` → R$1.000 × 0,65% = R$6,50.
- **`test_cofins_cst01_calculado`**: R$1.000 × 3,00% = R$30,00.
- **`test_pis_cst07_zero`**: CST `"07"` (operação isenta) → PIS = 0.
- **`test_cofins_cst09_zero`**: CST `"09"` → COFINS = 0.

#### `TestCreditosEntrada` (5 testes)

Créditos fiscais no recebimento de mercadorias:

| Cenário | CRT | Tipo entrada | Crédito IPI | Crédito ICMS |
|---------|-----|-------------|-------------|--------------|
| `test_regime_normal_compra_mp_gera_credito_ipi` | 3 | COMPRA_MP | R$100 | R$120 |
| `test_regime_normal_revenda_nao_gera_credito_ipi` | 3 | COMPRA_REVENDA | R$0 | R$120 |
| `test_simples_nacional_sem_credito_algum` | 1 | COMPRA_MP | R$0 | R$0 |
| `test_simples_crt2_sem_credito` | 2 | COMPRA_MP | R$0 | R$0 |
| `test_credito_pis_cofins_quando_informado` | 3 | COMPRA_MP | — | PIS=R$16,50 / COFINS=R$76,00 |

#### `TestArredondamento` (3 testes)

NF-e aceita no máximo 2 casas decimais. Valida que `valor_icms` e `valor_ipi` nunca excedam esse limite e que `total_impostos()` é a soma exata de todos os componentes.

---

### `unit/test_estoque.py` — 19 testes

**Módulo testado:** `app/services/estoque_service.py`
**Funções:** `movimentar()`, `get_saldo()`, `get_saldo_total_disponivel()`, `reservar_estoque()`, `liberar_reserva()`
**Banco:** SQLite in-memory com engine e session próprias

#### `TestGetSaldo` (2 testes)

- **`test_saldo_zerado_quando_nao_existe`**: `get_saldo()` retorna `Decimal("0")` quando não há registro — nunca lança exceção por linha ausente.
- **`test_saldo_retorna_quantidade_correta`**: Com `SaldoEstoque(quantidade=50)` inserido diretamente, retorna `Decimal("50")`.

#### `TestMovimentarEntrada` (4 testes)

- **`test_entrada_cria_saldo`**: `tipo="ENTRADA_COMPRA", quantidade=100` cria saldo de 100.
- **`test_entrada_acumula_saldo`**: Duas entradas (50 + 30) resultam em saldo 80 — não substitui, acumula.
- **`test_movimentacao_registra_saldo_apos`**: Campo `MovimentacaoEstoque.saldo_apos` reflete o saldo pós-movimentação para trilha de auditoria imutável.
- **`test_movimentacao_registra_tipo`**: O campo `tipo` é preservado exatamente como informado.

#### `TestMovimentarSaida` (4 testes)

**Regra crítica: estoque nunca pode ficar negativo.**

- **`test_saida_reduz_saldo`**: 100 disponível, saída de 30 → saldo 70.
- **`test_saida_maior_que_saldo_levanta_excecao`**: 10 disponível, saída de 50 → `HTTPException(422)`. Principal guard contra estoque negativo.
- **`test_saida_exata_do_saldo_permitida`**: Saída igual ao saldo → saldo 0 (zero é permitido).
- **`test_saldo_nunca_negativo_estoque_zerado`**: Qualquer saída com saldo zero → `HTTPException(422)`.

#### `TestSaldoTotalDisponivel` (2 testes)

- **`test_soma_todas_localizacoes`**: Produto em dois locais (30 + 20) → `get_saldo_total_disponivel()` retorna 50.
- **`test_nao_soma_status_reservado`**: DISPONIVEL=60, RESERVADO=20 → total disponível = 60.

#### `TestReservaEstoque` (3 testes)

- **`test_reserva_move_disponivel_para_reservado`**: Reservar 30 de 100 → DISPONIVEL=70, RESERVADO=30.
- **`test_reserva_falha_sem_saldo_suficiente`**: Reservar 50 com apenas 10 disponíveis → `HTTPException(422)`.
- **`test_reserva_cria_registro_de_reserva`**: Cria linha em `ReservaEstoque` com `status="ATIVA"` e `quantidade=20`.

#### `TestLiberarReserva` (4 testes)

`liberar_reserva(db, pedido_id, consumir: bool)` tem dois comportamentos distintos:

| `consumir` | Semântica | DISPONIVEL | RESERVADO | Status da reserva |
|-----------|-----------|------------|-----------|-------------------|
| `False` | Cancelamento | Volta (+30) | Zerado | `"LIBERADA"` |
| `True` | Expedição | Não volta | Zerado | `"CONSUMIDA"` |

- **`test_liberar_cancelamento_devolve_ao_disponivel`**: `consumir=False` → DISPONIVEL=100, RESERVADO=0.
- **`test_consumir_baixa_reservado_sem_voltar_ao_disponivel`**: `consumir=True` → DISPONIVEL=70, RESERVADO=0.
- **`test_reserva_fica_como_consumida_apos_expedicao`**: `ReservaEstoque.status == "CONSUMIDA"`.
- **`test_reserva_fica_como_liberada_apos_cancelamento`**: `ReservaEstoque.status == "LIBERADA"`.

---

### `unit/test_nfe_builder.py` — 15 testes

**Módulo testado:** `app/services/nfe_builder.py`
**Funções:** `build_payload_nfe()`, `_build_itens()`
**Mocks:** `_make_produto()`, `_make_cliente()`, `_make_nf()`, `_make_pedido()` usam `MagicMock` para simular objetos ORM sem banco

O payload gerado deve estar em conformidade com o schema do Focus NF-e. Campos faltantes ou com formato errado causam rejeição no SEFAZ.

#### `TestPayloadCamposObrigatorios` (6 testes)

- **`test_payload_tem_natureza_operacao`**: `payload["natureza_operacao"] == "VENDA DE MERCADORIA"`.
- **`test_payload_tem_cnpj_emitente`**: Chave `"cnpj_emitente"` presente.
- **`test_payload_tem_nome_emitente`**: Chave `"nome_emitente"` presente.
- **`test_payload_tem_destinatario`**: Ao menos `"cnpj_destinatario"` ou `"cpf_destinatario"` presente.
- **`test_payload_tem_items`**: Lista `"items"` presente e não vazia.
- **`test_payload_valor_total_correto`**: `payload["valor_total"] == 1000.0`.

#### `TestPayloadItens` (7 testes)

- **`test_item_tem_codigo_produto`**: `itens[0]["codigo_produto"] == "ABC-123"`.
- **`test_item_tem_ncm`**: NCM `"73181500"` → `"codigo_ncm": "73181500"`.
- **`test_item_sem_ncm_usa_padrao_8_zeros`**: `ncm=None` → `"codigo_ncm": "00000000"` (SEFAZ rejeita campo vazio).
- **`test_item_regime_normal_tem_icms_calculado`**: `itens[0]["icms_valor"]` igual ao `impostos.valor_icms`.
- **`test_item_simples_nacional_icms_zero`**: CRT 1 + CSOSN `"400"` → `icms_valor == 0`.
- **`test_item_tem_pis_quando_tributado`**: Chave `"pis_situacao_tributaria"` presente.
- **`test_item_numero_sequencial_comeca_em_1`**: Dois itens → `numero_item` 1 e 2 (obrigatório na NF-e).

#### `TestDestinatarioCNPJCPF` (2 testes)

- **`test_cnpj_14_digitos_vai_como_cnpj_destinatario`**: 14 dígitos → `"cnpj_destinatario"` presente, `"cpf_destinatario"` ausente.
- **`test_cpf_11_digitos_vai_como_cpf_destinatario`**: 11 dígitos → `"cpf_destinatario"` presente, `"cnpj_destinatario"` ausente.

---

## Testes de Integração

Os testes de integração testam os endpoints HTTP de ponta a ponta: request HTTP → FastAPI → SQLAlchemy → SQLite in-memory. Cada teste começa com banco limpo e cria seus próprios dados de suporte via helpers `_setup_*()`.

---

### `integration/test_api_crud.py` — 29 testes

**Módulo:** Endpoints base — health, auth, produtos, parceiros, estoque, dashboard

#### `TestHealthCheck` (1 teste)
- **`test_health_retorna_ok`**: `GET /health` retorna `{"status": "ok"}` sem autenticação.

#### `TestAuth` (3 testes)
- **`test_login_invalido_retorna_401`**: Credenciais inexistentes → 401.
- **`test_login_valido_retorna_token`**: `POST /auth/login` com `admin@teste.com`/`senha123` retorna `access_token`, `token_type="bearer"` e `perfil="admin"`.
- **`test_endpoint_autenticado_sem_token_retorna_401`**: `POST /produtos/` sem `Authorization` → 401.

#### `TestProdutosCRUD` (9 testes)
- **`test_listar_produtos_vazio`**: `GET /produtos/` com banco vazio → `[]`.
- **`test_criar_produto`**: POST com todos os campos fiscais (NCM, alíquotas) → 201, `codigo="PROD-001"`, `tipo="PRODUTO_BENEFICIADO"`.
- **`test_listar_produtos_apos_criacao`**: Produto criado aparece na listagem.
- **`test_detalhar_produto`**: `GET /produtos/{id}` retorna `id` correto.
- **`test_detalhar_produto_inexistente_retorna_404`**: ID 99999 → 404.
- **`test_atualizar_produto`**: `PUT /produtos/{id}` persiste `descricao="Depois"`.
- **`test_buscar_produto_por_descricao`**: `?q=especial` encontra "Parafuso Especial" (case-insensitive).
- **`test_buscar_produto_sem_resultado`**: Termo inexistente → `[]`.
- **`test_produto_sem_ncm_nao_tem_aliquotas_ibpt`**: `GET /produtos/{id}/aliquotas-ncm` sem NCM → 400.

#### `TestFornecedoresCRUD` (4 testes)
- **`test_listar_fornecedores_vazio`**: `GET /parceiros/fornecedores/` → `[]`.
- **`test_criar_fornecedor`**: POST retorna 201 com `razao_social` e `cnpj_cpf` persistidos.
- **`test_detalhar_fornecedor`**: `GET /fornecedores/{id}` retorna o registro.
- **`test_fornecedor_inexistente_retorna_404`**: ID 99999 → 404.

#### `TestClientesCRUD` (3 testes)
- **`test_criar_cliente`**: POST com `uf="RJ"`, `consumidor_final=False` → 201.
- **`test_listar_clientes`**: Dois clientes criados → listagem retorna 2 itens.
- **`test_atualizar_cliente`**: PUT persiste `razao_social="Cliente Atualizado"`.

#### `TestEstoqueCRUD` (6 testes)
- **`test_listar_localizacoes_vazio`**: `GET /estoque/localizacoes` → `[]`.
- **`test_criar_localizacao`**: POST com `corredor="A"`, `prateleira="01"` → 201.
- **`test_listar_saldos_vazio`**: `GET /estoque/saldos` → `[]` (público, sem auth).
- **`test_pronta_entrega_retorna_lista`**: `GET /estoque/pronta-entrega` → 200, lista (pode estar vazia).
- **`test_alertas_estoque_minimo_retorna_lista`**: `GET /estoque/alertas-estoque-minimo` → 200.
- **`test_listar_movimentacoes`**: `GET /estoque/movimentacoes` → 200 (público).

#### `TestDashboard` (3 testes)
- **`test_resumo_dashboard`**: `GET /dashboard/resumo` com auth → 200 com campos `ops_abertas`, `pedidos_pendentes_expedicao`, `lotes_no_banho`, `lotes_banho_atrasados`, `vendas_mes`, `data`.
- **`test_dashboard_sem_auth_retorna_401`**: Sem token → 401.
- **`test_dashboard_valores_zerados_sem_dados`**: Banco vazio → todos os contadores = 0.

---

### `integration/test_api_compras.py` — 13 testes

**Endpoints:** `GET /compras/`, `POST /compras/`, `PUT /compras/{id}/status`

Setup: `Fornecedor("Aços Brasil Ltda")` e `Produto("MP-ACO-001", tipo="MATERIA_PRIMA")`.

#### `TestListarPedidosCompra` (3 testes)
- **`test_listar_vazio`**: Banco vazio → `[]`.
- **`test_listar_apos_criacao`**: Pedido criado aparece na listagem.
- **`test_filtro_por_status_aberto`**: `?status=ABERTO` retorna 1 pedido; `?status=ENVIADO` retorna 0.

#### `TestCriarPedidoCompra` (6 testes)
- **`test_criar_basico_retorna_201`**: POST com 1 item (50 × R$8,00) → `status="ABERTO"`, `valor_total=400.0`, `numero` começa com `"PC-"`.
- **`test_numero_unico_dois_pedidos_mesmo_fornecedor`**: Dois POSTs para o mesmo fornecedor no mesmo dia → números distintos. Evita `UniqueViolationError` com sequência automática.
- **`test_valor_total_multiplos_itens`**: Dois itens (10 × R$5 + 20 × R$3) → `valor_total=110.0`.
- **`test_pedido_sem_itens_valor_zero`**: `itens=[]` → aceito com `valor_total=0.0`.
- **`test_criar_sem_auth_retorna_401`**: POST sem token → 401.
- **`test_criar_com_condicao_pagamento`**: Campos opcionais `condicao_pagamento="30/60/90 dias"` e `observacoes="Frete CIF"` são persistidos.

#### `TestAtualizarStatusCompra` (4 testes)
- **`test_atualizar_para_enviado`**: `PUT /compras/{id}/status?novo_status=ENVIADO` → `status="ENVIADO"`.
- **`test_atualizar_para_recebido`**: Status pode avançar direto para `RECEBIDO`.
- **`test_pedido_inexistente_retorna_404`**: ID 99999 → 404.
- **`test_atualizar_sem_auth_retorna_401`**: PUT sem token → 401.

---

### `integration/test_api_recebimento.py` — 7 testes

**Endpoints:** `GET /recebimento/`, `GET /recebimento/{id}`, `POST /recebimento/`

Setup: `Produto("MP-001", tipo="MATERIA_PRIMA", aliq_ipi=5%)`, `LocalizacaoEstoque("E-01")`, `Fornecedor("Siderúrgica Norte Ltda", uf="MG")`.

#### `TestListarEntradas` (2 testes)
- **`test_listar_entradas_vazio`**: Banco vazio → `[]`.
- **`test_detalhar_entrada_inexistente_404`**: ID 99999 → 404.

#### `TestRegistrarEntrada` (5 testes)
- **`test_entrada_compra_mp_da_estoque`**: POST com `tipo_entrada="COMPRA_MP"`, 100 unidades a R$50 → 201, `numero_nf="NF-12345"`, `status="LANCADA"`, `valor_produtos=5000.0`.
- **`test_entrada_calcula_credito_icms_regime_normal`**: CRT 3, 100 unidades a R$100, `aliq_icms=12%`, `aliq_ipi=5%` → `credito_icms=1200.0`, `credito_ipi=500.0` (IPI só em COMPRA_MP no Regime Normal).
- **`test_entrada_com_qc_usa_quantidade_aprovada`**: `quantidade=100`, `quantidade_aprovada=90`, `aprovado_qc=True` → `valor_produtos=900.0` (custo sobre aprovadas, não sobre total recebido).
- **`test_entrada_sem_auth_retorna_401`**: POST sem token → 401.
- **`test_listar_entradas_apos_criacao`**: NF registrada aparece em `GET /recebimento/`.

---

### `integration/test_api_producao.py` — 18 testes

**Endpoints:** `POST /producao/`, `GET /producao/`, `GET /producao/{id}`, `POST /producao/{id}/iniciar`, `POST /producao/{id}/concluir`, `POST /producao/conversao-rapida`

Setup: `Produto("MP-ACO", tipo="MATERIA_PRIMA")` com 500 unidades, `Produto("PA-PARAF", tipo="PRODUTO_BENEFICIADO")`, `Maquina("M-01")`, `LocalizacaoEstoque("B-01")`.

#### `TestCriarOP` (2 testes)
- **`test_criar_op_basica`**: POST com produto, máquina, `quantidade_planejada=100` e lista de materiais → 201, `status="ABERTA"`.
- **`test_criar_op_sem_auth_retorna_401`**: POST sem token → 401.

#### `TestListarOPs` (3 testes)
- **`test_listar_ops_vazio`**: Banco vazio → `[]`.
- **`test_listar_ops_com_filtro_status`**: `?status=ABERTA` retorna 1; `?status=CONCLUIDA` retorna 0.
- **`test_detalhar_op_inexistente_404`**: ID 99999 → 404.

#### `TestFluxoProducao` (6 testes)
- **`test_ciclo_completo_criar_iniciar_concluir`**: Cria OP → `POST /iniciar` (consome 100 MP) → `POST /concluir` (97 produzidos, 3 refugo). Verifica `status="CONCLUIDA"`, `quantidade_produzida=97.0`, `quantidade_refugo=3.0`, `yield_percent=97.0`.
- **`test_iniciar_op_consome_estoque_mp`**: Após `iniciar` com consumo de 200 MP, saldo vai de 500 → 300. Verificado via `get_saldo_total_disponivel()` diretamente no banco.
- **`test_iniciar_op_que_nao_existe_retorna_404`**: ID 99999 → 404.
- **`test_iniciar_op_ja_em_producao_retorna_422`**: Segundo `iniciar` na mesma OP (já `EM_PRODUCAO`) → 422.
- **`test_concluir_sem_localizacao_retorna_422`**: `POST /concluir` sem `localizacao_saida_id` → 422.
- **`test_iniciar_op_com_mp_insuficiente_retorna_422`**: Tentar consumir 600 com apenas 500 disponíveis → 422 (guard do estoque).

#### `TestConversaoRapida` (7 testes)

Endpoint `POST /producao/conversao-rapida`: consome MP e cria PA em chamada única, criando uma `OrdemProducao` com `status=CONCLUIDA` para rastreabilidade.

- **`test_conversao_basica_retorna_resumo`**: Body retorna `op_numero` (começa com `"OP-"`), `quantidade_mp_consumida=100.0`, `quantidade_pa_produzida=100.0`.
- **`test_conversao_reduz_saldo_mp`**: 500 disponíveis → consumir 150 → saldo MP = 350.
- **`test_conversao_aumenta_saldo_pa`**: PA parte de 0 → produzir 80 → saldo PA = 80.
- **`test_conversao_sem_localizacao_usa_automatica`**: Sem `localizacao_mp_id` → sistema usa a 1ª localização com saldo disponível → 201.
- **`test_conversao_mp_insuficiente_retorna_422`**: `quantidade_mp=9999` com apenas 500 disponíveis → 422.
- **`test_conversao_sem_auth_retorna_401`**: Sem token → 401.
- **`test_conversao_registra_op_na_listagem_como_concluida`**: OP criada aparece em `GET /producao/?status=CONCLUIDA` com o mesmo `numero` retornado pela conversão.

---

### `integration/test_api_beneficiamento.py` — 11 testes

**Endpoints:** `GET /beneficiamento/`, `GET /beneficiamento/em-transito`, `GET /beneficiamento/{id}`, `POST /beneficiamento/`, `POST /beneficiamento/{id}/retorno`

Setup: `Produto("BRUTO-M8", tipo="SEMI_ACABADO")` com 300 unidades, `Produto("ZINC-M8", tipo="PRODUTO_BENEFICIADO")`, `PrestadorBeneficiamento("Zincagem Industrial", prazo_retorno_dias=5, percentual_perda_esperado=1.5)`.

#### `TestListarLotes` (3 testes)
- **`test_listar_lotes_vazio`**: `GET /beneficiamento/` → `[]`.
- **`test_em_transito_vazio`**: `GET /beneficiamento/em-transito` → `[]`.
- **`test_detalhar_lote_inexistente_404`**: `GET /beneficiamento/99999` → 404.

#### `TestCriarLote` (5 testes)
- **`test_criar_lote_baixa_estoque_disponivel`**: POST com 100 unidades brutas → lote criado, saldo DISPONIVEL reduz de 300 para 200, saldo EM_BENEFICIAMENTO = 100.
- **`test_criar_lote_sem_estoque_suficiente_retorna_422`**: Tentar enviar mais do que disponível → 422.
- **`test_criar_lote_sem_auth_retorna_401`**: POST sem token → 401.
- **`test_listar_lotes_apos_criacao`**: Lote criado aparece em `GET /beneficiamento/`.
- **`test_em_transito_mostra_lote_enviado`**: Lote com status `EM_TRANSITO` aparece em `GET /beneficiamento/em-transito`.

#### `TestRetornoLote` (3 testes)
- **`test_retorno_completo_atualiza_status`**: `POST /beneficiamento/{id}/retorno` → lote fica `CONCLUIDO`, produto acabado entra no estoque DISPONIVEL.
- **`test_retorno_lote_inexistente_retorna_404`**: ID 99999 → 404.
- **`test_detalhar_lote_apos_criacao`**: `GET /beneficiamento/{id}` retorna dados do lote com seus itens.

---

### `integration/test_api_vendas.py` — 15 testes

**Endpoints:** `GET /vendas/`, `POST /vendas/`, `POST /vendas/{id}/confirmar`, `POST /vendas/{id}/cancelar`

Setup: `Produto("PV-001", preco_venda=5.50, aliq_icms=12%)` com 200 unidades, `Cliente("Moto Peças SP", uf="SP")`, `Cliente("Distribuidora MG", uf="MG")`.

#### Fluxo de status dos pedidos

```
ORCAMENTO → confirmar → CONFIRMADO → (picking) → EM_PICKING → PICKING_OK → (expedir) → EXPEDIDO
                    ↘ cancelar → CANCELADO
```

Reserva de estoque é criada automaticamente ao confirmar e liberada ao cancelar.

#### Testes principais
- **Criar pedido**: POST com `cliente_id`, `data_emissao`, lista de itens → 201, `status="ORCAMENTO"`, `valor_total` calculado.
- **Confirmar pedido**: `POST /vendas/{id}/confirmar` → `status="CONFIRMADO"`, estoque reservado automaticamente.
- **Cancelar pedido confirmado**: `POST /vendas/{id}/cancelar` → `status="CANCELADO"`, reserva liberada (saldo volta para DISPONIVEL).
- **Confirmar duas vezes**: Segundo `confirmar` em pedido já CONFIRMADO → 422.
- **Estoque insuficiente**: Confirmar pedido com quantidade maior que disponível → 422.
- **ICMS interestadual**: Pedido para cliente MG → CFOP `6102`, alíquota ICMS = 12% (interestadual).
- **Listagem por status**: `?status=ORCAMENTO` e `?status=CONFIRMADO` filtram corretamente.

---

### `integration/test_api_picking.py` — 21 testes

**Endpoints:** `POST /picking/{pedido_id}/iniciar`, `POST /picking/{pedido_id}/concluir`, `GET /picking/{conferencia_id}`, `POST /picking/{conferencia_id}/scan`

Setup: `Produto("PKG-001", codigo_barras="7891234567890")` com 100 unidades, `Cliente("Cliente Picking Ltda")`. Helper `_criar_pedido_confirmado()` cria e confirma um pedido de 10 unidades.

#### `TestIniciarPicking` (7 testes)
- **`test_iniciar_cria_conferencia_em_andamento`**: `POST /picking/{pedido_id}/iniciar` → 201, `status="EM_ANDAMENTO"`, `pedido_venda_id` correto.
- **`test_iniciar_move_pedido_para_em_picking`**: Após iniciar, `GET /vendas/{pedido_id}` → `status="EM_PICKING"`.
- **`test_iniciar_cria_itens_de_conferencia`**: Conferência criada tem 1 item com `status="PENDENTE"` e `quantidade_esperada=10.0`. Verificado via `GET /picking/{conf_id}` (o POST não carrega itens — sem `selectinload`).
- **`test_iniciar_pedido_inexistente_retorna_404`**: ID 99999 → 404.
- **`test_iniciar_pedido_orcamento_retorna_422`**: Pedido `ORCAMENTO` (não confirmado) → 422.
- **`test_iniciar_duas_vezes_rejeitado`**: Segundo `iniciar` no mesmo pedido (já `EM_PICKING`) → 409 ou 422.
- **`test_iniciar_sem_auth_retorna_401`**: Sem token → 401.

#### `TestConcluirPicking` (5 testes)
- **`test_concluir_move_para_picking_ok`**: `POST /picking/{pedido_id}/concluir` após iniciar → `status="PICKING_OK"`.
- **`test_concluir_sem_picking_iniciado`**: Pedido `CONFIRMADO` (sem picking aberto) também pode ser concluído → `status="PICKING_OK"`.
- **`test_concluir_pedido_inexistente_retorna_404`**: ID 99999 → 404.
- **`test_concluir_pedido_orcamento_retorna_422`**: Pedido `ORCAMENTO` → 422.
- **`test_concluir_sem_auth_retorna_401`**: Sem token → 401.

#### `TestDetalharConferencia` (2 testes)
- **`test_detalhar_conferencia_existente`**: `GET /picking/{conf_id}` retorna `id` correto.
- **`test_detalhar_conferencia_inexistente_retorna_404`**: ID 99999 → 404.

#### `TestScanPicking` (7 testes)

O scanner envia `codigo` (código do produto ou código de barras) e `quantidade`:

| Teste | Código | Qtd | Resultado esperado |
|-------|--------|-----|-------------------|
| `test_scan_codigo_correto_retorna_ok` | `"PKG-001"` | 10 | `resultado="OK"` |
| `test_scan_por_codigo_de_barras` | `"7891234567890"` | 10 | `resultado="OK"` |
| `test_scan_parcial_retorna_parcial` | `"PKG-001"` | 5 | `resultado="PARCIAL"`, `quantidade_conferida=5.0`, `quantidade_esperada=10.0` |
| `test_scan_excedente_retorna_divergencia` | `"PKG-001"` | 15 | `resultado="DIVERGENCIA_QUANTIDADE"` |
| `test_scan_codigo_inexistente_retorna_item_errado` | `"CODIGO-INVALIDO-XYZ"` | — | `resultado="ITEM_ERRADO"` |
| `test_scan_completo_conclui_conferencia` | `"PKG-001"` | 10 | `conferencia_concluida=true`, `percentual_geral=100.0` |
| `test_scan_sem_auth_retorna_401` | — | — | 401 |

---

### `integration/test_api_expedicao.py` — 12 testes

**Endpoints:** `GET /expedicao/`, `GET /expedicao/{pedido_id}/preview-fiscal`, `POST /expedicao/{pedido_id}/expedir`

Setup: `Produto("EXP-001", aliq_icms=12%, aliq_pis=0.65%, aliq_cofins=3%)` com 200 unidades reservadas. Helper `_pedido_picking_ok()` cria pedido de 30 unidades → confirma → conclui picking (status `PICKING_OK`).

#### `TestListarExpedicao` (1 teste)
- **`test_listar_vazio`**: `GET /expedicao/` → `[]`.

#### `TestPreviewFiscal` (3 testes)
- **`test_preview_retorna_impostos_por_item`**: `GET /expedicao/{pedido_id}/preview-fiscal` → lista de itens com `valor_icms`, `valor_pis`, `valor_cofins`, `cfop`. Não expede, apenas calcula.
- **`test_preview_pedido_inexistente_retorna_404`**: ID 99999 → 404.
- **`test_preview_sem_auth_retorna_401`**: Sem token → 401.

#### `TestExpedirPedido` (7 testes)
- **`test_expedir_picking_ok_retorna_expedido`**: `POST /expedicao/{pedido_id}/expedir` → `status="EXPEDIDO"`.
- **`test_expedir_consome_estoque_reservado`**: Após expedir 30 unidades de 200 disponíveis: `RESERVADO=0`, `DISPONIVEL=170`. O saldo reservado é consumido (não volta para disponível).
- **`test_expedir_com_transportadora`**: Body com `transportadora` e `numero_nf` opcionais → 200.
- **`test_expedir_pedido_inexistente_retorna_404`**: ID 99999 → 404.
- **`test_expedir_pedido_orcamento_retorna_422`**: Pedido `ORCAMENTO` → 422 (deve estar `PICKING_OK`).
- **`test_expedir_sem_auth_retorna_401`**: Sem token → 401.
- **`test_expedir_pedido_cancelado_retorna_422`**: Pedido cancelado → 422.

#### `TestFluxoCompletoExpedicao` (1 teste)
- **`test_fluxo_completo_orcamento_ate_expedido`**: Ciclo completo em um único teste:
  1. `POST /vendas/` → `ORCAMENTO`
  2. `POST /vendas/{id}/confirmar` → `CONFIRMADO` (reserva estoque)
  3. `POST /picking/{id}/concluir` → `PICKING_OK`
  4. `POST /expedicao/{id}/expedir` → `EXPEDIDO`

---

### `integration/test_fluxo_banho.py` — 6 testes

Usa banco in-memory próprio (não compartilhado com a API). Testa o serviço de beneficiamento diretamente via SQLAlchemy sem HTTP.

- **`test_saldo_disponivel_antes_remessa`**: Produto bruto tem 200 unidades DISPONIVEL antes do envio.
- **`test_remessa_reduz_disponivel`**: Após enviar 100 para banho, DISPONIVEL = 100.
- **`test_remessa_cria_saldo_em_beneficiamento`**: `EM_BENEFICIAMENTO = 100` após envio.
- **`test_retorno_cria_saldo_acabado`**: Após retorno de 95 unidades (5 perdas), produto acabado tem 95 DISPONIVEL.
- **`test_retorno_zera_em_beneficiamento`**: Saldo `EM_BENEFICIAMENTO` volta a 0 após retorno.
- **`test_lote_atrasado_detectavel`**: Lote com `data_retorno_prevista` no passado é retornado pela query de lotes atrasados.

---

### `integration/test_api_produtos_importar.py` — 20 testes

**Endpoints:** `POST /produtos/importar`, `GET /produtos/ncm/{ncm}`, `GET /produtos/unidades-medida`

#### `TestImportarProdutos` (10 testes)

O endpoint aceita `{"produtos": [...]}` e retorna `{"criados": N, "duplicados": N, "erros": [...]}`.

- **`test_importar_lista_simples_cria_produtos`**: 3 produtos novos → `criados=3`, `duplicados=0`, `erros=[]`.
- **`test_importar_produto_aparece_na_listagem`**: Produto importado é encontrado via `GET /produtos/?q=`.
- **`test_importar_duplicado_e_ignorado`**: Código já existente → `criados=0`, `duplicados=1`. Descrição original não é sobrescrita.
- **`test_importar_mistura_novos_e_duplicados`**: 1 existente + 2 novos → `criados=2`, `duplicados=1`.
- **`test_importar_com_aliquotas_persiste_valores_fiscais`**: Alíquotas informadas (`aliq_icms=12`, `aliq_ipi=5`) são persistidas e verificadas via `GET /produtos/{id}`.
- **`test_importar_unidade_desconhecida_usa_fallback_un`**: `unidade="INEXISTENTE"` → usa `UN` como fallback, `criados=1`, sem erros.
- **`test_importar_ncm_vazio_aceito`**: `ncm=""` e `ncm=null` → ambos aceitos, `criados=2`.
- **`test_importar_campos_opcionais_com_defaults`**: Sem preços ou alíquotas → defaults `0` aplicados, `criados=1`.
- **`test_importar_lista_vazia_retorna_zero`**: `produtos=[]` → `criados=0` sem erro.
- **`test_importar_sem_auth_retorna_401`**: POST sem token → 401.
- **`test_importar_preserva_tipo_correto`**: `tipo="PRODUTO_ACABADO"` informado é salvo sem ser sobrescrito para `MATERIA_PRIMA`.

#### `TestConsultarNcm` (7 testes)

Todos os testes mockam `httpx.AsyncClient` via `unittest.mock.patch("app.api.v1.produtos.httpx.AsyncClient")`.

```python
with patch("app.api.v1.produtos.httpx.AsyncClient") as mock_cls:
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_ctx.get = AsyncMock(return_value=mock_resp)
    mock_cls.return_value = mock_ctx
```

- **`test_ncm_valido_retorna_descricao`**: NCM `"73181600"` + mock 200 com `{"descricao": "Parafusos de ferro ou aço"}` → resposta com `ncm`, `descricao` e campo `aviso` sobre alíquotas.
- **`test_ncm_com_menos_de_8_digitos_retorna_400`**: `"7318"` → 400 antes de chamar API externa.
- **`test_ncm_com_mais_de_8_digitos_retorna_400`**: `"731816001"` → 400.
- **`test_ncm_com_letras_retorna_400`**: `"7318ABCD"` → 400.
- **`test_ncm_nao_encontrado_retorna_404`**: Mock retorna 404 → propagado como 404.
- **`test_ncm_servico_indisponivel_retorna_503`**: Mock lança `Exception("timeout")` → 503.
- **`test_ncm_remove_pontos_e_tracos`**: Input `"7318.16.00"` → normalizado para `"73181600"`, resposta retorna `ncm="73181600"`.

#### `TestListarUnidades` (2 testes)
- **`test_listar_vazio`**: Banco vazio → `[]`.
- **`test_listar_com_unidades`**: UN, KG, MT criadas → resultado ordenado alfabeticamente.

---

### `integration/test_security.py` — 38 testes

Arquivo dedicado exclusivamente a segurança. Cobre autenticação, autorização, injeção de código, validação de entrada e invariantes de negócio.

#### `TestAutenticacao` (16 testes)

Verifica que **todos** os endpoints de escrita exigem token JWT válido. Sem `Authorization: Bearer <token>` → 401:

| Módulo | Endpoints testados |
|--------|-------------------|
| Produtos | `POST /produtos/`, `POST /produtos/importar` |
| Parceiros | `POST /parceiros/clientes/`, `POST /parceiros/fornecedores/` |
| Estoque | `POST /estoque/localizacoes` |
| Vendas | `POST /vendas/`, `POST /vendas/1/confirmar`, `POST /vendas/1/cancelar` |
| Compras | `POST /compras/`, `PUT /compras/1/status` |
| Recebimento | `POST /recebimento/` |
| Produção | `POST /producao/`, `POST /producao/1/iniciar`, `POST /producao/1/concluir` |
| Beneficiamento | `POST /beneficiamento/`, `POST /beneficiamento/1/retorno` |
| Picking | `POST /picking/1/iniciar` |
| Expedição | `POST /expedicao/1/expedir` |
| Dashboard | `GET /dashboard/resumo` (único GET que exige auth) |

#### `TestTokenInvalido` (3 testes)

- **`test_token_adulterado_retorna_401`**: JWT com assinatura modificada (último caractere trocado) → 401. Verifica que o sistema valida a assinatura criptográfica, não apenas o formato.
- **`test_token_sem_bearer_retorna_401`**: Header `Authorization: <token>` sem prefixo `"Bearer "` → 401.
- **`test_token_completamente_invalido_retorna_401`**: String aleatória `"token_invalido_xpto"` → 401.

#### `TestSqlInjection` (4 testes)

Payloads de SQL injection enviados aos endpoints. O ORM (SQLAlchemy) usa queries parametrizadas, portanto os payloads são tratados como dados literais:

- **`test_sql_injection_em_busca_produto`**: `GET /produtos/?q='; DROP TABLE produtos; --` → 200 com lista vazia (não executa SQL).
- **`test_sql_injection_em_codigo_produto`**: `POST /produtos/` com `codigo="'; DROP TABLE produtos; --"` → 201 (código salvo literalmente) ou 422. Nunca 500.
- **`test_sql_injection_em_ncm_param`**: `GET /produtos/ncm/' OR '1'='1` → 400 (validação de formato rejeita antes de qualquer query).
- **`test_sql_injection_em_busca_parceiros`**: `GET /parceiros/clientes/?q=1; SELECT * FROM usuarios` → 200 com lista vazia.

#### `TestValidacaoEntrada` (5 testes)

- **`test_descricao_muito_longa_e_rejeitada`**: `descricao` com 10.000 caracteres → 422 (Pydantic valida `max_length`).
- **`test_preco_negativo_em_produto`**: `preco_venda="-999.99"` → 422 (validador rejeita valor negativo).
- **`test_quantidade_nao_numerica_em_importar`**: `preco_venda="abc"` no payload de importação → 422 (campo `Decimal` rejeita string não numérica).
- **`test_ncm_com_xss_retorna_400`**: `GET /produtos/ncm/<script>alert(1)</script>` → 400 ou 404. Nunca 200 ou 500 — o payload XSS é rejeitado pela validação de formato NCM ou não corresponde a nenhuma rota válida.
- **`test_id_nao_numerico_em_produto_retorna_422`**: `GET /produtos/abc` → 422 (FastAPI valida que path param `produto_id` seja inteiro).

#### `TestIntegridadeNegocio` (4 testes)

- **`test_estoque_nunca_fica_negativo_via_op`**: Criar OP e tentar iniciar consumindo 9.999 unidades com apenas 500 disponíveis → 422. Verifica o guard do serviço de estoque no contexto de produção.
- **`test_dupla_confirmacao_de_pedido_retorna_422`**: Confirmar o mesmo pedido duas vezes → segundo `confirmar` retorna 422 (pedido já está `CONFIRMADO`).
- **`test_picking_duplicado_retorna_409`**: Iniciar picking duas vezes no mesmo pedido → 409 ou 422 (pedido já está `EM_PICKING` na segunda chamada).
- **`test_importar_nao_sobrescreve_produto_existente`**: Importar produto com código já existente não altera a descrição original — regra de idempotência da importação.

#### `TestEndpointsPublicos` (6 testes)

Confirma que os endpoints de leitura são acessíveis sem autenticação (requisito de UX para o sistema interno):

- `GET /produtos/` → 200
- `GET /produtos/{id}` → 200 (produto criado previamente)
- `GET /parceiros/clientes/` → 200
- `GET /estoque/saldos` → 200
- `GET /producao/` → 200
- `GET /health` → 200

---

## Matriz de Cobertura por Módulo

| Arquivo de teste | Endpoints / Serviços | Testes | Regras de negócio críticas verificadas |
|-----------------|---------------------|--------|----------------------------------------|
| `unit/test_fiscal.py` | `fiscal.py` | 34 | ICMS inter/intraestadual, DIFAL, ST/MVA, IPI por CST, PIS/COFINS por CST, créditos na entrada, arredondamento |
| `unit/test_estoque.py` | `estoque_service.py` | 19 | Estoque nunca negativo, reserva falha sem saldo, liberar vs consumir reserva, saldo total por status |
| `unit/test_nfe_builder.py` | `nfe_builder.py` | 15 | Campos obrigatórios NF-e, NCM vazio → `"00000000"`, CNPJ vs CPF destinatário, numeração sequencial de itens |
| `integration/test_api_crud.py` | health, auth, produtos, parceiros, estoque, dashboard | 29 | JWT obrigatório em escrita, busca case-insensitive, IBPT requer NCM, dashboard zerado sem dados |
| `integration/test_api_recebimento.py` | `/recebimento/` | 7 | Crédito IPI só em COMPRA_MP (não em revenda), QC usa `quantidade_aprovada` no custo |
| `integration/test_api_compras.py` | `/compras/` | 13 | Números únicos mesmo fornecedor mesmo dia, `valor_total` calculado, filtro por status |
| `integration/test_api_producao.py` | `/producao/` | 18 | Consumo de MP ao iniciar, yield_percent, conversão rápida, localização automática |
| `integration/test_api_beneficiamento.py` | `/beneficiamento/` | 11 | Baixa DISPONIVEL ao enviar, cria EM_BENEFICIAMENTO, retorno cria produto acabado |
| `integration/test_api_vendas.py` | `/vendas/` | 15 | Reserva automática ao confirmar, liberação ao cancelar, CFOP interestadual, dupla confirmação bloqueada |
| `integration/test_api_picking.py` | `/picking/` | 21 | Scanner por código e barcode, PARCIAL/DIVERGENCIA/ITEM_ERRADO, 100% → conclui conferência |
| `integration/test_api_expedicao.py` | `/expedicao/` | 12 | Preview fiscal sem expedir, consumo da reserva na expedição, fluxo completo ORCAMENTO→EXPEDIDO |
| `integration/test_api_produtos_importar.py` | `/produtos/importar`, `/produtos/ncm/` | 20 | Idempotência (não sobrescreve), fallback UN, NCM normalizado, mock BrasilAPI, timeout→503 |
| `integration/test_security.py` | Todos os módulos | 38 | 401 em todos os endpoints de escrita, SQL injection via ORM, XSS rejeitado, JWT adulterado |
| `integration/test_fluxo_banho.py` | `beneficiamento_service` | 6 | Saldos EM_BENEFICIAMENTO, lotes atrasados detectáveis |
| **Total** | | **258** | |

---

## Decisões de Design dos Testes

### Por que SQLite e não PostgreSQL?

PostgreSQL seria mais fiel ao ambiente de produção, mas exigiria Docker em todo ambiente de desenvolvimento e CI. O SQLite in-memory com `StaticPool` roda em ~40 segundos sem dependências externas, e os comportamentos críticos testados (constraints, transações, queries) funcionam identicamente nos dois bancos via SQLAlchemy.

A única divergência relevante é que o SQLite não tem `SERIAL`/`SEQUENCE` — o Alembic gera as mesmas migrations para os dois, mas em produção o PostgreSQL usa sequências nativas enquanto o SQLite usa `AUTOINCREMENT`.

### Por que `StaticPool` nos testes de integração?

O FastAPI usa `get_db()` (dependency injection) para criar sessões, e os helpers `_setup_*()` criam sessões diretamente. Sem `StaticPool`, cada `AsyncSession` abriria uma conexão diferente apontando para bancos distintos em memória. Com `StaticPool`, todas as conexões reutilizam a mesma — dados inseridos nos helpers são visíveis para a API.

### Por que `scope="function"` em todas as fixtures?

Banco limpo por teste garante isolamento total. Com `scope="session"` ou `scope="module"`, a ordem de execução dos testes afetaria os dados disponíveis, tornando os testes dependentes entre si. O custo de recriar o banco a cada teste é baixo (~0.1s por função).

### Por que mocks no teste de NCM e não chamada real?

A BrasilAPI é um serviço externo. Testes que dependem de rede são frágeis (falham se a API estiver fora do ar ou rate-limitada), lentos e não reproduzíveis. O mock intercepta exatamente a classe `httpx.AsyncClient` no namespace onde ela é importada (`app.api.v1.produtos`), garantindo que o código real de tratamento de resposta e erros seja exercitado com respostas controladas.

### Por que `asyncio_mode = auto` no pytest.ini?

Com `asyncio_mode = auto`, todas as funções `async def` nos testes são tratadas automaticamente como corrotinas pelo pytest-asyncio, sem necessidade de `@pytest.mark.asyncio` em cada função. Isso evita centenas de decoradores repetitivos e mantém o código de teste limpo.

### Por que testes de segurança em arquivo separado?

`test_security.py` testa comportamentos transversais (autenticação, validação, injeção) que se aplicam a todos os módulos. Mantê-los separados evita poluir os testes funcionais com verificações de segurança repetitivas e facilita executar apenas a bateria de segurança em revisões de código: `pytest tests/integration/test_security.py -v`.

---

## Como Adicionar Novos Testes

### Padrão para endpoint novo

```python
class TestMeuEndpoint:
    async def test_cenario_feliz(self, client, auth_headers, test_engine):
        """Descrição clara do que está sendo verificado."""
        # 1. Setup: criar dados necessários diretamente no banco
        Session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
        async with Session() as session:
            obj = MinhaEntidade(campo="valor")
            session.add(obj)
            await session.commit()
            await session.refresh(obj)

        # 2. Ação: chamada HTTP
        r = await client.post("/api/v1/meu-endpoint/", json={...}, headers=auth_headers)

        # 3. Verificação: status + campos do body
        assert r.status_code == 201
        assert r.json()["campo"] == "valor esperado"

    async def test_sem_auth_retorna_401(self, client):
        """Todo endpoint de escrita deve ter este teste."""
        r = await client.post("/api/v1/meu-endpoint/", json={})
        assert r.status_code == 401
```

### Padrão para mock de API externa

```python
from unittest.mock import AsyncMock, patch, MagicMock

async def test_api_externa_ok(self, client):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"campo": "valor"}

    with patch("app.api.v1.meu_modulo.httpx.AsyncClient") as mock_cls:
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_ctx)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_ctx.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = mock_ctx

        r = await client.get("/api/v1/meu-endpoint/consulta")

    assert r.status_code == 200
```

### Checklist para novo endpoint

- [ ] Cenário feliz (status esperado + campos do body)
- [ ] Recurso inexistente → 404
- [ ] Transição de status inválida → 422
- [ ] Sem autenticação → 401 (se endpoint de escrita)
- [ ] Input inválido / fora de domínio → 422
- [ ] Invariante de negócio (ex: estoque não fica negativo)
