# RPC over MQTT
Use cases:

* RPC communication between MQTT clients
* Making JSON-RPC HTTP requests from MQTT agents via MQTT (http_bridge)
* Calling MQTT agents from outside world (http_bridge)

MQTT clients subscribe for topics *rpc/my_uid/+* and wait for RPC requests.

When somebody wants to send a request it is sent to *rpc/destination_uid/my_uid*.

Reply is then published to *rpc/destination_uid/my_uid/reply*.

If your broker users authentication be sure to allow these topics.

## Dependencies
* Python3 with asyncio
* hbmqtt
* tinyrpc

## JSON-RPC between MQTT clients
In out test case we have ClientA and ClientB, MQTT broker is running on localhost:1883.

ClientA wants to call *hello* method on ClientB. Here is the code.

ClientA:
```python
import asyncio
from mqttrpc import MQTTRPC



class ClientA(MQTTRPC):

    def run_hello_on_b(self, name):
        client_b = self.get_proxy_for('client_b')
        return client_b.hello(name)


loop = asyncio.get_event_loop()
client_a = ClientA(client_uid='client_a')
asyncio.ensure_future(client_a.serve_forever())
print(
    loop.run_until_complete(
        client_a.run_hello_on_b('Max')))
```

ClientB:
```python
import asyncio
from mqttrpc import MQTTRPC
from mqttrpc import dispatcher


class ClientB(MQTTRPC):
    
    @dispatcher.public
    def hello(self, name):
        print ('Got Hello request, sending back.')
        return 'Hello, {}'.format(name)


loop = asyncio.get_event_loop()
client_b = ClientB(client_uid='client_b')
print(
    loop.run_until_complete(
        client_b.serve_forever()))

```

Output from client B:
```sh
MacBook-Pro-Max:test max$ python3 client_a.py
Client not connected, waiting for it
Hello, Max
```
Output from client B:
```sh
MacBook-Pro-Max:test max$ python3 client_b.py
Got Hello request, sending back.
```


## Using HTTP Bridge to make outbound and inbound RPC
HTTP Bridge is a transparent bridge between JSON-RPC over MQTT and JSON-RPC over HTTP.

http_bridge starts MQTT client and HTTP server and cross-connects requests between them.

CLIENT_UID is MQTT uid used by MQTT agents to send RPC requests to.

HTTP_URL is real JSON-RPC HTTP server serving the request.

In the example below we use Odoo as RPC server.

First, start a http_bridge settings MQTT client UID and HTTP server URL.

```sh
CLIENT_UID=odoo_bridge HTTP_URL=http://localhost:8069/jsonrpc python3 http_bridge.py
```
Now let run the following code:
```python
import asyncio
from mqttrpc import MQTTRPC, OdooRPCProxy

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
loop.create_task(server.serve_forever())
print(
    loop.run_until_complete(server.run_partner_test('Administrator')))

```
Here is the output:
```sh
MacBook-Pro-Max:test max$ python3 test_mqttrpc_odoo.py
Client not connected, waiting for it
Administrator uid is:  1
Partner id is:  [3]
[3]
```

### Odoo note
See rpcproxy.py, OdooRPCProxy is a wrapper around RPCProxy, which shoud be used in other cases.

When using Odoo, you can avoid login call by looking up the login id and creating OdooRPCProxy with it:
```
proxy = OdooRPCProxy(self, 'odoo_bridge', uid=1)
```
After that you can call methods without prior call to login.

## TODO
* Describe notification calls (that do not require reply)
* Show IoT usage example when JSON-RPC is run over LoraWAN.

## Testing
Docker files are supplied with all examples.

```sh
cd test
docker-compose up -d db && sleep 5 &&  docker-compose up -d odoo broker
```
Wait 5 seconds for odoo test db init, after that run:
```sh
docker-compose up http_bridge test test_odoo
```
Output:
```sh
mqtt_broker is up-to-date
Starting mqttrpc_test ... done
mqttrpc_test   | INFO:mqtt_rpc:Connected.
mqttrpc_test   | Hello, World
mqttrpc_test exited with code 0
MacBook-Pro-Max:test max$
```
Notice 'Hello World' - that means RPC over MQTT is working.

Now test Odoo MQTT RPC bridge:
```sh
docker-compose up test_odoo
```
Output:
```sh
mqttrpc_test_odoo | INFO:mqtt_rpc:Connected.
mqttrpc_test_odoo | Administrator id is:  [3]
mqttrpc_test_odoo exited with code 0
MacBook-Pro-Max:test max$
```
Notice Administrator id = [3].§