import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const fetchMock = vi.fn();

function apiAnswer(answer: string, tool_calls: unknown[] = [], session_id = "session-1") {
  return Promise.resolve(new Response(JSON.stringify({ session_id, answer, tool_calls }), { status: 200 }));
}

function lastRequestBody() {
  const [, init] = fetchMock.mock.calls.at(-1)!;
  return JSON.parse(init.body);
}

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

async function typeAndSend(text: string) {
  await userEvent.type(screen.getByLabelText("Sua mensagem"), `${text}{Enter}`);
}

describe("App", () => {
  it("shows the challenge scenarios as suggestions and sends one on click", async () => {
    fetchMock.mockReturnValueOnce(apiAnswer("O endereço é **Rua 14 de Maio, 3200**."));
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: "Qual o endereço da loja?" }));

    expect(await screen.findByText("Rua 14 de Maio, 3200")).toBeInTheDocument();
    expect(lastRequestBody()).toEqual({ message: "Qual o endereço da loja?", session_id: null, today: null });
  });

  it("renders the answer as Markdown and labels the lookups the agent made", async () => {
    fetchMock.mockReturnValueOnce(
      apiAnswer("O **Takamine GD20** custa R$ 2.199,00.", [
        { name: "search_products", args: { query: "takamine gd20" } },
        { name: "get_policy", args: { topic: "pagamento" } },
      ]),
    );
    render(<App />);
    await typeAndSend("Quanto custa o Takamine GD20?");

    const bold = await screen.findByText("Takamine GD20");
    expect(bold.tagName).toBe("STRONG");
    const lookups = screen.getByRole("list", { name: "Consultas feitas pela melodIA" });
    expect(within(lookups).getByText(/Buscou no catálogo/)).toBeInTheDocument();
    expect(within(lookups).getByText(/Política: pagamento/)).toBeInTheDocument();
  });

  it("can hide the lookups", async () => {
    fetchMock.mockReturnValueOnce(apiAnswer("Oi!", [{ name: "get_policy", args: { topic: "horarios" } }]));
    render(<App />);
    await typeAndSend("oi");
    await screen.findByText("Oi!");

    await userEvent.click(screen.getByLabelText("Mostrar consultas"));
    expect(screen.queryByText(/Política: horários/)).not.toBeInTheDocument();
  });

  it("keeps the session and sends the simulated date", async () => {
    fetchMock.mockReturnValueOnce(apiAnswer("Oi!")).mockReturnValueOnce(apiAnswer("Claro!"));
    render(<App />);

    await userEvent.type(screen.getByLabelText("Data simulada"), "2026-02-20");
    await typeAndSend("oi");
    await screen.findByText("Oi!");
    await typeAndSend("pedido 7");
    await screen.findByText("Claro!");

    expect(lastRequestBody()).toEqual({ message: "pedido 7", session_id: "session-1", today: "2026-02-20" });
  });

  it("shows an error when the server is unreachable and lets the user try again", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("Failed to fetch"));
    render(<App />);
    await typeAndSend("oi");

    expect(await screen.findByRole("alert")).toHaveTextContent("Não consegui falar com o servidor");
    expect(screen.getByLabelText("Sua mensagem")).not.toBeDisabled();
  });

  it("does not send empty messages", async () => {
    render(<App />);
    await typeAndSend("   ");
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Enviar" })).toBeDisabled();
  });

  it("starts a new conversation and ends the old session on the server", async () => {
    fetchMock.mockReturnValueOnce(apiAnswer("Oi!")).mockReturnValueOnce(Promise.resolve(new Response("{}")));
    render(<App />);
    await typeAndSend("oi");
    await screen.findByText("Oi!");

    await userEvent.click(screen.getByRole("button", { name: "Nova conversa" }));

    expect(screen.queryByText("Oi!")).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith("/api/chat/session-1", { method: "DELETE" });
  });
});
