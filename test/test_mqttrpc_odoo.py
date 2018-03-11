import asyncio
import logging
from mqttrpc import MQTTRPC, OdooRPCProxy

logging.basicConfig(level=logging.INFO)
logging.getLogger('hbmqtt').setLevel(level=logging.INFO)


class TestOdooMQTTRPC(MQTTRPC):

    async def run_partner_test(self, partner_name):
        proxy = OdooRPCProxy(self, 'odoo_bridge')
        try:
            uid = await proxy.login('test', 'admin', 'admin')
            print ('Administrator uid is: ', uid)
            assert 1 == uid
            res = await proxy.execute('res.partner', 'search', [('name','=', 'Administrator')])
            print ('Partner id is: ', res)
            assert [3] == res
            return res
        except Exception as e:
            print (e, flush=True)


loop = asyncio.get_event_loop()
server = TestOdooMQTTRPC(loop=loop)
try:
    loop.create_task(server.serve_forever())
    assert [3] == loop.run_until_complete(server.run_partner_test('Administrator'))

finally:
    loop.run_until_complete(server.stop())
    loop.close()

