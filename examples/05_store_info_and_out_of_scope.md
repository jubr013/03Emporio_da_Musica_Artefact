# Store info, accessories and an off-topic question

> **Context:** Address and Saturday hours from the policies; an accessory request (the store sells instruments only) where the agent asks before suggesting partner stores; and an unrelated football question handled politely.
>
> Recorded with `python -m src.main --show-tools --today 2026-02-20` (model `gemini-3.5-flash-lite`). Unedited transcript; 🔧 lines are the tool calls the agent made.

---

**Cliente:** Oi! Qual o endereço da loja e até que horas vocês abrem no sábado?

> 🔧 `get_policy(topic='sobre_a_loja')`

> 🔧 `get_policy(topic='horarios')`

**melodIA:** Oi! 

Nossa loja fica na **Rua 14 de Maio, 3200 — Centro, Campo Grande/MS**.

Aos sábados, abrimos das **09:00 às 13:00**. 

Quer dar uma olhada em algum instrumento por aí?

**Cliente:** Vocês vendem cabo para guitarra?

**melodIA:** Não trabalhamos com acessórios — vendemos exclusivamente instrumentos musicais, como guitarras, violões, baixos e teclados, beleza? 

Gostaria de indicações de lojas parceiras aqui em Campo Grande que vendem cabos e outros acessórios?

**Cliente:** Quero sim

> 🔧 `get_policy(topic='lojas_parceiras')`

**melodIA:** Para cabos e outros acessórios, temos duas ótimas indicações de parceiros aqui em Campo Grande:

- **Palheta & Cia Acessórios Musicais**: especializada em cordas, palhetas, cabos, correias e cases.
- **Ponto do Músico Áudio**: focada em pedais, amplificadores e equipamentos de som.

É sempre bom conferir o endereço e o horário de funcionamento direto com eles, ok? 

Se precisar de ajuda com algum instrumento musical, estou por aqui!

**Cliente:** E você sabe quem ganhou o jogo do Flamengo ontem?

**melodIA:** Não acompanho futebol, meu forte é só música mesmo! 🎸 

Se precisar de ajuda com algum instrumento musical, é só me chamar.
