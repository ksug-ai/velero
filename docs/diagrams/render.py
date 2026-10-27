#!/usr/bin/env python3
"""Render the diagrams with a bundled, clickable KSUG.AI logo. Requires Graphviz and librsvg."""
import base64
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SVG = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG)
logo = base64.b64encode((ROOT / 'ai-app/static/ksug-ai-logo.png').read_bytes()).decode()

def element(parent, tag, attrs=None, text=None):
    child = ET.SubElement(parent, '{' + SVG + '}' + tag, attrs or {})
    child.text = text
    return child

for name, title, subtitle, footnote in [
    ('architecture', 'Protect an AI assistant with Velero', 'Application architecture & backup flow', 'GKE Workload Identity grants GCS access · Pause app writes during backups · File system backup, no disk snapshots'),
    ('restore', 'Recover the knowledge. Keep the conversation.', 'Velero restore workflow', 'Restore resources and both volumes, then import PostgreSQL · No reseeding of documents or conversation history'),
]:
    raw = subprocess.check_output(['dot', '-Tsvg', str(HERE / f'{name}.dot')])
    graph = ET.fromstring(raw)
    _, _, width, height = map(float, graph.attrib['viewBox'].split())
    canvas_width = 1600
    scale = (canvas_width - 80) / width
    if name == 'restore':
        scale = min(scale, 1.45)
    graph_width, graph_height = width * scale, height * scale
    canvas_height = 180 + graph_height + 70
    root = ET.Element('{' + SVG + '}svg', {
        'width': str(canvas_width), 'height': str(round(canvas_height)),
        'viewBox': f'0 0 {canvas_width} {canvas_height}', 'role': 'img',
        'aria-labelledby': 'title description',
    })
    element(root, 'title', {'id': 'title'}, 'KSUG.AI · ' + title)
    element(root, 'desc', {'id': 'description'}, subtitle + '. ' + footnote)
    element(root, 'rect', {'width': '100%', 'height': '100%', 'fill': '#ffffff'})
    link = element(root, 'a', {'href': 'https://ksug.ai', 'aria-label': 'Visit KSUG.AI'})
    element(link, 'image', {'x': '40', 'y': '24', 'width': '156', 'height': '130', 'href': 'data:image/png;base64,' + logo})
    element(root, 'text', {'x': '230', 'y': '54', 'font-family': 'Arial,sans-serif', 'font-size': '16', 'letter-spacing': '2', 'fill': '#365fff'}, 'KSUG.AI · VELERO RECOVERY LAB')
    element(root, 'text', {'x': '230', 'y': '98', 'font-family': 'Arial,sans-serif', 'font-size': '34', 'font-weight': '700', 'fill': '#152b36'}, title)
    element(root, 'text', {'x': '230', 'y': '132', 'font-family': 'Arial,sans-serif', 'font-size': '20', 'fill': '#64748b'}, subtitle)
    element(root, 'path', {'d': f'M40 167 H{canvas_width-40}', 'stroke': '#dbe3f0', 'stroke-width': '2'})
    group = element(root, 'g', {'transform': f'translate({(canvas_width-graph_width)/2} 180) scale({scale})'})
    for child in graph:
        group.append(child)
    element(root, 'text', {'x': '40', 'y': str(canvas_height - 24), 'font-family': 'Arial,sans-serif', 'font-size': '15', 'fill': '#475569'}, footnote)
    output = HERE / f'{name}.svg'
    ET.ElementTree(root).write(output, encoding='utf-8', xml_declaration=True)
    subprocess.run(['rsvg-convert', '-w', '2000', '-o', str(HERE / f'{name}.png'), str(output)], check=True)
    print('Rendered', name)
