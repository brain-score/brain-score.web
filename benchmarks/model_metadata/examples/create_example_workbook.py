#!/usr/bin/env python3
"""Build a small deterministic .xlsx fixture for the metadata generator."""

import argparse
import json
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
STATUS_STYLES = {"verified": 1, "inferred": 2, "undocumented": 3}
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _cell(reference, value, style=0):
    style_attribute = f' s="{style}"' if style else ""
    if isinstance(value, bool):
        return f'<c r="{reference}"{style_attribute} t="b"><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{reference}"{style_attribute}><v>{value}</v></c>'
    rendered = escape(str(value))
    return (
        f'<c r="{reference}"{style_attribute} t="inlineStr">'
        f'<is><t>{rendered}</t></is></c>'
    )


def _worksheet(definition):
    rows = [
        '<row r="1">'
        + _cell("A1", "Field ")
        + _cell("E1", definition["identifier"])
        + "</row>"
    ]
    for row_number, field in enumerate(definition["fields"], start=2):
        cells = [_cell(f"A{row_number}", field["name"])]
        if field["value"] is not None:
            cells.append(
                _cell(
                    f"E{row_number}",
                    field["value"],
                    STATUS_STYLES[field["status"]],
                )
            )
        rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    rows.append(
        '<row r="35">'
        + _cell("E35", definition["reference_url"], STATUS_STYLES["verified"])
        + "</row>"
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">'
        f'<sheetData>{"".join(rows)}</sheetData>'
        "</worksheet>"
    )


def _styles():
    fills = (
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF93C47D"/>'
        '<bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFFFE599"/>'
        '<bgColor indexed="64"/></patternFill></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFFF0000"/>'
        '<bgColor indexed="64"/></patternFill></fill>'
    )
    cell_formats = (
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="0" fillId="2" borderId="0" xfId="0" applyFill="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/>'
        '<xf numFmtId="0" fontId="0" fillId="4" borderId="0" xfId="0" applyFill="1"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<styleSheet xmlns="{MAIN_NS}">'
        '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
        f'<fills count="5">{fills}</fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        f'<cellXfs count="4">{cell_formats}</cellXfs>'
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


def _archive_member(archive, name, content):
    info = zipfile.ZipInfo(name, FIXED_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, content)


def create_workbook(definition_path, output_path):
    definition = json.loads(Path(definition_path).read_text(encoding="utf-8"))
    fields = definition.get("fields", [])
    if len(fields) != 33:
        raise ValueError(f"Expected 33 workbook fields, found {len(fields)}")
    for field in fields:
        if field["status"] not in STATUS_STYLES:
            raise ValueError(f"Unknown provenance status: {field['status']}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w") as archive:
        _archive_member(
            archive,
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            "</Types>",
        )
        _archive_member(
            archive,
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        _archive_member(
            archive,
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<workbook xmlns="{MAIN_NS}" xmlns:r="{REL_NS}">'
            '<sheets><sheet name="Metadata" sheetId="1" r:id="rId1"/></sheets>'
            "</workbook>",
        )
        _archive_member(
            archive,
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            "</Relationships>",
        )
        _archive_member(archive, "xl/styles.xml", _styles())
        _archive_member(archive, "xl/worksheets/sheet1.xml", _worksheet(definition))
    return output_path


def create_example_repository(definition_path, repo_root):
    definition = json.loads(Path(definition_path).read_text(encoding="utf-8"))
    plugin_root = (
        Path(repo_root)
        / "brainscore_vision"
        / "models"
        / definition["plugin"]
    )
    plugin_root.mkdir(parents=True, exist_ok=True)
    (plugin_root / "__init__.py").write_text(
        f'model_registry["{definition["identifier"]}"] = None\n',
        encoding="utf-8",
    )
    return plugin_root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--definition",
        type=Path,
        default=Path(__file__).with_name("synthetic_workbook.json"),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        help="optionally create a minimal vision-style repository for the example",
    )
    args = parser.parse_args()
    output = create_workbook(args.definition, args.output)
    print(f"Generated {output}")
    if args.repo_root:
        plugin_root = create_example_repository(args.definition, args.repo_root)
        print(f"Generated example model registry at {plugin_root}")


if __name__ == "__main__":
    main()
