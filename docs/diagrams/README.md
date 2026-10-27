# KSUG.AI diagrams

The architecture and restore images include the supplied KSUG.AI logo **inside each diagram**. SVG files embed the PNG bytes, so the logo stays with the diagram when it is downloaded or added to a presentation. The SVG logo links to https://ksug.ai; the documentation image links also point there. PNG files preserve the branding but do not contain clickable regions.

| Diagram | PNG | SVG | Editable source |
| --- | --- | --- | --- |
| Architecture and backup | [PNG](architecture.png) | [SVG](architecture.svg) | [Graphviz](architecture.dot) |
| Restore workflow | [PNG](restore.png) | [SVG](restore.svg) | [Graphviz](restore.dot) |

Regenerate from the repository root with Python 3, Graphviz (`dot`), and librsvg (`rsvg-convert`) installed:

```bash
python3 docs/diagrams/render.py
```

`render.py` embeds the original logo from `ai-app/static/ksug-ai-logo.png`, adds the branded heading and footer, and exports both formats. Edit the `.dot` files for node labels, connections, and grouping. The earlier Mermaid sources in [architecture.mmd](../architecture.mmd) and [restore.mmd](../restore.mmd) remain available as text alternatives; they do not generate the branded exports.
