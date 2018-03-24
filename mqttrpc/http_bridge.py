#!/usr/bin/env python3

import aiohttp
from aiohttp import web
import asyncio
from asyncio import Queue
from async_timeout import timeout
import json
import logging
import re
import signal
import os
from tinyrpc.protocols.jsonrpc import JSONRPCProtocol
from tinyrpc.exc import RPCError
from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_2


HTTP_URL = os.environ.get('HTTP_URL', 'http://localhost:8069/jsonrpc')
HTTP_BIND_ADDRESS = os.environ.get('HTTP_BIND_ADDRESS', '0.0.0.0')
HTTP_BIND_PORT = os.environ.get('HTTP_BIND_PORT', '8888')
HTTP_REQUEST_TIMEOUT = float(os.environ.get('HTTP_REQUEST_TIMEOUT', 4))
MQTT_URL = os.environ.get('MQTT_URL', 'mqtt://localhost/')
CLIENT_UID = os.environ.get('CLIENT_UID', 'http_bridge')
MQTT_REPLY_TIMEOUT = float(os.environ.get('MQTT_REPLY_TIMEOUT', 5))
DEBUG = os.environ.get('DEBUG', False)

logger = logging.getLogger('mqtt_http_bridge')
rpc_potocol = JSONRPCProtocol()

