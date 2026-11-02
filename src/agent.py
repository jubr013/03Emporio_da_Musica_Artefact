"""The agent: a hand-written function-calling loop on top of the Gemini API (google-genai SDK).

One turn = send the conversation -> if the model asks for tools, run them and send the results back ->
repeat until the model answers with text. The SDK's automatic function calling is disabled on purpose,
so every step is explicit (see docs/decisions.md).
"""
import os
import sys
from typing import Callable, Optional

from google import genai
from google.genai import errors, types

from src import policies, tools
from src.prompts import build_system_prompt

MAX_TOOL_ROUNDS = 6  # safety limit: stop if the model keeps asking for tools without answering

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
        self.history: list = []  # list of types.Content, the whole conversation
        self.on_tool_call = on_tool_call  # optional callback, e.g. to print tool calls in the CLI
        self.tool_declarations = types.Tool(function_declarations=_function_declarations())

    def _config(self) -> types.GenerateContentConfig:
        # Rebuilt every turn so the prompt has the store's current date/time (date honours STORE_TODAY)
        return types.GenerateContentConfig(
            system_instruction=build_system_prompt(tools.now()),
            tools=[self.tool_declarations],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            temperature=0.3,  # low: we want consistent, factual answers
        )

    def send(self, user_message: str) -> str:
        history_before = len(self.history)
        try:
            return self._answer(user_message)
        except errors.APIError as error:
            # Model unavailable even after retries (e.g. 503 high demand, 429 quota): undo this half-finished
            # turn so the history stays consistent, and answer politely instead of crashing.
            # The real reason goes to stderr for whoever runs the program, not to the customer.
            print(f"[Gemini API error {error.code}] {error.status}: {str(error.message)[:200]}", file=sys.stderr)
            del self.history[history_before:]
            return FALLBACK_ANSWER

    def _answer(self, user_message: str) -> str:
        self.history.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

        for _ in range(MAX_TOOL_ROUNDS):
            response = self.client.models.generate_content(
                model=self.model, contents=self.history, config=self._config()
            )
            if not response.candidates or response.candidates[0].content is None:
                return FALLBACK_ANSWER
            # Keep the model's turn exactly as returned (it may carry internal "thought signatures")
            self.history.append(response.candidates[0].content)

            calls = response.function_calls
            if not calls:
                return response.text or FALLBACK_ANSWER

            result_parts = []
            for call in calls:
                args = dict(call.args or {})
                result = run_tool(call.name, args)
                if self.on_tool_call:
                    self.on_tool_call(call.name, args, result)
                result_parts.append(types.Part(
                    function_response=types.FunctionResponse(id=call.id, name=call.name, response=result)
                ))
            # Tool results go back to the model as the next message in the conversation
            self.history.append(types.Content(role="user", parts=result_parts))

        return FALLBACK_ANSWER
