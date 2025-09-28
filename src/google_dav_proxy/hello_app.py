import asgineer


def HelloASGIApp(greeting: str):
    @asgineer.to_asgi
    async def app(request):
        return greeting

    return app
