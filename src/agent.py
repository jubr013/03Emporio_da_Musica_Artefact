"""The agent: a hand-written function-calling loop on top of the Gemini API (google-genai SDK).

One turn = send the conversation -> if the model asks for tools, run them and send the results back ->
repeat until the model answers with text. The SDK's automatic function calling is disabled on purpose,
so every step is explicit (see docs/decisions.md).
"""
import os
import re
import sys
from typing import Callable, Optional

from google import genai
from google.genai import errors, types

from src import policies, tools
from src.data_loader import normalize_text
from src.prompts import build_system_prompt

MAX_TOOL_ROUNDS = 6  # safety limit: stop if the model keeps asking for tools without answering
MAX_IDENTITY_ATTEMPTS = 3  # failed order verifications allowed per conversation (LGPD: no guessing contact details)

IDENTITY_BLOCKED_MESSAGE = (
    "Limite de tentativas de verificação atingido nesta conversa. Não consulte mais pedidos aqui: "
    "oriente o cliente a falar com a equipe pelo WhatsApp (67) 3321-4500."
)

UNVERIFIED_ORDER_TICKET_MESSAGE = (
    "Solicitação não registrada: o pedido informado não foi verificado nesta conversa. Antes, confirme o pedido "
    "com get_order_status (número do pedido + e-mail ou telefone usado na compra)."
)

# Claims the product data never supports and internal wording the customer shouldn't see. The prompt forbids them,
# but the model still slipped now and then ("queridinho dos professores"), so answers are checked in code.
# "sistema" alone is fine ("sistema de captação" is in product descriptions); "o/no/nosso sistema" is internal talk.
FORBIDDEN_IN_ANSWERS = {
    r"professor": "opiniões atribuídas a professores",
    r"mais vendid": "\"mais vendido\" (não temos dados de vendas)",
    r"queridinh": "\"queridinho\" (afirmação sem base nos dados)",
    r"ferramenta": "a palavra \"ferramenta\"",
    r"manual interno": "\"manual interno\"",
    r"\b(?:o|no|nosso) sistema\b(?! de)": "\"o sistema\" (fale \"consultei aqui\")",
}

REWRITE_REQUEST = (
    "[Revisão automática, não é mensagem do cliente] Reescreva sua última resposta ao cliente sem: {problems}. "
    "Mantenha as mesmas informações, preços e tom; mude só esses trechos."
)

FALLBACK_ANSWER = (
    "Desculpa, tive um problema para concluir sua consulta agora. "
    "Você pode tentar de novo ou falar com a equipe pelo WhatsApp (67) 3321-4500."
)


def _category_list() -> str:
    categories = tools._store().categories
    return ", ".join(f"{row.category_id}={row.name}" for row in categories.itertuples())


