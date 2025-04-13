"""Adapter for generating MCP server files from templates."""

import logging
from pathlib import Path
from typing import Any

import jinja2

from openapi_to_mcp.common.exceptions import GenerationError

logger = logging.getLogger(__name__)


class Generator:
    """Handles rendering templates and writing MCP server files."""

    def __init__(self, output_dir: str, context: dict[str, Any]) -> None:
        """
        Initialize the generator.

        Args:
            output_dir: The target directory for generated files.
            context: Data for template rendering (server_name, tools, etc.).
        """
        self.output_path = Path(output_dir)
        self.context = context
        # Template directory is relative to this file's parent's parent
        # This ensures it works with the new directory structure
        self.template_dir = Path(__file__).parent.parent / "templates"
        self.env: jinja2.Environment | None = None

    def generate_files(self) -> None:
        """
        Generate all necessary MCP server files from templates.

        Raises:
            GenerationError: If template rendering or file writing fails.
        """
        self._setup_environment()
        if not self.env:
            err_msg = "Internal error: Jinja2 environment not initialized."
            raise GenerationError(err_msg)

        self._ensure_output_directories()
        self._generate_static_files()
        self._generate_transport_file()

    def _setup_environment(self) -> None:
        """
        Initialize the Jinja2 template environment.

        Raises:
            GenerationError: If the template directory is not found.
        """
        if not self.template_dir.is_dir():
            err_msg = f"Template directory not found at {self.template_dir}"
            raise GenerationError(err_msg)

        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_dir),
            autoescape=jinja2.select_autoescape(["html", "xml", "j2"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _ensure_output_directories(self) -> None:
        """
        Create the output directory and src subdirectory.

        Raises:
            GenerationError: If directory creation fails.
        """
        try:
            self.output_path.mkdir(parents=True, exist_ok=True)
            src_path = self.output_path / "src"
            src_path.mkdir(exist_ok=True)
        except OSError as e:
            err_msg = (
                f"Failed to create output directories in '{self.output_path}': {e}"
            )
            raise GenerationError(err_msg) from e

    def _generate_static_files(self) -> None:
        """
        Generate static files from templates.

        Raises:
            GenerationError: If template rendering or file writing fails.
        """
        static_templates = {
            "package.json.j2": self.output_path / "package.json",
            "tsconfig.json.j2": self.output_path / "tsconfig.json",
            "src/server.ts.j2": self.output_path / "src" / "server.ts",
            "README.md.j2": self.output_path / "README.md",
            ".env.example.j2": self.output_path / ".env.example",
            "src/index.ts.j2": self.output_path / "src" / "index.ts",
        }

        for template_name, output_file in static_templates.items():
            self._render_and_write(template_name, output_file)

    def _generate_transport_file(self) -> None:
        """
        Generate the appropriate transport file based on context.

        Raises:
            GenerationError: If template rendering or file writing fails.
        """
        transport_output_file = self.output_path / "src" / "transport.ts"

        if self.context.get("transport") == "sse":
            transport_template_name = "src/transport_sse.ts.j2"
            logger.info("Rendering SSE transport template to src/transport.ts")
        else:
            transport_template_name = "src/transport_stdio.ts.j2"
            logger.info("Rendering STDIO transport template to src/transport.ts")

        self._render_and_write(transport_template_name, transport_output_file)

    def _render_and_write(self, template_name: str, output_file: Path) -> None:
        """
        Render a single template and write it to the output file.

        Args:
            template_name: The name of the template file.
            output_file: The output file path.

        Raises:
            GenerationError: If template rendering or file writing fails.
        """
        if not self.env:
            err_msg = "Internal error: Jinja2 environment not initialized."
            raise GenerationError(err_msg)

        try:
            template = self.env.get_template(template_name)
            rendered_content = template.render(self.context)

            with output_file.open("w", encoding="utf-8") as f:
                f.write(rendered_content)

        except jinja2.TemplateNotFound as e:
            err_msg = (
                f"Required template '{template_name}' not found in {self.template_dir}."
            )
            raise GenerationError(err_msg) from e
        except Exception as e:
            err_msg = f"Error rendering or writing template '{template_name}' to '{output_file}': {e}"
            raise GenerationError(err_msg) from e
