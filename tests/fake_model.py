"""A fake Gemini client for tests: scripted responses built with the SDK's real types, no API calls.

Shared by the agent loop tests and the web API tests.
"""
from google.genai import types

from src.agent import Agent


def text_response(text: str) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[types.Part(text=text)])
    )])


def tool_call_response(name: str, args: dict, call_id: str = "call-1") -> types.GenerateContentResponse:
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=[
            types.Part(function_call=types.FunctionCall(id=call_id, name=name, args=args))
        ])
    )])


class FakeModels:
    """Stands in for client.models: returns (or raises) the scripted items in order and records each request."""

    def __init__(self, script: list):
        self.script = list(script)
        self.requests = []
        self.models_used = []

    def generate_content(self, model, contents, config):
        self.requests.append(list(contents))  # copy: the agent keeps appending to the same list
        self.models_used.append(model)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, script: list):
        self.models = FakeModels(script)


def make_agent(script: list, **kwargs) -> Agent:
    return Agent(model="fake-model", client=FakeClient(script), **kwargs)
