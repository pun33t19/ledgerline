import pytest

from ledgerline.jsonrpc import Message, encode, error_response, parse
from ledgerline.proxy.interceptor import (
    FORWARD,
    Block,
    Chain,
    Decision,
    Direction,
    Forward,
    Interceptor,
    Replace,
)

pytestmark = pytest.mark.anyio

REQUEST = parse(b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"a"}}')
RESPONSE = parse(b'{"jsonrpc":"2.0","id":1,"result":{}}')


class Recorder(Interceptor):
    def __init__(self, name: str, log: list[str], decision: Decision = FORWARD) -> None:
        self.name, self.log, self.decision = name, log, decision
        self.seen: list[Message] = []

    async def on_request(self, request: Message, upstream: object) -> Decision:
        self.log.append(f"req:{self.name}")
        self.seen.append(request)
        return self.decision

    async def on_response(self, request: Message, response: Message) -> Decision:
        self.log.append(f"resp:{self.name}")
        return self.decision

    def observe(self, direction: Direction, message: Message) -> None:
        self.log.append(f"obs:{self.name}")


async def test_requests_in_order_responses_in_reverse() -> None:
    log: list[str] = []
    chain = Chain([Recorder("a", log), Recorder("b", log)])
    assert isinstance(await chain.on_request(REQUEST, None), Forward)  # type: ignore[arg-type]
    assert isinstance(await chain.on_response(REQUEST, RESPONSE), Forward)
    chain.observe("client→server", REQUEST)
    assert log == ["req:a", "req:b", "resp:b", "resp:a", "obs:a", "obs:b"]


async def test_first_block_wins() -> None:
    log: list[str] = []
    block = Block(error_response(1, -1, "no"), "test")
    chain = Chain([Recorder("a", log, block), Recorder("b", log)])
    assert await chain.on_request(REQUEST, None) is block  # type: ignore[arg-type]
    assert log == ["req:a"]


async def test_replacement_is_what_the_next_interceptor_sees() -> None:
    new_body = {**REQUEST.body, "params": {"name": "b"}}
    second = Recorder("b", [])
    chain = Chain([Recorder("a", [], Replace(new_body)), second])

    decision = await chain.on_request(REQUEST, None)  # type: ignore[arg-type]

    assert isinstance(decision, Replace)
    assert second.seen[0].params == {"name": "b"}
    assert second.seen[0].raw == encode(new_body).rstrip(b"\n")
