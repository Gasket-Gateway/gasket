"""Entry point for the Gasket Gateway application."""

from app import create_app, start_metrics_server

app = create_app()

# Start the metrics server in a background thread
start_metrics_server(app.config["GASKET"])

if __name__ == "__main__":
    server_config = app.config["GASKET"].get("server", {})
    app.run(
        host=server_config.get("host", "0.0.0.0"),
        port=server_config.get("port", 5000),
        debug=server_config.get("debug", False),
    )

