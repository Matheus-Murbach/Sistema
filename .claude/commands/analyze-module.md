# Analyze Module

Analyze the ERP module: **$ARGUMENTS**

Use the information below to locate files. Read all layers and generate a full structured report.

---

## Module → File Mapping

Some modules have singular models but plural API files. Use this reference:

| Module arg     | Model file                                      | API file                                         | Frontend page                                              |
|----------------|-------------------------------------------------|--------------------------------------------------|------------------------------------------------------------|
| recebimento    | backend/app/models/recebimento.py               | backend/app/api/v1/recebimento.py                | frontend/app/(app)/recebimento/page.tsx                    |
| beneficiamento | backend/app/models/beneficiamento.py            | backend/app/api/v1/beneficiamento.py             | frontend/app/(app)/beneficiamento/page.tsx                 |
| producao       | backend/app/models/producao.py                  | backend/app/api/v1/producao.py                   | frontend/app/(app)/producao/page.tsx                       |
| estoque        | backend/app/models/estoque.py                   | backend/app/api/v1/estoque.py                    | frontend/app/(app)/estoque/page.tsx                        |
| compras        | backend/app/models/compra.py                    | backend/app/api/v1/compras.py                    | frontend/app/(app)/compras/page.tsx                        |
| vendas         | backend/app/models/venda.py                     | backend/app/api/v1/vendas.py                     | frontend/app/(app)/vendas/page.tsx                         |
| picking        | backend/app/models/picking.py                   | backend/app/api/v1/picking.py                    | frontend/app/(app)/picking/page.tsx                        |
| expedicao      | backend/app/models/expedicao.py                 | backend/app/api/v1/expedicao.py                  | frontend/app/(app)/expedicao/page.tsx                      |
| fiscal         | (sem model direto)                              | (sem endpoint v1 direto)                          | frontend/app/(app)/fiscal/page.tsx                         |
| parceiros      | backend/app/models/parceiro.py                  | backend/app/api/v1/parceiros.py                  | frontend/app/(app)/cadastros/page.tsx (seção parceiros)    |
| produtos       | backend/app/models/produto.py                   | backend/app/api/v1/produtos.py                   | frontend/app/(app)/cadastros/page.tsx (seção produtos)     |
| maquina        | backend/app/models/maquina.py                   | (sem endpoint v1 direto)                          | frontend/app/(app)/configuracoes/page.tsx                  |
| usuario        | backend/app/models/usuario.py                   | backend/app/api/v1/auth.py                       | frontend/app/(app)/configuracoes/page.tsx                  |

Services available (check if relevant for this module):
- backend/app/services/estoque_service.py
- backend/app/services/fiscal.py
- backend/app/services/nfe_builder.py

Test files — scan for coverage of this module:
- backend/tests/unit/test_estoque.py
- backend/tests/unit/test_fiscal.py
- backend/tests/unit/test_nfe_builder.py
- backend/tests/integration/test_api_beneficiamento.py
- backend/tests/integration/test_api_crud.py
- backend/tests/integration/test_api_producao.py
- backend/tests/integration/test_api_recebimento.py
- backend/tests/integration/test_api_vendas.py
- backend/tests/integration/test_fluxo_banho.py

---

## Steps

1. Read the **model file** for this module. If not found, note it.
2. Read the **API file** for this module. If not found, note it.
3. Check if any **service file** is relevant (grep for the module name inside each service file).
4. Read the **frontend page** for this module.
5. Search the **test files** for test functions that exercise this module.

---

## Output Format

Produce the report in this exact structure:

---

### Módulo: [Nome]

**Propósito no ERP:** [1-2 frases descrevendo o papel do módulo no fluxo industrial]

---

#### Modelo de Dados

| Campo | Tipo | Obrigatório | Descrição / Relacionamento |
|-------|------|-------------|---------------------------|
| ...   | ...  | ...         | ...                       |

---

#### Endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET    | /... | ...       |
| POST   | /... | ...       |

---

#### Funcionalidades do Frontend

- List the main features visible in the page component (tables, forms, filters, actions)
- Note which API calls are made (fetch URLs)

---

#### Lógica de Negócio

- List business rules, calculations, validations found in the API or service layer
- Note any cross-module interactions (e.g., "updates estoque after venda is confirmed")

---

#### Cobertura de Testes

| Arquivo de Teste | Cenários Cobertos |
|-----------------|-------------------|
| ...             | ...               |

**Módulos sem teste:** list if no test file covers this module.

---

#### Gaps Identificados

- Missing endpoints (e.g., no DELETE, no list with filters)
- Missing validations (fields not validated, edge cases not handled)
- Frontend features not backed by an API endpoint
- Business rules implemented inline instead of in a service
- Other gaps observed

---

#### Sugestões de Melhoria

- Concrete, prioritized suggestions (P1 = critical, P2 = important, P3 = nice-to-have)
