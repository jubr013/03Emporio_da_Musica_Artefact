# Price check with an expired promotion

> **Context:** Customer asks the price of the Takamine GD20 and claims it had a 12% discount. The promotion exists but is inactive, so the agent states the current price transparently (policy 6.2/7.3) and answers installments from the payment policy.
>
> Recorded with `python -m src.main --show-tools --today 2026-02-20` (model `gemini-3.5-flash-lite`). Unedited transcript; 🔧 lines are the tool calls the agent made.

---

**Cliente:** Quanto custa o Takamine GD20?

> 🔧 `search_products(query='Takamine GD20')`

**melodIA:** O Takamine GD20 Dreadnought Natural custa R$ 2.199,00. 

No PIX, ele sai com 5% de desconto por R$ 2.089,05! Quer saber mais detalhes desse violão ou condições de parcelamento?

**Cliente:** Ué, ele não estava com 12% de desconto? Vi uma oferta especial dele

> 🔧 `get_product_details(product_id=95)`

> 🔧 `get_policy(topic='promocoes')`

**melodIA:** Dá uma olhada: no momento não temos nenhuma promoção ativa ou campanha de 12% vigente para esse modelo por aqui. O preço dele no catálogo é R$ 2.199,00 mesmo (ou R$ 2.089,05 no PIX). 

Pode ser que você tenha visto alguma oferta passada ou campanha específica que já encerrou. Mas olha, o GD20 é um violão incrível, com tampo em cedro sólido e um timbre super aconchegante. Quer que eu te ajude a ver as condições de parcelamento dele?

**Cliente:** E dá pra parcelar em quantas vezes no cartão?

> 🔧 `get_policy(topic='pagamento')`

**melodIA:** Dá sim! Você pode parcelar em até **12x sem juros** no cartão de crédito, desde que cada parcela seja de pelo menos R$ 100,00. 

Como o Takamine GD20 custa R$ 2.199,00, dá para dividir em até 12 vezes tranquilamente! Quer aproveitar e garantir o seu?
