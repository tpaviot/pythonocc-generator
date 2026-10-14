#!/usr/bin/env python3

##Copyright 2008-2026 Thomas Paviot (tpaviot@gmail.com)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import json
from pathlib import Path


def process_toolkits(occt_directory):
    """Process OCCT toolkits and generate JSON output."""
    # Verify the directory exists
    if not Path(occt_directory).is_dir():
        raise ValueError(f"Directory does not exist: {occt_directory}")

    occt_src_path = Path(occt_directory) / "src"
    if not occt_src_path.is_dir():
        raise ValueError(f"Source directory not found: {occt_src_path}")

    toolkits = {}

    # loop over the TK folders
    for toolkit in sorted(occt_src_path.glob("TK*")):
        packages_file = toolkit / "PACKAGES"

        if not packages_file.exists():
            print(f"Warning: PACKAGES file not found in {toolkit}")
            continue

        with packages_file.open(encoding="utf8") as f:
            packages = [line.strip() for line in f]

        # alphabetical sort
        packages.sort()
        # add the entry to the dict
        toolkits[toolkit.name] = packages

    return toolkits


def main():
    parser = argparse.ArgumentParser(
        description="Process OCCT toolkits and generate a JSON file containing package information."
    )
    parser.add_argument(
        "occt_directory",
        help="Path to the OCCT directory (e.g., /path/to/OCCT-7_8_1/)",
    )
    parser.add_argument(
        "--output",
        default="toolkits.json",
        help="Output JSON file path (default: toolkits.json)",
    )

    args = parser.parse_args()

    toolkits = process_toolkits(args.occt_directory)

    # save to json
    with Path(args.output).open("w", encoding="utf8") as f:
        json.dump(toolkits, f, indent=4, ensure_ascii=False)

    print(f"Successfully wrote toolkit information to {args.output}")
    print(f"Processed {len(toolkits)} toolkits")


if __name__ == "__main__":
    main()
