import asgineer


def HelloASGIApp(greeting: str):
    @asgineer.to_asgi
    async def app(request: asgineer.HttpRequest):
        return greeting

    return app