def _function_declarations() -> list:
    """Tool descriptions the model sees (name, when to use it, parameters as JSON Schema)."""
    return [
        types.FunctionDeclaration(
            name="search_products",
            description=(
                "Busca instrumentos no catálogo. Retorna nome, categoria, disponibilidade e preços "
                "(tabela, promoção ativa, PIX). Ordenado do mais barato. Categorias: " + _category_list()
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Palavras-chave (marca, modelo, tipo). Ex.: 'takamine gd20', 'nylon'."},
                    "category_id": {"type": "integer", "description": "ID da categoria."},
                    "max_price": {"type": "number", "description": "Preço final máximo em R$."},
                    "min_price": {"type": "number", "description": "Preço final mínimo em R$."},
                    "only_available": {"type": "boolean", "description": "true para só itens com estoque e ativos."},
                    "limit": {"type": "integer", "description": "Máximo de resultados (padrão 10)."},
                },
            },
        ),
        types.FunctionDeclaration(
            name="get_product_details",
            description="Detalhes de um produto: descrição, especificações, estoque, disponibilidade e preços.",
            parameters_json_schema={
                "type": "object",
                "properties": {"product_id": {"type": "integer"}},
                "required": ["product_id"],
            },
        ),
        types.FunctionDeclaration(
            name="get_order_status",
            description=(
                "Status de um pedido. Exige o número do pedido e o e-mail OU telefone do cliente. "
                "Para pedidos entregues, retorna os prazos de arrependimento, troca por defeito e garantia."
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "order_id": {"type": "integer"},
                    "email": {"type": "string"},
                    "phone": {"type": "string"},
                    "received_on": {"type": "string", "description": "Data de recebimento informada pelo cliente (AAAA-MM-DD), se diferente da previsão."},
                },
                "required": ["order_id"],
            },
        ),
        types.FunctionDeclaration(
            name="create_support_ticket",
            description=(
                "Registra uma solicitação para a equipe humana (devolução, troca, garantia, reclamação ou outro) "
                "e retorna um número de protocolo. Use só depois que o cliente confirmar que quer abrir a solicitação."
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "request_type": {"type": "string", "enum": tools.TICKET_TYPES},
                    "summary": {"type": "string", "description": "Resumo objetivo do pedido do cliente, para a equipe."},
                    "order_id": {"type": "integer"},
                    "customer_contact": {"type": "string", "description": "E-mail ou telefone informado pelo cliente."},
                },
                "required": ["request_type", "summary"],
            },
        ),
        types.FunctionDeclaration(
            name="get_delivery_info",
            description=(
                "Frete e prazo de entrega para a cidade do cliente. Diz se a cidade tem entrega local (motoboy, "
                "frete grátis a partir de R$ 500) e calcula a taxa; para outras cidades, retorna modalidades e prazos "
                "(o valor depende do CEP e não é informado aqui)."
            ),
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Cidade de entrega informada pelo cliente."},
                    "order_total_brl": {"type": "number", "description": "Preço final do que o cliente quer comprar (some se forem vários)."},
                },
                "required": ["city"],
            },
        ),
        types.FunctionDeclaration(
            name="get_policy",
            description="Texto da política da loja sobre um tópico.",
            parameters_json_schema={
                "type": "object",
                "properties": {"topic": {"type": "string", "enum": policies.list_policy_topics()}},
                "required": ["topic"],
            },
        ),
    ]


# Maps the name the model uses to the Python function that runs it
TOOL_FUNCTIONS: dict = {
    "search_products": tools.search_products,
    "get_product_details": tools.get_product_details,
    "get_order_status": tools.get_order_status,
    "create_support_ticket": tools.create_support_ticket,
    "get_delivery_info": tools.get_delivery_info,
    "get_policy": policies.get_policy,
}


def run_tool(name: str, args: dict) -> dict:
    """Runs one tool call. Errors become a dict, so the model can explain instead of the program crashing."""
    function = TOOL_FUNCTIONS.get(name)
    if function is None:
        return {"error": f"Ferramenta desconhecida: {name}"}
    try:
        return function(**args)
    except Exception as error:  # noqa: BLE001 - any tool failure is reported back to the model
        return {"error": f"Falha ao executar {name}: {error}"}


def forbidden_phrases(text: str) -> list:
    """Descriptions of the forbidden phrases found in an answer (accents and case ignored)."""
    normalized = normalize_text(text)
    return [description for pattern, description in FORBIDDEN_IN_ANSWERS.items() if re.search(pattern, normalized)]