class HttpMqttBridge(object):
    mqtt_replies = {} # Keep track of sent requests
    mqtt_reply_subscriptions = [] # Topics we subscribed for reply

    def __init__(self, loop=None):
        if not loop:
            loop = asyncio.get_event_loop()
        self.loop = loop
        self.mqtt_url = MQTT_URL
        self.mqtt_reply_timeout = MQTT_REPLY_TIMEOUT
        self.http_url = HTTP_URL
        self.http_request_timeout = HTTP_REQUEST_TIMEOUT
        self.client_uid = CLIENT_UID
        logger.info('Bridging {} with UID {}'.format(HTTP_URL, CLIENT_UID))
        self.client = MQTTClient(client_id=CLIENT_UID)
        logger.info('Initialized')
        self.http_server = None
        # Install signal handlers
        for signame in ('SIGINT', 'SIGTERM'):
            self.loop.add_signal_handler(getattr(signal, signame),
                lambda: asyncio.ensure_future(self.stop()))
        logger.info('Client {} initialized'.format(CLIENT_UID))


    async def stop(self):
        logger.info('Stopping...')
        # Check subscriptions
        await self.client.unsubscribe(self.mqtt_reply_subscriptions)
        await self.client.disconnect()
        tasks = [task for task in asyncio.Task.all_tasks() if task is not
                    asyncio.tasks.Task.current_task()]
        list(map(lambda task: task.cancel(), tasks))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        logger.debug('Finished cancelling tasks, result: {}'.format(results))


    async def process_messages(self):
        self.http_server = web.Server(self.process_http_requests)
        await loop.create_server(self.http_server,
                                 HTTP_BIND_ADDRESS, int(HTTP_BIND_PORT))
        await self.client.connect(self.mqtt_url)
        await self.client.subscribe([
            ('rpc/{}/+'.format(CLIENT_UID), QOS_2),
        ])
        logger.debug('Starting process messages...')
        while True:
            try:                
                await self.process_mqtt_message(
                    await self.client.deliver_message())
            except asyncio.CancelledError:
                return
            except Exception as e:
                raise e


    async def process_mqtt_message(self, message):
        await self.client._connected_state.wait()
        # Init a template for JSON-RPC error
        error =  { "jsonrpc": "2.0",
                  "id": None,
                  "error": {"message": None, "code": -1}
        }
        logger.debug('Message at topic {}: {}'.format(message.topic,
                                                      message.data))
        if re.search('^rpc/(\w+)/(\w+)$', message.topic):
            try:
                _, _, from_uid = message.topic.split('/')
                logger.debug('Request from {}'.format(from_uid))
                js = json.loads(message.data)
                logger.debug('RPC: {}'.format(js))
                self.loop.create_task(self.process_mqtt_request(from_uid, js))
            except json.decoder.JSONDecodeError:
                logger.error('Bad JSON data for request: {}'.format(message.data))
            except Exception as e:
                logger.exception(e)


        elif re.search('^rpc/(\w+)/(\w+)/reply$', message.topic):
            # RPC reply
            logger.debug('RPC reply at {}'.format(message.topic))
            _, _, context, _ = message.topic.split('/')
            data_str = message.data.decode()
            waiting_replies = self.mqtt_replies.get(message.topic)
            if not waiting_replies:
                logger.warning(
                    'Got an unexpected RPC reply from {}: {}'.format(
                        message.topic, data_str))
                return
            # Valid reply received, let put it in the queue.
            try:
                data_js = json.loads(data_str)
                logger.debug("It's a JSON reply.")
            except json.decoder.JSONDecodeError:                    
                logger.error('RPC reply bad json data: {}'.format(data_str))
                # If there is only one waiting request then match with it.                    
                if len(waiting_replies) == 1:
                    request_id = list(waiting_replies.keys())[0]
                    error['error']['message'] = "Bad JSON: {}".format(data_str)
                    await waiting_replies[key].put(error)
            else:
                # We got valid JSON from data
                request_id = data_js.get('id')
                if request_id not in waiting_replies.keys():
                    logger.error(
                        'Got a reply from {} without id: {}'.format(
                            message.topic, data_str))
                    # Try to match it with the only one request
                    if len(waiting_replies) == 1:
                        request_id = list(waiting_replies.keys())[0]
                        error['error']['message'] = "Bad reply id: {}".format(data_str)
                        await waiting_replies[key].put(error)
                    else:
                        # We cannot match, so forget it.
                        logger.error('Cannot match reply without id')

                else:
                    # Finally matched the request by id
                    logger.debug(
                        'Waiting reply found for request {}'.format(
                                                        request_id))
                    await waiting_replies[request_id].put(data_js)
        else:
            logger.warning('Unknown MQTT message, ignoring')



    async def process_http_requests(self, request):
        # Init a template for JSON-RPC error
        error =  { "jsonrpc": "2.0",
                  "id": None,
                  "error": {"message": None, "code": -1}
        }
        #         
        try:
            data = await request.text()
            rpc_potocol.parse_request(data)
        except RPCError as e:
            response = e.error_respond().serialize()
            logger.error('Bad RPC: {}'.format(response))
            return web.Response(text=response)
        except Exception as e:
            logger.exception(e)
            error['error']['message'] = str(e)
            return web.json_response(error)
        # We have valid RPC, let check it has MQTT destination
        js_data = json.loads(data)
        try:            
            dst = js_data['params'].pop('dst')
            timeout = js_data['params'].get('timeout') \
                                        and js_data['params'].pop('timeout')
            if not timeout:
                logger.debug('Setting default timeout={} on MQTT reply'.format(
                                                    self.mqtt_reply_timeout))
                timeout = self.mqtt_reply_timeout
            else:
                logger.debug('Setting timeout={} from params'.format(timeout))
        except KeyError:
            logger.error('Bad RPC, no dst specified: {}'.format(data))
            error['error']['message'] = "No dst specified"
            return web.json_response(error)
        
        # Check if it a notification call, publish return True then.
        if not js_data.get('id'):
            # Publish packet..
            logger.debug('RPC Notification: {}'.format(data))
            await self.client.publish('rpc/{}/{}'.format(dst, self.client_uid),
                                                json.dumps(js_data).encode())
            return web.Response(text='')

        # Subscribe for reply topic, check there is not already a subscription.
        reply_topic = 'rpc/{}/{}/reply'.format(dst, self.client_uid)
        self.mqtt_replies.setdefault(reply_topic, {})[js_data['id']] = Queue()
        if reply_topic not in self.mqtt_reply_subscriptions:
            logger.debug('Adding subscrption to reply topic {}'.format(reply_topic))
            self.mqtt_reply_subscriptions.append(reply_topic)
            await self.client.subscribe([(reply_topic, QOS_2)])
            logger.debug('Subscribed to reply topic {}'.format(reply_topic))
        else:
            logger.debug('Already subscribed for topic {}'.format(reply_topic))

        # Publish MQTT message and wait for reply
        await self.client.publish('rpc/{}/{}'.format(dst, self.client_uid),
                                              json.dumps(js_data).encode())
        logger.debug(
            'Published request id {} to {}'.format(js_data['id'], dst))
        try:
            reply_data = await asyncio.wait_for(
                self.mqtt_replies[reply_topic][js_data['id']].get(), timeout)
            self.mqtt_replies[reply_topic][js_data['id']].task_done()

        except asyncio.TimeoutError:
            del self.mqtt_replies[reply_topic][js_data['id']]
            error['error']['message'] = 'RPC Timeout'
            return web.json_response(error)
        else:
            # We got a reply. Let send a response.
            return web.json_response(reply_data)


    async def process_mqtt_request(self, from_uid, data):
        response = None
        async with aiohttp.ClientSession() as session:
            try:
                async with timeout(HTTP_REQUEST_TIMEOUT, loop=self.loop) as t:
                    async with session.get(self.http_url, json=data) as resp:
                        response, status = await resp.text(), resp.status
                        logger.debug('HTTP response: [{}] {}'.format(
                                                        resp.status, response))
            except asyncio.TimeoutError:
                if data.get('id'):
                    logger.debug('Timeout, sending RPC reply')
                    return await self.send_mqtt_rpc_error_message(
                        from_uid, data['id'], 'HTTP request timeout')
                else:
                    logger.warning('Notification timeout: {}'.format(data))

        # Parse response as JSON and inject error.data if present
        try:
            js_response = json.loads(response)
            if js_response.get('error') and js_response['error'].get('data'):
                js_response['error']['message'] = '{}: {}'.format(
                    js_response['error']['message'],
                    js_response['error']['data'])
                await self.client.publish(
                    'rpc/{}/{}/reply'.format(CLIENT_UID, from_uid),
                    json.dumps(js_response).encode())
            else:
                # No error
                await self.client.publish(
                    'rpc/{}/{}/reply'.format(CLIENT_UID, from_uid),
                    response.encode())

        except json.decoder.JSONDecodeError:
            return await self.send_mqtt_rpc_error_message(from_uid, data['id'],
                                            message='Cannot jsonify response')


    async def send_mqtt_rpc_error_message(self, to_uid, request_id, 
                                          message, code=-1):
        data = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {'message': message, 'code': code}
        }
        await self.client.publish('rpc/{}/{}/reply'.format(CLIENT_UID, to_uid),
                                  json.dumps(data).encode())


if __name__ == '__main__':
    formatter = '[%(asctime)s] %(levelname)s %(name)s %(message)s'
    logging.basicConfig(level=logging.DEBUG if DEBUG else logging.INFO, 
                        format=formatter)
    logging.getLogger('hbmqtt').setLevel(level=logging.WARNING)
    loop = asyncio.get_event_loop()
    server = HttpMqttBridge()
    loop.run_until_complete(server.process_messages())
