import asyncio
import logging
import os
from mqttrpc import MQTTRPC, dispatcher

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('hbmqtt').setLevel(level=logging.INFO)


class TestMQTTRPC(MQTTRPC):
    @dispatcher.public
    async def test(name=''):
        print('Hello')
        return 'Hello, {}'.format(name)


loop = asyncio.get_event_loop()
server = TestMQTTRPC(client_uid='test', loop=loop)
loop.run_until_complete(server.process_messages())
