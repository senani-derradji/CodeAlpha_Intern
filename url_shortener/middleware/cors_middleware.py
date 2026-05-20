from fastapi.middleware.cors import CORSMiddleware


def register_cors_middleware(app):

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5500"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )