from tinyrpc.dispatch import RPCDispatcher
from tinyrpc.exc import *

class AsyncRPCDispatcher(RPCDispatcher):
    async def dispatch(self, request, caller=None):
        return await self._dispatch(request, caller)

    async def _dispatch(self, request, caller):
        try:
            try:
                method = self.get_method(request.method)
            except KeyError as e:
                return request.error_respond(MethodNotFoundError(e))

            # we found the method
            try:
                if caller is not None:
                    result = await caller(method, request.args, request.kwargs)
                else:
                    result = await method(*request.args, **request.kwargs)
            except Exception as e:
                # an error occured within the method, return it
                return request.error_respond(e)

            # respond with result
            return request.respond(result)
        except Exception as e:
            # unexpected error, do not let client know what happened
            return request.error_respond(ServerError())
