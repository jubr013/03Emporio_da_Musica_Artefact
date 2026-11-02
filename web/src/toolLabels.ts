// Turns the agent's tool calls into short labels, so the UI shows WHEN it consulted data vs. policies.
import type { ToolCall } from "./api";

export type ToolKind = "data" | "policy" | "action";

export interface ToolLabel {
  kind: ToolKind;
  text: string;
}

const POLICY_TOPICS: Record<string, string> = {
  sobre_a_loja: "dados da loja",
  horarios: "horários",
  pagamento: "pagamento",
  trocas_e_devolucoes: "trocas e devoluções",
  frete_e_entregas: "frete e entregas",
  promocoes: "promoções",
  atendimento: "atendimento",
  garantia: "garantia",
  privacidade: "privacidade",
  lojas_parceiras: "lojas parceiras",
};

export function toolLabel({ name, args }: ToolCall): ToolLabel {
  switch (name) {
    case "search_products":
      return { kind: "data", text: args.query ? `Buscou no catálogo: “${args.query}”` : "Buscou no catálogo" };
    case "get_product_details":
      return { kind: "data", text: `Consultou o produto #${args.product_id}` };
    case "get_order_status":
      return { kind: "data", text: `Consultou o pedido #${args.order_id}` };
    case "get_policy": {
      const topic = String(args.topic ?? "");
      return { kind: "policy", text: `Política: ${POLICY_TOPICS[topic] ?? topic}` };
    }
    case "create_support_ticket":
      return { kind: "action", text: "Abriu uma solicitação para a equipe" };
    default:
      return { kind: "action", text: name };
  }
}
