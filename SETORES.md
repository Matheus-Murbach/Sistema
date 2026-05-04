# Setores da Empresa

Este documento descreve os cinco setores que compõem a operação da empresa, suas responsabilidades e o papel de cada um no fluxo produtivo e administrativo.

---

## 1. Estoque

O setor de Estoque é o coração físico da empresa. Ele controla tudo que entra e sai do almoxarifado, garantindo que materiais e produtos estejam disponíveis no lugar certo, na quantidade certa e no momento certo.

**Responsabilidades:**

- **Recebimento de mercadorias**: recebe e confere as notas fiscais de fornecedores, valida quantidades e qualidades dos itens entregues, e registra a entrada no sistema. É a porta de entrada de toda matéria-prima e produto de revenda.

- **Expedição**: prepara e libera os pedidos para entrega ao cliente, emitindo a nota fiscal de saída (NF-e). Garante que o produto correto saia com a documentação fiscal adequada.

- **Gestão de beneficiamento externo (remessa e retorno)**: quando itens precisam ser enviados para processamento externo (como banho/galvanização), o Estoque é responsável por emitir a nota fiscal de remessa, controlar o que foi enviado, e registrar o retorno dos itens beneficiados — garantindo rastreabilidade total do lote.

- **Controle de saldos e localizações**: mantém atualizado o saldo de cada produto por localização física (prateleiras, corredores, endereços do galpão). Sabe exatamente onde cada item está armazenado.

- **Registro de movimentações**: todo movimento de entrada ou saída é registrado de forma imutável no sistema, criando um histórico completo para rastreabilidade, auditorias e conciliações de inventário.

- **Gestão de reservas**: quando um pedido de venda é confirmado, o estoque reserva os itens correspondentes, impedindo que sejam usados em outras operações até que o pedido seja atendido.

---

## 2. Produção

O setor de Produção é responsável por transformar matéria-prima em produto acabado dentro da fábrica. Ele planeja, executa e controla todo o processo fabril.

**Responsabilidades:**

- **Ordens de Produção**: cria e acompanha as ordens de produção (OP), definindo quais produtos serão fabricados, em quais máquinas, em quais quantidades e em quais prazos. Controla o consumo de materiais em cada etapa e registra o produto acabado gerado ao final.

- **Gestão do beneficiamento externo (processo)**: acompanha o lote de itens enviados para industrialização externa (como banho/galvanização). Controla as etapas do processo, os prazos de retorno, o custo do serviço prestado pelo terceiro, a quantidade retornada e o refugo gerado — transformando o produto enviado no produto acabado que retorna.

---

## 3. Separação

O setor de Separação é o elo entre o almoxarifado e a expedição. Ele garante que cada pedido seja montado com precisão, qualidade e organização antes de ser entregue ao cliente.

**Responsabilidades:**

- **Estudo dos pedidos**: analisa os pedidos de venda confirmados, verifica quais itens precisam ser separados, identifica possíveis faltantes e planeja a ordem de separação para otimizar o fluxo.

- **Montagem de kits e pacotes**: reúne fisicamente todas as peças necessárias para cada pedido, garantindo que nenhum item falte ou seja trocado.

- **Montagem de pallets**: organiza e embala os volumes de forma adequada para o transporte, respeitando as especificações de cada tipo de produto e exigências do frete.

- **Conferência de qualidade**: verifica as peças antes de liberá-las para a expedição, identificando itens com defeito, fora de especificação ou incompatíveis com o pedido — evitando devoluções e insatisfação do cliente.

- **Organização do estoque no dia a dia**: durante a operação, mantém o almoxarifado em ordem — reposicionando itens, sinalizando endereços, e garantindo que o espaço físico esteja sempre organizado para facilitar as próximas separações.

---

## 4. Comercial

O setor Comercial é o escritório da empresa. Ele gerencia os negócios com clientes e fornecedores, cuida dos cadastros e garante que toda operação comercial e fiscal esteja correta e em conformidade com a legislação.

**Responsabilidades:**

- **Vendas**: atende clientes, elabora cotações, registra e acompanha pedidos de venda. Gerencia prazos, condições de pagamento e calcula impostos específicos como o DIFAL para vendas interestaduais.

- **Compras**: identifica necessidades de reposição, emite pedidos de compra para fornecedores, acompanha prazos de entrega e controla o histórico de aquisições. Monitora o ponto de pedido para garantir que o estoque nunca fique abaixo do mínimo necessário.

- **Cadastros**: mantém atualizados os dados mestres da empresa: produtos (código, descrição, NCM, unidade de medida), clientes e fornecedores (CNPJ, endereço, dados fiscais). A qualidade desses cadastros impacta diretamente a emissão correta das notas fiscais.

- **Fiscal**: configura e calcula os impostos aplicáveis a cada operação — ICMS, IPI, PIS, COFINS e ICMS-ST — com base na NCM de cada produto e no regime tributário da empresa. Gerencia a emissão de notas fiscais eletrônicas (NF-e) de entrada e saída, cuida das alíquotas e mantém a empresa em conformidade com o fisco.

---

## 5. TI

O setor de TI é responsável pela base tecnológica que sustenta toda a operação da empresa. Sem TI funcionando, nenhum outro setor opera com eficiência.

**Responsabilidades:**

- **Infraestrutura e suporte técnico**: garante o funcionamento contínuo de servidores, rede, computadores, impressoras, coletores de código de barras e demais equipamentos tecnológicos. Presta suporte aos usuários de todos os setores, resolve falhas e mantém os equipamentos operacionais e atualizados.

- **Sistemas e integrações**: mantém e evolui os sistemas da empresa (ERP, portais, painéis operacionais), gerencia as integrações com serviços externos (emissão de NF-e, consulta de alíquotas fiscais), controla os acessos e permissões de cada usuário por setor, e garante a segurança, integridade e backup dos dados da empresa.

---

## Fluxo entre setores

```
COMERCIAL
  ├── Pedido de Venda confirmado
  └── Pedido de Compra emitido
          ↓
ESTOQUE
  ├── Recebe matéria-prima do fornecedor
  └── Envia/recebe itens de beneficiamento externo
          ↓
PRODUÇÃO
  └── Fabrica o produto acabado (consome MP, gera produto)
          ↓
SEPARAÇÃO
  └── Separa, confere e monta os pedidos para entrega
          ↓
ESTOQUE
  └── Expede o pedido com NF-e para o cliente

TI — suporta todos os setores de forma transversal
```
