import asyncio
import logging
import os
from mqttrpc import MQTTRPC, dispatcher

logging.basicConfig(level=logging.INFO)
logging.getLogger('hbmqtt').setLevel(level=logging.INFO)


class TestMQTTRPC(MQTTRPC):
    @dispatcher.public
    def test(self, name):
        return 'Hello, {}'.format(name)

    async def run_test(self, name):
        await self._connected_state.wait()
        proxy = self.get_proxy_for('test')
        try:
            res = await proxy.test(name)
            print (res)
            return res
        except Exception as e:
            print (e)



loop = asyncio.get_event_loop()
server = TestMQTTRPC(client_uid='test', loop=loop)
loop.create_task(server.serve_forever())
assert 'Hello, World' == loop.run_until_complete(server.run_test('World'))
