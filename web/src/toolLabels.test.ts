import { describe, expect, it } from "vitest";

import { toolLabel } from "./toolLabels";

describe("toolLabel", () => {
  it("labels data lookups", () => {
    expect(toolLabel({ name: "search_products", args: { query: "takamine gd20" } })).toEqual({
      kind: "data",
      text: "Buscou no catálogo: “takamine gd20”",
    });
    expect(toolLabel({ name: "search_products", args: { category_id: 5 } }).text).toBe("Buscou no catálogo");
    expect(toolLabel({ name: "get_order_status", args: { order_id: 7, email: "x@y.com" } }).text).toBe(
      "Consultou o pedido #7",
    );
    expect(toolLabel({ name: "get_delivery_info", args: { city: "Dourados" } })).toEqual({
      kind: "data",
      text: "Consultou o frete para Dourados",
    });
  });

  it("labels policy lookups with a readable topic", () => {
    expect(toolLabel({ name: "get_policy", args: { topic: "trocas_e_devolucoes" } })).toEqual({
      kind: "policy",
      text: "Política: trocas e devoluções",
    });
  });

  it("labels support tickets as actions", () => {
    expect(toolLabel({ name: "create_support_ticket", args: {} }).kind).toBe("action");
  });

  it("falls back to the raw name for unknown tools", () => {
    expect(toolLabel({ name: "new_tool", args: {} })).toEqual({ kind: "action", text: "new_tool" });
  });
});
