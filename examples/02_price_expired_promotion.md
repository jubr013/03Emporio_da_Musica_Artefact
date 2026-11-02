# Price check with an expired promotion

> **Context:** Customer asks the price of the Takamine GD20 and claims it had a 12% discount. The promotion exists but is inactive, so the agent states the current price transparently (policy 6.2/7.3) and answers installments from the payment policy.
>
> Recorded with `python -m src.main --show-tools --today 2026-02-20` (model `gemini-3.5-flash-lite`). Unedited transcript; 🔧 lines are the tool calls the agent made.

---

**Cliente:** Quanto custa o Takamine GD20?

> 🔧 `search_products(query='Takamine GD20')`

**melodIA:** O Takamine GD20 Dreadnought Natural custa R$ 2.199,00 à vista (preço de tabela). Pagando no PIX, você ganha 5% de desconto e sai por R$ 2.089,05, e também dá para parcelar conforme as regras da loja! 

Ele está disponível aqui na Empório da Música. Quer garantir o seu ou saber mais sobre o parcelamento?

**Cliente:** Ué, ele não estava com 12% de desconto? Vi uma oferta especial dele

> 🔧 `get_product_details(product_id=95)`

> 🔧 `get_policy(topic='promocoes')`

**melodIA:** Dando uma olhada aqui, o Takamine GD20 está por R$ 2.199,00, sem nenhuma promoção ativa no momento. 

Nós temos algumas campanhas ao longo do ano — como a Black Friday, Aniversário da loja e Semana do Músico —, mas no momento essa oferta de 12% não está vigente. 

Ainda assim, se você fechar no PIX, ele tem aquele descontinho de 5%, saindo por R$ 2.089,05. O que acha?

**Cliente:** E dá pra parcelar em quantas vezes no cartão?

> 🔧 `get_policy(topic='pagamento')`

**melodIA:** Dá sim! Aqui na Empório da Música você pode parcelar no cartão de crédito em até **12x sem juros**, desde que a parcela seja de no mínimo R$ 100,00. 

Com o valor do Takamine GD20 (R$ 2.199,00), você consegue dividir em até 12 vezes tranquilamente sem juros! Quer fechar o pedido por aqui?