def _as_order_id(value) -> Optional[int]:
    """The model may send the order number as 7, 7.0 or "7"; anything else is not a valid order id."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


class Agent:
    """Keeps the conversation history in memory and answers one customer message at a time."""

    def __init__(self, model: Optional[str] = None, on_tool_call: Optional[Callable] = None, client=None):
        # `client` lets tests pass a fake model (no API calls). By default: the real Gemini client, which reads
        # GEMINI_API_KEY from the environment. The free tier sometimes answers 503 (high demand), so we retry
        # with exponential backoff before giving up.
        self.client = client or genai.Client(http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(attempts=5, initial_delay=2, max_delay=20)
        ))
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        # Used once if the main model's quota runs out (429). Has its own free quota. Empty value disables it.
        self.fallback_model = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.1-flash-lite") or None
        self.history: list = []  # list of types.Content, the whole conversation
        self.on_tool_call = on_tool_call  # optional callback, e.g. to print tool calls in the CLI
        self.tool_declarations = types.Tool(function_declarations=_function_declarations())
        self.failed_identity_checks = 0  # wrong e-mail/phone attempts in this conversation
        self.verified_orders: set = set()  # order ids whose owner was verified in this conversation

    def _run_tool_with_limits(self, name: str, args: dict) -> dict:
        """Runs a tool, enforcing per-conversation limits that a stateless tool can't track.

        Order lookups: after MAX_IDENTITY_ATTEMPTS failed verifications (wrong e-mail/phone), further lookups are
        refused for the rest of the conversation, so nobody can guess contact details by trial and error.
        Tickets about an order: only for an order verified in this conversation, so nobody can open a return or
        complaint on someone else's order.
        """
        if name == "get_order_status" and self.failed_identity_checks >= MAX_IDENTITY_ATTEMPTS:
            return {"verified": False, "blocked": True, "message": IDENTITY_BLOCKED_MESSAGE}
        if name == "create_support_ticket" and args.get("order_id") is not None:
            if _as_order_id(args["order_id"]) not in self.verified_orders:
                return {"created": False, "message": UNVERIFIED_ORDER_TICKET_MESSAGE}

        result = run_tool(name, args)
        if name == "get_order_status":
            contact_given = args.get("email") or args.get("phone")
            if contact_given and result.get("verified") is False:
                self.failed_identity_checks += 1
            elif result.get("verified") is True:
                self.verified_orders.add(result["order_id"])
        return result

    def _config(self) -> types.GenerateContentConfig:
        # Rebuilt every turn so the prompt has the store's current date/time (date honours STORE_TODAY)
        return types.GenerateContentConfig(
            system_instruction=build_system_prompt(tools.now()),
            tools=[self.tool_declarations],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0,  # customer service needs consistent, factual answers, not creative ones
        )

    def _generate(self) -> types.GenerateContentResponse:
        """Calls the model. If its quota is exhausted (429 even after the SDK's retries), switches to the fallback
        model for the rest of the conversation and tries again once."""
        try:
            return self.client.models.generate_content(model=self.model, contents=self.history, config=self._config())
        except errors.ClientError as error:
            if error.code != 429 or not self.fallback_model or self.fallback_model == self.model:
                raise
            print(f"[quota exhausted for {self.model}, switching to {self.fallback_model}]", file=sys.stderr)
            self.model = self.fallback_model
            return self.client.models.generate_content(model=self.model, contents=self.history, config=self._config())

    def send(self, user_message: str) -> str:
        history_before = len(self.history)
        try:
            answer = self._answer(user_message)
        except errors.APIError as error:
            # Model unavailable even after retries (e.g. 503 high demand, 429 quota).
            # The real reason goes to stderr for whoever runs the program, not to the customer.
            print(f"[Gemini API error {error.code}] {error.status}: {str(error.message)[:200]}", file=sys.stderr)
            answer = None
        if answer is None:
            # No usable answer (API error, empty response, tool round limit): undo this half-finished turn so the
            # history doesn't end on an unanswered message or tool result, and answer politely instead of crashing.
            del self.history[history_before:]
            return FALLBACK_ANSWER
        return answer

    def _answer(self, user_message: str) -> Optional[str]:
        """Runs one turn. Returns the answer text, or None if the turn produced no usable answer."""
        self.history.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
        rewrite_at = None  # history index of an answer sent back for rewriting (only once per turn)

        for _ in range(MAX_TOOL_ROUNDS):
            response = self._generate()
            if not response.candidates or response.candidates[0].content is None:
                return None
            # Keep the model's turn exactly as returned (it may carry internal "thought signatures")
            self.history.append(response.candidates[0].content)

            calls = response.function_calls
            if not calls:
                text = response.text or None
                problems = forbidden_phrases(text or "")
                if text and problems and rewrite_at is None:
                    # Ask for one rewrite; the bad answer and this request are removed once it arrives
                    rewrite_at = len(self.history) - 1
                    request = REWRITE_REQUEST.format(problems="; ".join(problems))
                    self.history.append(types.Content(role="user", parts=[types.Part(text=request)]))
                    continue
                if rewrite_at is not None:
                    del self.history[rewrite_at:rewrite_at + 2]
                return text

            result_parts = []
            for call in calls:
                args = dict(call.args or {})
                result = self._run_tool_with_limits(call.name, args)
                if self.on_tool_call:
                    self.on_tool_call(call.name, args, result)
                result_parts.append(types.Part(
                    function_response=types.FunctionResponse(id=call.id, name=call.name, response=result)
                ))
            # Tool results go back to the model as the next message in the conversation
            self.history.append(types.Content(role="user", parts=result_parts))

        return None
