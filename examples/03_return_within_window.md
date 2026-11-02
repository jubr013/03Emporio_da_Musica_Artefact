# Return request inside the 7-day window (non-trivial)

> **Context:** Customer regrets a purchase. The agent asks for order number + e-mail (identity check), gets the order and policy, gives the deadline computed in code, confirms the receipt date based on the delivery estimate, and opens a support ticket with a protocol number. Today is set to 2026-02-20; delivery estimate was 2026-02-17.
>
> Recorded with `python -m src.main --show-tools --today 2026-02-20` (model `gemini-3.5-flash-lite`). Unedited transcript; 🔧 lines are the tool calls the agent made.

---

**Cliente:** Oi, me arrependi da compra do meu ukulele, posso devolver?

**melodIA:** Olá! Com certeza, dá pra devolver sim se você se arrependeu. 

Para eu conferir os prazos certinho para o seu caso, me passa por favor o **número do pedido** e o **e-mail ou telefone** que você usou na compra?

**Cliente:** Pedido 7, email leticia.rocha@jmail.com

> 🔧 `get_order_status(email='leticia.rocha@jmail.com', order_id=7)`

> 🔧 `get_policy(topic='trocas_e_devolucoes')`

**melodIA:** Letícia, vi aqui que a previsão de entrega do seu ukulele Shelby SU-21S Soprano foi no dia 17/02 (me confirme se recebeu por volta dessa data, por favor!). 

Como você comprou online, você tem o direito de arrependimento e pode solicitar a devolução até o dia **24/02/2026** (daqui a 4 dias). 

Para isso, o instrumento precisa estar na embalagem original, sem sinais de uso, com todos os acessórios e manuais. O frete de devolução é por nossa conta e o reembolso é feito na mesma forma de pagamento.

Você confirma que deseja abrir a solicitação de devolução?

**Cliente:** Recebi sim, por volta disso. Quero devolver sim

> 🔧 `create_support_ticket(summary='Cliente Letícia Rocha solicita a devolução do Ukulele Shelby SU-21S Soprano (Pedido 7) por arrependimento, dentro do prazo de 7 dias.', request_type='devolucao', order_id=7, customer_contact='leticia.rocha@jmail.com')`

**melodIA:** Prontinho, Letícia! Registrei a sua solicitação de devolução.

O seu número de protocolo é **EM20260220-A13B0A**. Nossa equipe vai entrar em contato com você em até 24 horas úteis para dar continuidade ao processo por lá, combinado? 

Se precisar de mais alguma coisa é só falar!
