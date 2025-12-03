
import argparse
from .engine import ConversionOrchestrator, ConversionPlan
from .registry import load_builtin_plugins


def build_parser():
    p = argparse.ArgumentParser(description="AtomX Log Converter CLI")
    p.add_argument("-i", "--input", action="append", required=True, help="Input file(s)")
    p.add_argument("-o", "--output-formats", required=True, help="Comma-separated output formats (e.g., blf,csv)")
    p.add_argument("--outdir", default="converted_logs", help="Output directory")
    p.add_argument("--name-template", default="{basename}_{fmt}", help="Output naming template")
    return p


def main():
    args = build_parser().parse_args()
    outputs = [o.strip() for o in args.output_formats.split(",") if o.strip()]
    plan = ConversionPlan(inputs=args.input, outputs=outputs, outdir=args.outdir, name_template=args.name_template)
    orch = ConversionOrchestrator(load_builtin_plugins())
    report = orch.convert(plan)
    for entry in report.entries:
        status = entry.get("status")
        if status == "success":
            print(f"[OK] {entry['input']} -> {entry['output']}")
        elif status == "warning":
            print(f"[WARN] {entry['input']}: {entry['message']}")
        else:
            print(f"[ERROR] {entry['input']}: {entry['message']}")


if __name__ == "__main__":
    main()
