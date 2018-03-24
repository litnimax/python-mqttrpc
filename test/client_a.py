import asyncio
from mqttrpc import MQTTRPC



class ClientA(MQTTRPC):

    async def run_hello_on_b(self, name):
        client_b = self.get_proxy_for('client_b')
        return await client_b.hello(name)


loop = asyncio.get_event_loop()
client_a = ClientA(client_uid='client_a')
asyncio.ensure_future(client_a.process_messages())
print(
    loop.run_until_complete(
        client_a.run_hello_on_b('Max')))
