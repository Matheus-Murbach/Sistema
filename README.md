# Sistema ERP Industrial

ERP completo para controle industrial com suporte a:
- Expedição de entrada (compra de MP, revenda, retorno de beneficiamento)
- Beneficiamento externo / banho (Remessa para Industrialização - CFOP 5901/6901)
- PCP - Ordens de produção com controle por máquina
- Estoque com localização física e reserva de pedidos
- Compras com ponto de pedido automático
- Vendas com cálculo fiscal em tempo real
- Picking com leitor de código de barras (WebSocket)
- Expedição de saída com emissão de NF-e integrada (Focus NF-e)
- Tributação automática por NCM (IBPT API)

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.12 + FastAPI + SQLAlchemy 2 async |
| Banco | PostgreSQL 16 |
| Cache/Fila | Redis 7 + Celery |
| Frontend | Next.js 15 + React 19 + Tailwind CSS |
| NF-e | Focus NF-e API |
| Impostos | IBPT API |

## Início rápido

```bash
# 1. Copiar variáveis de ambiente
cp .env.example .env
# Editar .env com seus dados fiscais, certificado digital e tokens

# 2. Subir todos os serviços
docker-compose up -d

# 3. Acessar
# Frontend: http://localhost:3000
# API docs: http://localhost:8000/docs
```

## Configuração obrigatória antes de usar em produção

1. **Regime tributário** — confirmar com contador e ajustar `EMPRESA_CRT` no `.env`
   - `1` = Simples Nacional
   - `3` = Regime Normal (Lucro Presumido ou Real)

2. **Certificado Digital A1** — copiar arquivo `.pfx` para `backend/certificados/`

3. **Focus NF-e** — criar conta em focusnfe.com.br e adicionar token no `.env`

4. **IBPT** — criar conta em ibpt.com.br para busca de alíquotas por NCM

5. **Tributação por produto** — preencher NCM, CST ICMS/IPI/PIS/COFINS e alíquotas no cadastro de cada produto

## Módulos

```
backend/
  app/
    models/         Entidades do banco (SQLAlchemy)
    api/v1/         Endpoints REST por módulo
    services/       Lógica de negócio (fiscal.py, estoque_service.py, nfe_builder.py)
    integrations/   Focus NF-e, IBPT
    tasks/          Celery tasks (verificação NF-e)
  alembic/          Migrations

frontend/
  app/(app)/        Páginas autenticadas
    dashboard/      Resumo operacional
    recebimento/    Entrada de NF de fornecedor
    beneficiamento/ Controle de lotes de banho
    producao/       Ordens de produção (PCP)
    estoque/        Saldos, pronta entrega, alertas
    compras/        Pedidos de compra
    vendas/         Pedidos de venda
    picking/        Conferência com scanner
    expedicao/      Emissão NF-e de saída
```

## Pontos de atenção fiscal

- **ICMS-ST**: produtos com MVA precisam de CST correto e % MVA cadastrado
- **DIFAL**: vendas interestaduais para consumidor final — calculado automaticamente
- **Banho (CFOP 5901/6902)**: operação de Remessa para Industrialização, tratamento fiscal específico
- **IPI**: incide apenas em produtos industrializados; produtos de revenda pura ficam isentos