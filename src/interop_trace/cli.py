"""Command-line entry point for Interop Trace."""

import typer

app = typer.Typer(
    help="Tracing interoperability across bioinformatics databases and workflows.",
    invoke_without_command=True,
    no_args_is_help=True,
)


@app.callback()
def callback() -> None:
    """Provide the command group."""


def main() -> None:
    """Run the command-line application."""
    app()
