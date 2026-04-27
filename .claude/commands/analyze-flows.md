# Analyze Flows

Trace the end-to-end business flows of the ERP system. Read the relevant API and model files for each flow and identify where data passes between modules — and where the chain breaks.

---

## Known ERP Flows

### Flow 1: Compra → Recebimento → Estoque
```
Compra (purchase order created)
  → Recebimento (goods received, quality check)
    → Estoque (inventory updated)
```

### Flow 2: Venda → Picking → Expedição → NF-e
```
Venda (sale order created)
  → Picking (items separated from stock)
    → Expedição (shipment prepared)
      → NF-e (fiscal document issued via fiscal service)
```

### Flow 3: Produção → Estoque → Expedição
```
Produção (manufacturing order, raw material consumed)
  → Estoque (finished goods added)
    → Expedição (shipment of finished goods)
```

### Flow 4: Beneficiamento (subcontracted processing)
```
Estoque (material sent out)
  → Beneficiamento (external processing tracked)
    → Estoque (processed material returned)
```

---

## Files to Read

For each flow, read the API files of the involved modules and look for:
- Foreign key references between models (how module A passes an ID to module B)
- Status fields and state machine transitions (e.g., `status: "pendente" → "confirmado"`)
- Explicit cross-module calls (one router importing another router's logic or service)
- Service functions that orchestrate multiple modules

Key files:
- backend/app/api/v1/recebimento.py
- backend/app/api/v1/compras.py
- backend/app/api/v1/estoque.py
- backend/app/api/v1/vendas.py
- backend/app/api/v1/picking.py
- backend/app/api/v1/expedicao.py
- backend/app/api/v1/producao.py
- backend/app/api/v1/beneficiamento.py
- backend/app/models/recebimento.py
- backend/app/models/compra.py
- backend/app/models/estoque.py
- backend/app/models/venda.py
- backend/app/models/picking.py
- backend/app/models/expedicao.py
- backend/app/models/producao.py
- backend/app/models/beneficiamento.py
- backend/app/services/estoque_service.py
- backend/app/services/fiscal.py
- backend/app/services/nfe_builder.py
- backend/tests/integration/test_fluxo_banho.py

---

## Output Format

---

### Fluxos de Negócio — ERP Industrial

---

#### Fluxo 1: Compra → Recebimento → Estoque

```
[Compra] ──(compra_id)──► [Recebimento] ──(atualiza)──► [Estoque]
```

**Elo Compra → Recebimento:**
- How does recebimento reference a compra? (FK field, manual entry, etc.)
- What data is transferred?
- Is the link enforced or optional?

**Elo Recebimento → Estoque:**
- When/how does recebimento trigger a stock update?
- Is it automatic (service call) or manual (separate endpoint)?
- What happens to stock quantity / lot tracking?

**Quebras identificadas:**
- List any missing links, missing status transitions, or manual steps that should be automated

---

#### Fluxo 2: Venda → Picking → Expedição → NF-e

```
[Venda] ──(venda_id)──► [Picking] ──(picking_id)──► [Expedição] ──► [NF-e]
```

**Elo Venda → Picking:**
- How does picking reference a venda?
- Does picking decrement estoque?

**Elo Picking → Expedição:**
- What data passes from picking to expedição?
- Are all picked items automatically in the expedição?

**Elo Expedição → NF-e:**
- How is fiscal.py / nfe_builder.py triggered?
- What data from expedição feeds the NF-e?
- Is the NF-e generated automatically or requires a manual action?

**Quebras identificadas:**
- List gaps, missing automations, missing validations

---

#### Fluxo 3: Produção → Estoque → Expedição

```
[Produção] ──(consome)──► [Estoque matéria-prima]
[Produção] ──(gera)──► [Estoque produto acabado]
[Estoque] ──► [Expedição]
```

**Elo Produção → Estoque (consumo):**
- How is raw material consumption tracked?
- Is estoque_service.py called?

**Elo Produção → Estoque (produto acabado):**
- When production is finished, how does it add to stock?

**Quebras identificadas:**
- List gaps

---

#### Fluxo 4: Beneficiamento

```
[Estoque] ──(saída)──► [Beneficiamento externo] ──(retorno)──► [Estoque]
```

**Rastreamento de saída e retorno:**
- How is the outgoing material tracked in beneficiamento model?
- How is the return registered?
- Is there a test covering this flow? (check test_fluxo_banho.py)

**Quebras identificadas:**
- List gaps

---

#### Resumo dos Fluxos

| Fluxo | Elos implementados | Elos faltando | Status geral |
|-------|-------------------|---------------|--------------|
| Compra → Recebimento → Estoque | ... | ... | Completo / Parcial / Quebrado |
| Venda → Picking → Expedição → NF-e | ... | ... | Completo / Parcial / Quebrado |
| Produção → Estoque | ... | ... | Completo / Parcial / Quebrado |
| Beneficiamento | ... | ... | Completo / Parcial / Quebrado |

---

#### Recomendações Prioritárias

List the top 5 most important improvements to make the flows robust, in priority order.
