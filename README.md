# RPC over MQTT
This 

## HTTP Bridge
HTTP Bridge is a transparent bridge between JSON-RPC over MQTT and JSON-RPC over HTTP.

http_bridge starts MQTT client and HTTP server and cross-connects requests between them.

CLIENT_UID is MQTT uid used by MQTT agents to send RPC requests to.
HTTP_URL is real JSON-RPC HTTP server serving the request.

Example how to run http_bridge: 

## Test with Odoo
```
cd test
docker-compose up -d db && sleep 5 &&  docker-compose up -d odoo broker
```
Wait 5 seconds for odoo test db init, after that run:
```
docker-compose up http_bridge test test_odoo
```
Output:
```
mqtt_broker is up-to-date
Starting mqttrpc_test ... done
mqttrpc_test   | INFO:mqtt_rpc:Connected.
mqttrpc_test   | Hello, World
mqttrpc_test exited with code 0
MacBook-Pro-Max:test max$
```
Notice 'Hello World' - that means RPC over MQTT is working.

Now test Odoo MQTT RPC bridge:
```
docker-compose up test_odoo
```
Output:
```
mqttrpc_test_odoo | INFO:mqtt_rpc:Connected.
mqttrpc_test_odoo | Administrator id is:  [3]
mqttrpc_test_odoo exited with code 0
MacBook-Pro-Max:test max$
```
Notice Administrator is is 3. Bridge is working.