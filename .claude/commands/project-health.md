# Project Health

Perform a comprehensive health check of the ERP project. Read files across the entire codebase and produce a structured report.

---

## Project Structure Reference

```
backend/
  app/
    models/          → recebimento, beneficiamento, producao, estoque, compra, venda,
                        picking, expedicao, produto, parceiro, maquina, usuario
    api/v1/          → recebimento, beneficiamento, producao, estoque, compras, vendas,
                        picking, expedicao, parceiros, produtos, auth, dashboard
    services/        → estoque_service.py, fiscal.py, nfe_builder.py
  tests/
    unit/            → test_estoque.py, test_fiscal.py, test_nfe_builder.py
    integration/     → test_api_beneficiamento.py, test_api_crud.py, test_api_producao.py,
                        test_api_recebimento.py, test_api_vendas.py, test_fluxo_banho.py

frontend/
  app/(app)/         → recebimento, beneficiamento, producao, estoque, compras, vendas,
                        picking, expedicao, fiscal, cadastros, configuracoes, dashboard
```

---

## Steps

1. **Test coverage matrix** — for each backend module, check whether a test file covers it (search by module name in all test files). Mark covered/not covered.

2. **TODOs and FIXMEs** — run a search across all `.py` and `.tsx` files for `TODO`, `FIXME`, `HACK`, `XXX`, `NOTE:`. List them grouped by file.

3. **Modules without a service layer** — list which modules have complex business logic embedded directly in the API router instead of a service file.

4. **Frontend ↔ API alignment** — for each frontend page, check which API routes it calls. Identify:
   - Frontend calls that have no corresponding API endpoint
   - API endpoints that have no frontend UI

5. **Code pattern consistency** — spot-check 3-4 API files and 2-3 frontend pages for:
   - Async/await usage consistency
   - Error handling patterns (HTTPException vs raw exceptions in backend)
   - Response model usage (Pydantic schemas vs raw dicts)
   - Naming conventions (snake_case in backend, camelCase in frontend)

6. **Missing models** — identify if any frontend page or API endpoint references data that has no corresponding model file.

---

## Output Format

---

### Saúde Geral do Projeto ERP

**Data da análise:** [today]  
**Módulos analisados:** [count]

---

#### Cobertura de Testes por Módulo

| Módulo | Tem Teste Unit? | Tem Teste Integration? | Arquivos de Teste |
|--------|----------------|------------------------|-------------------|
| ...    | Sim / Não      | Sim / Não              | ...               |

**Módulos sem nenhuma cobertura:** [list]

---

#### TODOs / FIXMEs encontrados

| Arquivo | Linha | Texto |
|---------|-------|-------|
| ...     | ...   | ...   |

---

#### Lógica de Negócio sem Service Layer

Modules with business logic embedded directly in the router (no dedicated service):

- [module]: [brief description of what logic is inline]

---

#### Alinhamento Frontend ↔ API

**Chamadas do frontend sem endpoint correspondente:**
- [page] calls [route] → not found in any api/v1 file

**Endpoints sem UI correspondente:**
- [endpoint] exists in [api file] → no frontend page calls it

---

#### Consistência de Padrões

| Padrão | Status | Observação |
|--------|--------|------------|
| Async/await no backend | OK / Inconsistente | ... |
| HTTPException para erros | OK / Inconsistente | ... |
| Schemas Pydantic em responses | OK / Inconsistente | ... |
| snake_case no backend | OK / Inconsistente | ... |
| camelCase no frontend | OK / Inconsistente | ... |

---

#### Resumo de Riscos

| Prioridade | Risco | Módulos Afetados |
|-----------|-------|-----------------|
| P1 | ... | ... |
| P2 | ... | ... |
| P3 | ... | ... |
